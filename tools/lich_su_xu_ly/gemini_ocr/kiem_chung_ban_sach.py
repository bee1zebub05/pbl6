# -*- coding: utf-8 -*-
"""Kiem chung va cham chat luong text_clean_gemma.

Bon lop kiem tra, tu chac chan nhat den suy doan:
  1. DOI CHIEU SU THAT DA XAC MINH — nhung cho da mo PDF goc/hoi model xac nhan trong
     phien lam viec. Day la kiem tra dang tin nhat vi co dap an.
  2. DO PHU — du 455 tai lieu? co file rong? co cho danh dau thieu?
  3. CHI SO NGON NGU — ty le ky tu co dau, mat do chu/trang so voi so trang PDF that
  4. SO DANG NGO — dung bo luat cua soi_so.py

    python kiem_chung_ban_sach.py
    python kiem_chung_ban_sach.py --chi-tiet
"""
import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from soi_so import quet_file                    # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import pymupdf
except ImportError:
    pymupdf = None

GOC = Path(__file__).resolve().parents[2]
SACH = GOC / "data" / "processed" / "text_clean_gemma"
RAW_PDF = GOC / "data" / "raw"
RAW_TXT = GOC / "data" / "processed" / "text_raw"

DAU = ("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ"
       "ùúủũụưừứửữựỳýỷỹỵđ")
DAU += DAU.upper()

# Nhung SU THAT da xac minh trong phien: mo PDF goc, hoi model, hoac nguoi dung xac nhan
SU_THAT = [
    ("0019", "05/NQ-HĐT", "số hiệu — Gemma đọc trang 1 PDF gốc xác nhận"),
    ("0436", "1974/QĐ-ĐHĐN", "số hiệu — người dùng xác nhận"),
    ("0436", "ngày 27", "ngày ban hành — người dùng xác nhận 27/5/2025"),
    ("0082", "2347", "số hiệu — bản OCR xác minh"),
    ("0082", "ngày 14 tháng 11 năm 2018", "ngày — sửa từ 'ngày A4 tháng 11'"),
    ("0004", "33/2020/QĐ-TTg", "sửa từ 33/2020/Q4-TTg"),
    ("0009", "44/2007/QĐ-BGDĐT", "sửa từ 44/2007/0Đ-BGDĐT"),
    ("0263", "08/NQ-HĐĐH", "sửa từ 08/NO-HĐĐH"),
    ("0265", "05/NQ-HĐT", "sửa từ 05/NQ-HDT"),
    ("0216", "31/2011/NĐ-CP", "sửa từ 31/201 1/ND CP"),
    ("0415", "13/NQ-HĐĐH", "sửa từ 1 3/NQ-HDDH"),
    ("0330", "29/2023/TT-BGDĐT", "sửa từ 39/2023/TT-BGDĐT2023"),
]


def ty_le_dau(t):
    return 100.0 * sum(1 for c in t if c in DAU) / max(1, len(t))


def so_chu_cai(t):
    return sum(1 for c in t if c.isalpha())


def bo_moc(t):
    return re.sub(r"-{3,}\s*\[Trang \d+\]\s*-{3,}", "", t)


