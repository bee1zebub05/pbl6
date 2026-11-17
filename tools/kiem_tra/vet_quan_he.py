# -*- coding: utf-8 -*-
"""Vét đủ quan hệ hiệu lực (REPLACES / REPEALS / AMENDS) bằng luật, bù chỗ model bỏ sót.

    python tools/kiem_tra/vet_quan_he.py --do              # đo trên tập chuẩn kiem_pdf_v4
    python tools/kiem_tra/vet_quan_he.py --chi 0143,0284   # in các quan hệ vét được
    python tools/kiem_tra/vet_quan_he.py --chi ... --ghi   # thêm quan hệ còn thiếu vào JSON v4

Vì sao cần: đo trên 136 văn bản đã đối chiếu PDF, Gemini chỉ bắt được 29% quan hệ bãi bỏ.
Model trả lời đủ khi câu bãi bỏ nêu một văn bản, nhưng bỏ cả danh sách khi văn bản viết

    Bãi bỏ toàn bộ các văn bản quy phạm pháp luật sau đây:
    1. Chỉ thị số 17/CT-LT ngày 18 tháng 9 năm 1993 ...
    2. Quyết định số 61/2002/QĐ-BGD&ĐT ...

`quan_he_hieu_luc.py` cũng hụt đúng chỗ này: mỗi câu chỉ lấy MỘT số hiệu đầu tiên. Ở đây
mỗi câu kích hoạt được mở rộng tới hết câu, hoặc tới hết danh sách nếu câu kết bằng dấu
hai chấm, rồi lấy MỌI số hiệu trong đó (danh sách: mỗi mục một số hiệu, số hiệu đầu mục).

Chia việc: luật lo độ ĐỦ (vét số hiệu), model lo phần cần hiểu nghĩa (căn cứ, dẫn chiếu).
Luật chỉ THÊM quan hệ còn thiếu, không bao giờ xoá hay đổi quan hệ model đã ghi. Số hiệu
lấy từ .txt nên còn lỗi OCR — mọi quan hệ thêm vào vẫn phải qua bước đối chiếu ảnh PDF.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
GOC = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GOC / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from legal_knowledge_graph.core.normalize import normalize_document_number  # noqa: E402
import quan_he_hieu_luc as QH  # noqa: E402  — LOAI, MOT_PHAN, NGUOC_TRUOC, NGUOC_SAU, trong_can_cu

TXT = GOC / "data" / "clean" / "text_final"
V4 = GOC / "data" / "clean" / "json" / "v4"
EVAL = GOC / "data" / "eval" / "kiem_pdf_v4"

KICH = re.compile(r"bãi\s*bỏ|thay\s*thế|hết\s*hiệu\s*lực", re.I)
# Số hiệu: 17/CT-LT, 61/2002/QĐ-BGD&ĐT, 06/2007/TTLT-BGDĐT-BNV-BTC, 29-NQ/TW
SO = r"(\d{1,5}[a-zA-Z]?\s*/\s*(?:\d{4}\s*/\s*)?[A-ZĐ][\wĐ&\-]{0,40}(?:/[A-ZĐ][\wĐ&\-]{0,30})?|\d{1,5}-[A-ZĐ]{1,4}/[A-ZĐ]{1,4})"
SO_HIEU = re.compile(r"(?:(?:%s)\s*(?:liên\s*tịch\s*)?(?:số\s*)?|số\s*)%s" % (QH.LOAI, SO), re.I)
DIEU = re.compile(r"^\s*Điều\s+\d+", re.M)
CUOI_DS = re.compile(r"^\s*(?:Điều\s+\d+|KT\.|TM\.|Nơi\s*nhận|BỘ\s*TRƯỞNG|GIÁM\s*ĐỐC|HIỆU\s*TRƯỞNG)", re.M)
# "bãi bỏ điểm b khoản 2 Điều 4 tại Quyết định X", "thay thế cụm từ ... của X": chỉ đụng
# một phần văn bản đích -> AMENDS, không phải bãi bỏ/thay thế cả văn bản
MOT_PHAN = re.compile(r"một\s*(?:số|phần)|cụm\s*từ|điểm\s+[a-zđ]\b|khoản\s+\d|mục\s+\d|"
                      r"phần\s+[IVX\d]|phụ\s*lục|bảng\s+\d|điều\s+\d", re.I)
# số hiệu thứ hai trở đi mà đứng sau "của/theo/tại" là văn bản được nhắc trong tên văn bản
# đích ("thay thế Thông tư 08/2017 ... thi hành một số điều của Nghị định 91/2017"), bỏ
PHU = re.compile(r"(?:của|theo|tại|hướng\s*dẫn|thi\s*hành)\s*(?:\S+\s*){0,2}$", re.I)
UU_TIEN = {"REPLACES": 0, "REPEALS": 1, "AMENDS": 2}


def khoa(so: str) -> str:
    """Khoá so trùng: bỏ '&' để 15/2004/QĐ-BGD&ĐT trùng 15/2004/QĐ-BGDĐT."""
    return normalize_document_number(so.replace("&", ""))


def _cau(t: str, vt: int) -> tuple[int, int]:
    """Biên câu chứa vị trí vt: từ đầu dòng tới dấu . ; hoặc xuống dòng."""
    dau = t.rfind("\n", 0, vt) + 1
    m = re.compile(r"[.;](?=\s)|\n").search(t, vt)
    return dau, (m.start() if m else len(t))


def _loai(kich: str, doan: str) -> str:
    k = kich.lower()
    if MOT_PHAN.search(doan):
        return "AMENDS"
    return "REPLACES" if "thay" in k else "REPEALS"


def vet(t: str, so_minh: str = "") -> list[dict]:
    """-> [{targetDocumentNumber, relationType, context}] vét được từ toàn văn t."""
    ra: dict[str, dict] = {}
    minh = khoa(so_minh) if so_minh else None
    da_ds: list[tuple[int, int]] = []   # vùng danh sách đã vét, từ kích hoạt lồng bên trong bỏ qua

    def them(so, loai, ctx):
        so = re.sub(r"\s+", "", so).rstrip("-.,;:")
        k = khoa(so)
        if not k or k == minh or (k in ra and UU_TIEN[ra[k]["relationType"]] <= UU_TIEN[loai]):
            return
        ra[k] = {"targetDocumentNumber": so, "relationType": loai,
                         "targetArticle": None, "context": re.sub(r"\s+", " ", ctx).strip()[:400]}

    for m in KICH.finditer(t):
        if QH.trong_can_cu(t, m.start()) or any(a <= m.start() < b for a, b in da_ds):
            continue
        dau, cuoi = _cau(t, m.start())
        cau = t[dau:cuoi]
        sau = t[m.start():cuoi]
        # thể bị động: "được thay thế bởi X", "đã bị bãi bỏ theo X" -> X tác động lên văn bản này
        if QH.NGUOC_TRUOC.search(t[max(0, m.start() - 25):m.end()]) or QH.NGUOC_SAU.search(sau[:60]):
            continue
        loai = _loai(m.group(0), sau[:80])
        # Câu kết bằng dấu hai chấm -> danh sách các mục phía dưới
        if re.search(r":\s*$", t[dau:t.find("\n", m.start()) if "\n" in t[m.start():] else len(t)]):
            het = t.find("\n", m.start())
            c = CUOI_DS.search(t, het + 1)
            vung = t[het + 1:(c.start() if c else len(t))]
            da_ds.append((het + 1, het + 1 + len(vung)))
            for dong in re.split(r"\n(?=\s*(?:\d{1,3}|[a-zđ])[.)]\s)", vung):
                dong = dong.strip()
                if not dong:
                    continue
                s = SO_HIEU.search(dong)
                if s:
                    them(s.group(1), _loai(m.group(0), cau + " " + dong[:s.start()]), dong)
            continue
        # "Quyết định số X ... hết hiệu lực": số hiệu đứng TRƯỚC từ kích hoạt. Câu kiểu này
        # thường kéo theo cả tên dài của văn bản đích, trong tên lại nhắc văn bản khác (0011:
        # "TTLT 20/2014 hướng dẫn ... Nghị định 49/2010 ... và Nghị định 74/2013 ... hết hiệu
        # lực"). Nên chỉ lấy số hiệu ĐỨNG ĐẦU mỗi vế (đầu câu hoặc ngay sau dấu chấm phẩy).
        if "hiệu" in m.group(0).lower():
            for ve in t[dau:m.start()].split(";"):
                s = SO_HIEU.search(ve)
                if s and len(re.sub(r"^\s*(?:\d{1,3}|[a-zđ])[.)]\s*", "", ve[:s.start()])) <= 25:
                    them(s.group(1), loai, cau)
            continue
        for i, s in enumerate(SO_HIEU.finditer(sau)):
            if i and PHU.search(sau[max(0, s.start() - 40):s.start()]):
                continue
            them(s.group(1), _loai(m.group(0), sau[:s.start()]), cau)
    return list(ra.values())


def tim_txt(ma):
    ds = sorted(TXT.rglob(f"{ma}_*.txt"))
    return ds[0] if ds else None


def tim_json(ma):
    ds = sorted(V4.rglob(f"{ma}_*.json"))
    return ds[0] if ds else None


HIEU_LUC = ("REPLACES", "REPEALS", "AMENDS")
TU_THEM = ("REPLACES", "REPEALS")


def do():
    """Đo trên tập chuẩn: luật đơn lẻ, và model + luật (luật chỉ bù chỗ thiếu)."""
    tong = {k: [0, 0, 0, 0, 0] for k in HIEU_LUC}   # chuẩn, luật đúng, luật ra, model đúng, gộp đúng
    sai = []
    for c in sorted((EVAL / "chuan").glob("*.json")):
        g = EVAL / "goc" / c.name
        p = tim_txt(c.stem)
        if not g.exists() or not p:
            continue
        dc, dg = (json.load(open(x, encoding="utf-8")) for x in (c, g))
        t = io.open(p, encoding="utf-8", errors="replace").read()
        luat = vet(t, dg["document"]["documentNumber"])
        k = lambda x: (khoa(x["targetDocumentNumber"]), x["relationType"])
        C = {k(x) for x in dc["citations"]}
        L = {k(x) for x in luat}
        G = {k(x) for x in dg["citations"]}
        for loai in HIEU_LUC:
            c_, l_, g_ = ({x for x in S if x[1] == loai} for S in (C, L, G))
            gop = g_ | {x for x in l_ if loai in TU_THEM and x[0] not in {y[0] for y in G}}
            tong[loai][0] += len(c_); tong[loai][1] += len(l_ & c_); tong[loai][2] += len(l_)
            tong[loai][3] += len(g_ & c_); tong[loai][4] += len(gop & c_)
            for x in l_ - c_:
                sai.append((c.stem, *x))
    print("| Loại | Số trong chuẩn | Model bắt được | Luật bắt được (đúng/ra) | Model + luật |")
    print("|---|---|---|---|---|")
    for loai, (n, ld, lr, md, gd) in tong.items():
        print(f"| {loai} | {n} | {md} ({md / max(n, 1):.0%}) | {ld}/{lr} | {gd} ({gd / max(n, 1):.0%}) |")
    print(f"\nLuật ra mà chuẩn không có ({len(sai)}):")
    for x in sai:
        print("  ", *x)


def ghi(ma, in_ra=True):
    p, j = tim_txt(ma), tim_json(ma)
    if not p or not j:
        return 0
    d = json.load(open(j, encoding="utf-8"))
    t = io.open(p, encoding="utf-8", errors="replace").read()
    da = {khoa(c["targetDocumentNumber"]): c["relationType"] for c in d["citations"]}
    # Chỉ tự thêm REPLACES/REPEALS: đo trên tập chuẩn luật đúng 17/17 và 92/92, còn AMENDS
    # chỉ 4/10 (ranh giới "sửa một phần" với "nhắc tên văn bản" quá mờ) — AMENDS để model lo.
    vet_ra = [x for x in vet(t, d["document"]["documentNumber"]) if x["relationType"] in TU_THEM]
    moi = [x for x in vet_ra if khoa(x["targetDocumentNumber"]) not in da]
    # Số hiệu đã có nhưng model gán loại khác: không tự đổi, chỉ báo để kiểm bằng ảnh PDF.
    # (Nhóm 4, 0432: model ghi REPEALS cho 6 thông tư mà Điều 17 viết "thay thế" — luật đúng.)
    for x in vet_ra:
        k = khoa(x["targetDocumentNumber"])
        if k in da and da[k] != x["relationType"] and in_ra:
            print(f"  ? {ma}: {x['targetDocumentNumber']} JSON ghi {da[k]}, luật đọc ra "
                  f"{x['relationType']} — kiểm ảnh PDF: {x['context'][:90]}")
    if not moi:
        return 0
    d["citations"].extend(moi)
    note = (d.get("note") or "").rstrip()
    cau = "Thêm %d quan hệ hiệu lực do vet_quan_he.py vét từ toàn văn: %s." % (
        len(moi), ", ".join(f"{x['relationType']} {x['targetDocumentNumber']}" for x in moi))
    d["note"] = f"{note}{'' if not note or note.endswith('.') else '.'} {cau}".strip()
    j.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    if in_ra:
        print(f"  + {ma}: {cau}")
    return len(moi)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--do", action="store_true")
    ap.add_argument("--chi", default="")
    ap.add_argument("--ghi", action="store_true")
    a = ap.parse_args()
    if a.do:
        return do()
    for ma in [x.strip() for x in a.chi.split(",") if x.strip()]:
        if a.ghi:
            ghi(ma)
            continue
        p = tim_txt(ma)
        if not p:
            continue
        for x in vet(io.open(p, encoding="utf-8", errors="replace").read()):
            print(f"{ma}  {x['relationType']:9} {x['targetDocumentNumber']:28} {x['context'][:70]}")


if __name__ == "__main__":
    main()
