# -*- coding: utf-8 -*-
"""Thanh tien do OCR — doc thang tu o dia nen dung du chay bang duong nao.

    python tien_do.py            # xem 1 lan roi thoat
    python tien_do.py --lap      # tu cap nhat moi 20 giay
    python tien_do.py --lap --nhip 60
"""
import argparse
import os
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
SRC = GOC / "data" / "raw"
OUT = GOC / "data" / "clean_data"
HONG = GOC / "data" / "_hong_thieu_khuc"
EXTS = {".pdf", ".doc", ".docx"}
RONG = 34          # be ngang thanh tien do


def thanh(xong, tong, rong=RONG):
    if not tong:
        return "─" * rong
    n = int(rong * xong / tong)
    return "█" * n + "░" * (rong - n)


def quet():
    """-> {thu_muc: (xong, tong)}, danh sach file da xong kem thoi diem"""
    tm = {}
    moc = []
    for f in SRC.rglob("*"):
        if f.suffix.lower() not in EXTS:
            continue
        rel = f.relative_to(SRC).as_posix()
        thu = rel.rsplit("/", 1)[0] if "/" in rel else "."
        dich = OUT / Path(rel).with_suffix(".txt")
        try:
            co = dich.stat().st_size > 0
            if co:
                moc.append(dich.stat().st_mtime)
        except OSError:
            co = False
        x, t = tm.get(thu, (0, 0))
        tm[thu] = (x + (1 if co else 0), t + 1)
    return tm, moc


def ve(bat_dau_phien):
    tm, moc = quet()
    xong = sum(x for x, _t in tm.values())
    tong = sum(t for _x, t in tm.values())
    con = tong - xong

    # toc do: dua tren cac file hoan thanh trong 30 phut gan nhat
    bay = time.time()
    gan = [m for m in moc if bay - m < 1800]
    moi_phut = len(gan) / 30.0 if gan else 0.0
    con_lai = ("%.0f phút" % (con / moi_phut)) if moi_phut > 0.02 else "chưa đo được"

    n_hong = len(list(HONG.rglob("*.txt"))) if HONG.exists() else 0
    n_thieu = 0
    for f in OUT.rglob("*.txt"):
        try:
            if "KHÔNG OCR ĐƯỢC" in f.read_text(encoding="utf-8", errors="ignore")[:4000]:
                n_thieu += 1
        except OSError:
            pass

    print("\033[2J\033[H" if bat_dau_phien else "", end="")
    print("═" * 78)
    print(" TIẾN ĐỘ OCR   %s   %s" % (thanh(xong, tong), time.strftime("%H:%M:%S")))
    print(" %d/%d file  (%.1f%%)   còn %d   |   %.1f file/phút   |   ước còn %s"
          % (xong, tong, 100.0 * xong / max(1, tong), con, moi_phut, con_lai))
    if n_hong or n_thieu:
        print(" ⚠ %d file thiếu khúc đã tách ra _hong_thieu_khuc | %d file đang lỗi trong clean_data"
              % (n_hong, n_thieu))
    print("═" * 78)
    for thu in sorted(tm, key=lambda k: (-tm[k][1], k)):
        x, t = tm[thu]
        dau = "✔" if x == t else " "
        print(" %s %-30s %s %3d/%-3d" % (dau, thu[-30:], thanh(x, t, 22), x, t))
    print("═" * 78)

    # ── dang lam gi ngay luc nay ──
    log = Path(__file__).resolve().parent / "gemma_toanbo.log"
    if log.exists():
        try:
            dong = log.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            dong = []
        hd = [l.rstrip() for l in dong if ("[" in l and "]" in l) or "bắt đầu" in l][-10:]
        if hd:
            print(" ĐANG LÀM GÌ (10 dòng cuối của log)")
            for l in hd:
                print("  " + l.strip()[:74])
            print("═" * 78)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lap", action="store_true")
    ap.add_argument("--nhip", type=int, default=20)
    a = ap.parse_args()
    if not a.lap:
        ve(False)
        return
    try:
        while True:
            ve(True)
            print(" (Ctrl+C để thoát — tự cập nhật mỗi %ds)" % a.nhip)
            time.sleep(a.nhip)
    except KeyboardInterrupt:
        print("\nDừng xem.")


if __name__ == "__main__":
    main()
