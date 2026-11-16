# -*- coding: utf-8 -*-
"""Cham chat luong dot OCR MOI (goi API) so voi ban dang dung trong text_clean_gemma.

Cau hoi can tra loi truoc khi bo 3 tieng chay 243 file con lai:
    ban OCR bang API co THAT SU tot hon ban OCR bang Gemini chat web khong,
    va tot hon o cho nao?

Do bang nhung thu KIEM CHUNG DUOC, khong doan:
  1. NGUOI KY   — truong yeu nhat, va la ly do chinh cua ca dot nay
  2. NGAY BAN HANH
  3. CAN CU PHAP LY  (so quan he trich duoc)
  4. Ty le ky tu co dau  — duoi 12% la ban hong
  5. So chu cai      — mat noi dung thi khong duoc nhan du co them thong tin

    python danh_gia_dot_moi.py
    python danh_gia_dot_moi.py --chi-tiet
"""
import argparse
import io
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trich_do_thi as T                                # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
SACH = GOC / "data" / "processed" / "text_clean_gemma"
MOI = GOC / "data" / "processed" / "text_gemma_moi"

DAU = ("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ"
       "ùúủũụưừứửữựỳýỷỹỵđ")
DAU += DAU.upper()


def don(t):
    """Bo ky tu markdown truoc khi cham.

    Output tho cua model co ** quanh ten va chuc danh ("**Pham Manh Hung**"). Ban trong
    text_clean_gemma da qua bo lam sach nen khong con. So thang hai ban la so tao voi
    sach — mau ten neo vao dau dong nen truot het cho co **, khien 7 tai lieu bi bao
    "mat nguoi ky" trong khi ten van nguyen ven.
    """
    t = re.sub(r"\*{1,3}", "", t)
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"(?<!`)`{1,2}(?!`)", "", t)
    t = re.sub(r"^\s*-{3,}\s*$", "", t, flags=re.M)
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip() + "\n"


def ty_le_dau(t):
    return 100.0 * sum(1 for c in t if c in DAU) / max(1, len(t))


def so_chu(t):
    return sum(1 for c in t if c.isalpha())


def dem_can_cu(t):
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
    ap.add_argument("--chi-tiet", action="store_true")
    a = ap.parse_args()

    hang = []
    for fm in sorted(MOI.rglob("*.txt")):
        doc = fm.name[:4]
        fc = next((p for p in SACH.rglob(doc + "_*.txt")), None)
        if not fc:
            continue
        tm = don(io.open(fm, encoding="utf-8", errors="replace").read())
        tc = io.open(fc, encoding="utf-8", errors="replace").read()
        hang.append({
            "doc": doc, "ten": fc.name[5:46],
            "ky_cu": T.tim_nguoi_ky(tc), "ky_moi": T.tim_nguoi_ky(tm),
            "ngay_cu": co_ngay(tc), "ngay_moi": co_ngay(tm),
            "cc_cu": dem_can_cu(tc), "cc_moi": dem_can_cu(tm),
            "dau_cu": ty_le_dau(tc), "dau_moi": ty_le_dau(tm),
            "chu_cu": so_chu(tc), "chu_moi": so_chu(tm),
            "thieu": "[[KHÔNG OCR ĐƯỢC" in tm,
        })

    if not hang:
        print("Chưa có file nào để chấm.")
        return
    n = len(hang)

    print("=" * 92)
    print("CHẤM ĐỢT OCR MỚI (gọi API) — %d tài liệu" % n)
    print("=" * 92)
    print("%-30s %14s %14s %12s" % ("CHỈ SỐ", "bản đang dùng", "bản API mới", "chênh"))
    print("-" * 92)

    kc, km = sum(1 for h in hang if h["ky_cu"]), sum(1 for h in hang if h["ky_moi"])
    print("%-30s %13d%% %13d%% %+11d%%"
          % ("Đọc được NGƯỜI KÝ", 100 * kc // n, 100 * km // n,
             100 * km // n - 100 * kc // n))
    nc, nm = sum(h["ngay_cu"] for h in hang), sum(h["ngay_moi"] for h in hang)
    print("%-30s %13d%% %13d%% %+11d%%"
          % ("Đọc được NGÀY BAN HÀNH", 100 * nc // n, 100 * nm // n,
             100 * nm // n - 100 * nc // n))
    cc, cm = sum(h["cc_cu"] for h in hang), sum(h["cc_moi"] for h in hang)
    print("%-30s %14d %14d %+12d" % ("Tổng quan hệ CĂN_CỨ", cc, cm, cm - cc))
    dc = sum(h["dau_cu"] for h in hang) / n
    dm = sum(h["dau_moi"] for h in hang) / n
    print("%-30s %13.1f%% %13.1f%% %+11.1f" % ("Tỉ lệ ký tự có dấu (TB)", dc, dm, dm - dc))
    uc, um = sum(h["chu_cu"] for h in hang), sum(h["chu_moi"] for h in hang)
    print("%-30s %14s %14s %+11.0f%%"
          % ("Tổng chữ cái", "{:,}".format(uc), "{:,}".format(um),
             100.0 * (um - uc) / max(1, uc)))
    print("-" * 92)

    them_ky = [h for h in hang if h["ky_moi"] and not h["ky_cu"]]
    mat_ky = [h for h in hang if h["ky_cu"] and not h["ky_moi"]]
    khac_ky = [h for h in hang if h["ky_cu"] and h["ky_moi"] and h["ky_cu"] != h["ky_moi"]]
    print("  NGƯỜI KÝ: bản mới lấy thêm %d | mất %d | đọc khác nhau %d"
          % (len(them_ky), len(mat_ky), len(khac_ky)))
    print("  Bản mới THIẾU KHÚC: %d tài liệu" % sum(1 for h in hang if h["thieu"]))
    print("=" * 92)

    if them_ky:
        print("  Người ký LẤY THÊM được:")
        for h in them_ky[:15]:
            print("     %s  %-24s %s" % (h["doc"], h["ky_moi"][:24], h["ten"][:38]))
        if len(them_ky) > 15:
            print("     … và %d tài liệu nữa" % (len(them_ky) - 15))
    if khac_ky:
        print()
        print("  Người ký ĐỌC KHÁC NHAU (cần xem):")
        for h in khac_ky:
            print("     %s  cũ=%-22s mới=%-22s" % (h["doc"], h["ky_cu"][:22], h["ky_moi"][:22]))
    if mat_ky:
        print()
        print("  Người ký BẢN MỚI MẤT (bản cũ có):")
        for h in mat_ky:
            print("     %s  cũ=%-22s %s" % (h["doc"], h["ky_cu"][:22], h["ten"][:36]))

    if a.chi_tiet:
        print()
        print("%-5s %-9s %-9s %5s %5s %6s %6s %7s" %
              ("doc", "ký cũ", "ký mới", "cc cũ", "cc mới", "dấu cũ", "dấu mới", "chữ %"))
        for h in sorted(hang, key=lambda x: x["doc"]):
            print("%-5s %-9s %-9s %5d %5d %5.1f%% %6.1f%% %+6.0f%%"
                  % (h["doc"], "có" if h["ky_cu"] else "—", "có" if h["ky_moi"] else "—",
                     h["cc_cu"], h["cc_moi"], h["dau_cu"], h["dau_moi"],
                     100.0 * (h["chu_moi"] - h["chu_cu"]) / max(1, h["chu_cu"])))


if __name__ == "__main__":
    main()
