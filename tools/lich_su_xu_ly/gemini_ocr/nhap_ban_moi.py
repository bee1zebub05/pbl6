# -*- coding: utf-8 -*-
"""Nhap ban OCR moi (goi API) vao text_clean_gemma qua CONG KIEM DINH.

Ban moi KHONG tu dong thang. Phai dat CA BON dieu kien:
  1. khong con dau [[KHONG OCR DUOC]]        — thieu khuc la mat noi dung
  2. ty le ky tu co dau >= 12%               — duoi la ban hong / font cu
  3. giu >= 85% so CHU CAI cua ban cu        — mat chu thi khong duoc nhan
  4. THEM duoc thong tin: nguoi ky, hoac ngay, hoac quan he can cu

Dieu 4 la diem khac biet: neu ban moi khong them gi ma chi "sach hon" thi GIU BAN CU —
doi ban dang dung ma khong duoc gi la rui ro thua.

LUON lam sach markdown truoc khi so va truoc khi ghi. Output tho cua model co ** quanh
ten ("**Pham Manh Hung**"); khong don thi mau nguoi ky truot het va bao "mat nguoi ky"
oan — da do that mot lan voi 7 tai lieu.

    python nhap_ban_moi.py              # xem truoc
    python nhap_ban_moi.py --apply      # ghi that (luu .bak7)
"""
import argparse
import io
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trich_do_thi as T                                # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
SACH = GOC / "data" / "processed" / "text_clean_gemma"
MOI = GOC / "data" / "processed" / "text_gemma_moi"
LUU = GOC / "data" / "_ban_luu_truoc_khi_sua"

DAU = ("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ"
       "ùúủũụưừứửữựỳýỷỹỵđ")
DAU += DAU.upper()
NGUONG_DAU = 12.0
NGUONG_CHU = 0.85


def don(t):
    """Bo ky tu markdown, chuan hoa khoang trang. GIU nguyen moc trang."""
    t = re.sub(r"\*{1,3}", "", t)
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"(?<!`)`{1,2}(?!`)", "", t)
    t = re.sub(r"^\s*-{3,}\s*$", "", t, flags=re.M)
    t = t.replace("Ð", "Đ").replace("ð", "đ").replace("ﬁ", "fi").replace("ﬂ", "fl")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n[ \t]+", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip() + "\n"


def ty_le_dau(t):
    return 100.0 * sum(1 for c in t if c in DAU) / max(1, len(t))


def so_chu(t):
    return sum(1 for c in t if c.isalpha())


def dem_quan_he(t):
    n = {m.group(2) for m in T.CAN_CU.finditer(t)}
    n |= {m.group(2) for m in T.THAY_THE.finditer(t)}
    ten = set()
    for m in T.CAN_CU_TEN.finditer(t):
        x = T.don_ten_luat(m.group(1), t[m.end():m.end() + 220])
        if x:
            ten.add(x)
    return len(n) + len(ten)


def co_ngay(t):
    return bool(T.NGAY.search(T.trang_dau(t)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    if not MOI.exists():
        print("Chưa có %s" % MOI)
        return 0

    nhan, giu, lydo = [], [], {}
    for fm in sorted(MOI.rglob("*.txt")):
        doc = fm.name[:4]
        fc = next((p for p in SACH.rglob(doc + "_*.txt")), None)
        if not fc:
            continue
        tm = don(io.open(fm, encoding="utf-8", errors="replace").read())
        tc = io.open(fc, encoding="utf-8", errors="replace").read()

        if "[[KHÔNG OCR ĐƯỢC" in tm:
            giu.append(doc); lydo[doc] = "bản mới thiếu khúc"; continue
        d = ty_le_dau(tm)
        if d < NGUONG_DAU:
            giu.append(doc); lydo[doc] = "dấu chỉ %.1f%%" % d; continue
        tyle = so_chu(tm) / max(1, so_chu(tc))
        if tyle < NGUONG_CHU:
            giu.append(doc); lydo[doc] = "chỉ %.0f%% chữ cái" % (100 * tyle); continue

        them = []
        if T.tim_nguoi_ky(tm) and not T.tim_nguoi_ky(tc):
            them.append("người ký")
        if co_ngay(tm) and not co_ngay(tc):
            them.append("ngày")
        dq = dem_quan_he(tm) - dem_quan_he(tc)
        if dq > 0:
            them.append("+%d quan hệ" % dq)
        if not them:
            giu.append(doc); lydo[doc] = "không thêm thông tin gì"; continue

        nhan.append((doc, fc, tm, ", ".join(them)))

    print("=" * 90)
    print("NHẬP BẢN OCR MỚI  %s" % ("(GHI THẬT)" if a.apply else "(chỉ xem trước)"))
    print("=" * 90)
    print("  Xét %d tài liệu | NHẬN %d | giữ bản cũ %d"
          % (len(nhan) + len(giu), len(nhan), len(giu)))
    print("-" * 90)
    from collections import Counter
    for k, v in Counter(lydo.values()).most_common():
        print("  giữ bản cũ vì %-34s %3d" % (k, v))
    print("-" * 90)
    for doc, _f, _t, vs in nhan[:20]:
        print("  ✔ %s  %s" % (doc, vs))
    if len(nhan) > 20:
        print("  … và %d tài liệu nữa" % (len(nhan) - 20))
    print("=" * 90)

    if a.apply:
        for doc, fc, tm, _v in nhan:
            rel = fc.relative_to(SACH)
            b = LUU / (str(rel) + ".bak7")
            b.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fc, b)
            fc.write_text(tm, encoding="utf-8", newline="\n")
        print("Đã thay %d file (bản lưu .bak7 trong %s)" % (len(nhan), LUU))
    elif nhan:
        print(">>> Mới là XEM TRƯỚC. Thêm --apply để ghi thật.")
    return len(nhan)


if __name__ == "__main__":
    main()
