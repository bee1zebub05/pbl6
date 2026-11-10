#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Xuất các chỗ JSON v4 lệch với nhãn Claude (hai agent đã đồng ý) ra phan_xu.csv để người phân xử.

    python data/eval/v4_gold/xuat_phan_xu.py          # tạo phan_xu.csv (không ghi đè nếu đã có)
    python data/eval/v4_gold/xuat_phan_xu.py --dem    # đếm kết quả sau khi người điền cột ai_dung

Theo quy ước --gop-ref của tinh_diem.py. Chỉ lấy cặp mà hai agent gán giống hệt nhau,
nên mỗi dòng là "v4 nói X, Claude (cả hai) nói Y". Cột ai_dung điền một trong:
CLAUDE, V4, CA_HAI_SAI.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

DAY = Path(__file__).resolve().parent
sys.path.insert(0, str(DAY))
import tinh_diem as t  # noqa: E402

RA = DAY / "phan_xu.csv"
HIEU_LUC = {"REPLACES", "AMENDS", "REPEALS"}
TEN = {"BASED_ON": "Căn cứ", "REFERENCES": "Dẫn chiếu", "REPLACES": "Thay thế",
       "AMENDS": "Sửa đổi", "REPEALS": "Bãi bỏ"}


def viet(ls) -> str:
    return " + ".join(TEN[x] for x in sorted(ls)) if ls else "(không ghi)"


def ngu_canh(d: dict, dich: str) -> str:
    for c in d.get("citations") or []:
        if t.so(c.get("targetDocumentNumber")) == dich:
            return (c.get("context") or c.get("evidence") or "").replace("\n", " ").strip()
    return ""


def xuat() -> int:
    if RA.exists():
        print(f"{RA.name} đã có, không ghi đè (xoá đi nếu muốn tạo lại).")
        return 1
    t.GOP_REF = True
    ds = json.loads((DAY / "danh_sach_103.json").read_text(encoding="utf-8"))
    tho_a = t.doc_bo(DAY / "nhan_ai_1", ds)
    tho_v = t.doc_v4(ds)
    A = {k: t.tach(v) for k, v in tho_a.items()}
    B = {k: t.tach(v) for k, v in t.doc_bo(DAY / "nhan_ai_2", ds).items()}
    V = {k: t.tach(v) for k, v in tho_v.items()}
    nguon = {Path(p).stem: p for p in ds}
    dong = []
    for doc in sorted(A):
        for dich in sorted(set(A[doc]["qh"]) | set(B[doc]["qh"]) | set(V[doc]["qh"])):
            a, b, v = A[doc]["qh"].get(dich), B[doc]["qh"].get(dich), V[doc]["qh"].get(dich)
            if a is None and b is None and v:            # v4 ghi thừa
                kieu, claude, ctx = "v4 ghi thừa", "(không ghi)", ngu_canh(tho_v[doc], dich)
            elif a == b and a is not None and v != a:   # hai agent đồng ý, v4 khác
                kieu = "v4 bỏ sót" if v is None else "khác loại"
                claude, ctx = viet(a), ngu_canh(tho_a[doc], dich)
            else:
                continue
            v4 = viet(v)
            uu = "1-hiệu lực" if (HIEU_LUC & (a or set())) or (HIEU_LUC & (v or set())) else "2-khác"
            dong.append({"uu_tien": uu, "van_ban": doc[:60], "dich": dich, "kieu": kieu,
                         "v4_ghi": v4, "claude_ghi": claude, "cau_trong_van_ban": ctx,
                         "file_txt": nguon[doc], "ai_dung": "", "ghi_chu": ""})
    dong.sort(key=lambda r: (r["uu_tien"], r["van_ban"], r["dich"]))
    with RA.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dong[0]))
        w.writeheader()
        w.writerows(dong)
    print(f"Đã ghi {RA} ({len(dong)} dòng):", dict(Counter(r["uu_tien"] for r in dong)), dict(Counter(r["kieu"] for r in dong)))
    return 0


def dem() -> int:
    with RA.open(encoding="utf-8-sig") as f:
        dong = list(csv.DictReader(f))
    da = [r for r in dong if r["ai_dung"].strip()]
    c = Counter(r["ai_dung"].strip().upper() for r in da)
    print(f"Đã phân xử {len(da)}/{len(dong)} dòng: {dict(c)}")
    if da:
        print(f"=> Claude đúng {c['CLAUDE']}/{len(da)} trường hợp ({c['CLAUDE'] / len(da):.0%}).")
        for uu in sorted({r['uu_tien'] for r in da}):
            nhom = [r for r in da if r["uu_tien"] == uu]
            print(f"   {uu}: Claude đúng {sum(r['ai_dung'].strip().upper() == 'CLAUDE' for r in nhom)}/{len(nhom)}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", action="store_true")
    raise SystemExit(dem() if ap.parse_args().dem else xuat())
