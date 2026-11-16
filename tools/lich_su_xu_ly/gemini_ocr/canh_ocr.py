# -*- coding: utf-8 -*-
"""Canh tien trinh OCR nen, chi bao khi CO CHUYEN — khong bao cao dinh ky.

Ba truong hop dung va bao:
  1. OCR chay xong (tien trinh khong con)
  2. OCR CHET giua chung (tien trinh mat ma chua den 47/47)
  3. OCR TREO: log khong nhuc nhich qua `--treo` phut

Khong in tien do tung file — muc dich la de KHONG phai hoi lai, chu khong phai de
in them. Ket thuc thi in mot bang tong ket duy nhat.

    python canh_ocr.py --pid 15816
"""
import argparse
import io
import os
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
GOC = Path(__file__).resolve().parents[2]
LOG = Path(__file__).resolve().parent / "ocr_tiep.log"   # doi bang --log
MOI = GOC / "data" / "processed" / "text_gemma_moi"
TIEN_DO = re.compile(r"(\d+)/(\d+)\s+[\d.]+%")


def con_song(pid):
    if os.name != "nt":
        return Path("/proc/%d" % pid).exists()
    import ctypes
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
    if not h:
        return False
    ma = ctypes.c_ulong()
    ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(ma))
    ctypes.windll.kernel32.CloseHandle(h)
    return ma.value == 259          # STILL_ACTIVE


def _cpu(pid):
    try:
        import ctypes
        import ctypes.wintypes as w
        h = ctypes.windll.kernel32.OpenProcess(0x0400 | 0x0010, False, pid)
        if not h:
            return None
        t = [w.FILETIME() for _ in range(4)]
        ok = ctypes.windll.kernel32.GetProcessTimes(
            h, *[ctypes.byref(x) for x in t])
        ctypes.windll.kernel32.CloseHandle(h)
        if not ok:
            return None
        return sum((x.dwHighDateTime << 32) + x.dwLowDateTime for x in t[2:])
    except Exception:
        return None


def _ket_noi(pid):
    """So ket noi TCP dang ESTABLISHED cua tien trinh. -1 neu khong dem duoc."""
    try:
        import subprocess
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "@(Get-NetTCPConnection -OwningProcess %d -State Established "
             "-ErrorAction SilentlyContinue).Count" % pid],
            capture_output=True, text=True, timeout=30)
        return int((r.stdout or "0").strip() or 0)
    except Exception:
        return -1


def song_that(pid, cho=90):
    """Tien trinh co THAT SU dang lam viec khong? (khong chi 'con ton tai')

    Cho ket noi API dang mo, hoac CPU tang len sau `cho` giay. Doi voi OCR thi CPU
    bang 0 la binh thuong — no dang doi mang — nen phai xet ca hai dau, khong the
    ket luan bang mot dau.
    """
    if _ket_noi(pid) > 0:
        return True
    a = _cpu(pid)
    time.sleep(cho)
    b = _cpu(pid)
    if a is None or b is None:
        return True             # khong do duoc thi cho la con song, dung bao bua
    return b > a


def doc_tien_do():
    if not LOG.exists():
        return 0, 0
    ds = TIEN_DO.findall(io.open(LOG, encoding="utf-8", errors="replace").read())
    return (int(ds[-1][0]), int(ds[-1][1])) if ds else (0, 0)


def tong_ket(ly_do):
    xong, tong = doc_tien_do()
    fs = list(MOI.rglob("*.txt"))
    hong = kh = 0
    for f in fs:
        n = len(re.findall(r"KHÔNG OCR ĐƯỢC TRANG",
                           io.open(f, encoding="utf-8", errors="replace").read()))
        if n:
            hong += 1
            kh += n
    print("=" * 78)
    print("OCR — %s" % ly_do)
    print("=" * 78)
    print("  Tiến độ đợt này : %d/%d file" % (xong, tong))
    print("  Tổng bản đã ra  : %d file trong text_gemma_moi" % len(fs))
    print("  Còn khúc hỏng   : %d file / %d khúc" % (hong, kh))
    print("-" * 78)
    print("  Bước tiếp theo:")
    print("    1. python va_khuc_hong.py --thu-muc data/processed/text_gemma_moi "
          "--apply")
    print("    2. python nhap_ban_moi.py          (cổng lọc 4 điều kiện)")
    print("    3. python trich_dieu_khoan.py && python trich_do_thi.py")
    print("    4. cd ../viz && python xuat_neo4j.py --ra ../../data/do_thi/"
          "do_thi_dut.cql")
    print("=" * 78)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    # Moi lan khoi dong lai OCR ghi ra mot log khac. Canh sai log thi doc tien do cu,
    # bao "dung som 12/14" trong khi that ra da chay xong — da bi dung mot lan.
    ap.add_argument("--log", default=None, help="file log cua tien trinh dang canh")
    ap.add_argument("--treo", type=int, default=45, help="phút log đứng im thì báo treo")
    ap.add_argument("--nhip", type=int, default=120, help="giây giữa hai lần kiểm")
    a = ap.parse_args()
    if a.log:
        global LOG
        LOG = Path(a.log)

    print("Đang canh PID %d — chỉ báo khi xong, chết, hoặc treo quá %d phút."
          % (a.pid, a.treo))
    while True:
        time.sleep(a.nhip)
        xong, tong = doc_tien_do()

        if not con_song(a.pid):
            tong_ket("ĐÃ XONG" if tong and xong >= tong
                     else "TIẾN TRÌNH DỪNG SỚM (%d/%d) — cần chạy lại" % (xong, tong))
            return

        im = (time.time() - LOG.stat().st_mtime) / 60 if LOG.exists() else 0
        if im <= a.treo:
            continue

        # Log im KHONG co nghia la treo: log chi ghi mot dong MOI FILE XONG, ma cuoi
        # hang doi la nhung file 100-305 trang, cham hon 45 phut la binh thuong. Ban
        # dau toi bao treo chi dua vao mtime cua log -> bao dong gia ngay lan dau.
        # Treo THAT thi phai hoi du ba dau: log im, KHONG con ket noi API nao, va CPU
        # khong nhuc nhich.
        if song_that(a.pid):
            continue
        print("⚠ OCR TREO: log im %d phút, không còn kết nối API, CPU đứng yên — "
              "đang ở %d/%d." % (im, xong, tong))
        tong_ket("NGHI TREO — kiểm bằng tay")
        return


if __name__ == "__main__":
    main()
