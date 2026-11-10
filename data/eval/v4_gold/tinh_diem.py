#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tính độ đồng thuận giữa hai bộ nhãn và độ chính xác của JSON v4 (Ontology §6.1–6.2).

    python data/eval/v4_gold/tinh_diem.py
    python data/eval/v4_gold/tinh_diem.py --a nhan_ai_1 --b nhan_ai_2
    python data/eval/v4_gold/tinh_diem.py --ds danh_sach_20.json   # mẫu 20 văn bản đầu

Đơn vị so khớp:
- Trích dẫn: cặp (văn bản nguồn, số hiệu đích đã chuẩn hoá) + loại quan hệ.
  Tách hai tầng lỗi theo §6.2: *phát hiện* (có bắt được cặp nguồn–đích không,
  bỏ qua nhãn) và *phân loại* (trong các cặp cả hai bên cùng có, nhãn có khớp không).
- Người ký: (văn bản, person_id).
- Nhóm đối tượng: (văn bản, tên nhóm).

Cohen's κ cho quan hệ tính trên hợp các cặp nguồn–đích của hai người gán;
bên nào không có cặp đó thì nhãn là KHONG. Một cặp có nhiều nhãn thì nhãn là
tập nhãn ghép lại (hiếm).

Ghi kết quả ra ket_qua.md và ket_qua.json cạnh file này.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

GOC = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(GOC / "src"))
from legal_knowledge_graph.core import normalize as nz  # noqa: E402

DAY = Path(__file__).resolve().parent
V4 = GOC / "data" / "clean" / "json" / "v4"
LOAI = ("BASED_ON", "REFERENCES", "REPLACES", "AMENDS", "REPEALS")


def so(x: str | None) -> str:
    return nz.normalize_document_number(x or "").strip()


def doc_bo(thu_muc: Path, ten_file: list[str]) -> dict[str, dict]:
    ra = {}
    for ten in ten_file:
        p = thu_muc / (Path(ten).stem + ".json")
        if p.exists():
            ra[Path(ten).stem] = json.loads(p.read_text(encoding="utf-8"))
    return ra


def doc_v4(ten_file: list[str]) -> dict[str, dict]:
    can = {Path(t).stem for t in ten_file}
    ra = {}
    for p in V4.rglob("*.json"):  # gồm cả _nghi_ngo/
        d = json.loads(p.read_text(encoding="utf-8"))
        stem = Path(d.get("sourceFile") or p.name).stem
        if stem in can:
            ra[stem] = d
    return ra


GOP_REF = False  # --gop-ref: cặp đã có nhãn khác thì bỏ REFERENCES đi kèm


def tach(d: dict) -> dict:
    """Rút ba tập đơn vị so khớp từ một file (nhãn gán hoặc JSON v4)."""
    goc = so((d.get("document") or {}).get("documentNumber") or d.get("documentNumber"))
    qh: dict[str, set[str]] = {}
    for c in d.get("citations") or []:
        dich = so(c.get("targetDocumentNumber"))
        loai = c.get("relationType")
        if not dich or dich == goc or loai not in LOAI:
            continue
        qh.setdefault(dich, set()).add(loai)
    if GOP_REF:
        for ls in qh.values():
            if len(ls) > 1:
                ls.discard("REFERENCES")
    ky = set()
    for s in d.get("signers") or []:
        ten = s.get("fullName") if isinstance(s, dict) else s
        if ten:
            ky.add(nz.person_id(ten))
    tg = (d.get("document") or {}).get("targetGroups") if "document" in d else d.get("targetGroups")
    return {"qh": qh, "ky": ky, "tg": {nhom(x) for x in tg or []}}


def nhom(ten: str) -> str:
    """HUONG_DAN.md viết tắt hai tên nhóm; quy về tên chuẩn trong target_groups_seed.json."""
    if ten.startswith("Doanh nghiệp"):
        return "Doanh nghiệp, đối tác/tổ chức nước ngoài"
    if ten.startswith("Hội đồng"):
        return "Hội đồng và thành viên hội đồng"
    return ten


