"""Danh gia chat luong ket qua OCR trong clean_data so voi PDF goc trong raw.

Khong co "dap an" (PDF la ban scan) nen script do cac dau hieu HONG co the phat hien
mot cach may moc:
  - con dinh MA NGUON  (text_content = \"\"\", import, with open...)
  - CUT NGANG          (khong ket thuc bang dau cau / thieu phan ky ten cuoi van ban)
  - THIEU TRANG        (so ky tu / so trang PDF qua thap so voi mat bang chung)
  - LOI PHAT SINH      (chuoi [[TRANG n KHONG OCR DUOC]])
  - TRUNG LAP          (mot doan dai lap lai nhieu lan - dau hieu model bi ket)

Chay:
    python danh_gia_clean.py                        # ca cay
    python danh_gia_clean.py --only "pdf/Khac"      # 1 thu muc
"""
import argparse
import os
import re
import sys
from pathlib import Path

try:
    import pymupdf
except ImportError:
    pymupdf = None

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

MA_NGUON_RE = re.compile(
    r'text_content\s*=|with\s+open\(|^\s*import\s|^\s*from\s+\w+\s+import|print\(f?"', re.M)
KET_THUC_RE = re.compile(r'[.。;:/\)\]"\'”]\s*$|\./\.\s*$')
# Ket van ban hanh chinh VN thuong co mot trong nhung cum nay
DUOI_VAN_BAN_RE = re.compile(
    r'nơi nhận|TM\.|KT\.|THỦ TƯỚNG|BỘ TRƯỞNG|CHỦ TỊCH|GIÁM ĐỐC|HIỆU TRƯỞNG|đã ký', re.I)


def so_trang(pdf: Path):
    if not pymupdf:
        return None
    try:
        with pymupdf.open(pdf) as d:
            return d.page_count
    except Exception:
        return None


def doan_lap(text, n=200):
    """Doan n ky tu xuat hien nhieu lan -> model bi ket lap.

    BO QUA duong ke bang ASCII (+---+---+) va khoang trang: tai lieu nhieu bang thi
    nhung dong do lap la BINH THUONG, tinh vao se bao dong gia (da gap 1 lan).
    """
    sach = re.sub(r"[-+=_|\s]", "", text)
    if len(sach) < n * 4:
        return 0
    mau = {}
    for i in range(0, len(sach) - n, n):
        k = sach[i:i + n]
        mau[k] = mau.get(k, 0) + 1
    return max(mau.values()) if mau else 0


def ket_hop_ly(duoi):
    """Duoi van ban co ve tron ven khong?

    Van ban hanh chinh thuong ket bang dau cau, phan ky ten, HOAC mot dong bang/danh
    sach (khong co dau cau cuoi). Chi coi la cut khi dong cuoi dut giua chung mot tu.
    """
    d = duoi.rstrip()
    if not d:
        return False
    if KET_THUC_RE.search(d) or DUOI_VAN_BAN_RE.search(d):
        return True
    cuoi = d.split("\n")[-1].strip()
    # dong bang (co dau |) hoac muc danh sach -> ket thuc kieu nay la binh thuong
    if "|" in cuoi or re.match(r"^[-*+•]|^\d+[.)]|^[A-ZĐ]{2,}", cuoi):
        return True
    # dut giua tu: ky tu cuoi la chu va dong qua ngan so voi be rong thuong gap
    return len(cuoi) < 40


def main():
    here = Path(__file__).resolve().parent
    root = here.parents[1]

    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(root / "data" / "raw"))
    ap.add_argument("--out", default=str(root / "data" / "clean_data"))
    ap.add_argument("--only", default="")
    a = ap.parse_args()

    src, out = Path(a.src), Path(a.out)
    only = a.only.replace("\\", "/").strip("/")

    hang, tong_loi = [], 0
    for pdf in sorted(src.rglob("*")):
        if pdf.suffix.lower() not in (".pdf", ".doc", ".docx"):
            continue
        rel = pdf.relative_to(src).as_posix()
        if only and not rel.startswith(only):
            continue
        txt = out / Path(rel).with_suffix(".txt")

        trang = so_trang(pdf) if pdf.suffix.lower() == ".pdf" else None
        if not txt.exists():
            hang.append((rel, trang, 0, 0, ["CHUA CO FILE"]))
            tong_loi += 1
            continue

        t = txt.read_text(encoding="utf-8", errors="replace")
        loi = []
        if MA_NGUON_RE.search(t):
            loi.append("CON MA NGUON")
        if "[[TRANG" in t:
            loi.append("THIEU TRANG (bao loi)")
        if len(t.strip()) < 200:
            loi.append("QUA NGAN")
        if not ket_hop_ly(t.strip()[-400:]):
            loi.append("NGHI CUT NGANG")
        lap = doan_lap(t)
        if lap >= 3:
            loi.append("LAP DOAN x%d" % lap)
        # nguong dat sau, khi da biet trung vi cua ca bo

        tong_loi += bool(loi)
        hang.append((rel, trang, len(t), round(len(t) / trang) if trang else 0, loi))

    if not hang:
        print("Khong co file nao khop bo loc.")
        return

    # So voi TRUNG VI cua chinh bo du lieu nay - dang tin hon nguong cung, vi mat do
    # chu/trang khac nhau theo loai tai lieu. Day la tin hieu bat duoc MAT NOI DUNG.
    mat_do = [tb for _r, tr, _n, tb, _l in hang if tr and tr >= 3 and tb]
    trung_vi = sorted(mat_do)[len(mat_do) // 2] if mat_do else 0
    if trung_vi:
        nguong = trung_vi * 0.6
        for i, (rel, tr, n, tb, loi) in enumerate(hang):
            if tr and tr >= 3 and tb and tb < nguong:
                loi.append("MAT NOI DUNG? %.0f chu/trang, trung vi %d" % (tb, trung_vi))
                hang[i] = (rel, tr, n, tb, loi)

    print("=" * 100)
    print("%-52s %6s %8s %8s  %s" % ("FILE", "TRANG", "KY TU", "CHU/TR", "CANH BAO"))
    print("-" * 100)
    for rel, trang, n, tb, loi in hang:
        ten = rel if len(rel) <= 50 else "..." + rel[-47:]
        print("%-52s %6s %8d %8s  %s"
              % (ten, trang if trang else "-", n, tb if tb else "-",
                 ", ".join(loi) if loi else "OK"))
    print("-" * 100)
    tot = len(hang) - tong_loi
    print("Tong: %d file | dat: %d | co canh bao: %d" % (len(hang), tot, tong_loi))
    print("=" * 100)


if __name__ == "__main__":
    main()
