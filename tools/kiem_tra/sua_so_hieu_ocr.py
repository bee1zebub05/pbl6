# -*- coding: utf-8 -*-
"""Sua so hieu bi OCR doc chu cai thanh chu so, trong NGU CANH VIEN DAN.

    python tools/kiem_tra/sua_so_hieu_ocr.py          # chi xem, khong ghi
    python tools/kiem_tra/sua_so_hieu_ocr.py --ghi    # ghi that, co sao luu

Chi dong toi nhung cho hoi du BA dieu kien, de khong sua mo:

  1. Nam ngay sau "<loai van ban> ... so " — tuc chac chan la so hieu.
  2. Phan so co chu cai o vi tri chu so (O thay 0, I/l thay 1, S thay 5...).
  3. Gia tri sau khi sua KHAC gia tri dang co — khong doi gi thi bo qua.

Khong dung cho chu cai HOP LE trong so hieu: `213b/QĐ-ĐHBK`, `16a/2019/TT-BGDĐT`
— chu cai o do nam SAU day so, khong phai thay cho chu so.
"""
from __future__ import annotations

import argparse
import io
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
KHO = GOC / "data" / "clean" / "text_final"

LOAI = (r"Nghị\s*quyết|Quyết\s*định|Thông\s*tư|Nghị\s*định|Chỉ\s*thị|Luật|"
        r"Kế\s*hoạch|Công\s*văn|Hướng\s*dẫn|Pháp\s*lệnh")
RX = re.compile(r"(?P<dau>(?:%s)[^\n]{0,24}?số\s*)(?P<so>[0-9OolISBZG]{1,6})"
                r"(?P<duoi>\s*/\s*[A-ZĐ][\w\-Đ]{1,20})" % LOAI, re.I)

# Chi cac ky tu HAY bi OCR doc nham thanh chu so. Khong them chu cai khac vao
# day: `213b` co chu `b` hop le, sua la hong so hieu that.
NHAM = {"O": "0", "o": "0", "l": "1", "I": "1", "S": "5", "B": "8",
        "Z": "2", "G": "6"}


def _sua(so: str) -> str:
    return "".join(NHAM.get(c, c) for c in so)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ghi", action="store_true", help="ghi that (mac dinh chi xem)")
    a = ap.parse_args()

    tong = 0
    for p in sorted(KHO.rglob("*.txt")):
        t = io.open(p, encoding="utf-8").read()
        doi = []

        def thay(m):
            so = m.group("so")
            if so.isdigit():
                return m.group(0)
            moi = _sua(so)
            if moi == so or not moi.isdigit():
                return m.group(0)
            doi.append((so + m.group("duoi").strip(), moi + m.group("duoi").strip()))
            return m.group("dau") + moi + m.group("duoi")

        moi = RX.sub(thay, t)
        if not doi:
            continue
        tong += len(doi)
        print("%s  %s" % (p.name[:4], p.parent.name))
        for cu, mo in doi:
            print("    %-26s -> %s" % (cu.replace("\n", " "), mo.replace("\n", " ")))
        if a.ghi:
            shutil.copy2(p, str(p) + ".truoc_khi_sua_so_hieu")
            io.open(p, "w", encoding="utf-8", newline="\n").write(moi)

    print("\n%d chỗ ở %s" % (tong, "ĐÃ GHI (có sao lưu .truoc_khi_sua_so_hieu)"
                             if a.ghi else "chưa ghi — thêm --ghi để sửa thật"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
