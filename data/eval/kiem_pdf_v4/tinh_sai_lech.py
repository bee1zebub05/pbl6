"""Đo độ sai lệch của JSON do model trả về so với bản đã đối chiếu PDF gốc.

    python data/eval/kiem_pdf_v4/tinh_sai_lech.py            # in bảng, ghi ket_qua.md + ket_qua.json

Mỗi văn bản có hai bản: goc/<mã>.json (model trả về, chưa ai sửa) và chuan/<mã>.json
(đã đối chiếu ảnh PDF gốc, qua trọng tài). Chỉ chấm các văn bản có đủ cả hai bản.

Trường đơn (so khớp sau chuẩn hoá): số hiệu, loại văn bản, ngày ban hành, ngày hiệu lực,
trạng thái, cơ quan ban hành, số Điều. Trường tập hợp (Precision / Recall / F1 gộp vi mô):
người ký (họ tên + chức vụ), trích dẫn (số hiệu đích + loại quan hệ, chấm cả từng loại),
nhóm đối tượng, lĩnh vực.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

GOC = Path(__file__).resolve().parent
REPO = GOC.parents[2]
sys.path.insert(0, str(REPO / "src"))
from legal_knowledge_graph.core.normalize import normalize_document_number, slug  # noqa: E402

LOAI = ("BASED_ON", "REFERENCES", "REPLACES", "AMENDS", "REPEALS")


def doc(d):
    return d.get("document") or {}


def so_dieu(d):
    return len(d.get("articles") or []) + sum(len(n.get("articles") or []) for n in d.get("normativeContents") or [])


DON = {
    "so_hieu": lambda d: normalize_document_number(doc(d).get("documentNumber") or ""),
    "loai_van_ban": lambda d: slug(doc(d).get("documentType") or ""),
    "ngay_ban_hanh": lambda d: doc(d).get("issueDate"),
    "ngay_hieu_luc": lambda d: doc(d).get("effectiveDate"),
    "trang_thai": lambda d: doc(d).get("status"),
    "co_quan": lambda d: slug((d.get("organization") or {}).get("name") or ""),
    "so_dieu": so_dieu,
}


def tap(d, ten):
    if ten == "nguoi_ky":
        return {(slug(s.get("fullName") or ""), slug(" ".join(s.get("position") or []))) for s in d.get("signers") or []}
    if ten == "trich_dan":
        return {(normalize_document_number(c.get("targetDocumentNumber") or ""), c.get("relationType"))
                for c in d.get("citations") or []}
    if ten == "nhom_doi_tuong":
        return {slug(x) for x in doc(d).get("targetGroups") or []}
    if ten == "linh_vuc":
        return {slug(x) for x in doc(d).get("topics") or []}
    raise KeyError(ten)


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def main() -> int:
    cap = []
    for c in sorted((GOC / "chuan").glob("*.json")):
        g = GOC / "goc" / c.name
        if g.exists():
            cap.append((c.stem, json.load(open(g, encoding="utf-8")), json.load(open(c, encoding="utf-8"))))
    if not cap:
        print("chưa có văn bản nào đủ cả goc/ và chuan/")
        return 1
    kq = {"so_van_ban": len(cap), "truong_don": {}, "truong_tap": {}, "trich_dan_theo_loai": {}, "van_ban_sai": {}}
    for ten, f in DON.items():
        sai = [ma for ma, g, c in cap if f(g) != f(c)]
        kq["truong_don"][ten] = {"dung": len(cap) - len(sai), "tong": len(cap), "ty_le_dung": round(1 - len(sai) / len(cap), 4)}
        if sai:
            kq["van_ban_sai"][ten] = sai
    for ten in ("nguoi_ky", "trich_dan", "nhom_doi_tuong", "linh_vuc"):
        tp = fp = fn = 0
        for _, g, c in cap:
            a, b = tap(g, ten), tap(c, ten)
            tp, fp, fn = tp + len(a & b), fp + len(a - b), fn + len(b - a)
        p, r, f1 = prf(tp, fp, fn)
        kq["truong_tap"][ten] = {"tp": tp, "fp": fp, "fn": fn, "P": round(p, 4), "R": round(r, 4), "F1": round(f1, 4)}
    for loai in LOAI:
        tp = fp = fn = 0
        for _, g, c in cap:
            a = {x for x in tap(g, "trich_dan") if x[1] == loai}
            b = {x for x in tap(c, "trich_dan") if x[1] == loai}
            tp, fp, fn = tp + len(a & b), fp + len(a - b), fn + len(b - a)
        p, r, f1 = prf(tp, fp, fn)
        kq["trich_dan_theo_loai"][loai] = {"so_chuan": tp + fn, "so_model": tp + fp, "P": round(p, 4), "R": round(r, 4), "F1": round(f1, 4)}

    dong = [f"# Độ sai lệch JSON model so với bản đối chiếu PDF gốc", "",
            f"Số văn bản chấm: {len(cap)}.", "", "| Trường | Đúng | Tỷ lệ đúng |", "|---|---|---|"]
    dong += [f"| {k} | {v['dung']}/{v['tong']} | {v['ty_le_dung']:.1%} |" for k, v in kq["truong_don"].items()]
    dong += ["", "| Trường tập hợp | P | R | F1 |", "|---|---|---|---|"]
    dong += [f"| {k} | {v['P']:.2f} | {v['R']:.2f} | {v['F1']:.2f} |" for k, v in kq["truong_tap"].items()]
    dong += ["", "| Loại quan hệ | Số trong bản chuẩn | Số model trả về | P | R | F1 |", "|---|---|---|---|---|---|"]
    dong += [f"| {k} | {v['so_chuan']} | {v['so_model']} | {v['P']:.2f} | {v['R']:.2f} | {v['F1']:.2f} |"
             for k, v in kq["trich_dan_theo_loai"].items()]
    if kq["van_ban_sai"]:
        dong += ["", "Văn bản sai theo trường: " + "; ".join(f"{k}: {', '.join(v)}" for k, v in kq["van_ban_sai"].items())]
    (GOC / "ket_qua.md").write_text("\n".join(dong) + "\n", encoding="utf-8")
    (GOC / "ket_qua.json").write_text(json.dumps(kq, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\n".join(dong))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
