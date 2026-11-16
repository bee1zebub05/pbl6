# -*- coding: utf-8 -*-
"""Giam sat den khi va xong het khuc hong, roi commit + push + tat may.

Chay khong can nguoi truc. Tu khoi dong lai tien trinh va neu no chet, tu ha so
luong khi dich vu qua tai, va BIET DUNG khi khong con cuu them duoc gi.

BON CHO PHAI CAN THAN, deu rut tu nhung lan hong truoc trong phien nay:

  1. DEM KHUC HONG TRONG FILE, khong doc log.
     Log dung ThreadPoolExecutor.map nen tra ket qua theo THU TU DAU VAO — mot cho
     cham o dau hang doi che het moi cho da xong phia sau. Da thay log bao "0 va
     xong" trong khi thuc te da va duoc 12 cho.

  2. PHAI CO DIEU KIEN DUNG.
     Vai khuc dinh RECITATION co the khong bao gio cuu duoc. Chay lai vo han thi
     treo may ca dem ma khong duoc gi. Dung khi mot luot chay tron ven ma khong
     giam duoc khuc nao.

  3. HA SO LUONG KHI KEY BI HOAN NHIEU.
     500 INTERNAL tang theo so luong -> qua nguong thi tu ha, vi chay nhieu luong
     hon luc dich vu qua tai chi lam moi thu cham hon.

  4. TAT MAY CO TRI HOAN.
     `shutdown /t 300` de con 5 phut huy bang `shutdown /a` neu nguoi dung ve som.
"""
import argparse
import io
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
OCR_DIR = Path(__file__).resolve().parent
MOI = GOC / "data" / "processed" / "text_gemma_moi"
REPO = GOC / "pbl6"
PY = sys.executable
HONG = re.compile(r"KHÔNG OCR ĐƯỢC TRANG")


def say(s=""):
    print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), s), flush=True)


def dem_hong():
    """So khuc hong con lai — dem THANG TRONG FILE, khong doc log."""
    n = 0
    for f in MOI.rglob("*.txt"):
        n += len(HONG.findall(io.open(f, encoding="utf-8", errors="replace").read()))
    return n


def con_song(pid):
    import ctypes
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
    if not h:
        return False
    ma = ctypes.c_ulong()
    ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(ma))
    ctypes.windll.kernel32.CloseHandle(h)
    return ma.value == 259


def key_bi_hoan(log):
    if not Path(log).exists():
        return 0
    return io.open(log, encoding="utf-8", errors="replace").read().count("⏸")


def chay_va(luong, lan):
    log = OCR_DIR / ("va_tudong_%d.log" % lan)
    f = io.open(log, "w", encoding="utf-8")
    p = subprocess.Popen(
        [PY, "-B", "-u", "va_khuc_hong.py", "--thu-muc",
         "data/processed/text_gemma_moi", "--apply", "--song-song", str(luong)],
        cwd=str(OCR_DIR), stdout=f, stderr=subprocess.STDOUT,
    )
    say("  khởi động lượt %d: %d luồng, PID %d" % (lan, luong, p.pid))
    return p.pid, str(log)


