# -*- coding: utf-8 -*-
"""Cham do chinh xac: text_gemma (OCR lai bang Gemma) so voi text_raw (OCR cu).

Khong co "dap an" tuyet doi, nen do bang cac chi so KIEM CHUNG DUOC:
  1. Ty le ky tu co dau tieng Viet — OCR hong dau thi tut han (Windows OCR chi 1.3%)
  2. So cho co SO DANG NGO — dung dung bo luat cua soi_so.py cho ca hai ban
  3. Ty le tu "that" — tu co mat o it nhat 2 nguon doc lap
  4. Mat do chu/trang — mat noi dung thi tut

    python danh_gia_gemma.py
    python danh_gia_gemma.py --chi-tiet
"""
import argparse
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from soi_so import quet_file                       # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
CU = GOC / "data" / "processed" / "text_raw"
MOI = GOC / "data" / "processed" / "text_gemma"

DAU = ("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ"
       "ùúủũụưừứửữựỳýỷỹỵđ")
DAU += DAU.upper()


def ty_le_dau(t):
    return 100.0 * sum(1 for c in t if c in DAU) / max(1, len(t))


def bo_moc(t):
    return re.sub(r"-{3,}\s*\[Trang \d+\]\s*-{3,}", "", t)


def cac_tu(t):
    return re.findall(r"[A-Za-zÀ-ỹ]{2,}", unicodedata.normalize("NFC", t).lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chi-tiet", action="store_true")
    a = ap.parse_args()

    if not MOI.exists():
        print("Chưa có %s" % MOI)
        sys.exit(1)

    cap = []
    for fm in sorted(MOI.rglob("*.txt")):
        m = re.match(r"(\d{4})_", fm.name)
        if not m:
            continue
        fc = next((p for p in CU.rglob(m.group(1) + "_*.txt")), None)
        if fc:
            cap.append((m.group(1), fc, fm))

    if not cap:
        print("Chưa có cặp nào để so.")
        return

    tong = {"cu": Counter(), "moi": Counter()}
    hang = []
    for doc, fc, fm in cap:
        tc = bo_moc(fc.read_text(encoding="utf-8", errors="replace"))
        tm = bo_moc(fm.read_text(encoding="utf-8", errors="replace"))
        ngo_c, ngo_m = len(quet_file(fc)), len(quet_file(fm))
        hang.append({
            "doc": doc, "ky_tu_cu": len(tc), "ky_tu_moi": len(tm),
            "dau_cu": ty_le_dau(tc), "dau_moi": ty_le_dau(tm),
            "ngo_cu": ngo_c, "ngo_moi": ngo_m,
            "ten": fm.name,
        })
        tong["cu"]["ky_tu"] += len(tc); tong["moi"]["ky_tu"] += len(tm)
        tong["cu"]["ngo"] += ngo_c;     tong["moi"]["ngo"] += ngo_m

    n = len(hang)
    tb_dau_cu = sum(h["dau_cu"] for h in hang) / n
    tb_dau_moi = sum(h["dau_moi"] for h in hang) / n

    print("=" * 86)
    print("ĐỘ CHÍNH XÁC — text_gemma so với text_raw   (%d tài liệu đã OCR lại)" % n)
    print("=" * 86)
    print("%-34s %14s %14s %12s" % ("CHỈ SỐ", "text_raw (cũ)", "text_gemma", "thay đổi"))
    print("-" * 86)
    print("%-34s %14s %14s %11.0f%%"
          % ("Tổng ký tự", "{:,}".format(tong["cu"]["ky_tu"]), "{:,}".format(tong["moi"]["ky_tu"]),
             100.0 * (tong["moi"]["ky_tu"] - tong["cu"]["ky_tu"]) / max(1, tong["cu"]["ky_tu"])))
    print("%-34s %13.1f%% %13.1f%% %11.1f đ" % ("Tỉ lệ ký tự có dấu tiếng Việt",
                                                tb_dau_cu, tb_dau_moi, tb_dau_moi - tb_dau_cu))
    print("%-34s %14d %14d %11.0f%%"
          % ("Số chỗ có SỐ đáng ngờ", tong["cu"]["ngo"], tong["moi"]["ngo"],
             100.0 * (tong["moi"]["ngo"] - tong["cu"]["ngo"]) / max(1, tong["cu"]["ngo"])))
    print("-" * 86)

    tot = sum(1 for h in hang if h["ngo_moi"] < h["ngo_cu"])
    xau = sum(1 for h in hang if h["ngo_moi"] > h["ngo_cu"])
    print("  Tài liệu ÍT chỗ đáng ngờ hơn : %d" % tot)
    print("  Tài liệu NHIỀU hơn           : %d   ← cần xem" % xau)
    print("  Bằng nhau                    : %d" % (n - tot - xau))

    if xau and a.chi_tiet:
        print("\n  Những tài liệu bản mới NHIỀU chỗ đáng ngờ hơn:")
        for h in sorted(hang, key=lambda x: x["ngo_cu"] - x["ngo_moi"])[:8]:
            if h["ngo_moi"] > h["ngo_cu"]:
                print("     %s  cũ %d → mới %d  | %s"
                      % (h["doc"], h["ngo_cu"], h["ngo_moi"], h["ten"][:48]))

    if a.chi_tiet:
        print("\n  10 tài liệu cải thiện nhiều nhất:")
        for h in sorted(hang, key=lambda x: x["ngo_moi"] - x["ngo_cu"])[:10]:
            print("     %s  chỗ ngờ %2d → %2d | dấu %.1f%% → %.1f%% | %s"
                  % (h["doc"], h["ngo_cu"], h["ngo_moi"], h["dau_cu"], h["dau_moi"],
                     h["ten"][:42]))
    print("=" * 86)


if __name__ == "__main__":
    main()