def tim(doc):
    return next((p for p in SACH.rglob(doc + "_*.txt")), None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chi-tiet", action="store_true")
    a = ap.parse_args()

    if not SACH.exists():
        print("Chưa có %s" % SACH)
        sys.exit(1)

    fs = sorted(p for p in SACH.rglob("*.txt"))
    print("=" * 88)
    print("KIỂM CHỨNG text_clean_gemma")
    print("=" * 88)

    # ── 1. Doi chieu su that da xac minh ──
    print("① ĐỐI CHIẾU VỚI SỰ THẬT ĐÃ XÁC MINH  (có đáp án — đáng tin nhất)")
    print("-" * 88)
    dat = 0
    for doc, chuoi, vi_sao in SU_THAT:
        f = tim(doc)
        if not f:
            print("   ✖ %s  không thấy file" % doc)
            continue
        t = f.read_text(encoding="utf-8", errors="replace")
        ok = chuoi in t
        dat += ok
        print("   %s %s  %-26s %s" % ("✔" if ok else "✖", doc, chuoi[:26], vi_sao[:36]))
    print("   → %d/%d đúng" % (dat, len(SU_THAT)))

    # ── 2. Do phu ──
    print()
    print("② ĐỘ PHỦ")
    print("-" * 88)
    n_pdf = len([p for p in RAW_PDF.rglob("*.pdf")])
    rong = [f for f in fs if f.stat().st_size < 200]
    thieu = [f for f in fs if "KHÔNG OCR ĐƯỢC" in f.read_text(encoding="utf-8", errors="replace")]
    print("   File trong bản sạch      : %d" % len(fs))
    print("   File PDF trong data/raw  : %d" % n_pdf)
    print("   File rỗng / quá ngắn     : %d" % len(rong))
    print("   File có chỗ đánh dấu thiếu: %d" % len(thieu))
    for f in thieu[:5]:
        print("      · %s" % f.name[:66])

    # ── 3. Chi so ngon ngu ──
    print()
    print("③ CHỈ SỐ NGÔN NGỮ")
    print("-" * 88)
    tls, matdo = [], []
    thap = []
    for f in fs:
        t = bo_moc(f.read_text(encoding="utf-8", errors="replace"))
        tl = ty_le_dau(t)
        tls.append(tl)
        if tl < 15:
            thap.append((f.name, tl))
        if pymupdf:
            m = re.match(r"(\d{4})_", f.name)
            pdf = next((p for p in RAW_PDF.rglob(m.group(1) + "_*.pdf")), None) if m else None
            if pdf:
                try:
                    with pymupdf.open(pdf) as d:
                        n = d.page_count
                    if n >= 3:
                        matdo.append(so_chu_cai(t) / n)
                except Exception:
                    pass
    tls.sort()
    print("   Tỉ lệ ký tự có dấu : trung vị %.1f%% | thấp nhất %.1f%% | cao nhất %.1f%%"
          % (tls[len(tls) // 2], tls[0], tls[-1]))
    print("      (văn bản tiếng Việt thật: 18–23%. Windows OCR hỏng dấu chỉ đạt 1,3%)")
    print("   File có tỉ lệ dấu < 15%% : %d" % len(thap))
    for ten, tl in sorted(thap, key=lambda x: x[1])[:5]:
        print("      · %.1f%%  %s" % (tl, ten[:60]))
    if matdo:
        matdo.sort()
        tv = matdo[len(matdo) // 2]
        print("   Mật độ chữ cái/trang : trung vị %.0f | thấp nhất %.0f" % (tv, matdo[0]))
        print("   File dưới 50%% trung vị : %d" % sum(1 for x in matdo if x < tv * 0.5))

    # ── 4. So dang ngo ──
    print()
    print("④ SỐ ĐÁNG NGỜ  (dùng đúng bộ luật đã dò text_raw lúc đầu)")
    print("-" * 88)
    tong_ngo = 0
    ngo_theo_file = []
    for f in fs:
        n = len(quet_file(f))
        tong_ngo += n
        if n:
            ngo_theo_file.append((f.name, n))
    print("   Tổng chỗ đáng ngờ còn lại : %d" % tong_ngo)
    print("   Số file có chỗ đáng ngờ   : %d / %d" % (len(ngo_theo_file), len(fs)))
    if a.chi_tiet:
        for ten, n in sorted(ngo_theo_file, key=lambda x: -x[1])[:10]:
            print("      %3d chỗ  %s" % (n, ten[:64]))

    # so voi text_raw luc dau
    ngo_cu = 0
    for f in RAW_TXT.rglob("*.txt"):
        if not f.name.endswith(".bak"):
            ngo_cu += len(quet_file(f))
    print("   So với text_raw hiện tại  : %d → %d  (%+.0f%%)"
          % (ngo_cu, tong_ngo, 100.0 * (tong_ngo - ngo_cu) / max(1, ngo_cu)))
    print("=" * 88)


if __name__ == "__main__":
    main()