def prf(du_doan: set, chuan: set) -> dict:
    tp = len(du_doan & chuan)
    p = tp / len(du_doan) if du_doan else (1.0 if not chuan else 0.0)
    r = tp / len(chuan) if chuan else 1.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"P": round(p, 3), "R": round(r, 3), "F1": round(f, 3), "tp": tp, "du_doan": len(du_doan), "chuan": len(chuan)}


def kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    if not n:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return round((po - pe) / (1 - pe), 3) if pe < 1 else 1.0


def tap(bo: dict[str, dict], truong: str) -> set:
    ra = set()
    for doc, t in bo.items():
        if truong == "qh":
            ra |= {(doc, dich, l) for dich, ls in t["qh"].items() for l in ls}
        elif truong == "cap":
            ra |= {(doc, dich) for dich in t["qh"]}
        else:
            ra |= {(doc, x) for x in t[truong]}
    return ra


def so_sanh(du: dict[str, dict], chuan: dict[str, dict]) -> dict:
    ra = {
        "phat_hien_cap": prf(tap(du, "cap"), tap(chuan, "cap")),
        "quan_he_tong": prf(tap(du, "qh"), tap(chuan, "qh")),
        "nguoi_ky": prf(tap(du, "ky"), tap(chuan, "ky")),
        "doi_tuong": prf(tap(du, "tg"), tap(chuan, "tg")),
        "theo_loai": {},
    }
    q_du, q_ch = tap(du, "qh"), tap(chuan, "qh")
    for l in LOAI:
        ra["theo_loai"][l] = prf({x for x in q_du if x[2] == l}, {x for x in q_ch if x[2] == l})
    # tầng phân loại: trong các cặp cả hai cùng có, nhãn có khớp không
    chung = tap(du, "cap") & tap(chuan, "cap")
    dung = sum(du[d]["qh"][t] == chuan[d]["qh"][t] for d, t in chung)
    ra["phan_loai_tren_cap_chung"] = {"dung": dung, "tong": len(chung),
                                     "ti_le": round(dung / len(chung), 3) if chung else None}
    return ra


def dong_thuan(a: dict[str, dict], b: dict[str, dict]) -> dict:
    cap = sorted(tap(a, "cap") | tap(b, "cap"))
    nhan = lambda bo, d, t: "+".join(sorted(bo[d]["qh"].get(t, []))) or "KHONG"  # noqa: E731
    la, lb = [nhan(a, d, t) for d, t in cap], [nhan(b, d, t) for d, t in cap]
    # κ chỉ trên các cặp cả hai cùng phát hiện: đo riêng việc chọn loại quan hệ
    chung = [(x, y) for x, y in zip(la, lb) if x != "KHONG" and y != "KHONG"]
    return {
        "so_cap": len(cap),
        "dong_y_tho": round(sum(x == y for x, y in zip(la, lb)) / len(cap), 3) if cap else None,
        "kappa_quan_he": kappa(la, lb),
        "kappa_loai_tren_cap_chung": kappa([x for x, _ in chung], [y for _, y in chung]),
        "so_cap_chung": len(chung),
        "nguoi_ky": prf(tap(a, "ky"), tap(b, "ky")),
        "doi_tuong": prf(tap(a, "tg"), tap(b, "tg")),
        "bat_dong": [{"van_ban": d, "dich": t, "a": x, "b": y}
                     for (d, t), x, y in zip(cap, la, lb) if x != y],
    }