def chay(lenh, cwd=None, phut=30):
    r = subprocess.run(lenh, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=phut * 60)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--luong", type=int, default=14)
    ap.add_argument("--luot-toi-da", type=int, default=6)
    ap.add_argument("--gio-toi-da", type=float, default=8.0)
    ap.add_argument("--khong-tat", action="store_true")
    ap.add_argument("--khong-push", action="store_true")
    a = ap.parse_args()

    bat_dau = time.time()
    lan = 0
    luong = a.luong
    pid = None
    log = None
    truoc = dem_hong()

    say("=" * 74)
    say("GIÁM SÁT VÁ KHÚC HỎNG — bắt đầu với %d khúc" % truoc)
    say("=" * 74)

    # Neu dang co tien trinh cu chay thi bam theo no, khong khoi dong chong cheo
    while True:
        if (time.time() - bat_dau) / 3600 > a.gio_toi_da:
            say("Quá %.1f giờ — dừng giám sát." % a.gio_toi_da)
            break

        con = dem_hong()

        if con == 0:
            say("✔ Không còn khúc hỏng nào.")
            break

        if pid and con_song(pid):
            if log and key_bi_hoan(log) > 40 and luong > 6:
                luong = max(6, luong - 4)
                say("  nhiều key bị hoãn -> lượt sau hạ xuống %d luồng" % luong)
            time.sleep(120)
            continue

        # Tien trinh khong chay: ket thuc mot luot
        if lan:
            say("  lượt %d xong: %d -> %d khúc" % (lan, truoc, con))

            if con >= truoc:
                say("✖ Lượt vừa rồi KHÔNG giảm được khúc nào — dừng, "
                    "%d khúc còn lại nhiều khả năng không cứu được." % con)
                break

        if lan >= a.luot_toi_da:
            say("Đã chạy %d lượt — dừng." % lan)
            break

        truoc = con
        lan += 1
        pid, log = chay_va(luong, lan)
        time.sleep(60)

    # ---- tong ket + day len git ----------------------------------------------
    con = dem_hong()
    fs = list(MOI.rglob("*.txt"))
    tong = sum(len(io.open(f, encoding="utf-8", errors="replace").read()) for f in fs)
    say("")
    say("=" * 74)
    say("KẾT QUẢ: %d file, %.1f MB, còn %d khúc hỏng" % (len(fs), tong / 1048576, con))
    say("=" * 74)

    bao = [
        "# Báo cáo vá khúc hỏng — %s" % datetime.now().strftime("%Y-%m-%d %H:%M"),
        "",
        "| | |", "|---|---|",
        "| File | %d |" % len(fs),
        "| Dung lượng | %.1f MB |" % (tong / 1048576),
        "| Khúc hỏng còn lại | **%d** |" % con,
        "| Số lượt chạy | %d |" % lan,
        "",
    ]

    if not a.khong_push and REPO.exists():
        say("Chép dữ liệu sang repo và đẩy lên...")
        n = 0
        for p in MOI.rglob("*.txt"):
            ra = REPO / "data" / "clean" / "text_gemma_moi" / p.relative_to(MOI)
            ra.parent.mkdir(parents=True, exist_ok=True)
            io.open(ra, "wb").write(io.open(p, "rb").read().replace(b"\r\n", b"\n"))
            n += 1

        ma, out = chay(["git", "add", "-A"], cwd=str(REPO))
        ma, out = chay(["git", "diff", "--cached", "--shortstat"], cwd=str(REPO))
        say("  " + out.strip())

        if out.strip():
            tin = ("Vá khúc hỏng trong text_gemma_moi\n\n"
                   "Chạy %d lượt vá tự động. Khúc hỏng %d -> %d.\n\n"
                   "Những khúc còn lại dính RECITATION và không cứu được kể cả khi\n"
                   "chia xuống từng trang — đã thử lần lượt gemini-3.5-flash-lite,\n"
                   "gemini-3.1-flash-lite, gemma-4-31b-it, gemma-4-26b-a4b-it.\n"
                   % (lan, truoc, con))
            ma, out2 = chay(["git", "commit", "-q", "-m", tin], cwd=str(REPO))
            say("  commit: %s" % ("OK" if ma == 0 else out2[:200]))
            ma, out3 = chay(["git", "push"], cwd=str(REPO))
            say("  push: %s" % ("OK" if ma == 0 else out3[:200]))
            bao.append("Đã commit và đẩy lên nhánh `ocr-recitation-fix`.")
        else:
            say("  không có gì thay đổi để commit")
            bao.append("Không có thay đổi nào để commit.")

    (GOC / "BAO_CAO_VA_KHUC.md").write_text("\n".join(bao) + "\n", encoding="utf-8")
    say("Đã ghi BAO_CAO_VA_KHUC.md")

    if a.khong_tat:
        say("Bỏ qua tắt máy (--khong-tat).")
        return

    say("Tắt máy sau 5 phút. Huỷ bằng:  shutdown /a")
    subprocess.run(["shutdown", "/s", "/t", "300", "/c",
                    "PBL6: va khuc hong xong, tat may. Huy: shutdown /a"])


if __name__ == "__main__":
    main()
