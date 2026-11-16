# -*- coding: utf-8 -*-
"""Kiem moc trang bang MO NEO DOC LAP: so trang IN TREN GIAY.

VI SAO CAN. So noi dung giua ban cu va ban moi khong phat hien duoc lech trang:
ban moi doc bang theo thu tu khac va day du hon nen diem giong tut xuong vi ly do
LANH TINH, con lech that thi lai co the van cao diem. Da do that tren 0101 — diem
giong ca trang 50%, nhung so trang in tren giay cho thay tu trang 12 tro di ban
moi LECH DUNG MOT TRANG.

So trang in tren giay la mo neo tot vi no:
  - nam san trong noi dung, khong phai thu ta tu dat ra
  - tang dan deu, nen doi chieu duoc ca huong lech
  - doc lap hoan toan voi cach OCR doc bang

CACH LAM. Voi moi van ban, tim day so tang dan deu 1 don vi xuyen qua cac trang cua
BAN CU (do chinh la so trang in). Neu tim duoc, kiem xem trang N cua ban moi co
chua dung so do khong.

    python kiem_moc_trang.py
    python kiem_moc_trang.py --doc 0101 --chi-tiet
"""
import argparse
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from can_trang import tach_moc                      # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
CU = GOC / "data" / "processed" / "text_clean_gemma"
SO = re.compile(r"\b(\d{1,6})\b")


def day_so_trang(cu):
    """Tim so IN TREN GIAY cua tung trang. -> {so_trang_file: so_in} hoac {}.

    Cach nhan: co mot hang so d sao cho rat nhieu trang N deu chua so (goc + N*1).
    Thu moi goc co the co tu cac so xuat hien o trang dau tien.
    """
    trang = sorted(cu)
    if len(trang) < 5:
        return {}

    bo = {s: set(int(x) for x in SO.findall(cu[s]) if len(x) <= 6) for s in trang}
    tot = {}

    for goc in sorted(bo[trang[0]]):
        ra = {}
        for i, s in enumerate(trang):
            ung = goc + i
            if ung in bo[s]:
                ra[s] = ung
        if len(ra) > len(tot):
            tot = ra

    # doi hoi it nhat mot nua so trang co mo neo thi moi tin la day so trang that
    return tot if len(tot) >= max(4, len(trang) * 0.5) else {}


def kiem(d, chi_tiet=False):
    """-> (so trang khop, tong mo neo, lech dau tien) hoac None."""
    pc = list(CU.rglob(d + "_*.txt"))
    pm = list((GOC / "data" / "processed" / "text_gemma_trang").rglob(d + "_*.txt"))

    if not (pc and pm):
        return None

    cu = dict(tach_moc(io.open(pc[0], encoding="utf-8", errors="replace").read()))
    mo = dict(tach_moc(io.open(pm[0], encoding="utf-8", errors="replace").read()))
    neo = day_so_trang(cu)

    if not neo:
        return None

    khop = 0
    tong = 0
    lech = None

    for s in sorted(neo):
        if s not in mo:
            continue
        tong += 1
        co = set(int(x) for x in SO.findall(mo[s]))

        if neo[s] in co:
            khop += 1
        else:
            if lech is None:
                lech = s
            if chi_tiet:
                gan = [x for x in co if abs(x - neo[s]) <= 3]
                print("   trang %-3d cần %d, thấy %s" % (s, neo[s], sorted(gan) or "—"))

    return khop, tong, lech


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", default=None)
    ap.add_argument("--chi-tiet", action="store_true")
    a = ap.parse_args()

    ds = ([a.doc] if a.doc
          else sorted({f.name[:4] for f in
                       (GOC / "data" / "processed" / "text_gemma_trang").rglob("*.txt")}))

    print("=" * 78)
    print("KIỂM MỐC TRANG BẰNG SỐ TRANG IN TRÊN GIẤY")
    print("=" * 78)

    co_neo = 0
    sach = []
    ban = []

    for d in ds:
        r = kiem(d, a.chi_tiet or bool(a.doc))
        if not r:
            continue

        khop, tong, lech = r
        co_neo += 1
        ty = khop / max(1, tong)

        (sach if ty >= 0.9 else ban).append((d, khop, tong, ty, lech))

        if a.doc:
            print("  %s: %d/%d mốc khớp (%.0f%%)%s"
                  % (d, khop, tong, 100 * ty,
                     ", lệch từ trang %d" % lech if lech else ""))

    if a.doc:
        return

    print("  Văn bản có số trang in để đối chiếu : %d / %d" % (co_neo, len(ds)))
    print("  ✔ khớp ≥90%%  : %d" % len(sach))
    print("  ✖ dưới 90%%   : %d" % len(ban))

    if ban:
        print("-" * 78)
        print("  %-6s %10s %8s   %s" % ("doc", "khớp", "tỷ lệ", "lệch từ trang"))
        for d, khop, tong, ty, lech in sorted(ban, key=lambda x: x[3]):
            print("  %-6s %6d/%-3d %7.0f%%   %s"
                  % (d, khop, tong, 100 * ty, lech if lech else "—"))


if __name__ == "__main__":
    main()
