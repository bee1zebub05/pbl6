# -*- coding: utf-8 -*-
"""Canh xac_minh_so.py chay xong roi TAT MAY.

An toan:
  - CHI tat khi log co dau hieu HOAN TAT that su ("Bảng đối chiếu:").
  - Neu tien trinh chet giua chung ma chua xong -> KHONG tat, de nguyen may
    cho nguoi dung xu ly (chay lai la di tiep nho diem luu).
  - Truoc khi tat co 120 giay de huy:  shutdown /a

    python tat_may_khi_xong.py              # cho, xong thi tat
    python tat_may_khi_xong.py --thu-thoi   # chi bao, khong tat that
"""
import argparse
import io
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LOG = Path(__file__).resolve().parent / "xac_minh.log"
DAU_HIEU_XONG = "Bảng đối chiếu:"
HOAN = 120          # giay de kip huy


def dang_chay():
    """Con tien trinh xac_minh_so.py nao khong?"""
    try:
        r = subprocess.run(["wmic", "process", "where", "name='python.exe'", "get", "commandline"],
                           capture_output=True, text=True, timeout=25)
        return "xac_minh_so.py" in (r.stdout or "")
    except Exception:
        # wmic bi go bo tren Windows moi -> dung PowerShell
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\").CommandLine"],
                capture_output=True, text=True, timeout=25)
            return "xac_minh_so.py" in (r.stdout or "")
        except Exception:
            return True      # khong biet chac -> coi nhu con chay, TUYET DOI khong tat bua


def da_xong():
    if not LOG.exists():
        return False
    try:
        return DAU_HIEU_XONG in io.open(LOG, encoding="utf-8", errors="replace").read()
    except OSError:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nhip", type=int, default=60)
    ap.add_argument("--thu-thoi", action="store_true", help="chi bao, khong tat may")
    a = ap.parse_args()

    print("Đang canh xac_minh_so.py. Kiểm tra mỗi %ds." % a.nhip)
    print("Huỷ việc canh này: đóng cửa sổ hoặc Ctrl+C.")
    print("-" * 68)
    try:
        while True:
            xong, chay = da_xong(), dang_chay()
            t = time.strftime("%H:%M:%S")
            if xong and not chay:
                print("[%s] ĐÃ CHẠY XONG." % t)
                if a.thu_thoi:
                    print("   (--thu-thoi: không tắt máy thật)")
                    return
                print("   Máy sẽ TẮT sau %d giây." % HOAN)
                print("   HUỶ TẮT MÁY: mở cmd/PowerShell rồi gõ:  shutdown /a")
                subprocess.run(["shutdown", "/s", "/t", str(HOAN),
                                "/c", "OCR da chay xong - tat may theo yeu cau"])
                return
            if not chay and not xong:
                print("[%s] ⚠ Tiến trình đã dừng NHƯNG log chưa báo hoàn tất." % t)
                print("   KHÔNG tắt máy — có thể bị lỗi giữa chừng.")
                print("   Chạy lại  python xac_minh_so.py  là đi tiếp từ điểm lưu.")
                return
            print("[%s] còn đang chạy…" % t)
            time.sleep(a.nhip)
    except KeyboardInterrupt:
        print("\nĐã huỷ canh. Máy sẽ không tự tắt.")


if __name__ == "__main__":
    main()
