# -*- coding: utf-8 -*-
"""Soi RAC trong kho cuoi truoc khi dung do thi.

Khong chi markdown. Lan nay soi ca nhung loai rac da gap rai rac trong phien:

  1. Loi dan / nhai lenh cua model
  2. Markdown con sot (**, ###, <br>, ``` )
  3. WATERMARK cua trang luat — 'THƯ VIỆN PHÁP LUẬT', 'LawSoft', so dien thoai,
     ma so 8 chu so. Loai nay nguy vi no chen GIUA CAU, khong phai o le trang.
  4. Mojibake / ky tu dieu khien
  5. Khoi LAP LAI — model doi khi xuat lai nguyen mot doan
  6. Chuoi ky tu vo nghia dai (rac OCR nang)
  7. Dong chi toan dau cham / gach

    python scripts/soi_rac.py
    python scripts/soi_rac.py --nguon data/clean/text_clean_gemma
"""
import argparse
import io
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
KHO = ROOT / "data" / "clean" / "text_final"

MAU = [
    ("lời dẫn model",
     re.compile(r"chào\s+bạn|bạn\s+cung\s+cấp|đã\s+được\s+OCR|dạng\s+plaintext", re.I)),
    ("nhại lại câu lệnh",
     re.compile(r"ĐỌC VÀ CHUYỂN ĐỔI TOÀN BỘ", re.I)),
    ("markdown đậm/nghiêng", re.compile(r"\*\*|(?<!\*)\*[^\s*][^*\n]{0,60}\*(?!\*)")),
    ("tiêu đề markdown", re.compile(r"^#{1,6}\s", re.M)),
    ("thẻ HTML", re.compile(r"<(?:br|p|div|span|b|i|u)\b[^>]{0,20}>", re.I)),
    ("rào code", re.compile("`" * 3)),
    ("lỗ chưa OCR", re.compile(r"\[\[KHÔNG OCR ĐƯỢC")),
    # Watermark trang luat — chen giua cau, rat hai
    ("watermark ThuVienPhapLuat",
     re.compile(r"ThuVienPhapLuat|THƯ VIỆN PHÁP LUẬT|LawSoft|LAWSOFT", re.I)),
    ("số điện thoại watermark", re.compile(r"\+?84[\s-]?\d{2}[\s-]?\d{4}[\s-]?\d{4}")),
    ("mã số watermark", re.compile(r"(?<!\d)09\d{6}(?!\d)")),
    ("ký tự điều khiển", re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")),
    ("dòng chỉ dấu chấm/gạch", re.compile(r"^[\s.·•_\-–—]{8,}$", re.M)),
    ("chuỗi lặp một ký tự", re.compile(r"(.)\1{14,}")),
]

# Chu Cyrillic / Han tu lan vao — da tung gap (ten ky thi tieng Nga)
LA = re.compile(r"[Ѐ-ӿ一-鿿]")


def khoi_lap(t, dai=220):
    """Co doan >= `dai` ky tu xuat hien hai lan lien tiep khong?"""
    s = re.sub(r"\s+", " ", t)
    n = len(s)
    for i in range(0, n - 2 * dai, dai):
        a = s[i:i + dai]
        if s.find(a, i + dai, i + dai * 3) != -1:
            return a[:70]
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chi-tiet", action="store_true")
    ap.add_argument("--nguon", default=None)
    a = ap.parse_args()

    global KHO
    if a.nguon:
        p = Path(a.nguon)
        KHO = p if p.is_absolute() else ROOT / p

    fs = sorted(KHO.rglob("*.txt"))
    dem = Counter()
    file_dinh = Counter()
    vi_du = {}
    lap = []
    la_chu = []

    for f in fs:
        t = io.open(f, encoding="utf-8", errors="replace").read()

        for ten, bt in MAU:
            v = bt.findall(t)
            if v:
                dem[ten] += len(v)
                file_dinh[ten] += 1
                if ten not in vi_du:
                    m = bt.search(t)
                    vi_du[ten] = (f.name[:4],
                                  re.sub(r"\s+", " ", t[max(0, m.start() - 45):
                                                        m.start() + 55]))

        k = khoi_lap(t)
        if k:
            lap.append((f.name[:4], k))

        v = LA.findall(t)
        if len(v) > 3:
            la_chu.append((f.name[:4], len(v), "".join(v[:14])))

    print("=" * 88)
    print("SOI RÁC TOÀN DIỆN — %s (%d văn bản)" % (KHO.name, len(fs)))
    print("=" * 88)

    if not dem and not lap and not la_chu:
        print("  ✔ Không phát hiện loại rác nào.")
    else:
        print("%-32s %8s %8s   %s" % ("loại", "số file", "số lần", "ví dụ"))
        print("-" * 88)
        for ten, n in dem.most_common():
            d, vd = vi_du[ten]
            print("%-32s %8d %8d   [%s] %s"
                  % (ten, file_dinh[ten], n, d, vd[:40]))

    if lap:
        print("-" * 88)
        print("  Khối lặp lại (model xuất trùng đoạn): %d file" % len(lap))
        for d, k in lap[:5]:
            print("     %s  %s" % (d, k))

    if la_chu:
        print("-" * 88)
        print("  Chữ Cyrillic / Hán lẫn vào: %d file" % len(la_chu))
        for d, n, s in la_chu[:5]:
            print("     %s  %d ký tự  %s" % (d, n, s))

    sach = len(fs) - len({d for _t, (d, _v) in vi_du.items()})
    print("=" * 88)
    tong_file_dinh = len({f.name[:4] for f in fs
                          if any(bt.search(io.open(f, encoding="utf-8",
                                                   errors="replace").read())
                                 for _t, bt in MAU)})
    print("  File có ít nhất một loại rác : %d / %d" % (tong_file_dinh, len(fs)))
    print("  File sạch                    : %d / %d"
          % (len(fs) - tong_file_dinh, len(fs)))


if __name__ == "__main__":
    main()
