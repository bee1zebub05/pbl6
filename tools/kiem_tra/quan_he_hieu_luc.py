# -*- coding: utf-8 -*-
"""Tach ba quan he HIEU LUC theo Ontology v0.3 §4: REPLACES / AMENDS / REPEALS.

VI SAO PHAI TACH — day la loi VE NGHIA, khong phai loi ky thuat:

    REPLACES  (thay the)          -> B HET hieu luc, co van ban thay
    AMENDS    (sua doi, bo sung)  -> B VAN CON hieu luc, chi doi vai dieu
    REPEALS   (bai bo)            -> B HET hieu luc, KHONG co van ban thay

Truoc day gop ca ba vao mot quan he THAY_THE. Hau qua: mot van ban "sua doi, bo sung"
bi coi la "thay the" -> suy ra van ban goc het hieu luc, NGUOC HAN su that.

BA CAI BAY KHI PHAN LOAI (deu lay tu du lieu that):

  1. Trigger nam trong menh de "Can cu"
     "Can cu Luat Giao duc dai hoc SUA DOI, BO SUNG mot so dieu cua Luat so 38/2005"
     -> day chi la TEN cua luat duoc vien dan, KHONG phai quan he sua doi cua van ban
        dang xet. Bat vao la sai hoan toan.

  2. Chieu nguoc
     "Luat nay duoc SUA DOI, BO SUNG theo Luat so 09/2017/QH14"
     -> AMENDED_BY (B sua A), khong phai AMENDS (A sua B).
     Phan biet bang gioi tu: "cua X" = chieu xuoi, "theo/boi X" = chieu nguoc.

  3. "bai bo mot so dieu" khac "bai bo <van ban>"
     "Bai bo mot so diem, khoan, dieu cua Luat 20/2023/QH15" -> that ra la AMENDS
     "Bai bo Quyet dinh so 2673/QD-DHBK"                     -> moi la REPEALS

    python quan_he_hieu_luc.py                # thong ke tren ca kho
    python quan_he_hieu_luc.py --chi-tiet     # in tung cho bat duoc
    python quan_he_hieu_luc.py --doc 0278     # soi mot van ban
"""
import argparse
import io
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
SACH = GOC / "data" / "clean" / "text_final"

SO_HIEU = r"(\d{1,5}\s*/\s*(?:\d{4}\s*/\s*)?[A-ZĐ][\w\-Đ]{1,20})"
LOAI = (r"nghị\s*định|nghị\s*quyết|quyết\s*định|thông\s*tư\s*liên\s*tịch|thông\s*tư|"
        r"chỉ\s*thị|luật|bộ\s*luật|pháp\s*lệnh|kế\s*hoạch|hướng\s*dẫn|quy\s*chế|"
        r"quy\s*định|công\s*văn|điều\s*lệ")

# Cum "Can cu ..." dai toi dau: lay 200 ky tu truoc trigger de xet
TAM_CAN_CU = 200
CAN_CU = re.compile(r"[Cc]ăn\s*cứ", re.I)

# Chieu XUOI: "sua doi ... CUA <van ban X>"  -> van ban nay tac dong len X
# Chieu NGUOC: "duoc sua doi ... THEO/BOI <van ban X>" -> X tac dong len van ban nay
NGUOC_TRUOC = re.compile(r"(được|đã)\s*(sửa\s*đổi|bổ\s*sung|thay\s*thế|bãi\s*bỏ)", re.I)
# Gioi tu NGAY SAU trigger quyet dinh chieu, khong kem gi the bi dong o phia truoc:
#   "sua doi, bo sung mot so dieu CUA  Nghi dinh X"  -> van ban nay sua X   (xuoi)
#   "sua doi, bo sung           THEO Nghi dinh X"    -> X sua van ban nay   (nguoc)
NGUOC_SAU = re.compile(r"(theo|bởi|bằng)\s*(?:%s)" % LOAI, re.I)

MAU = [
    # (ten quan he, bieu thuc, co xet "mot so dieu" khong)
    ("REPLACES", re.compile(
        r"thay\s*thế(?:\s*cho)?[^.;]{0,60}?(?:%s)[^\d]{0,25}%s" % (LOAI, SO_HIEU), re.I),
     False),
    ("AMENDS", re.compile(
        r"sửa\s*đổi[,\s]*(?:bổ\s*sung)?[^.;]{0,70}?(?:%s)[^\d]{0,25}%s" % (LOAI, SO_HIEU),
        re.I), False),
    ("REPEALS", re.compile(
        r"bãi\s*bỏ[^.;]{0,60}?(?:%s)[^\d]{0,25}%s" % (LOAI, SO_HIEU), re.I), True),
    ("REPEALS", re.compile(
        r"hết\s*hiệu\s*lực[^.]{0,120}?(?:%s)[^\d]{0,25}%s" % (LOAI, SO_HIEU), re.I), True),
]

