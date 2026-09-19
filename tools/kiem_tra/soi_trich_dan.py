# -*- coding: utf-8 -*-
"""Soi tung trich dan: so hieu dich co kiem chung duoc tu CHINH corpus khong?

    python tools/kiem_tra/soi_trich_dan.py            # chi bao cao
    python tools/kiem_tra/soi_trich_dan.py --ghi      # sua nhung cho chac chan

Van de: rat nhieu van ban viet can cu theo TEN + NGAY chu khong kem so hieu —
"Căn cứ Luật Tổ chức Chính phủ ngày 19 tháng 6 năm 2015;". Model buoc phai dien
`targetDocumentNumber` (schema bat buoc) nen no tu che: co khi dan luon ngay
vao lam so hieu (25/12/2001), co khi lay so hieu tu kien thuc rieng — ma kien
thuc rieng thi sai that: Luat To chuc Chinh phu 2015 la 76/2015/QH13, model
ghi 19/2015/QH13 (ghep tu ngay 19/6).

Bon muc do kiem chung, CHI dung du lieu cua nguoi dung, khong dung kien thuc
ngoai:

  NGUYEN VAN  so hieu xuat hien y nguyen trong .txt cua chinh van ban do
  OCR         xuat hien nhung bi OCR lam ban ("6950/QĐ- DHDN" -> 6950/QĐ-ĐHĐN)
  DOI CHIEU   so hieu tro toi mot van ban CO THAT trong corpus, va tieu de +
              ngay ban hanh cua van ban do khop voi cau can cu
  TRA BANG    corpus co cho khac viet du "Luật X số 08/2012/QH13 ngày 18/6/2012",
              ghep lai suy ra duoc so hieu
  KHONG RO    khong cach nao kiem chung -> bao cao, KHONG tu sua
"""
from __future__ import annotations

import argparse
import collections
import io
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
KHO_TXT = GOC / "data" / "clean" / "text_final"
RA = GOC / "data" / "kg_json"

LOAI = (r"(?:Bộ luật|Luật|Pháp lệnh|Nghị định|Thông tư liên tịch|Thông tư"
        r"|Nghị quyết|Quyết định|Chỉ thị)")
SO = r"[0-9]{1,4}[a-zA-Z]?(?:/[0-9]{4})?/[A-Za-zĐđ][A-Za-zĐđ0-9\-]{1,14}"
XAU = re.compile(r"\b(này|có hiệu lực|kèm theo|thay thế|quy định chi tiết"
                 r"|sửa đổi|bổ sung|của Chính phủ|của Bộ|ban hành)\b", re.I)

_CO_SO = re.compile(
    r"(" + LOAI + r")\s+([A-ZĐÀ-Ỹa-zà-ỹ][^,;\n]{2,58}?)\s*số[:\s]*(" + SO + r")"
    r"[^\n]{0,24}?ngày\s*(\d{1,2})\s*(?:tháng|[/-])\s*(\d{1,2})\s*(?:năm|[/-])\s*(\d{4})")
_KHONG_SO = re.compile(
    r"(" + LOAI + r")\s+([A-ZĐÀ-Ỹa-zà-ỹ][^,;\n]{2,58}?)\s*"
    r"ngày\s*(\d{1,2})\s*(?:tháng|[/-])\s*(\d{1,2})\s*(?:năm|[/-])\s*(\d{4})")


def _gon(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s or "").lower()).strip(" ,;.")


