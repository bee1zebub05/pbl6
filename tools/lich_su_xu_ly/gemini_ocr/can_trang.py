# -*- coding: utf-8 -*-
"""Khoi phuc moc TUNG TRANG cho ban OCR moi, dua vao ban cu da phan trang dung.

VAN DE. Hai kho bo tro cho nhau nhung moi kho thieu mot thu:

    text_clean_gemma   OCR kem hon, nhung phan trang CHINH XAC tung trang
                       (0245: 305 moc cho 305 trang)
    text_gemma_moi     OCR tot hon han (nguoi ky 50% -> 91%), nhung chi phan
                       theo KHUC 5 TRANG (0245: 61 moc)

Ban moi gui 5 trang mot luot nen chi biet ranh gioi khuc, khong biet ranh gioi
tung trang ben trong. Muon vua co noi dung tot vua dinh vi duoc tung trang thi
phai LAY RANH GIOI TU BAN CU roi ap vao ban moi.

CACH LAM. Khong so khop chuoi tho — hai ban khac nhau chinh vi loi OCR. Thay vao
do can chinh o muc TU, sau khi bo dau va ha chu thuong:

  1. Ban cu: lay tu cua tung trang trong khuc -> biet vi tri RANH GIOI theo chi so tu
  2. Ban moi: tach tu, nho vi tri ky tu cua tung tu
  3. difflib.SequenceMatcher tim cac KHOI TRUNG giua hai day tu
  4. Chieu ranh gioi tu chi so cu sang chi so moi qua khoi trung chua no
  5. Cat ban moi tai vi tri ky tu tuong ung

KHONG DOAN BUA. Neu ty le tu khop duoi nguong thi GIU NGUYEN khuc do, khong cat.
Cat sai con te hon khong cat: doc gia se tin vao mot so trang sai.

    python can_trang.py                 # xem truoc, khong ghi
    python can_trang.py --doc 0082      # soi mot van ban
    python can_trang.py --apply --ra data/processed/text_gemma_trang
"""
import argparse
import difflib
import io
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
CU = GOC / "data" / "processed" / "text_clean_gemma"
MOI = GOC / "data" / "processed" / "text_gemma_moi"

MOC = re.compile(r"-{3,}\s*\[Trang\s+(\d+)\]\s*-{3,}")
TU = re.compile(r"[0-9a-z]+")
# Cac van ban duoc cuu bang cat 2x2 co cau truc rieng, khong cat lai duoc
GOC_MANH = re.compile(r"\[Trang \d+ — góc ")

NGUONG_KHOP = 0.30       # ty le tu cua ban cu tim thay trong ban moi
MOC_MOI = "----- [Trang %d] -----"


