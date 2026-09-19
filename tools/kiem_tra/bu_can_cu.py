# -*- coding: utf-8 -*-
"""Bu nhung trich dan "Can cu ... so <so hieu> ..." model bo sot.

    python tools/kiem_tra/bu_can_cu.py          # chi bao cao
    python tools/kiem_tra/bu_can_cu.py --ghi    # them that

Chi lay nhung cau can cu CO SO HIEU ghi ro trong nguon — so hieu chep nguyen
van tu .txt, khong suy dien gi. Cau can cu chi ghi ten va ngay (kieu "Căn cứ
Luật Tổ chức Chính phủ ngày 19 tháng 6 năm 2015;") thi BO QUA, vi do chinh la
loai da phai go o bo_trich_dan_bia.py.

relationType luon la BASED_ON: day la muc "Căn cứ" o dau van ban.
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
RA = GOC / "data" / "clean" / "json" / "v1"

# "Căn cứ Nghị định số 34/2016/NĐ-CP ngày 14 tháng 5 năm 2016 của Chính phủ..."
CAN_CU = re.compile(r"(?m)^[ \t]*Căn cứ[^\n]{10,400}")
SO_HIEU = re.compile(
    r"số[:\s]*([0-9]{1,4}[a-zA-Z]?(?:/[0-9]{4})?/[A-Za-zĐđ][A-Za-zĐđ0-9\-]{1,14})")


def _khoa(s: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", s or "")).lower()


def doc_can_cu(txt: str):
    """-> [(so hieu, cau can cu)] cho nhung cau CO so hieu."""
    ra = []
    for c in CAN_CU.finditer(txt):
        cau = " ".join(c.group(0).split())
        for m in SO_HIEU.finditer(cau):
            sh = m.group(1)
            # Duoi phai co it nhat 2 chu cai. Nguon OCR hong kieu "6950/QĐ- DHDN"
            # se cho ra "6950/QĐ-" cut duoi — bo, khong doan phan con thieu.
            if sh.endswith("-"):     # "6950/QĐ-" — nguon OCR lam dut duoi
                continue
            duoi = sh.rsplit("/", 1)[-1].strip("-")
            if len(re.sub(r"[^A-Za-zĐđ]", "", duoi)) < 2:
                continue
            ra.append((sh, cau))
    return ra


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ghi", action="store_true")
    a = ap.parse_args()

    txt = {p.name[:4]: p for p in KHO_TXT.rglob("*.txt")}
    them = collections.defaultdict(list)

    for j in sorted(RA.rglob("*.json")):
        ma = j.name[:4]
        d = json.loads(io.open(j, encoding="utf-8").read())
        goc = io.open(txt[ma], encoding="utf-8", errors="replace").read()
        co = {_khoa(c.get("targetDocumentNumber")) for c in (d.get("citations") or [])}
        minh = _khoa(d["document"].get("documentNumber"))
        moi = []
        for sh, cau in doc_can_cu(goc):
            k = _khoa(sh)
            if k in co or k == minh:
                continue
            co.add(k)
            moi.append({"targetDocumentNumber": sh, "relationType": "BASED_ON",
                        "context": cau[:400]})
        if not moi:
            continue
        them[ma] = [x["targetDocumentNumber"] for x in moi]
        if a.ghi:
            d["citations"] = (d.get("citations") or []) + moi
            io.open(j, "w", encoding="utf-8", newline="\n").write(
                json.dumps(d, ensure_ascii=False, indent=2) + "\n")

    n = sum(len(v) for v in them.values())
    print("Bù %d trích dẫn ở %d file%s"
          % (n, len(them), "" if a.ghi else "   (thêm --ghi để ghi thật)"))
    for ma, ds in sorted(them.items())[:40]:
        print("   %s  %d: %s" % (ma, len(ds), ", ".join(ds[:6])))
    if len(them) > 40:
        print("   … còn %d file nữa" % (len(them) - 40))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
