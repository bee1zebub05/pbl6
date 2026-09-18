# -*- coding: utf-8 -*-
"""Tach DIEU/KHOAN thanh node `Article` — Ontology v0.3 §2.7.

Cho phep hai thu ma cap van ban khong lam duoc:
  - Retrieval o CAP DIEU KHOAN: tra ve dung Dieu 5 thay vi ca van ban 40 trang
  - `AMENDS` tro CHINH XAC toi tung Dieu: "sua doi Dieu 12 cua Nghi dinh X"

BA CHO PHAI CAN THAN — deu lay tu du lieu that:

  1. "Dieu" trong PHAN VIEN DAN khong phai la dieu CUA van ban nay:
        "Can cu Dieu 15 Nghi dinh so 85/2016/ND-CP"
        "quy dinh tai khoan 2 Dieu 7 cua Thong tu 08/2021"
     -> chi nhan "Dieu N" khi no DUNG DAU DONG va sau no la TIEU DE, khong phai so hieu.

  2. Van ban co PHU LUC cung danh so Dieu lai tu dau -> "Dieu 1" xuat hien hai lan.
     Giu ca hai nhung danh so thu tu (`thu_tu`) de phan biet.

  3. OCR nuot dau cham: "Dieu 5 Pham vi dieu chinh" (khong co dau cham sau so).
     -> dau cham la TUY CHON trong mau.

    python trich_dieu_khoan.py                  # thong ke
    python trich_dieu_khoan.py --doc 0082       # soi mot van ban
    python trich_dieu_khoan.py --ra dieu.json   # xuat ra file
"""
import argparse
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
SACH = GOC / "data" / "clean" / "text_final"

LOAI = (r"nghị\s*định|nghị\s*quyết|quyết\s*định|thông\s*tư|chỉ\s*thị|luật|bộ\s*luật|"
        r"pháp\s*lệnh|quy\s*chế|quy\s*định|thông\s*tư\s*liên\s*tịch")

# "Dieu 5." / "Dieu 5" / "Dieu 5a." — dau cham tuy chon vi OCR hay nuot
#
# KHONG chan do dai phan duoi. Trong Quyet dinh, Dieu 1/2/3 thuong la CA DOAN nam tron
# tren mot dong (do duoc: 148-392 ky tu). Moc chan 120 ky tu cu lam regex truot sach ca
# van ban -> 15 van ban ra 0 Dieu du van ban co du. Viec loc vien dan van do LA_VIEN_DAN
# va kiem chu hoa dam nhiem, ca hai chi soi phan DAU nen khong phu thuoc do dai.
DIEU = re.compile(r"^[ \t]*(Điều)\s+(\d{1,3}[a-zA-Z]?)\s*[.．:]?\s*(.*)$", re.M)

# `tieu_de` chi la nhan hien thi -> cat ngan lai cho bang voi hanh vi cu.
DAI_TIEU_DE = 120

# Sau "Dieu N" ma la SO HIEU van ban khac -> VIEN DAN, khong phai dieu cua van ban nay.
#   "Điều 15 Nghị định số 85/2016/NĐ-CP"   -> vien dan, bo
#   "Điều 2. Quyết định này có hiệu lực"   -> KHONG phai vien dan, phai giu
# Phan biet bang chinh SO HIEU: co "<Loai> ... 99/2019" moi la vien dan; "<Loai> NÀY" thi khong.
LA_VIEN_DAN = re.compile(
    r"^\s*(?:của|tại)?\s*(?:%s)[^.]{0,24}?\d{1,5}\s*/"
    r"|^\s*(?:số\s*)?\d{1,5}\s*/" % LOAI, re.I)

# Tieu de phan noi dung duoc ban hanh kem theo (NormativeContent) — dong in hoa dung mot minh
TIEU_DE_ND = re.compile(
    r"^[ \t]*(QUY\s*ĐỊNH|QUY\s*CHẾ|ĐIỀU\s*LỆ|QUY\s*TRÌNH|NỘI\s*QUY|HƯỚNG\s*DẪN)"
    r"[ \t]*$", re.M)

# Moc trang chen giua van ban, phai bo truoc khi cat than dieu
MOC_TRANG = re.compile(r"-{3,}\s*\[Trang\s+\d+\]\s*-{3,}")

KHOAN = re.compile(r"^[ \t]*(\d{1,2})\s*\.\s+(?=[A-ZĐÀ-Ỹ])", re.M)

