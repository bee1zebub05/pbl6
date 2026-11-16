# -*- coding: utf-8 -*-
"""Doi chieu text_raw voi text_gemma, BU TRU cho nhau — tap trung vao SO va NGAY THANG.

Hai ban OCR doc lap, moi ban manh yeu khac nhau:
  - text_raw   : OCR cu, hay sai ky tu giong nhau (Đ->4, Q->0), nhung bo qua dong cham
  - text_gemma : Gemma doc, dung dau tot hon, nhung co file bi bom day dau cham (0269)

Y tuong: cai gi CA HAI BEN GIONG NHAU thi gan nhu chac dung. Cho nao LECH thi dung
LUAT HOP LE de phan xu (ngay 1-31, thang 1-12, nam 1900-2100, so hieu phai co phan so).

Do do DAY DU bang SO CHU CAI, khong phai tong ky tu — vi dau cham lam phinh gia.

    python bu_tru_hai_ban.py               # bao cao tong hop
    python bu_tru_hai_ban.py --chi-tiet    # in tung cho lech
"""
import argparse
import csv
import difflib
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from soi_so import kiem_ngay, kiem_so_hieu           # noqa: E402
from xac_minh_so import TOKEN, bo_dau_cau, chuan, loai_token   # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
CU = GOC / "data" / "processed" / "text_raw"
MOI = GOC / "data" / "processed" / "text_gemma"
RA = GOC / "data" / "doi_chieu_so" / "bu_tru"

DAU = ("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ"
       "ùúủũụưừứửữựỳýỷỹỵđ")
DAU += DAU.upper()

NGAY_RE = re.compile(r"ngày\s+(\S{1,4})\s+tháng\s+(\S{1,4})\s+năm\s+(\S{1,6})", re.I)
SO_RE = re.compile(r"^\d{1,5}\s*/")


def bo_moc(t):
    return re.sub(r"-{3,}\s*\[Trang \d+\]\s*-{3,}", "", t)


def so_chu_cai(t):
    return sum(1 for c in t if c.isalpha())


def ty_le_dau(t):
    return 100.0 * sum(1 for c in t if c in DAU) / max(1, len(t))


def hop_le(tok):
    """Token nay co hop le khong? -> (hop_le, ly_do)"""
    m = NGAY_RE.search(tok)
    if m:
        ld = kiem_ngay(m)
        return (ld is None), (ld or "")
    if SO_RE.match(bo_dau_cau(tok)):
        class G:
            def __init__(s, v): s.v = v
            def group(s, _i): return s.v
        ld = kiem_so_hieu(G(bo_dau_cau(tok)))
        return (ld is None), (ld or "")
    return True, ""


def rut_token(t):
    """-> danh sach token da chuan hoa, giu thu tu, bo trung"""
    ra, thay = [], set()
    for x in TOKEN.findall(t):
        x = chuan(x)
        k = bo_dau_cau(x).lower().replace(" ", "")
        if k and k not in thay:
            thay.add(k)
            ra.append(x)
    return ra


