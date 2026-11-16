# -*- coding: utf-8 -*-
"""Va nhung cho '[[KHONG OCR DUOC TRANG a-b]]' con sot trong ban sach.

Luc OCR hang loat, mot vai khuc 5 trang bi tu choi (RECITATION) hoac het luot thu, de
lai mot cho danh dau thieu. Day la so it nen dang cong sua rieng: cat DUNG cac trang do,
thu lai theo tung buoc nho dan — ca khuc, roi TUNG TRANG mot. Mot trang le de duoc chap
nhan hon han mot khuc, vi noi dung ngan hon nen it bi coi la 'doc lai van ban cong khai'.

    python va_cho_thieu.py            # xem truoc: co nhung cho nao
    python va_cho_thieu.py --apply    # OCR va va that vao ban sach
"""
import argparse
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gemma_ocr as G                                  # noqa: E402
from sach_hoa import lam_sach, kiem_dinh               # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import pymupdf
except ImportError:
    pymupdf = None

GOC = Path(__file__).resolve().parents[2]
SACH = GOC / "data" / "processed" / "text_clean_gemma"
GEM = GOC / "data" / "processed" / "text_gemma"
RAW_PDF = GOC / "data" / "raw"

MOC = re.compile(r"\[\[KHÔNG OCR ĐƯỢC TRANG (\d+)-(\d+)\]\]")
MODELS = ["gemma-4-31b-it", "gemini-3.5-flash-lite"]


def cat(pdf, tu, den):
    """-> bytes cua PDF chi gom trang tu..den (1-based, ke ca hai dau)."""
    with pymupdf.open(pdf) as d:
        nho = pymupdf.open()
        nho.insert_pdf(d, from_page=tu - 1, to_page=min(den, d.page_count) - 1)
        buf = io.BytesIO()
        nho.save(buf)
        nho.close()
    return buf.getvalue()


def tim_pdf(doc):
    return next((p for p in RAW_PDF.rglob(doc + "_*.pdf")), None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    if not pymupdf:
        print("Thiếu pymupdf")
        sys.exit(1)

    viec = []
    for f in sorted(SACH.rglob("*.txt")):
        t = f.read_text(encoding="utf-8", errors="replace")
        for m in MOC.finditer(t):
            doc = re.match(r"(\d{4})_", f.name)
            viec.append((f, doc.group(1) if doc else "?", int(m.group(1)), int(m.group(2))))

    print("=" * 84)
    print("VÁ CHỖ THIẾU %s" % ("(GHI THẬT)" if a.apply else "(chỉ xem trước)"))
    print("=" * 84)
    if not viec:
        print("  Không còn chỗ nào thiếu.")
        return
    for f, doc, tu, den in viec:
        print("  %s  trang %d-%d  | %s" % (doc, tu, den, f.name[:52]))
    if not a.apply:
        print("\n>>> Mới là XEM TRƯỚC. Thêm --apply để OCR và vá thật.")
        return

    qlk = G.QuanLyKey()
    qlk.kiem_tra()
    print("-" * 84)

    for f, doc, tu, den in viec:
        pdf = tim_pdf(doc)
        if not pdf:
            print("  ✖ %s: không thấy PDF gốc" % doc)
            continue
        print("  ▸ %s trang %d-%d — %s" % (doc, tu, den, pdf.name[:46]))

        # buoc 1: ca khuc mot lan
        phan = {}
        b = cat(pdf, tu, den)
        t, ghi = G._ocr_hai_tang(qlk, b, G.PROMPT, MODELS, so_trang=den - tu + 1)
        if t:
            print("      cả khúc: OK (%d ký tự) [%s]" % (len(t), ghi))
            phan = {tu: t}
        else:
            # buoc 2: tung trang mot — ngan hon nen it bi tu choi hon
            print("      cả khúc hỏng (%s) → thử từng trang" % str(ghi)[:50])
            for tr in range(tu, den + 1):
                bt = cat(pdf, tr, tr)
                tt, gg = G._ocr_hai_tang(qlk, bt, G.PROMPT, MODELS, so_trang=1, min_ky_tu=80)
                if tt:
                    phan[tr] = tt
                    print("      trang %d: OK (%d ký tự) [%s]" % (tr, len(tt), gg))
                else:
                    print("      trang %d: vẫn hỏng (%s)" % (tr, str(gg)[:46]))

        if not phan:
            print("      ✖ không cứu được, giữ nguyên dấu thiếu")
            continue

        if len(phan) == 1 and tu in phan and (den - tu) > 0:
            moi = phan[tu]
        else:
            moi = "\n\n".join(
                "----- [Trang %d] -----\n\n%s" % (tr, phan[tr]) for tr in sorted(phan))
        con_thieu = [tr for tr in range(tu, den + 1) if tr not in phan] if len(phan) > 1 else []
        if con_thieu:
            moi += "\n\n[[KHÔNG OCR ĐƯỢC TRANG %s]]" % ", ".join(map(str, con_thieu))

        for dich in (f, next((p for p in GEM.rglob(doc + "_*.txt")), None)):
            if not dich or not dich.exists():
                continue
            noi_dung = dich.read_text(encoding="utf-8", errors="replace")
            moi_nd = MOC.sub(lambda m: moi if int(m.group(1)) == tu else m.group(0),
                             noi_dung, count=0)
            if moi_nd != noi_dung:
                dich.write_text(moi_nd, encoding="utf-8", newline="\n")
        print("      ✔ đã vá %d/%d trang" % (len(phan) if len(phan) > 1 else den - tu + 1,
                                             den - tu + 1))
    print("=" * 84)


if __name__ == "__main__":
    main()
