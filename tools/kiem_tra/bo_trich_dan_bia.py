# -*- coding: utf-8 -*-
"""Bo nhung trich dan co so hieu KHONG kiem chung duoc tu du lieu goc.

    python tools/kiem_tra/bo_trich_dan_bia.py          # chi bao cao
    python tools/kiem_tra/bo_trich_dan_bia.py --ghi    # xoa that

Vi sao phai bo chu khong giu:

Nguon viet can cu theo TEN + NGAY, khong kem so hieu — "Căn cứ Luật Tổ chức
Chính phủ ngày 19 tháng 6 năm 2015;". Schema bat buoc `targetDocumentNumber`
nen model phai dien, va no tu che: co khi dan luon ngay lam so hieu
(25/12/2001), co khi ghep so tu ngay (19/6/2015 -> "19/2015/QH13", so that la
76/2015/QH13).

So hieu la KHOA cua node Document trong do thi. Mot so hieu bia se sinh node
ma; te hon, no co the trung voi mot van ban CO THAT rooi tao canh sai trong khi
nhin vao khong phan biet duoc. Do that tren corpus: 6 so hieu kieu nay tro
trung vao van ban co that.

Chi bo nhung cho da vet HET nam duong kiem chung ma van chiu (xem
soi_trich_dan.py). Cau can cu khong mat: no van nam nguyen trong .txt, va tom
tat lai trong truong `note`.
"""
from __future__ import annotations

import argparse
import collections
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import soi_trich_dan as S  # noqa: E402

GHI_CHU = ("%d trích dẫn bị gỡ vì số hiệu không kiểm chứng được từ bản gốc "
           "(nguồn chỉ ghi tên và ngày, không có số hiệu): %s. "
           "Câu căn cứ vẫn nằm nguyên trong bản .txt.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ghi", action="store_true")
    a = ap.parse_args()

    txt = {p.name[:4]: p for p in S.KHO_TXT.rglob("*.txt")}
    bang, ho = S.hoc_bang(), S._ho_so_corpus()
    bo = collections.defaultdict(list)

    for j in sorted(S.RA.rglob("*.json")):
        ma = j.name[:4]
        d = json.loads(io.open(j, encoding="utf-8").read())
        goc = io.open(txt[ma], encoding="utf-8", errors="replace").read()
        mo = S._mo(goc)
        giu = []
        for c in (d.get("citations") or []):
            if S.soi(c, goc, mo, bang, ho)[0] == "KHONG RO":
                bo[ma].append(c.get("targetDocumentNumber") or "(trống)")
            else:
                giu.append(c)
        if ma not in bo:
            continue
        if a.ghi:
            d["citations"] = giu
            cu = (d.get("note") or "").strip()
            them = GHI_CHU % (len(bo[ma]), ", ".join(bo[ma]))
            d["note"] = (cu + " " if cu else "") + them
            loi = S.__dict__.get("_validate")
            io.open(j, "w", encoding="utf-8", newline="\n").write(
                json.dumps(d, ensure_ascii=False, indent=2) + "\n")

    n = sum(len(v) for v in bo.values())
    print("Gỡ %d trích dẫn ở %d file%s" % (n, len(bo), "" if a.ghi else "  (thêm --ghi để xoá thật)"))
    for ma, ds in sorted(bo.items()):
        print("   %s  %d: %s" % (ma, len(ds), ", ".join(ds)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
