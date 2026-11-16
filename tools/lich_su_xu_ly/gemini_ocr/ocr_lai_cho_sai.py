# -*- coding: utf-8 -*-
"""OCR lai nhung van ban / trang con sai sau khi da dung ban cuoi.

Ba van ban duoi day CHUA TUNG duoc OCR lai bang Gemma — chung khong nam trong danh
sach 287 file cua dot truoc, nen van giu nguyen ban Gemini web tu dau:

    0377  3560/QĐ-BGDĐT   17 trang, ty le dau 6,4% — OCR hong han
    0338  621/BGDĐT-TĐKT   1 trang, khoi ky bi cat cut, ngay mat dau ('ngay')
    0488  783/QC-ĐHBK      5 trang, thieu ca ngay/nguoi ky/can cu

Rieng 0271 thi CA HAI ban deu sai ngay: ban cu doc '14/06/2019' (sai nam — day la
Thong tu nam 2023), ban Gemma doc '29/02/2023' (2023 khong nhuan, khong co ngay do).
Chi can OCR lai TRANG 1.

Thu tu model theo dung thu tu nguoi dung chot: Flash truoc, het quota moi sang Gemma.

    python ocr_lai_cho_sai.py            # xem truoc
    python ocr_lai_cho_sai.py --apply
"""
import argparse
import glob
import io
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gemma_ocr as G                                   # noqa: E402
from sach_hoa import lam_sach                           # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import pymupdf
except ImportError:
    pymupdf = None

GOC = Path(__file__).resolve().parents[2]
RA = GOC / "data" / "processed" / "text_gemma_vet"

MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite",
          "gemma-4-31b-it", "gemma-4-26b-a4b-it"]

# doc -> danh sach trang can OCR lai; None = ca file
VIEC = {
    "0377": None,
    "0338": None,
    "0488": None,
    "0271": [1],
}

MOC = "----- [Trang %d] -----"


def cat(pdf, trang):
    import io as _io
    with pymupdf.open(pdf) as d:
        nho = pymupdf.open()
        for t in trang:
            if 1 <= t <= d.page_count:
                nho.insert_pdf(d, from_page=t - 1, to_page=t - 1)
        b = _io.BytesIO()
        nho.save(b)
        nho.close()
    return b.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--song-song", type=int, default=6)
    a = ap.parse_args()

    if not pymupdf:
        print("Thiếu pymupdf.")
        return

    ke = []
    for d, trs in VIEC.items():
        p = glob.glob(str(GOC / "data" / "raw" / "pdf" / "**" / ("%s_*.pdf" % d)),
                      recursive=True)
        if not p:
            print("  ✖ %s: không thấy PDF" % d)
            continue
        n = len(pymupdf.open(p[0]))
        ke.append({"doc": d, "pdf": Path(p[0]),
                   "trang": trs if trs else list(range(1, n + 1)), "tong": n})

    print("=" * 78)
    print("OCR LẠI CHỖ SAI")
    print("=" * 78)
    for x in ke:
        print("  %s  %2d/%d trang  %s"
              % (x["doc"], len(x["trang"]), x["tong"], x["pdf"].name[:48]))
    print("-" * 78)

    if not a.apply:
        print(">>> Mới là XEM TRƯỚC. Thêm --apply để chạy.")
        return

    qlk = G.QuanLyKey()
    qlk.kiem_tra_sau()
    print("-" * 78)

    def lam(x):
        log = []
        phan = {}
        for t in x["trang"]:
            s, ghi = G._ocr_hai_tang(qlk, cat(x["pdf"], [t]), G.PROMPT, MODELS, 1,
                                     min_ky_tu=80)
            if s:
                phan[t] = s
                log.append("      trang %-3d OK %6d ký tự [%s]" % (t, len(s), ghi))
            else:
                log.append("      trang %-3d ✖ %s" % (t, str(ghi)[:44]))
            time.sleep(0.5)

        if not phan:
            return x, log + ["      ✖ không cứu được trang nào"], None

        noi = "\n\n".join("%s\n%s" % (MOC % t, phan[t]) for t in sorted(phan))
        return x, log, noi

    with ThreadPoolExecutor(max_workers=a.song_song) as bom:
        for x, log, noi in bom.map(lam, ke):
            print("  ▸ %s" % x["doc"])
            for d in log:
                print(d)

            if noi is None:
                continue

            # ghi ra thu muc rieng, giu nguyen cay thu muc linh vuc cua ban cu
            cu = glob.glob(str(GOC / "data" / "processed" / "text_final" / "**"
                               / ("%s_*.txt" % x["doc"])), recursive=True)
            if not cu:
                print("      ✖ không thấy bản cũ để lấy đường dẫn")
                continue
            rel = Path(cu[0]).relative_to(GOC / "data" / "processed" / "text_final")
            p = RA / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            io.open(p, "w", encoding="utf-8", newline="\n").write(noi + "\n")
            print("      ✔ ghi %s" % p.relative_to(GOC))

    print("-" * 78)
    print("Xong. Đối chiếu rồi gộp bằng tay hoặc chạy lại dung_ban_cuoi.py.")


if __name__ == "__main__":
    main()