def ghep(toks_a, toks_b):
    """Ghep token hai ben: cung loai + giong nhat. -> [(a, b)] voi a hoac b co the None."""
    con_b = list(toks_b)
    cap = []
    for a in toks_a:
        la = loai_token(a)
        uv = sorted(((difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio(), b)
                     for b in con_b if loai_token(b) == la), reverse=True)
        if uv and uv[0][0] >= 0.6:
            cap.append((a, uv[0][1]))
            con_b.remove(uv[0][1])
        else:
            cap.append((a, None))
    for b in con_b:
        cap.append((None, b))
    return cap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chi-tiet", action="store_true")
    a = ap.parse_args()

    cap_file = []
    for fm in sorted(MOI.rglob("*.txt")):
        m = re.match(r"(\d{4})_", fm.name)
        if not m:
            continue
        fc = next((p for p in CU.rglob(m.group(1) + "_*.txt")), None)
        if fc:
            cap_file.append((m.group(1), fc, fm))
    if not cap_file:
        print("Chưa có cặp nào.")
        return

    tong = Counter()
    hang = []
    day_du = {"raw": 0, "gemma": 0, "hoa": 0}

    for doc, fc, fm in cap_file:
        tc = bo_moc(fc.read_text(encoding="utf-8", errors="replace"))
        tm = bo_moc(fm.read_text(encoding="utf-8", errors="replace"))
        cc, cm = so_chu_cai(tc), so_chu_cai(tm)
        if cm > cc * 1.03:
            day_du["gemma"] += 1
        elif cc > cm * 1.03:
            day_du["raw"] += 1
        else:
            day_du["hoa"] += 1

        for x, y in ghep(rut_token(tc), rut_token(tm)):
            if x and y:
                if bo_dau_cau(x).lower().replace(" ", "") == bo_dau_cau(y).lower().replace(" ", ""):
                    tong["khớp"] += 1
                    continue
                hx, lx = hop_le(x)
                hy, ly = hop_le(y)
                if hy and not hx:
                    kl, chon = "gemma đúng", y
                elif hx and not hy:
                    kl, chon = "raw đúng", x
                else:
                    kl, chon = "chưa phân xử", ""
                tong[kl] += 1
                hang.append({"doc": doc, "raw": x, "gemma": y, "ket_luan": kl,
                             "chon": chon, "loi_raw": lx, "loi_gemma": ly})
            elif x:
                tong["chỉ có ở raw"] += 1
                hang.append({"doc": doc, "raw": x, "gemma": "", "ket_luan": "chỉ có ở raw",
                             "chon": x, "loi_raw": hop_le(x)[1], "loi_gemma": ""})
            else:
                tong["chỉ có ở gemma"] += 1
                hang.append({"doc": doc, "raw": "", "gemma": y, "ket_luan": "chỉ có ở gemma",
                             "chon": y, "loi_raw": "", "loi_gemma": hop_le(y)[1]})

    n = sum(tong.values())
    print("=" * 88)
    print("BÙ TRỪ text_raw ↔ text_gemma — %d tài liệu, %d token số" % (len(cap_file), n))
    print("=" * 88)
    print("  BẢN NÀO ĐẦY ĐỦ HƠN (đo bằng SỐ CHỮ CÁI, không tính dấu chấm/ký hiệu)")
    print("     text_gemma đầy hơn : %3d tài liệu" % day_du["gemma"])
    print("     text_raw   đầy hơn : %3d tài liệu" % day_du["raw"])
    print("     xấp xỉ nhau        : %3d tài liệu" % day_du["hoa"])
    print("-" * 88)
    print("  ĐỐI CHIẾU TỪNG SỐ")
    for k in ("khớp", "gemma đúng", "raw đúng", "chưa phân xử",
              "chỉ có ở gemma", "chỉ có ở raw"):
        if tong[k]:
            print("     %-18s %5d  (%.1f%%)" % (k, tong[k], 100.0 * tong[k] / n))
    print("-" * 88)
    print("  'khớp' = hai bản OCR ĐỘC LẬP cho cùng kết quả → gần như chắc đúng")
    print("=" * 88)

    RA.mkdir(parents=True, exist_ok=True)
    p = RA / "bu_tru.csv"
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["doc", "raw", "gemma", "ket_luan", "chon",
                                          "loi_raw", "loi_gemma"])
        w.writeheader()
        w.writerows(hang)
    print("Bảng chi tiết: %s  (%d dòng)" % (p, len(hang)))

    if a.chi_tiet:
        print("\nVí dụ phân xử được:")
        for r in [x for x in hang if x["ket_luan"] in ("gemma đúng", "raw đúng")][:12]:
            print("   %s  raw=%-24s gemma=%-24s → %s"
                  % (r["doc"], r["raw"][:24], r["gemma"][:24], r["ket_luan"]))


if __name__ == "__main__":
    main()