def _khoa(s: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", s or "")).lower()


def _mo(s: str) -> str:
    """Bo dau, bo ky tu la — de so khop khi OCR lam ban."""
    s = unicodedata.normalize("NFD", (s or "").lower()).replace("đ", "d")
    return re.sub(r"[^a-z0-9]", "", re.sub(r"[̀-ͯ]", "", s))


def hoc_bang():
    """(loai, ten, ngay) -> so hieu, hoc tu nhung cho corpus viet DU."""
    bang = collections.defaultdict(collections.Counter)
    for p in KHO_TXT.rglob("*.txt"):
        g = re.sub(r"\s+", " ", io.open(p, encoding="utf-8", errors="replace").read())
        for m in _CO_SO.finditer(g):
            ten = _gon(m.group(2))
            if not ten or XAU.search(ten):
                continue
            ngay = "%02d/%02d/%s" % (int(m.group(4)), int(m.group(5)), m.group(6))
            bang[(_gon(m.group(1)), ten, ngay)][m.group(3)] += 1
    return bang


def doc_can_cu(context: str):
    m = _KHONG_SO.search(context or "")
    if not m:
        return None
    ten = _gon(m.group(2))
    if not ten or XAU.search(ten):
        return None
    return (_gon(m.group(1)), ten,
            "%02d/%02d/%s" % (int(m.group(3)), int(m.group(4)), m.group(5)))


def _ho_so_corpus():
    """so hieu -> (ma, tieu de, ngay ban hanh) cua 455 van ban."""
    ra = {}
    for j in RA.rglob("*.json"):
        d = json.loads(io.open(j, encoding="utf-8").read())
        ra[_khoa(d["document"].get("documentNumber"))] = (
            j.name[:4], d["document"].get("title") or "", d["document"].get("issueDate"))
    return ra


def soi(c, goc_txt, mo_txt, bang, ho_so):
    """-> (muc do, so hieu de nghi hoac None, ghi chu)."""
    sh = (c.get("targetDocumentNumber") or "").strip()
    ct = c.get("context") or ""
    if not sh:
        return "KHONG RO", None, "trong"
    if _khoa(sh) in _khoa(goc_txt):
        return "NGUYEN VAN", None, ""
    if _mo(sh) and _mo(sh) in mo_txt:
        return "OCR", None, "co trong .txt nhung bi OCR lam ban"

    kh = doc_can_cu(ct)

    # doi chieu: so hieu tro toi mot van ban co that trong corpus
    d = ho_so.get(_khoa(sh))
    if d and kh:
        ma, tieu, ngay = d
        if _mo(kh[1]) and _mo(kh[1]) in _mo(tieu) and ngay == kh[2]:
            return "DOI CHIEU", None, "khop tiêu đề + ngày của %s" % ma

    # tra bang hoc tu corpus
    if kh:
        cand = bang.get(kh)
        if cand and len(cand) == 1:
            moi = next(iter(cand))
            if _khoa(moi) != _khoa(sh):
                return "TRA BANG", moi, "corpus viết đủ ở chỗ khác"
            return "TRA BANG", None, ""
    return "KHONG RO", None, (" ".join(ct.split())[:76] or "không có context")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ghi", action="store_true", help="sửa những chỗ TRA BANG chắc chắn")
    a = ap.parse_args()

    txt = {p.name[:4]: p for p in KHO_TXT.rglob("*.txt")}
    bang, ho_so = hoc_bang(), _ho_so_corpus()
    dem = collections.Counter()
    sua = collections.defaultdict(list)
    mo_ho = []

    for j in sorted(RA.rglob("*.json")):
        ma = j.name[:4]
        d = json.loads(io.open(j, encoding="utf-8").read())
        goc = io.open(txt[ma], encoding="utf-8", errors="replace").read()
        mo_txt = _mo(goc)
        doi = False
        for c in (d.get("citations") or []):
            muc, moi, ghi = soi(c, goc, mo_txt, bang, ho_so)
            dem[muc] += 1
            if muc == "KHONG RO":
                mo_ho.append((ma, c.get("targetDocumentNumber"), ghi))
            if moi:
                sua[ma].append((c.get("targetDocumentNumber"), moi, ghi))
                if a.ghi:
                    c["targetDocumentNumber"] = moi
                    doi = True
        if doi:
            io.open(j, "w", encoding="utf-8", newline="\n").write(
                json.dumps(d, ensure_ascii=False, indent=2) + "\n")

    tong = sum(dem.values())
    print("=" * 66)
    print("  %s trích dẫn trên %d file" % (format(tong, ","), len(list(RA.rglob('*.json')))))
    for m in ("NGUYEN VAN", "OCR", "DOI CHIEU", "TRA BANG", "KHONG RO"):
        print("    %-11s %5d   %5.2f%%" % (m, dem[m], 100.0 * dem[m] / max(tong, 1)))
    print("=" * 66)

    if sua:
        print("\nĐỀ NGHỊ SỬA (%d chỗ, tra được từ chính corpus):"
              % sum(len(v) for v in sua.values()))
        for ma, ds in sorted(sua.items()):
            for cu, moi, ghi in ds:
                print("   %s  %-18s -> %-18s  %s" % (ma, cu, moi, ghi))
        if not a.ghi:
            print("   (thêm --ghi để sửa thật)")

    if mo_ho:
        print("\nKHÔNG KIỂM CHỨNG ĐƯỢC — %d chỗ, KHÔNG tự sửa:" % len(mo_ho))
        for ma, sh, ghi in mo_ho:
            print("   %s  %-18s  %s" % (ma, sh, ghi))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
