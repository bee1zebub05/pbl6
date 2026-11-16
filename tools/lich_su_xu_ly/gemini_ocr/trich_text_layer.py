# -*- coding: utf-8 -*-
"""Trich text tu PDF CO SAN TEXT LAYER — khong can OCR, khong ton API.

Nhieu PDF trong bo khong phai ban scan ma la PDF SO (do may tao). Chu trong do la
chu THAT, trich ra la chinh xac tuyet doi. OCR nhung file nay bang model vua cham,
vua co the sai, vua hay bi RECITATION chan (da gap voi 0328).

Ghi ra: data/processed/text_gemma/<cung cay thu muc>.txt  (cung cho voi ban OCR de
dung chung mot quy trinh doi chieu), kem moc '----- [Trang N] -----' tung trang.

    python trich_text_layer.py             # xem truoc
    python trich_text_layer.py --apply     # ghi that
    python trich_text_layer.py --nguong 200   # nguong ky tu/trang de coi la co text layer
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import pymupdf
except ImportError:
    pymupdf = None

GOC = Path(__file__).resolve().parents[2]
SRC = GOC / "data" / "raw"
RA = GOC / "data" / "processed" / "text_gemma"


def duong_dan_dai(p):
    if os.name != "nt":
        return str(p)
    p = os.path.abspath(str(p))
    return p if p.startswith("\\\\?\\") else "\\\\?\\" + p


DAU = ("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ"
       "ùúủũụưừứửữựỳýỷỹỵđ")
DAU += DAU.upper()
NGUONG_DAU = 12.0     # van ban tieng Viet that co 18-23% ky tu co dau


def co_text_layer(pdf, nguong):
    """Co text layer DUNG UNICODE khong?

    CHI dem ky tu la CHUA DU. Nhieu PDF tieng Viet dung font cu (VNI/TCVN3): byte trong
    file khong anh xa sang Unicode chuan, trich ra duoc 'chu' nhung SAI HET DAU —
    'BỘ GIÁO DỤC' thanh 'B GIAO DI)C'. Ban OCR con tot hon han ban trich.
    Da tung ghi de 41 file bang loai text hong nay truoc khi phat hien.
    -> phai kiem TY LE KY TU CO DAU, duoi 12% la font cu, khong dung duoc.
    """
    try:
        with pymupdf.open(pdf) as d:
            n = min(3, d.page_count)
            if not n:
                return False, 0
            t = "".join(d[i].get_text() for i in range(n))
            tb = len(t.strip()) / n
            if tb <= nguong:
                return False, tb
            tl_dau = 100.0 * sum(1 for c in t if c in DAU) / max(1, len(t))
            if tl_dau < NGUONG_DAU:
                return False, tb      # font cu -> coi nhu khong dung duoc
            return True, tb
    except Exception:
        return False, 0


def trich(pdf):
    phan = []
    with pymupdf.open(pdf) as d:
        for i, pg in enumerate(d, 1):
            t = pg.get_text().strip()
            phan.append("----- [Trang %d] -----\n\n%s" % (i, t))
    return "\n\n".join(phan).strip() + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--nguong", type=int, default=200, help="ky tu/trang toi thieu")
    ap.add_argument("--tat-ca", action="store_true",
                    help="quet toan bo data/raw thay vi chi cac file trong ds_nat.json")
    a = ap.parse_args()

    if not pymupdf:
        print("Thiếu pymupdf")
        sys.exit(1)

    if a.tat_ca:
        ds = sorted(SRC.rglob("*.pdf"))
    else:
        import json
        j = json.loads((Path(__file__).resolve().parent / "ds_nat.json").read_text(encoding="utf-8"))
        ds = []
        for x in j:
            p = Path(x["pdf"])
            ds.append(p if p.is_absolute() else GOC / p)

    print("=" * 86)
    print("TRÍCH TEXT LAYER %s" % ("(GHI THẬT)" if a.apply else "(chỉ xem trước)"))
    print("  Xét %d file | ngưỡng %d ký tự/trang" % (len(ds), a.nguong))
    print("  Ghi ra: %s" % RA)
    print("=" * 86)

    n_co = n_ghi = n_bo = n_da_co = 0
    tong_ky_tu = 0
    for pdf in ds:
        if not pdf.exists():
            continue
        ok, tb = co_text_layer(pdf, a.nguong)
        if not ok:
            n_bo += 1
            continue
        n_co += 1
        rel = pdf.relative_to(SRC).with_suffix(".txt")
        dich = RA / rel
        try:
            if dich.stat().st_size > 0:
                n_da_co += 1
                continue
        except OSError:
            pass
        try:
            t = trich(pdf)
        except Exception as e:
            print("  ✖ %s: %s" % (pdf.name[:52], str(e)[:40]))
            continue
        tong_ky_tu += len(t)
        n_ghi += 1
        if n_ghi <= 10:
            print("  ✔ %-56s %2d trang %7d ký tự" % (pdf.name[:56], t.count("[Trang"), len(t)))
        if a.apply:
            os.makedirs(duong_dan_dai(dich.parent), exist_ok=True)
            with open(duong_dan_dai(dich), "w", encoding="utf-8", newline="\n") as f:
                f.write(t)
    if n_ghi > 10:
        print("  … và %d file nữa" % (n_ghi - 10))

    print("-" * 86)
    print("Có text layer: %d | %s: %d | đã có sẵn: %d | không có text layer: %d"
          % (n_co, "đã ghi" if a.apply else "sẽ ghi", n_ghi, n_da_co, n_bo))
    print("Tổng ký tự trích được: %s" % "{:,}".format(tong_ky_tu))
    if not a.apply:
        print("\n>>> Mới là XEM TRƯỚC. Thêm --apply để ghi thật.")


if __name__ == "__main__":
    main()
