# -*- coding: utf-8 -*-
"""Ap 107 cho LECH cua dot soat v2 vao text_clean_gemma, sau khi da phan xu tung nhom.

Ba nhom, xu ly khac han nhau:

  A. SO GIONG HET, chi khac chu dinh lien sau  (68 cho)
     "ngay 16 thang 4 nam 2021QU" — chu 'QU' la dau cua "QUYET DINH" o dong sau bi dinh
     vao. Con so DA DUNG. Thay ca token bang ban moi se XOA MAT 'QU' cua tu ke tiep ->
     chi chen xuong dong giua nam va phan chu, khong dung gi den so.

  B. BAN SACH BI CUT, ban moi day du hon  (2 cho)  -> lay ban moi.

  C. THAT SU LECH SO  (37 cho)
     - 26 cho la loi ky tu hien nhien (Q4->QD, I1->11, Q1113->QH13...) -> lay ban moi
     - 11 cho da MO PDF DOC BANG MAT, ghi phan xu trong PHAN_XU ben duoi

    python ap_soat_v2.py            # xem truoc
    python ap_soat_v2.py --apply    # ghi that (co backup .bak)
"""
import argparse
import csv
import re
import shutil
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
SACH = GOC / "data" / "processed" / "text_clean_gemma"
BANG = GOC / "data" / "soat_so_v2" / "doi_chieu_so.csv"

# Ket qua DOC TRUC TIEP PDF (render trang ra anh roi doc bang mat), khoa theo (doc, so_cu).
# 'sach'  = giu nguyen ban sach, ban OCR moi sai
# 'moi'   = lay ban OCR moi
PHAN_XU = {
    # PDF ghi dung nguyen van "Thong tu so 08/TT-BNV ngay 27/10/2017" — ban moi TU Y
    # them nam vao thanh 08/2017/TT-BNV. Do la sua sai su that.
    ("0027", "08/TT-BNV"): "sach",
    # "tu ngay 01 thang 7 nam truoc den ngay 30 thang 6 nam sau" la CUM TU chi ky han,
    # khong phai ngay thang. Bi ghep nham voi ngay o dau van ban.
    ("0027", "ngày 01 tháng 7 năm trước"): "sach",
    ("0027", "ngày 30 tháng 6 năm sau."): "sach",
    ("0043", "ngày 14 tháng 5 năm 2021QU"): "moi",     # so viet tay ro la 11
    ("0149", "17/2010/1T-BGDDT"): "moi",               # PDF: 17/2010/TT-BGDDT
    ("0149", "ngày Ø/ tháng A/ năm 2020."): "moi",     # PDF viet tay: 01 thang 11
    ("0204", "ngày 28 tháng 3 năm 2016"): "moi",       # PDF: ND 168/2018 ngay 28/12/2018
    ("0250", "ngày 26 tháng 12 năm 2018"): "moi",      # PDF: hieu luc tu 10/2/2019
    ("0343", "ngày 26 tháng 11 năm 2003;"): "moi",     # PDF: TT 01/2011/TT-BNV 19/01/2011
    ("0431", "01/3/2025"): "moi",                      # PDF: bien ban hop ngay 10/4/2025
    ("0450", "ngày 10 tháng 12 năm 2025Th"): "moi",    # PDF viet tay: 28 thang 11 nam 2025
    ("0461", "ngày 26 tháng 2 năm 2026"): "moi",       # PDF: den het 31 thang 8 nam 2026
}
# Cho de trong trong bieu mau — hai ban chi khac so dau cham, khong phai loi
BO_QUA = {("0250", "ngày ... tháng ... năm 20..."), ("0450", "ngày ... tháng ... năm 202")}


def so(t):
    return re.findall(r"\d+", t or "")


def gon(t):
    return re.sub(r"[^0-9A-Za-zÀ-ỹĐđ]", "", t or "")


def bodau(t):
    t = unicodedata.normalize("NFD", t or "")
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return t.replace("Đ", "D").replace("đ", "d").upper()


def xep_nhom(cu, moi):
    if so(cu) == so(moi):
        return "A"
    if gon(moi) and bodau(gon(moi)) in bodau(gon(cu)):
        return "A"
    if gon(cu) and bodau(gon(cu)) in bodau(gon(moi)):
        return "B"
    return "C"