# Chu hay bi OCR doc nham thanh chu so, dung khi vá "Điều 1l" -> "Điều 11"
NHAM_CHU_SO = {"l": "1", "I": "1", "i": "1", "O": "0", "o": "0", "S": "5", "s": "5",
               "Z": "2", "B": "8", "G": "6"}


def _so(s):
    return int(re.match(r"\d+", s).group())


def tach_dieu(t, dai_toi_da=4000):
    """-> [{so, tieu_de, than, thu_tu, so_khoan}]

    `than` la doan tu sau tieu de Dieu nay den truoc Dieu ke tiep, cat bot neu qua dai.
    """
    t = MOC_TRANG.sub("\n", t)
    moc = []
    for m in DIEU.finditer(t):
        tieu = re.sub(r"\s+", " ", m.group(3)).strip(" .:-")
        # "Dieu 15 Nghi dinh so 85/2016" -> vien dan, bo
        if LA_VIEN_DAN.match(m.group(3)):
            continue
        # Vien dan bi NGAT DONG giua cau: "... khong qua muoi nam tu\nDieu 76 cua Bo luat nay"
        # Tieu de that luon mo dau bang CHU HOA; vien dan mo dau bang chu thuong hoac dau cau
        # ("cua Bo luat nay", "; khoan 5 Dieu 37"). Loc duoc ca hai kieu chi bang mot dieu kien.
        if tieu and not re.match(r"[A-ZĐÀ-Ỹ\d]", tieu):
            continue
        moc.append((m.start(), m.end(), m.group(2), tieu))

    # --- Lam sach dua tren TINH DON DIEU cua day so Dieu -------------------------------
    # OCR doc "Dieu 11" thanh "Dieu 1l" (chu L) -> tut ve 1, vo khoi. Sua khi no lam day
    # lien tuc tro lai. Chi sua voi chu de nham chu so; "Dieu 8a" la so that, phai giu.
    truoc = 0
    sach = []
    for d, c, so, tieu in moc:
        m = re.match(r"(\d+)([a-zA-Z])$", so)
        if m and m.group(2) in NHAM_CHU_SO:
            moi = m.group(1) + NHAM_CHU_SO[m.group(2)]
            if _so(so) <= truoc < int(moi):
                so = moi
        sach.append([d, c, so, tieu])
        truoc = _so(so)

    # Vien dan TU THAN bi ngat dong: "quy dinh tai\nDieu 15 Nghi dinh nay tru cac..."
    # Khong co so hieu (nen luat vien dan khong bat), mo dau bang chu hoa (nen loc hoa
    # khong bat). Dau hieu duy nhat: no la mot CU NHAY LE — Dieu ke tiep lai vuot qua
    # Dieu lien truoc. Khoi that su bat dau lai thi cac Dieu sau do di len tu do.
    moc = [x for i, x in enumerate(sach)
           if not (0 < i < len(sach) - 1
                   and _so(x[2]) <= _so(sach[i - 1][2]) < _so(sach[i + 1][2]))]

    ra = []
    khoi = 0
    truoc = 0
    for i, (d, c, so, tieu) in enumerate(moc):
        n = _so(so)
        # So Dieu quay ve 1 (hoac lui lai) = het van ban chinh, sang phan ban hanh kem theo.
        # Day chinh la ranh gioi Document | NormativeContent trong Ontology §2.6.
        if i and n <= truoc:
            khoi += 1
        truoc = n
        het = moc[i + 1][0] if i + 1 < len(moc) else len(t)
        than = t[c:het].strip()
        ra.append({
            "so": "Điều %s" % so,
            "tieu_de": tieu[:DAI_TIEU_DE],
            "than": than[:dai_toi_da],
            "thu_tu": i + 1,
            "khoi": khoi,
            "so_khoan": len(KHOAN.findall(than)),
            "so_ky_tu": len(than),
        })
    return ra


