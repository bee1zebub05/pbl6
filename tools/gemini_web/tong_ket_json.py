# -*- coding: utf-8 -*-
"""Tong ket toan bo `data/kg_json` — dem duoc gi, mat gi, va vi sao.

    python tools/gemini_web/tong_ket_json.py

Ba phan:

  1. SO LUONG   — bao nhieu file, bao nhieu node/canh sinh ra.
  2. CANH BAO   — gom theo loai, KEM phan loai nguyen nhan. Quan trong nhat la
                  tach "model bo bot" ra khoi "schema khong co cho chua".
  3. LO HONG    — dem chinh xac bao nhieu van ban co noi dung that KHONG vao
                  duoc do thi, chia hai dang:
                    a) phu luc / danh sach dang bang
                    b) ban kem theo danh muc kieu 1. / 1.1 / 2.3.1 thay vi Dieu
"""
from __future__ import annotations

import collections
import io
import json
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
RA = GOC / "data" / "kg_json"
KHO_TXT = GOC / "data" / "clean" / "text_final"

BANG = re.compile(r"^\s*\|.*\|\s*$", re.M)
MUC_SO = re.compile(r"^\s*\d{1,2}(?:\.\d{1,2}){0,3}\.?\s+[A-ZĐÀ-Ỹ]", re.M)  # 1. / 1.1 / 2.3.1
DIEU = re.compile(r"^[ \t]*Điều\s+\d{1,3}[a-zA-Z]?\s*(?:[.．:]|\s+(?=[A-ZĐÀ-Ỹ]))", re.M)


def _txt_cua(ma: str):
    for p in KHO_TXT.rglob("*.txt"):
        if p.name.startswith(ma):
            return p
    return None


def main() -> int:
    if not RA.exists():
        print("Chua co %s" % RA)
        return 1

    files = sorted(RA.rglob("*.json"))
    live = [p for p in files if "_nghi_ngo" not in str(p)]
    nghi = [p for p in files if "_nghi_ngo" in str(p)]

    print("=" * 78)
    print("TONG KET  %s" % RA.relative_to(GOC))
    print("=" * 78)
    print("\n1. SO LUONG")
    print("   file JSON      : %d  (sach %d · nghi ngo %d)"
          % (len(files), len(live), len(nghi)))

    dem = collections.Counter()
    loai = collections.Counter()
    for p in files:
        d = json.load(io.open(p, encoding="utf-8"))
        loai[d["document"]["documentType"]] += 1
        dem["citations"] += len(d.get("citations") or [])
        dem["signers"] += len(d.get("signers") or [])
        dem["mentions"] += len(d.get("mentions") or [])
        na = len(d.get("articles") or [])
        nn = sum(len(n.get("articles") or []) for n in d.get("normativeContents") or [])
        dem["articles"] += na + nn
        dem["normativeContents"] += len(d.get("normativeContents") or [])
    for k in ("articles", "citations", "signers", "mentions", "normativeContents"):
        print("   %-14s : %s" % (k, format(dem[k], ",d").replace(",", ".")))
    print("   loai van ban   : %s"
          % ", ".join("%s=%d" % x for x in loai.most_common(8)))

    # ---------- canh bao ----------
    ck = GOC / "tools" / "gemini_web" / "trang_thai_json.json"
    if ck.exists():
        st = json.load(io.open(ck, encoding="utf-8"))
        cb = collections.Counter()
        for v in st.get("xong", {}).values():
            for x in v.get("canh_bao") or []:
                cb[re.split(r"[:(]", x)[0].strip()] += 1
        if cb:
            print("\n2. CANH BAO")
            for k, v in cb.most_common():
                print("   %-34s %d" % (k, v))

    # ---------- lo hong schema ----------
    print("\n3. LO HONG SCHEMA — noi dung that khong vao duoc do thi")
    phu_luc, muc_so, that_su_thieu = [], [], []
    for p in files:
        d = json.load(io.open(p, encoding="utf-8"))
        ma = p.name[:4]
        tx = _txt_cua(ma)
        if not tx:
            continue
        goc = io.open(tx, encoding="utf-8", errors="replace").read()
        than = sum(len(a.get("text") or "") for a in (d.get("articles") or []))
        than += sum(len(a.get("text") or "")
                    for n in (d.get("normativeContents") or [])
                    for a in (n.get("articles") or []))
        if than >= len(goc) * 0.35:
            continue                       # phan lon noi dung da vao Dieu -> khong mat gi

        # Cong van / Ke hoach / Huong dan von khong co cau truc Dieu. Khong co
        # Dieu de chep thi khong phai "mat", day la hinh dang that cua van ban.
        if d["document"]["documentType"] in ("Công văn", "Kế hoạch", "Hướng dẫn"):
            continue

        # Moi van ban deu co phan KHONG thuoc than Dieu: tieu ngu, so hieu, can cu,
        # noi nhan, khoi ky. Chung da nam o cac truong khac nen khong phai "mat".
        # Van ban nho thi phan nay chiem ti le lon -> doi them nguong tuyet doi.
        mat = len(goc) - than
        if mat < 3000:
            continue

        n_bang = len(BANG.findall(goc))
        n_muc = len(MUC_SO.findall(goc))
        n_dieu = len({m.group(0) for m in DIEU.finditer(goc)})
        if n_bang >= 20:
            phu_luc.append((ma, mat, n_bang))
        elif n_muc >= 10 and n_muc > n_dieu:
            muc_so.append((ma, mat, n_muc))
        else:
            that_su_thieu.append((ma, mat, n_dieu))

    for ten, ds, cot in (
            ("a) Phu luc / danh sach dang BANG", phu_luc, "dong bang"),
            ("b) Ban kem theo danh muc 1. / 1.1 (khong phai Dieu)", muc_so, "muc so"),
            ("c) CHUA GIAI THICH DUOC — phai doc tay", that_su_thieu, "Dieu trong txt")):
        tong = sum(x[1] for x in ds)
        print("\n   %s: %d van ban, mat ~%s ky tu"
              % (ten, len(ds), format(tong, ",d").replace(",", ".")))
        for ma, mat, n in sorted(ds, key=lambda x: -x[1])[:8]:
            print("      %s  mat %7s ky tu  (%s: %d)"
                  % (ma, format(mat, ",d").replace(",", "."), cot, n))
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