def tim_file(doc):
    return next((p for p in SACH.rglob(doc + "_*.txt")), None)


def bt_linh_hoat(tok):
    r"""Bieu thuc khop token du khoang trang trong file khac voi trong bang.

    Token trong CSV da qua chuan() nen moi khoang trang thanh mot dau cach, con trong
    file no co the vat qua hai dong ("ngay 16 thang 4\nnam 2021"). So khop nguyen van se
    truot — 57/107 cho khong tim thay chi vi ly do nay.
    """
    phan = [re.escape(c) for c in tok if not c.isspace()]
    return re.compile(r"\s*".join(phan))


def thay_mot_lan(t, cu, moi):
    """-> (van ban moi, co thay duoc khong). Uu tien khop nguyen van, khong thi khop lỏng."""
    if cu in t:
        return t.replace(cu, moi, 1), True
    m = bt_linh_hoat(cu).search(t)
    if m:
        return t[:m.start()] + moi + t[m.end():], True
    return t, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    hang = [x for x in csv.DictReader(open(BANG, encoding="utf-8-sig"))
            if x["khop"] == "LỆCH"]
    theo_doc = defaultdict(list)
    for x in hang:
        theo_doc[x["doc_id"]].append(x)

    dem = defaultdict(int)
    nhat_ky = []

    for doc, xs in sorted(theo_doc.items()):
        f = tim_file(doc)
        if not f:
            dem["không thấy file"] += len(xs)
            continue
        t = goc = f.read_text(encoding="utf-8", errors="replace")

        for x in xs:
            cu, moi = x["so_cu"], x["so_moi"]
            if (doc, cu) in BO_QUA:
                dem["bỏ qua (ô trống biểu mẫu)"] += 1
                continue
            nhom = xep_nhom(cu, moi)
            quyet = PHAN_XU.get((doc, cu))

            if quyet == "sach":
                dem["giữ bản sạch (đã đọc PDF)"] += 1
                nhat_ky.append((doc, cu, cu, "đọc PDF: bản sạch đúng"))
                continue

            if nhom == "A" and not quyet:
                # chi tach chu bi dinh, KHONG dung den con so
                if cu.startswith(moi) and len(cu) > len(moi):
                    thua = cu[len(moi):]
                    t, ok = thay_mot_lan(t, cu, moi + "\n" + thua)
                    if ok:
                        dem["tách chữ dính (số giữ nguyên)"] += 1
                        nhat_ky.append((doc, cu, moi + "⏎" + thua, "chữ dính vào số"))
                    else:
                        dem["không tìm thấy trong file"] += 1
                else:
                    dem["A: chỉ khác cách viết, bỏ qua"] += 1
                continue

            # nhom B, nhom C loi ky tu, va nhung cho da doc PDF ket luan 'moi'
            t, ok = thay_mot_lan(t, cu, moi)
            if ok:
                dem["lấy bản OCR mới"] += 1
                nhat_ky.append((doc, cu, moi,
                                "đọc PDF: OCR mới đúng" if quyet == "moi"
                                else ("bản sạch bị cụt" if nhom == "B" else "lỗi ký tự")))
            else:
                dem["không tìm thấy trong file"] += 1

        if a.apply and t != goc:
            shutil.copy2(f, str(f) + ".bak")
            f.write_text(t, encoding="utf-8", newline="\n")

    print("=" * 90)
    print("ÁP KẾT QUẢ SOÁT v2  %s" % ("(GHI THẬT)" if a.apply else "(chỉ xem trước)"))
    print("=" * 90)
    for k in sorted(dem, key=lambda k: -dem[k]):
        print("   %-34s %3d" % (k, dem[k]))
    print("-" * 90)
    print("   TỔNG                               %3d" % sum(dem.values()))
    print("-" * 90)
    print("11 chỗ đã MỞ PDF ĐỌC BẰNG MẮT:")
    for d, cu, moi, ly in nhat_ky:
        if "đọc PDF" in ly:
            print("   %s  %-30s → %-30s %s" % (d, cu[:30], moi[:30], ly))
    print("=" * 90)
    if not a.apply:
        print(">>> Mới là XEM TRƯỚC. Thêm --apply để ghi thật.")


if __name__ == "__main__":
    main()
