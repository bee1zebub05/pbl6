# -*- coding: utf-8 -*-
"""Gom 1500+ cho LECH thanh cac NHOM cung mau sai, de duyet theo nhom thay vi tung dong.

Doc ket_qua.jsonl, rut ra "mau sai" o muc ky tu (vd '4→Đ' nghia la OCR doc Đ thanh 4),
xep theo so lan xuat hien, xuat file goi de nguoi doc duyet nhanh.

    python gom_nhom_lech.py
    python gom_nhom_lech.py --vi-du 5      # moi nhom in 5 vi du thay vi 3
"""
import argparse
import difflib
import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RA = Path(__file__).resolve().parents[2] / "data" / "doi_chieu_so"


def mau_sai(cu, moi):
    """'2344 /QĐ-ĐHBK' vs '2347 /QĐ-ĐHBK'  ->  '4→7'  (chi giu phan khac nhau)."""
    ra = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, cu, moi).get_opcodes():
        if tag != "equal":
            ra.append("%s→%s" % (cu[i1:i2] or "∅", moi[j1:j2] or "∅"))
    return " , ".join(ra)[:44] or "(giống hệt)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vi-du", type=int, default=3)
    a = ap.parse_args()

    kq = RA / "ket_qua.jsonl"
    if not kq.exists():
        print("Chưa có %s" % kq)
        sys.exit(1)

    d = [json.loads(l) for l in io.open(kq, encoding="utf-8") if l.strip()]
    lech = [x for x in d if x["khop"] == "LỆCH"]
    kh_thay = [x for x in d if x["khop"] == "KHÔNG THẤY"]

    nhom = defaultdict(list)
    for x in lech:
        nhom[mau_sai(x["so_cu"], x["so_moi"])].append(x)
    xep = sorted(nhom.items(), key=lambda kv: -len(kv[1]))

    md = RA / "nhom_loi.md"
    with open(md, "w", encoding="utf-8", newline="\n") as f:
        f.write("# Các chỗ số LỆCH, gom theo mẫu sai\n\n")
        f.write("- Tổng token đối chiếu: **%d**\n" % len(d))
        f.write("- LỆCH: **%d** | Không tìm thấy đối ứng: %d | Khớp: %d\n"
                % (len(lech), len(kh_thay), len(d) - len(lech) - len(kh_thay)))
        f.write("- Số mẫu sai khác nhau: **%d**\n\n" % len(nhom))
        f.write("Ký hiệu `4→Đ` nghĩa là OCR cũ đọc chữ `Đ` thành số `4`.\n")
        f.write("`∅→0` nghĩa là OCR cũ **thiếu** ký tự `0`.\n\n")
        f.write("---\n\n")

        tich = 0
        for i, (m, ds) in enumerate(xep, 1):
            tich += len(ds)
            f.write("## %d. `%s` — %d chỗ  *(cộng dồn %.0f%%)*\n\n" % (i, m, len(ds), 100 * tich / len(lech)))
            f.write("| doc | trang | cũ | mới |\n|---|---|---|---|\n")
            for x in ds[: a.vi_du]:
                f.write("| %s | %s | `%s` | `%s` |\n" % (x["doc_id"], x["trang"], x["so_cu"], x["so_moi"]))
            if len(ds) > a.vi_du:
                f.write("\n*… và %d chỗ nữa cùng mẫu này*\n" % (len(ds) - a.vi_du))
            f.write("\n")

    # ban tom tat cuc ngan de doc truoc
    tt = RA / "tom_tat.md"
    with open(tt, "w", encoding="utf-8", newline="\n") as f:
        f.write("# Tóm tắt — đọc file này trước\n\n")
        f.write("| | |\n|---|---|\n")
        f.write("| Token số đã đối chiếu | **%d** |\n" % len(d))
        f.write("| **LỆCH (OCR cũ sai)** | **%d (%.0f%%)** |\n" % (len(lech), 100 * len(lech) / len(d)))
        f.write("| Không tìm thấy đối ứng | %d |\n" % len(kh_thay))
        f.write("| Khớp | %d |\n" % (len(d) - len(lech) - len(kh_thay)))
        f.write("| Số mẫu sai khác nhau | %d |\n\n" % len(nhom))
        f.write("## 15 mẫu sai phổ biến nhất\n\n")
        f.write("| # | mẫu | số chỗ | cộng dồn | ví dụ |\n|---|---|---|---|---|\n")
        tich = 0
        for i, (m, ds) in enumerate(xep[:15], 1):
            tich += len(ds)
            x = ds[0]
            f.write("| %d | `%s` | %d | %.0f%% | `%s` → `%s` |\n"
                    % (i, m, len(ds), 100 * tich / len(lech), x["so_cu"][:24], x["so_moi"][:24]))
        f.write("\n**%d mẫu đầu đã chiếm %.0f%% tổng số chỗ lệch.**\n" % (15, 100 * tich / len(lech)))
        f.write("\nXem chi tiết từng nhóm: `nhom_loi.md`. Xem toàn bộ: `doi_chieu_so.csv`.\n")

    print("Đã gom %d chỗ lệch thành %d nhóm mẫu sai." % (len(lech), len(nhom)))
    print("  Đọc trước : %s" % tt)
    print("  Chi tiết  : %s" % md)


if __name__ == "__main__":
    main()
