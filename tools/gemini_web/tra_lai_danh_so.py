# -*- coding: utf-8 -*-
"""Tra lai tien to danh so cho ban VOT tu markdown.

Ban vot lay bang innerText nen marker cua <ol><li> ("1." "2."...) khong nam
trong text -> mat. Chu "a)" "d)" thi con vi chung la chu that trong <li>.

Cach lam: dong bo tung dong giua BAN GOC va BAN VOT. Dong nao ban goc co tien
to ma ban vot khong co, VA phan chu con lai khop nhau, thi gan lai tien to DO
CHINH BAN GOC. Khong bia ra so nao, khong sua chu.

    python tra_lai_danh_so.py <ma>            # chi bao cao, khong ghi
    python tra_lai_danh_so.py <ma> --ghi      # ghi that
"""
import argparse, csv, difflib, io, json, re, sys, unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# tools/gemini_web/ -> len 2 cap la goc repo
GOC_DIR = Path(__file__).resolve().parents[2]
CSV_FILE = GOC_DIR / "data" / "kiem_tra" / "can_sua.csv"
TRANG_THAI = Path(__file__).resolve().parent / "trang_thai_sua_txt.json"

TIEN_TO = re.compile(r"^(\s*)(\d{1,3}\.\s)")   # "  12. "


def bo_dau(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def khoa(dong):
    """Khoa so sanh: bo tien to danh so, bo dau, bo khoang trang."""
    return bo_dau(TIEN_TO.sub("", dong))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ma")
    ap.add_argument("--ghi", action="store_true", help="ghi de len ban vot")
    a = ap.parse_args()

    hang = {}
    with io.open(CSV_FILE, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            hang[r["ma"]] = r
    if a.ma not in hang:
        sys.exit("khong co ma %s trong CSV" % a.ma)

    tt = json.loads(TRANG_THAI.read_text(encoding="utf-8"))
    if a.ma not in tt["xong"]:
        sys.exit("ma %s chua xong" % a.ma)
    duong_dan_vot = Path(tt["xong"][a.ma]["duong_dan"])

    goc = io.open(hang[a.ma]["duong_dan_txt"], encoding="utf-8").read().split("\n")
    vot = io.open(duong_dan_vot, encoding="utf-8").read().split("\n")

    kg = [khoa(x) for x in goc]
    kv = [khoa(x) for x in vot]

    sm = difflib.SequenceMatcher(None, kg, kv, autojunk=False)
    ra = list(vot)
    da_tra = 0
    khong_khop = []

    for th, i1, i2, j1, j2 in sm.get_opcodes():
        if th != "equal":
            continue
        for k in range(i2 - i1):
            dg, dv = goc[i1 + k], vot[j1 + k]
            m = TIEN_TO.match(dg)
            if not m:
                continue                      # ban goc khong co tien to
            if TIEN_TO.match(dv):
                continue                      # ban vot van con tien to
            if not khoa(dg):
                continue                      # dong rong, bo qua
            ra[j1 + k] = m.group(1) + m.group(2) + dv.lstrip()
            da_tra += 1

    # Con sot: dong nao ban goc co tien to ma khong dong bo duoc
    co_tien_to = sum(1 for x in goc if TIEN_TO.match(x) and khoa(x))
    con_lai = sum(1 for x in ra if TIEN_TO.match(x) and khoa(x))

    print("%s" % a.ma)
    print("  ban goc co tien to danh so : %d dong" % co_tien_to)
    print("  ban vot truoc khi sua      : %d dong"
          % sum(1 for x in vot if TIEN_TO.match(x) and khoa(x)))
    print("  da tra lai                 : %d dong" % da_tra)
    print("  ban vot sau khi sua        : %d dong" % con_lai)
    print("  con thieu                  : %d dong" % (co_tien_to - con_lai))

    if a.ghi:
        sao = duong_dan_vot.with_suffix(".txt.truoc_khi_tra_so")
        if not sao.exists():
            sao.write_text("\n".join(vot), encoding="utf-8", newline="")
        duong_dan_vot.write_text("\n".join(ra), encoding="utf-8", newline="")
        print("  -> da ghi. Ban truoc khi sua: %s" % sao.name)
    else:
        print("  (chi bao cao — them --ghi de ghi that)")


if __name__ == "__main__":
    main()