# "bai bo mot so DIEU/KHOAN/DIEM cua X" -> sua doi mot phan, khong phai bai bo ca van ban
# "mot phan" cung la sua doi mot phan, khong phai bai bo ca van ban — da bo sot o 0466
# ("bai bo mot phan boi Nghi dinh 24/2022").
MOT_PHAN = re.compile(r"một\s*(?:số\s*(?:điều|khoản|điểm|nội\s*dung)|phần)", re.I)


def chuan_so(s):
    s = re.sub(r"\s+", "", (s or "").strip(" .,;:*"))
    p = s.upper().split("/")
    if p and p[0].isdigit():
        p[0] = str(int(p[0]))
    return "/".join(p)


def trong_can_cu(t, vt):
    """Trigger co nam trong mot menh de 'Can cu ...' khong?

    Lay TAM_CAN_CU ky tu truoc trigger; neu co 'Can cu' ma GIUA no va trigger khong co
    dau cham phay/xuong dong ket menh de thi coi nhu van trong menh de do.
    """
    dau = max(0, vt - TAM_CAN_CU)
    truoc = t[dau:vt]
    m = None
    for m in CAN_CU.finditer(truoc):
        pass
    if not m:
        return False
    giua = truoc[m.end():]
    return not re.search(r"[;\n]", giua)


def phan_loai(t):
    """-> [(quan_he, so_hieu_dich, vi_tri_phan_tram, doan_van)]

    Bo qua trigger nam trong menh de 'Can cu', va doi chieu khi cau o the bi dong.
    """
    ra = []
    da = set()
    for ten, bt, xet_mot_phan in MAU:
        for m in bt.finditer(t):
            if trong_can_cu(t, m.start()):
                continue
            so = chuan_so(m.group(m.lastindex))
            doan = re.sub(r"\s+", " ", m.group(0))

            qh = ten
            # "bai bo mot so dieu cua X" -> thuc chat la sua doi
            if xet_mot_phan and MOT_PHAN.search(doan):
                qh = "AMENDS"
            # the bi dong -> doi chieu
            truoc = t[max(0, m.start() - 60):m.start() + 30]
            if NGUOC_TRUOC.search(truoc) or NGUOC_SAU.search(doan):
                qh = {"REPLACES": "REPLACED_BY", "AMENDS": "AMENDED_BY",
                      "REPEALS": "REPEALED_BY"}[qh]

            khoa = (qh, so)
            if khoa in da:
                continue
            da.add(khoa)
            ra.append((qh, so, 100.0 * m.start() / max(1, len(t)), doan[:110]))
    return ra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chi-tiet", action="store_true")
    ap.add_argument("--doc", default=None)
    a = ap.parse_args()

    fs = sorted(SACH.rglob("*.txt"))
    if a.doc:
        fs = [f for f in fs if f.name.startswith(a.doc)]

    dem = Counter()
    so_vb = Counter()
    vi_du = {}
    tong = 0
    for f in fs:
        t = io.open(f, encoding="utf-8", errors="replace").read()
        kq = phan_loai(t)
        if not kq:
            continue
        tong += 1
        loai_co = set()
        for qh, so, vt, doan in kq:
            dem[qh] += 1
            loai_co.add(qh)
            vi_du.setdefault(qh, (f.name[:4], so, vt, doan))
            if a.chi_tiet or a.doc:
                print("  %-12s -> %-18s [%3.0f%%] %s" % (qh, so, vt, doan[:74]))
        for q in loai_co:
            so_vb[q] += 1

    if a.doc:
        return
    print("=" * 90)
    print("TÁCH BA QUAN HỆ HIỆU LỰC  (Ontology v0.3 §4)")
    print("=" * 90)
    print("  Văn bản có ít nhất 1 quan hệ hiệu lực: %d / %d" % (tong, len(fs)))
    print("-" * 90)
    print("%-14s %8s %12s   %s" % ("QUAN HỆ", "số cạnh", "số văn bản", "ví dụ"))
    print("-" * 90)
    for qh, n in dem.most_common():
        d, so, vt, doan = vi_du[qh]
        print("%-14s %8d %12d   [%s→%s] %s" % (qh, n, so_vb[qh], d, so[:14], doan[:40]))
    print("=" * 90)
    print("  REPLACES = B hết hiệu lực, có văn bản thay")
    print("  AMENDS   = B VẪN còn hiệu lực, chỉ đổi vài điều")
    print("  REPEALS  = B hết hiệu lực, không có văn bản thay")


if __name__ == "__main__":
    main()
