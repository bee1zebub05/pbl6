# -*- coding: utf-8 -*-
"""Xem tien do xac_minh_so.py — mot khoi tu lam moi tai cho, khong troi man hinh.

    python xem_xac_minh.py            # tu cap nhat moi 10 giay
    python xem_xac_minh.py --nhip 5
"""
import argparse
import io
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LOG = Path(__file__).resolve().parent / "xac_minh.log"
BANG = Path(__file__).resolve().parents[2] / "data" / "doi_chieu_so"
DONG_TD = re.compile(r"(\d+)/(\d+)\s+([\d.]+)%\s+xong (\d+)\s+hỏng (\d+)\s+lệch (\d+).*?còn ~(\d+) phút")


def ve():
    if not LOG.exists():
        print("Chưa thấy xac_minh.log — đã chạy xac_minh_so.py chưa?")
        return False
    s = io.open(LOG, encoding="utf-8", errors="replace").read()
    dong = [l for l in s.splitlines() if "%" in l and ("█" in l or "░" in l)]
    xong_han = "Bảng đối chiếu" in s

    print("\033[2J\033[H", end="")
    print("═" * 76)
    print(" XÁC MINH SỐ TRONG text_raw            %s" % time.strftime("%H:%M:%S"))
    print("═" * 76)
    if not dong:
        print(" Chưa có lượt nào hoàn thành — đang khởi động / kiểm tra key…")
    else:
        m = DONG_TD.search(dong[-1])
        if m:
            r, tong, pc, xong, hong, lech, con = m.groups()
            r, tong = int(r), int(tong)
            n = int(46 * r / tong)
            print(" %s %s%%" % ("█" * n + "░" * (46 - n), pc))
            print(" %d/%d lượt   xong %s   hỏng %s   LỆCH %s   còn ~%s phút"
                  % (r, tong, xong, hong, lech, con))
        print("─" * 76)
        print(" Mấy lượt gần nhất:")
        for l in dong[-4:]:
            t = re.sub(r"[█░]+", "", l).strip()
            print("   " + t[:70])
    if xong_han:
        print("═" * 76)
        print(" ĐÃ XONG. Bảng đối chiếu ở: %s" % BANG)
    print("═" * 76)
    return xong_han


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nhip", type=int, default=10)
    a = ap.parse_args()
    try:
        while True:
            if ve():
                break
            print(" (Ctrl+C để thoát — làm mới mỗi %ds)" % a.nhip)
            time.sleep(a.nhip)
    except KeyboardInterrupt:
        print("\nThoát.")


if __name__ == "__main__":
    main()
