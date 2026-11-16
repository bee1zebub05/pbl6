# -*- coding: utf-8 -*-
"""Chen khoi ky vet duoc vao cuoi file text, de bo trich doc duoc nhu binh thuong.

Ten nguoi ky CO TREN GIAY nhung ban OCR khong bat duoc (con dau de len chu, bo cuc
hai cot bi xao). `vet_nguoi_ky.py` da OCR lai rieng trang do va hoi dung mot viec.
Gio chen ket qua vao cuoi file, GHI RO LA CHEN THEM chu khong tron lan vao phan
OCR goc.

PHAI LOC PLACEHOLDER. Model doc trung o BIEU MAU trong phu luc:
    '(Ký, ghi rõ họ tên và đóng dấu)'  <- cho trong de nguoi ta dien, khong phai ten
    '.....'                            <- dong cham cham
Nhan ra bang chinh hinh dang: co dau ngoac, co chuoi dau cham, hoac khong co tu nao
viet hoa dung kieu ten nguoi.
"""
import argparse
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trich_do_thi import HO_VIET, _bo_dau, chuan_chuc_danh  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
KHO = GOC / "data" / "processed" / "text_final"
VET = GOC / "data" / "nguoi_ky_vet.json"

MOC = "----- [Khối ký — OCR lại trang %s] -----"
TEN = re.compile(r"^([A-ZĐÀ-Ỹ][a-zà-ỹ]+(?:\s+[A-ZĐÀ-Ỹ][a-zà-ỹ]+){1,4})$")
HH = re.compile(r"^(?:(?:PGS|GS|TS|ThS|CN)[\s.,]*)+", re.I)


def loc(ten):
    """-> ten sach, hoac '' neu la placeholder cua bieu mau."""
    s = re.sub(r"\s+", " ", (ten or "").strip())

    # dau hieu bieu mau: ngoac don, chuoi cham, chu 'ký, ghi rõ'
    if re.search(r"ký\s*,?\s*ghi\s*rõ|đóng\s*dấu|\.{3,}|^\(|họ\s*và\s*tên", s, re.I):
        return ""

    s = s.strip(" .,:-")
    con = HH.sub("", s).strip(" .,")
    m = TEN.match(con)

    if not m:
        return ""

    tu = m.group(1).split()

    if not (2 <= len(tu) <= 5):
        return ""

    # phai bat dau bang ho nguoi Viet — chinh cho nay loai 'Thủ Trưởng Đơn Vị'
    if _bo_dau(tu[0]).lower() not in HO_VIET:
        return ""

    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    if not VET.exists():
        print("Chưa có %s — chạy vet_nguoi_ky.py --apply trước." % VET.name)
        return

    d = json.loads(VET.read_text(encoding="utf-8"))

    nhan = []
    bo = []
    for doc, x in sorted(d.items()):
        ten = loc(x["ho_ten"])
        (nhan if ten else bo).append((doc, x, ten or x["ho_ten"]))

    print("=" * 84)
    print("NẠP NGƯỜI KÝ VÉT ĐƯỢC")
    print("=" * 84)
    print("  Nhận : %d" % len(nhan))
    for doc, x, ten in nhan:
        print("     %s %-20s %-26s %s" % (doc, x["so_hieu"], ten, x["chuc_danh"][:26]))
    print("  Loại : %d  (placeholder biểu mẫu, không phải người ký)" % len(bo))
    for doc, x, ten in bo:
        print("     %s %-20s %s" % (doc, x["so_hieu"], ten[:46]))

    if not a.apply:
        print("=" * 84)
        print(">>> Mới là XEM TRƯỚC. Thêm --apply để chèn vào kho.")
        return

    n = 0
    for doc, x, ten in nhan:
        p = list(KHO.rglob(doc + "_*.txt"))
        if not p:
            continue
        t = io.open(p[0], encoding="utf-8", errors="replace").read()

        if MOC % x["trang"] in t:
            continue

        cd = chuan_chuc_danh(x["chuc_danh"]) or x["chuc_danh"]
        them = "\n\n%s\n%s\n%s\n" % (MOC % x["trang"], x["chuc_danh"].strip(), ten)
        io.open(p[0], "w", encoding="utf-8", newline="\n").write(t.rstrip() + them)
        n += 1

    print("=" * 84)
    print("Đã chèn khối ký vào %d file." % n)


if __name__ == "__main__":
    main()