def bang(ten_cot: list[str], dong: list[list]) -> str:
    s = "| " + " | ".join(ten_cot) + " |\n|" + "---|" * len(ten_cot) + "\n"
    return s + "".join("| " + " | ".join(str(x) for x in r) + " |\n" for r in dong)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="nhan_ai_1")
    ap.add_argument("--b", default="nhan_ai_2")
    ap.add_argument("--gop-ref", action="store_true",
                    help="cặp vừa BASED_ON/REPLACES/AMENDS/REPEALS vừa REFERENCES chỉ tính nhãn mạnh; ghi ra ket_qua_gop_ref.*")
    ap.add_argument("--ds", default="danh_sach_103.json", help="danh_sach_20.json để tính lại trên mẫu 20 văn bản đầu")
    args = ap.parse_args()
    global GOP_REF
    GOP_REF = args.gop_ref
    hau_to = "_gop_ref" if GOP_REF else ""

    ds = json.loads((DAY / args.ds).read_text(encoding="utf-8"))
    A = {k: tach(v) for k, v in doc_bo(DAY / args.a, ds).items()}
    B = {k: tach(v) for k, v in doc_bo(DAY / args.b, ds).items()}
    V = {k: tach(v) for k, v in doc_v4(ds).items()}
    chung = sorted(set(A) & set(B) & set(V))
    thieu = {"a": len(ds) - len(A), "b": len(ds) - len(B), "v4": len(ds) - len(V)}
    A, B, V = ({k: x[k] for k in chung} for x in (A, B, V))

    dt = dong_thuan(A, B)
    va, vb = so_sanh(V, A), so_sanh(V, B)
    kq = {"so_van_ban": len(chung), "thieu": thieu, "dong_thuan": dt, "v4_so_voi_a": va, "v4_so_voi_b": vb}
    (DAY / f"ket_qua{hau_to}.json").write_text(json.dumps(kq, ensure_ascii=False, indent=1), encoding="utf-8")

    tb = lambda x, y: round((x + y) / 2, 3)  # noqa: E731
    md = [f"# Kết quả đối chứng JSON v4 ({len(chung)} văn bản)\n",
          f"Bộ nhãn A = `{args.a}`, B = `{args.b}`, danh sách `{args.ds}`. Sinh bởi "
          + ("`python data/eval/v4_gold/tinh_diem.py --gop-ref` (cặp đã có nhãn mạnh thì bỏ REFERENCES đi kèm).\n"
             if GOP_REF else "`python data/eval/v4_gold/tinh_diem.py`.\n"),
          "## Độ đồng thuận giữa A và B\n",
          bang(["Chỉ số", "Giá trị"], [
              ["Số cặp nguồn–đích (hợp hai bên)", dt["so_cap"]],
              ["Tỉ lệ đồng ý thô", dt["dong_y_tho"]],
              ["Cohen's κ (quan hệ, kể cả KHONG)", dt["kappa_quan_he"]],
              [f"Cohen's κ (loại quan hệ, trên {dt['so_cap_chung']} cặp cả hai cùng có)", dt["kappa_loai_tren_cap_chung"]],
              ["F1 người ký giữa A và B", dt["nguoi_ky"]["F1"]],
              ["F1 nhóm đối tượng giữa A và B", dt["doi_tuong"]["F1"]],
          ]),
          "\n## Độ chính xác của JSON v4\n",
          bang(["Hạng mục", "P (A)", "R (A)", "F1 (A)", "P (B)", "R (B)", "F1 (B)", "F1 trung bình"],
               [[ten, va[k]["P"], va[k]["R"], va[k]["F1"], vb[k]["P"], vb[k]["R"], vb[k]["F1"], tb(va[k]["F1"], vb[k]["F1"])]
                for ten, k in [("Phát hiện cặp nguồn–đích", "phat_hien_cap"), ("Quan hệ (cặp + loại)", "quan_he_tong"),
                               ("Người ký", "nguoi_ky"), ("Nhóm đối tượng", "doi_tuong")]]),
          "\n### Theo từng loại quan hệ\n",
          bang(["Loại", "Số nhãn A", "Số nhãn B", "Số trong v4", "F1 (A)", "F1 (B)", "F1 trung bình"],
               [[l, va["theo_loai"][l]["chuan"], vb["theo_loai"][l]["chuan"], va["theo_loai"][l]["du_doan"],
                 va["theo_loai"][l]["F1"], vb["theo_loai"][l]["F1"], tb(va["theo_loai"][l]["F1"], vb["theo_loai"][l]["F1"])]
                for l in LOAI]),
          f"\nTầng phân loại: trên các cặp v4 và A cùng phát hiện, v4 gán đúng loại "
          f"{va['phan_loai_tren_cap_chung']['dung']}/{va['phan_loai_tren_cap_chung']['tong']}; "
          f"so với B: {vb['phan_loai_tren_cap_chung']['dung']}/{vb['phan_loai_tren_cap_chung']['tong']}.\n",
          f"\nVăn bản thiếu nhãn: {thieu}. Danh sách bất đồng giữa A và B: `ket_qua.json` → `dong_thuan.bat_dong`.\n"]
    (DAY / f"ket_qua{hau_to}.md").write_text("".join(md), encoding="utf-8")
    print("".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
