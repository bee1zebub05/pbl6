# -*- coding: utf-8 -*-
"""Trich text tu 5 file .doc trong data/raw/doc_new — nguon duy nhat CHUA co ban text.

Gemma chi nhan PDF nen 5 file .doc nay bi bo lai tu dau. Chung la .doc NHI PHAN cu
(OLE2), khong phai .docx (zip) nen khong unzip ra XML duoc. Dung `antiword` — cong cu
doc dinh dang do — voi bang ma UTF-8 de giu dau tieng Viet.

Luu y: antiword khong mo duoc duong dan co ky tu tieng Viet, phai chep sang ten ASCII
trong thu muc tam truoc.

Chu y day KHONG phai OCR: chu trong .doc la chu THAT do may tao, trich ra la chinh xac
tuyet doi — khong co rui ro doc nham ky tu nhu voi ban scan.

    python trich_doc.py            # xem truoc
    python trich_doc.py --apply    # ghi vao text_clean_gemma
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
RAW = GOC / "data" / "raw"
SACH = GOC / "data" / "processed" / "text_clean_gemma"

DAU = ("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ"
       "ùúủũụưừứửữựỳýỷỹỵđ")
DAU += DAU.upper()
NGUONG_DAU = 12.0


def ty_le_dau(t):
    return 100.0 * sum(1 for c in t if c in DAU) / max(1, len(t))


def don(t):
    """Bo khung bang cua antiword, ky tu thay the, chuan hoa khoang trang.

    antiword ve bang bang ky tu '|' va dong '---'. Giu nguyen thi van ban day gach doc,
    vua kho doc vua lam hong viec chia doan khi embedding.
    """
    ra = []
    for d in t.split("\n"):
        if re.fullmatch(r"\s*\|[\s|+-]*\|\s*", d):      # dong ke ngang cua bang
            continue
        if d.lstrip().startswith("|"):
            o = [x.strip() for x in d.strip().strip("|").split("|")]
            o = [x for x in o if x and not re.fullmatch(r"[-=]+", x)]
            d = "    ".join(o)
        ra.append(d)
    t = "\n".join(ra)
    t = t.replace("�", "").replace("\x0c", "\n")
    t = unicodedata.normalize("NFC", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip() + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    ds = sorted(p for p in RAW.rglob("*") if p.suffix.lower() in (".doc", ".docx"))
    if not ds:
        print("Không thấy file .doc nào.")
        return

    tam = Path(tempfile.mkdtemp(prefix="doc_"))
    print("=" * 88)
    print("TRÍCH TEXT TỪ FILE .doc  %s" % ("(GHI THẬT)" if a.apply else "(chỉ xem trước)"))
    print("=" * 88)

    n_ok = 0
    for f in ds:
        doc_id = f.name[:4]
        # antiword khong mo duoc duong dan co dau tieng Viet -> chep sang ten ASCII
        tmp = tam / (doc_id + ".doc")
        shutil.copy2(f, tmp)
        try:
            r = subprocess.run(["antiword", "-m", "UTF-8.txt", str(tmp)],
                               capture_output=True, timeout=120)
            t = r.stdout.decode("utf-8", errors="replace")
        except Exception as e:
            print("  ✖ %s: %s" % (doc_id, str(e)[:60]))
            continue

        t = don(t)
        tl = ty_le_dau(t)
        chu = sum(1 for c in t if c.isalpha())
        # cung cong kiem dinh nhu ban OCR: dau duoi 12% la ban hong/font cu
        if len(t) < 400 or tl < NGUONG_DAU:
            print("  ✖ %s  loại: %d ký tự, dấu %.1f%%" % (doc_id, len(t), tl))
            continue

        # cay thu muc ban sach bo cap 'pdf/' va 'doc_new/' — chi giu ten linh vuc
        dich = SACH / f.parent.name / (f.stem + ".txt")
        n_ok += 1
        print("  ✔ %s  %7s ký tự | %6s chữ | dấu %.1f%%  →  %s/"
              % (doc_id, "{:,}".format(len(t)), "{:,}".format(chu), tl, f.parent.name))
        if a.apply:
            dich.parent.mkdir(parents=True, exist_ok=True)
            dich.write_text(t, encoding="utf-8", newline="\n")

    shutil.rmtree(tam, ignore_errors=True)
    print("-" * 88)
    print("Trích được %d / %d file." % (n_ok, len(ds)))
    if not a.apply:
        print("\n>>> Mới là XEM TRƯỚC. Thêm --apply để ghi thật.")


if __name__ == "__main__":
    main()
