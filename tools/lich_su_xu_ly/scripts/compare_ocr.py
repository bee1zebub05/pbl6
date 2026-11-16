"""So sanh 2 ban OCR cua cung 1 file PDF (vd: ban chay qua chat Gemini vs ban goi API).

Do khong co "dap an" (PDF nay la ban scan, khong co text layer), script do:
  - do dai, so dong, so tu
  - do tuong dong tong the (difflib SequenceMatcher tren chuoi da chuan hoa)
  - cac MOC KIEM TRA cung: so hieu van ban, ngay thang, ten dieu, so tien... co du khong
  - dong chi co o mot ben (dau hieu mat noi dung / bia them)

Chay:
    python compare_ocr.py ban_a.txt ban_b.txt [--nhan-a "chat"] [--nhan-b "api"]
"""
import argparse
import difflib
import re
import sys
import unicodedata
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Nhung chuoi BAT BUOC phai co trong ban OCR dung cua Nghi dinh 78/2020/ND-CP.
# Chon toan cac chi tiet de sai khi OCR: so hieu, ngay, ten rieng, con so.
MOC = [
    "78/2020/NĐ-CP",
    "ngày 06 tháng 7 năm 2020",
    "sĩ quan dự bị",
    "Điều 1. Phạm vi điều chỉnh",
    "Điều 27",
    "26/2002/NĐ-CP",
    "14/2016/NĐ-CP",
    "ngày 19 tháng 8 năm 2020",
    "Nguyễn Xuân Phúc",
    "Chỉ huy trưởng Ban Chỉ huy quân sự cấp xã",
    "quân nhân chuyên nghiệp",
    "Bộ Giáo dục và Đào tạo",
]


def chuan_hoa(s):
    s = unicodedata.normalize("NFC", s)
    s = s.replace(" ", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def rut_gon(s):
    """Bo dau cau + khoang trang de so sanh noi dung, khong so sanh cach xuong dong."""
    return re.sub(r"[^\w]+", "", chuan_hoa(s).lower())


def dong_sach(s):
    return [d.strip() for d in chuan_hoa(s).split("\n") if d.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--nhan-a", default="A")
    ap.add_argument("--nhan-b", default="B")
    ap.add_argument("--so-dong-le", type=int, default=8)
    x = ap.parse_args()

    ta = Path(x.a).read_text(encoding="utf-8", errors="replace")
    tb = Path(x.b).read_text(encoding="utf-8", errors="replace")
    la, lb = dong_sach(ta), dong_sach(tb)

    print("=" * 78)
    print("%-28s %14s %14s" % ("CHI SO", x.nhan_a, x.nhan_b))
    print("-" * 78)
    print("%-28s %14d %14d" % ("Ky tu", len(chuan_hoa(ta)), len(chuan_hoa(tb))))
    print("%-28s %14d %14d" % ("Dong (bo dong trong)", len(la), len(lb)))
    print("%-28s %14d %14d" % ("Tu", len(chuan_hoa(ta).split()), len(chuan_hoa(tb).split())))

    ra, rb = rut_gon(ta), rut_gon(tb)
    ratio = difflib.SequenceMatcher(None, ra, rb, autojunk=False).ratio()
    print("-" * 78)
    print("Do tuong dong (bo dau cau, bo xuong dong): %.2f%%" % (ratio * 100))

    print("-" * 78)
    print("MOC KIEM TRA (chi tiet de sai khi OCR)")
    print("%-46s %8s %8s" % ("", x.nhan_a, x.nhan_b))
    thieu_a = thieu_b = 0
    for m in MOC:
        ca = rut_gon(m) in ra
        cb = rut_gon(m) in rb
        thieu_a += (not ca)
        thieu_b += (not cb)
        print("%-46s %8s %8s" % (m[:44], "co" if ca else "THIEU", "co" if cb else "THIEU"))
    print("%-46s %8d %8d" % ("=> so moc thieu", thieu_a, thieu_b))

    # Dong chi co o mot ben
    sa, sb = set(la), set(lb)
    chi_a = [d for d in la if d not in sb]
    chi_b = [d for d in lb if d not in sa]
    print("-" * 78)
    print("Dong chi xuat hien o %s: %d | chi o %s: %d" % (x.nhan_a, len(chi_a), x.nhan_b, len(chi_b)))
    for nhan, ds in ((x.nhan_a, chi_a), (x.nhan_b, chi_b)):
        if ds:
            print("  vi du chi co o %s:" % nhan)
            for d in ds[: x.so_dong_le]:
                print("    | " + d[:110])
    print("=" * 78)


if __name__ == "__main__":
    main()
