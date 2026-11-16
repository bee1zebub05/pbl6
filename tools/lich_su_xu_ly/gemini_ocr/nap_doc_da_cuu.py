# -*- coding: utf-8 -*-
"""Don va nap 5 van ban .doc da cuu duoc vao text_clean_gemma.

Duong di cua 5 file nay:
  data/raw/doc_new/**/*.doc  ->  bi CUT CUT 122-124 byte o cuoi (tai ve do dang)
                             ->  dem 0 cho tron sector (tren BAN SAO, khong dung file goc)
                             ->  Word COM doc ra text
                             ->  script nay don rac va ghi vao ban sach

Day KHONG phai OCR: chu trong .doc la chu THAT do may tao, khong co rui ro doc nham.

    python nap_doc_da_cuu.py            # xem truoc
    python nap_doc_da_cuu.py --apply    # ghi that
"""
import argparse
import io
import os
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
RAW = GOC / "data" / "raw"
SACH = GOC / "data" / "processed" / "text_clean_gemma"
TAM = Path(os.environ.get("TEMP", "/tmp")) / "claude"

DAU = ("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ"
       "ùúủũụưừứửữựỳýỷỹỵđ")
DAU += DAU.upper()
NGUONG_DAU = 12.0


def ty_le_dau(t):
    return 100.0 * sum(1 for c in t if c in DAU) / max(1, len(t))


def don(t):
    """Don rac dac trung cua text lay tu Word COM.

    - \\x07 la dau ket o / ket dong cua BANG trong Word -> tach thanh dong rieng, neu
      khong thi cac o bang dinh lien nhau thanh mot khoi chu vo nghia.
    - 'Ð' (U+00D0, chu Eth cua tieng Iceland) hay bi dung nham cho 'Đ' (U+0110) trong
      van ban tieng Viet cu. Hai ky tu NHIN GIONG HET nhau nhung khac ma -> tim kiem
      va so khop se truot. Doi het ve U+0110.
    - \\x0c la dau sang trang.
    """
    t = t.replace("Ð", "Đ").replace("ð", "đ")
    t = t.replace("\x07", "\n").replace("\x0b", "\n").replace("\x0c", "\n")
    t = re.sub(r"[\x00-\x08\x0e-\x1f]", "", t)
    t = unicodedata.normalize("NFC", t)
    t = re.sub(r"^[\s\-–—=_.]{3,}$", "", t, flags=re.M)   # dong ke ngang trang tri
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n[ \t]+", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip() + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--nguon", action="append", default=None,
                    help="thư mục chứa .txt đã trích (lặp lại được)")
    a = ap.parse_args()

    nguon = [Path(x) for x in (a.nguon or [])]
    if not nguon:
        p = TAM / "f--DUT4-PBL6" / "2f904124-08db-406b-a197-fa1eb45bd494" / "scratchpad"
        nguon = [p / "doc2_txt", p / "doc3_txt"]

    # doc_id -> duong dan .doc goc, de biet ghi vao thu muc linh vuc nao
    goc = {}
    for f in RAW.rglob("*"):
        if f.suffix.lower() in (".doc", ".docx"):
            goc[f.name[:4]] = f

    print("=" * 90)
    print("NẠP VĂN BẢN .doc ĐÃ CỨU  %s" % ("(GHI THẬT)" if a.apply else "(chỉ xem trước)"))
    print("=" * 90)

    n = 0
    for d in nguon:
        if not d.exists():
            continue
        for f in sorted(d.glob("*.txt")):
            doc_id = f.stem[:4]
            src = goc.get(doc_id)
            if not src:
                print("  ✖ %s: không thấy file .doc gốc" % doc_id)
                continue
            t = don(io.open(f, encoding="utf-8", errors="replace").read())
            tl = ty_le_dau(t)
            chu = sum(1 for c in t if c.isalpha())
            if len(t) < 400 or tl < NGUONG_DAU:
                print("  ✖ %s loại: %d ký tự, dấu %.1f%%" % (doc_id, len(t), tl))
                continue
            dich = SACH / src.parent.name / (src.stem + ".txt")
            n += 1
            print("  ✔ %s | %8s ký tự | %6s chữ | dấu %4.1f%% | %s"
                  % (doc_id, "{:,}".format(len(t)), "{:,}".format(chu), tl,
                     src.parent.name))
            print("       → %s" % dich.relative_to(GOC).as_posix()[:96])
            if a.apply:
                dich.parent.mkdir(parents=True, exist_ok=True)
                dich.write_text(t, encoding="utf-8", newline="\n")

    print("-" * 90)
    print("Nạp %d văn bản." % n)
    if not a.apply:
        print("\n>>> Mới là XEM TRƯỚC. Thêm --apply để ghi thật.")


if __name__ == "__main__":
    main()
