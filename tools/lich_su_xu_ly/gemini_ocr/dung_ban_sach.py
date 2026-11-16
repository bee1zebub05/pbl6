# -*- coding: utf-8 -*-
"""Dung BAN SACH cuoi cung: uu tien Gemma, thieu thi lay text_raw, co cong kiem dinh.

Nguon:
  data/processed/text_gemma  — Gemma OCR lai (113 tai lieu hong nang)
  data/processed/text_raw    — OCR cu, DA duoc sua 1.069 cho tu vong xac minh so
  data/doi_chieu_so/bu_tru/bu_tru.csv — ket qua phan xu tung token so

Quy tac chon nguon cho MOI tai lieu:
  1. Co ban Gemma va ban do QUA KIEM DINH   -> dung Gemma
  2. Khong thi dung text_raw
Kiem dinh ban Gemma (de khong lay nham ban hong):
  - ty le ky tu co dau >= 12%      (duoi la font cu / OCR hong)
  - so CHU CAI >= 80% ban raw      (duoi la mat noi dung — do bang chu cai, khong
                                    phai tong ky tu, vi dau cham lam phinh gia)

Sau khi chon: ap cac cho 'raw dung' tu bang bu_tru (Gemma sai, raw dung), bo ky tu
markdown, chuan hoa khoang trang.

    python dung_ban_sach.py             # xem truoc
    python dung_ban_sach.py --apply     # ghi that
"""
import argparse
import csv
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
RAW = GOC / "data" / "processed" / "text_raw"
GEM = GOC / "data" / "processed" / "text_gemma"
BU = GOC / "data" / "doi_chieu_so" / "bu_tru" / "bu_tru.csv"
RA = GOC / "data" / "processed" / "text_clean_gemma"

DAU = ("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ"
       "ùúủũụưừứửữựỳýỷỹỵđ")
DAU += DAU.upper()
NGUONG_DAU = 12.0
NGUONG_CHU = 0.80


def duong_dan_dai(p):
    if os.name != "nt":
        return str(p)
    p = os.path.abspath(str(p))
    return p if p.startswith("\\\\?\\") else "\\\\?\\" + p


def so_chu_cai(t):
    return sum(1 for c in t if c.isalpha())


def ty_le_dau(t):
    return 100.0 * sum(1 for c in t if c in DAU) / max(1, len(t))


def lam_sach_van_ban(t):
    """Bo ky tu markdown model hay them, chuan hoa khoang trang. GIU nguyen moc trang."""
    t = re.sub(r"\*{1,3}", "", t)
    t = re.sub(r"(?<!`)`{1,2}(?!`)", "", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip() + "\n"


def nap_raw_dung():
    """doc_id -> [(chuoi_gemma_sai, chuoi_raw_dung)]"""
    d = defaultdict(list)
    if not BU.exists():
        return d
    for r in csv.DictReader(open(BU, encoding="utf-8-sig")):
        if r["ket_luan"] == "raw đúng" and r["gemma"] and r["raw"]:
            d[r["doc"]].append((r["gemma"], r["raw"]))
    return d


def bt_linh_hoat(tok):
    return re.compile(r"\s*".join(re.escape(c) for c in tok if not c.isspace()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    raw_dung = nap_raw_dung()
    ix_gem = {}
    for f in GEM.rglob("*.txt"):
        m = re.match(r"(\d{4})_", f.name)
        if m:
            ix_gem[m.group(1)] = f

    dem = Counter()
    ly_do_bo = []
    n_sua = 0
    for fr in sorted(RAW.rglob("*.txt")):
        if fr.name.endswith(".bak"):
            continue
        m = re.match(r"(\d{4})_", fr.name)
        if not m:
            continue
        doc = m.group(1)
        tr = fr.read_text(encoding="utf-8", errors="replace")
        fg = ix_gem.get(doc)
        nguon, t = "raw", tr

        if fg:
            tg = fg.read_text(encoding="utf-8", errors="replace")
            tl = ty_le_dau(tg)
            tyle_chu = so_chu_cai(tg) / max(1, so_chu_cai(tr))
            if tl < NGUONG_DAU:
                ly_do_bo.append((doc, "dấu chỉ %.1f%% (font cũ/OCR hỏng)" % tl))
            elif tyle_chu < NGUONG_CHU:
                ly_do_bo.append((doc, "chỉ %.0f%% chữ cái so với raw" % (100 * tyle_chu)))
            else:
                nguon, t = "gemma", tg

        # ap cac cho raw dung (Gemma sai)
        if nguon == "gemma" and doc in raw_dung:
            for sai, dung in raw_dung[doc]:
                bt = bt_linh_hoat(sai)
                if bt.search(t):
                    t = bt.sub(dung, t, count=1)
                    n_sua += 1

        t = lam_sach_van_ban(t)
        dem[nguon] += 1
        if a.apply:
            dich = RA / fr.relative_to(RAW)
            os.makedirs(duong_dan_dai(dich.parent), exist_ok=True)
            with open(duong_dan_dai(dich), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(t)

    print("=" * 84)
    print("DỰNG BẢN SẠCH  %s" % ("(GHI THẬT)" if a.apply else "(chỉ xem trước)"))
    print("  Ghi ra: %s" % RA)
    print("=" * 84)
    print("  Lấy từ Gemma        : %3d tài liệu" % dem["gemma"])
    print("  Lấy từ text_raw     : %3d tài liệu" % dem["raw"])
    print("  TỔNG                : %3d tài liệu" % sum(dem.values()))
    print("  Chỗ Gemma sai đã sửa lại theo raw: %d" % n_sua)
    if ly_do_bo:
        print("-" * 84)
        print("  Bản Gemma BỊ LOẠI vì không qua kiểm định (%d):" % len(ly_do_bo))
        for doc, ld in ly_do_bo[:12]:
            print("     %s  %s" % (doc, ld))
        if len(ly_do_bo) > 12:
            print("     … và %d tài liệu nữa" % (len(ly_do_bo) - 12))
    print("=" * 84)
    if not a.apply:
        print(">>> Mới là XEM TRƯỚC. Thêm --apply để ghi thật.")


if __name__ == "__main__":
    main()
