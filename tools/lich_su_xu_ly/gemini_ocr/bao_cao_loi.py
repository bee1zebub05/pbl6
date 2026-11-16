"""Liet ke file OCR HONG / CHUA CHAY, gom theo thu muc — de danh dau va thu lai sau.

Doc thang tu state.json + clean_data nen chay duoc CA KHI bridge dang tat.
Xuat ra man hinh + 2 file de mo bang Excel hoac dan vao bao cao:
    bao_cao_loi.csv
    bao_cao_loi.md

Chay:
    python bao_cao_loi.py                     # ca cay
    python bao_cao_loi.py --only "pdf/Khac"   # 1 thu muc
    python bao_cao_loi.py --requeue           # xoa danh dau that bai -> chay lai tu dau
"""
import argparse
import csv
import json
import os
import sys
from pathlib import Path

try:
    import pymupdf
except ImportError:
    pymupdf = None

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

EXTS = {".pdf", ".doc", ".docx"}
MAX_ATTEMPTS = 3


def so_trang(p):
    if not pymupdf or p.suffix.lower() != ".pdf":
        return 0
    try:
        with pymupdf.open(p) as d:
            return d.page_count
    except Exception:
        return 0


def main():
    here = Path(__file__).resolve().parent
    root = here.parents[1]

    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(root / "data" / "raw"))
    ap.add_argument("--out", default=str(root / "data" / "clean_data"))
    ap.add_argument("--state", default=str(here / "state.json"))
    ap.add_argument("--only", default="")
    ap.add_argument("--requeue", action="store_true",
                    help="xoa danh dau 'failed' de batch chay lai nhung file do")
    x = ap.parse_args()

    src, out = Path(x.src), Path(x.out)
    only = x.only.replace("\\", "/").strip("/")
    state = {}
    if os.path.isfile(x.state):
        try:
            state = json.load(open(x.state, encoding="utf-8"))
        except Exception as e:
            print("state.json hỏng: %s" % e)

    if x.requeue:
        n = 0
        for _rel, st in state.items():
            if st.get("status") == "failed":
                st["status"] = "pending"
                st["attempts"] = 0
                n += 1
        json.dump(state, open(x.state, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("Đã bỏ đánh dấu thất bại cho %d file — batch sẽ chạy lại chúng." % n)
        return

    thu_muc = {}
    for f in sorted(src.rglob("*")):
        if f.suffix.lower() not in EXTS:
            continue
        rel = f.relative_to(src).as_posix()
        if only and not rel.startswith(only):
            continue
        tm = rel.rsplit("/", 1)[0] if "/" in rel else "."
        o = thu_muc.setdefault(tm, {"tong": 0, "xong": 0, "hong": [], "cho": []})
        o["tong"] += 1

        txt = out / Path(rel).with_suffix(".txt")
        if txt.exists() and txt.stat().st_size > 0:
            o["xong"] += 1
            continue

        st = state.get(rel) or {}
        muc = {
            "thu_muc": tm,
            "ten": f.name,
            "rel": rel,
            "trang": so_trang(f),
            "mb": round(f.stat().st_size / 1048576, 2),
            "lan_thu": st.get("attempts", 0),
            "trang_thai": st.get("status", "chưa chạy"),
            "loi": (st.get("error") or "")[:160],
            "nguon": st.get("nguon", ""),
            "gemma_che_do": st.get("gemma_che_do", ""),
        }
        (o["hong"] if st.get("status") == "failed" else o["cho"]).append(muc)

    # ── ra màn hình ──────────────────────────────────────────────────────────
    tong = xong = hong = cho = 0
    print("=" * 104)
    for tm in sorted(thu_muc):
        o = thu_muc[tm]
        tong += o["tong"]; xong += o["xong"]; hong += len(o["hong"]); cho += len(o["cho"])
        tt = "✔" if not o["hong"] and not o["cho"] else " "
        print("%s %-58s xong %3d/%-3d | hỏng %2d | chờ %2d"
              % (tt, tm[:58], o["xong"], o["tong"], len(o["hong"]), len(o["cho"])))
        for m in o["hong"]:
            het = " [HẾT LƯỢT]" if m["lan_thu"] >= MAX_ATTEMPTS else ""
            print("      ✖ %-52s %2d trang | thử %d lần%s"
                  % (m["ten"][:52], m["trang"], m["lan_thu"], het))
            print("        └ %s" % m["loi"])
    print("-" * 104)
    print("TỔNG: %d file | xong %d | hỏng %d | chờ %d" % (tong, xong, hong, cho))
    print("=" * 104)

    # ── file đã phải dùng đường lui Gemma ────────────────────────────────────
    fb = []
    for rel, st in state.items():
        if only and not rel.startswith(only):
            continue
        if st.get("nguon") or st.get("gemma_hong"):
            fb.append((rel, st))
    if fb:
        print()
        print("FILE ĐÃ FALLBACK SANG GEMMA (%d file)" % len(fb))
        print("-" * 104)
        for rel, st in sorted(fb):
            tm = rel.rsplit("/", 1)[0] if "/" in rel else "."
            ten = rel.rsplit("/", 1)[-1]
            if st.get("gemma_xong"):
                kh = st.get("gemma_khuc_hong") or []
                them = (" | thiếu khúc: " + ", ".join("%d-%d" % (h["tu"], h["den"]) for h in kh)) if kh else ""
                print("  ✔ %-46s %s" % (ten[:46], tm[:28]))
                print("      %s | %d ký tự%s" % (st.get("gemma_che_do", "?"), st.get("chars", 0), them))
            else:
                print("  ✖ %-46s %s" % (ten[:46], tm[:28]))
                print("      Gemma cũng hỏng: %s" % st.get("gemma_hong", "?"))
            print("      lỗi Gemini trước đó: %s" % (st.get("loi_gemini") or st.get("error", ""))[:80])
        print("=" * 104)

    # ── xuất file ────────────────────────────────────────────────────────────
    tat_ca = [m for o in thu_muc.values() for m in o["hong"] + o["cho"]]
    if not tat_ca:
        print("Không có file nào hỏng hay còn chờ — không xuất báo cáo.")
        return

    csv_p = here / "bao_cao_loi.csv"
    with open(csv_p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["thu_muc", "ten", "rel", "trang", "mb",
                                          "lan_thu", "trang_thai", "loi",
                                          "nguon", "gemma_che_do"])
        w.writeheader()
        w.writerows(tat_ca)

    md_p = here / "bao_cao_loi.md"
    with open(md_p, "w", encoding="utf-8", newline="\n") as f:
        f.write("# File OCR chưa xong\n\n")
        f.write("Tổng %d file | xong %d | hỏng %d | chờ %d\n\n" % (tong, xong, hong, cho))
        for tm in sorted(thu_muc):
            o = thu_muc[tm]
            if not o["hong"] and not o["cho"]:
                continue
            f.write("## %s\n\n" % tm)
            f.write("| | File | Trang | Lần thử | Lỗi |\n|---|---|---|---|---|\n")
            for m in o["hong"]:
                f.write("| ✖ | %s | %d | %d | %s |\n"
                        % (m["ten"], m["trang"], m["lan_thu"], m["loi"].replace("|", "/")))
            for m in o["cho"]:
                f.write("| ⏳ | %s | %d | %d | chưa chạy |\n" % (m["ten"], m["trang"], m["lan_thu"]))
            f.write("\n")

    print("Đã xuất: %s" % csv_p)
    print("         %s" % md_p)


if __name__ == "__main__":
    main()