def tach_noi_dung(t, ds):
    """Khoi 1 -> node NormativeContent (Ontology §2.6), neu that su la Quy dinh kem theo.

    Mot Quyet dinh ban hanh kem Quy che co hinh dang rat rieng:
        khoi 0 = 2-4 Dieu thi hanh ("Ban hanh kem theo...", "co hieu luc tu ngay ky")
        khoi 1 = ban Quy che, hang chuc Dieu
    Con Nghi dinh dai kem PHU LUC BIEU MAU thi nguoc lai: khoi 0 dai (67 Dieu), cac khoi
    sau chi la mau Quyet dinh 4-5 Dieu. Nhung khoi do KHONG phai NormativeContent.
    Phan biet bang chinh ti le do — khong can tu dien, khong can model.
    """
    khoi = {}
    for x in ds:
        khoi.setdefault(x["khoi"], []).append(x)
    if 1 not in khoi or len(khoi[0]) > 6 or len(khoi[1]) < 5:
        return []
    dau = khoi[1][0]
    tieu_hoa = [m for m in TIEU_DE_ND.finditer(t)]
    ten = ""
    for m in tieu_hoa:                       # tieu de in hoa gan nhat TRUOC Dieu 1 cua khoi 1
        ten = re.sub(r"\s+", " ", m.group(1)).title()
    return [{
        "loai": ten or "Quy định",
        "so_dieu": len(khoi[1]),
        "dieu_cuoi": khoi[1][-1]["so"],
        "thu_tu_dau": dau["thu_tu"],
    }]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", default=None)
    ap.add_argument("--ra", default=str(GOC / "data" / "kiem_tra" / "dieu_khoan.json"))
    a = ap.parse_args()

    fs = sorted(SACH.rglob("*.txt"))
    if a.doc:
        fs = [f for f in fs if f.name.startswith(a.doc)]

    theo_vb = {}
    co_nd = []
    dem = Counter()
    tong_dieu = tong_khoan = 0
    for f in fs:
        t = io.open(f, encoding="utf-8", errors="replace").read()
        ds = tach_dieu(t)
        if not ds:
            continue
        doc = f.name[:4]
        nd = tach_noi_dung(t, ds)
        theo_vb[doc] = {"dieu": ds, "noi_dung": nd}
        if nd:
            co_nd.append((doc, nd[0]["loai"], nd[0]["so_dieu"]))
        dem[len(ds)] += 1
        tong_dieu += len(ds)
        tong_khoan += sum(x["so_khoan"] for x in ds)
        if a.doc:
            print("  %s — %d điều" % (f.name[:44], len(ds)))
            for x in ds[:14]:
                print("     %-10s %-52s (%d khoản, %d ký tự)"
                      % (x["so"], x["tieu_de"][:52], x["so_khoan"], x["so_ky_tu"]))
            if len(ds) > 14:
                print("     … và %d điều nữa" % (len(ds) - 14))

    if a.doc:
        return

    p = Path(a.ra)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(theo_vb, ensure_ascii=False), encoding="utf-8")

    ds = sorted(k for k, v in dem.items() for _ in range(v))
    print("=" * 88)
    print("TÁCH ĐIỀU / KHOẢN  (Ontology v0.3 §2.7 — node Article)")
    print("=" * 88)
    print("  Văn bản có cấu trúc Điều : %d / %d  (%.0f%%)"
          % (len(theo_vb), len(fs), 100.0 * len(theo_vb) / max(1, len(fs))))
    print("  Tổng số Điều             : %s" % "{:,}".format(tong_dieu))
    print("  Tổng số Khoản            : %s" % "{:,}".format(tong_khoan))
    print("  Điều/văn bản             : trung vị %d | ít nhất %d | nhiều nhất %d"
          % (ds[len(ds) // 2], ds[0], ds[-1]))
    co_tieu = sum(1 for v in theo_vb.values() for x in v["dieu"] if x["tieu_de"])
    print("  Có tiêu đề Điều          : %d / %d  (%.0f%%)"
          % (co_tieu, tong_dieu, 100.0 * co_tieu / max(1, tong_dieu)))
    print("-" * 88)
    print("  NormativeContent (§2.6) — Quy định/Quy chế ban hành kèm theo: %d văn bản"
          % len(co_nd))
    for doc, loai, n in co_nd[:6]:
        print("      %s  %-12s %3d điều" % (doc, loai, n))
    print("-" * 88)
    print("  Ví dụ (5 điều đầu của 2 văn bản):")
    for doc in list(theo_vb)[:2]:
        print("   %s:" % doc)
        for x in theo_vb[doc]["dieu"][:5]:
            print("      %-10s %-50s %d khoản" % (x["so"], x["tieu_de"][:50], x["so_khoan"]))
    print("=" * 88)
    print("Đã ghi: %s  (%.1f MB)" % (p, p.stat().st_size / 1048576))


if __name__ == "__main__":
    main()