def bo_dau(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D").lower()


def tach_moc(t):
    """-> [(so_trang, text)] theo thu tu xuat hien."""
    v = list(MOC.finditer(t))
    ra = []
    for i, m in enumerate(v):
        het = v[i + 1].start() if i + 1 < len(v) else len(t)
        ra.append((int(m.group(1)), t[m.end():het].strip()))
    return ra


def tu_co_vi_tri(t):
    """-> ([tu da bo dau], [(dau, cuoi) trong chuoi goc])"""
    b = bo_dau(t)
    tu, vt = [], []
    for m in TU.finditer(b):
        tu.append(m.group(0))
        vt.append((m.start(), m.end()))
    return tu, vt


def can_mot_khuc(cu_trang, moi_text):
    """Cat `moi_text` thanh tung trang theo ranh gioi cua `cu_trang`.

    cu_trang: [(so_trang, text cu)] cac trang nam trong khuc nay
    -> ([(so_trang, text moi)], ty_le_khop) hoac (None, ty_le) neu khong du tin cay
    """
    if len(cu_trang) <= 1:
        return [(cu_trang[0][0], moi_text)] if cu_trang else None, 1.0

    # day tu ban cu + vi tri ranh gioi giua cac trang
    tu_cu, ranh = [], []
    for _so, tx in cu_trang:
        tu_cu += TU.findall(bo_dau(tx))
        ranh.append(len(tu_cu))
    ranh = ranh[:-1]                       # bo ranh gioi cuoi (= het khuc)

    tu_moi, vt_moi = tu_co_vi_tri(moi_text)

    if not tu_cu or not tu_moi:
        return None, 0.0

    khoi = difflib.SequenceMatcher(None, tu_cu, tu_moi,
                                   autojunk=False).get_matching_blocks()
    khop = sum(k.size for k in khoi)
    ty_le = khop / max(1, len(tu_cu))

    if ty_le < NGUONG_KHOP:
        return None, ty_le

    def chieu(i_cu):
        """Chi so tu trong ban cu -> chi so tu trong ban moi."""
        # khoi chua i_cu thi chieu truc tiep
        for k in khoi:
            if k.a <= i_cu < k.a + k.size:
                return k.b + (i_cu - k.a)
        # khong khoi nao chua -> lay dau khoi dau tien nam sau i_cu
        for k in khoi:
            if k.a >= i_cu and k.size:
                return k.b
        return len(tu_moi)

    cat = [chieu(i) for i in ranh]

    # ranh gioi phai tang dan; khong tang tuc can chinh loan -> bo
    if any(cat[i] >= cat[i + 1] for i in range(len(cat) - 1)):
        return None, ty_le

    ra = []
    truoc_kytu = 0
    for i, (so, _tx) in enumerate(cu_trang):
        if i < len(cat):
            j = cat[i]
            sau = vt_moi[j][0] if j < len(vt_moi) else len(moi_text)
        else:
            sau = len(moi_text)
        ra.append((so, moi_text[truoc_kytu:sau].strip()))
        truoc_kytu = sau
    return ra, ty_le


def can_mot_file(p_cu, p_moi):
    """-> (text moi da phan trang, so khuc cat duoc, tong khuc, ty le trung binh)"""
    t_cu = io.open(p_cu, encoding="utf-8", errors="replace").read()
    t_moi = io.open(p_moi, encoding="utf-8", errors="replace").read()

    if GOC_MANH.search(t_moi):
        return None, 0, 0, 0.0          # van ban cuu bang cat goc, de nguyen

    cu = dict(tach_moc(t_cu))
    khuc = tach_moc(t_moi)

    if not cu or not khuc:
        return None, 0, 0, 0.0

    het_trang = max(cu)
    ra = []
    cat_duoc = 0
    ds_ty_le = []

    for i, (bat_dau, noi_dung) in enumerate(khuc):
        ket = (khuc[i + 1][0] - 1) if i + 1 < len(khuc) else het_trang
        trong_khuc = [(s, cu[s]) for s in range(bat_dau, ket + 1) if s in cu]

        if not trong_khuc:
            ra.append((bat_dau, noi_dung))
            continue

        chia, ty_le = can_mot_khuc(trong_khuc, noi_dung)
        ds_ty_le.append(ty_le)

        if chia:
            ra += chia
            cat_duoc += 1
        else:
            # khong du tin cay -> giu nguyen khuc, ghi ro pham vi
            ra.append((bat_dau, noi_dung, ket))

    khoi = []
    for x in ra:
        if len(x) == 3:
            so, nd, ket = x
            khoi.append("----- [Trang %d-%d] -----\n%s" % (so, ket, nd))
        else:
            so, nd = x
            khoi.append("%s\n%s" % (MOC_MOI % so, nd))

    tb = sum(ds_ty_le) / len(ds_ty_le) if ds_ty_le else 0.0
    return "\n\n".join(khoi) + "\n", cat_duoc, len(khuc), tb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", default=None)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--ra", default="data/processed/text_gemma_trang")
    a = ap.parse_args()

    ra_dir = Path(a.ra)
    ra_dir = ra_dir if ra_dir.is_absolute() else GOC / ra_dir

    fs = sorted(MOI.rglob("*.txt"))
    if a.doc:
        fs = [f for f in fs if f.name.startswith(a.doc)]

    print("=" * 92)
    print("CĂN MỐC TRANG: lấy ranh giới từ bản cũ, áp vào nội dung bản mới")
    print("=" * 92)
    print("%-6s %8s %8s %8s %7s   %s"
          % ("doc", "trang cũ", "khúc mới", "cắt được", "khớp", "kết quả"))
    print("-" * 92)

    tong = ok = bo = ghi = 0
    for f in fs:
        d = f.name[:4]
        p_cu = list(CU.rglob(d + "_*.txt"))

        if not p_cu:
            print("%-6s %8s %8s %8s %7s   không có bản cũ để đối chiếu"
                  % (d, "—", "—", "—", "—"))
            bo += 1
            continue

        t, cat, n_khuc, ty = can_mot_file(p_cu[0], f)
        tong += 1

        if t is None:
            print("%-6s %8s %8s %8s %7s   bỏ qua (văn bản cứu bằng cắt góc)"
                  % (d, "", "", "", ""))
            bo += 1
            continue

        so_cu = len(tach_moc(io.open(p_cu[0], encoding="utf-8",
                                     errors="replace").read()))
        moc_ra = len(MOC.findall(t))
        dat = cat == n_khuc
        ok += dat

        if a.doc or not dat:
            print("%-6s %8d %8d %8s %6.0f%%   %d mốc ra%s"
                  % (d, so_cu, n_khuc, "%d/%d" % (cat, n_khuc), 100 * ty, moc_ra,
                     "" if dat else "  ← có khúc không cắt được"))

        if a.apply:
            p = ra_dir / f.relative_to(MOI)
            p.parent.mkdir(parents=True, exist_ok=True)
            io.open(p, "w", encoding="utf-8", newline="\n").write(t)
            ghi += 1

    print("-" * 92)
    print("  Xử lý %d văn bản | cắt trọn vẹn %d | bỏ qua %d" % (tong, ok, bo))

    if a.apply:
        print("  Đã ghi %d file vào %s" % (ghi, ra_dir))
    else:
        print("  >>> Mới là XEM TRƯỚC. Thêm --apply để ghi ra.")


if __name__ == "__main__":
    main()
