"""
§6.3–6.5 — bộ câu hỏi, ba hệ tìm kiếm, và số đo retrieval.

## Ba hệ (§6.4)

    BM25    tìm kiếm văn bản thuần, dùng full-text index của Neo4j
    KG      trả lời bằng truy vấn Cypher đi theo quan hệ
    HYBRID  BM25 lọc ứng viên -> KG mở rộng theo quan hệ, rồi trộn điểm

Dùng full-text index sẵn có của Neo4j làm BM25 thay vì dựng một hệ riêng: cả ba
hệ khi đó đọc **đúng một kho, đúng một bản text** — chênh lệch đo được là do
cách truy vấn chứ không do khác dữ liệu. Neo4j chấm điểm bằng Lucene, tức đúng
BM25.

## Gold answer ở đâu ra

Đây là chỗ dễ tự lừa mình nhất. Với nhóm câu hỏi **single-hop dựa trên
metadata** (cơ quan ban hành, lĩnh vực, tình trạng hiệu lực), đáp án đúng suy
thẳng từ metadata crawler — nguồn này **không phải** đầu ra của hệ thống đang
được chấm, nên tự sinh được, không thiên lệch.

Với nhóm **multi-hop** và **hiệu lực**, đáp án phụ thuộc vào chính các quan hệ
mà ta đang muốn đánh giá. Tự sinh đáp án từ graph rồi chấm graph là lập luận
vòng tròn. Nên phần này chỉ sinh **khung câu hỏi**, cột đáp án để trống cho
người điền sau khi đọc văn bản.

Mỗi câu hỏi trong `queries.csv` vì vậy có cột `nguon_dap_an`:

    metadata  -> máy tự điền, dùng được ngay
    nguoi     -> người phải điền, để trống thì câu đó bị bỏ khi chấm
"""

from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path

from ..core import config
from ..core.console import say
from ..rag.engines import HE, _bm25, _hybrid, _kg

NHOM = ("single-hop", "multi-hop", "hieu-luc")
K_MAC_DINH = (1, 3, 5, 10)


# ============================================================
# SINH BỘ CÂU HỎI
# ============================================================

_COT = [
    "id",
    "nhom",
    "cau_hoi",
    "tu_khoa",        # chuỗi đưa cho BM25
    "cypher_tham_so", # JSON tham số cho truy vấn KG
    "loai_truy_van",  # tên mẫu Cypher bên dưới
    "nguon_dap_an",
    "DAP_AN",         # danh sách số hiệu, ngăn bằng ';'
]


def _q(idx: int, nhom: str, **kw) -> dict:
    return {"id": f"Q{idx:03d}", "nhom": nhom, **kw}


def sinh_cau_hoi(driver, so_luong: int = 45) -> list[dict]:
    """
    Sinh bộ câu hỏi từ chính dữ liệu trong graph.

    Không bịa câu hỏi trên trời: mọi thực thể được nhắc tới (tên đơn vị, lĩnh
    vực, số hiệu) đều lấy từ graph, nên câu nào cũng có ít nhất một đáp án.
    """

    cau_hoi: list[dict] = []
    idx = 1

    with driver.session(database=config.NEO4J_DATABASE) as s:
        # --- single-hop: đáp án suy từ metadata, tự sinh được ---
        orgs = s.run(
            "MATCH (d:Document)-[:ISSUED_BY]->(o:Organization) "
            "WHERE d.is_stub = false AND d.status = 'CON_HIEU_LUC' "
            "WITH o, count(d) AS n WHERE n >= 5 "
            "RETURN o.name AS ten ORDER BY n DESC LIMIT 6"
        ).data()

        for org in orgs:
            cau_hoi.append(
                _q(idx, "single-hop",
                   cau_hoi=f"Văn bản nào do {org['ten']} ban hành và còn hiệu lực?",
                   tu_khoa=org["ten"],
                   cypher_tham_so=json.dumps({"ten": org["ten"]}, ensure_ascii=False),
                   loai_truy_van="theo_co_quan",
                   nguon_dap_an="metadata", DAP_AN="")
            )
            idx += 1

        topics = s.run(
            "MATCH (d:Document)-[:HAS_TOPIC]->(t:Topic) "
            "WHERE d.is_stub = false WITH t, count(d) AS n WHERE n >= 8 "
            "RETURN t.name AS ten ORDER BY n DESC LIMIT 8"
        ).data()

        for topic in topics:
            cau_hoi.append(
                _q(idx, "single-hop",
                   cau_hoi=f"Các văn bản còn hiệu lực về lĩnh vực {topic['ten']}?",
                   tu_khoa=topic["ten"],
                   cypher_tham_so=json.dumps({"ten": topic["ten"]}, ensure_ascii=False),
                   loai_truy_van="theo_linh_vuc",
                   nguon_dap_an="metadata", DAP_AN="")
            )
            idx += 1

        # --- hiệu lực: đáp án phải người xác nhận ---
        thay_the = s.run(
            "MATCH (a:Document)-[:REPLACES]->(b:Document) "
            "WHERE b.is_stub = false "
            "RETURN b.so_hieu_norm AS cu, b.so_hieu AS hien LIMIT 10"
        ).data()

        for row in thay_the:
            cau_hoi.append(
                _q(idx, "hieu-luc",
                   cau_hoi=f"Văn bản nào thay thế {row['hien']}?",
                   tu_khoa=row["hien"],
                   cypher_tham_so=json.dumps({"key": row["cu"]}, ensure_ascii=False),
                   loai_truy_van="thay_the",
                   nguon_dap_an="nguoi", DAP_AN="")
            )
            idx += 1

        con_hieu_luc = s.run(
            "MATCH (d:Document)-[:PROMULGATES]->(c:NormativeContent) "
            "WHERE c.contentType = 'Quy chế' AND c.status = 'CON_HIEU_LUC' "
            "RETURN d.so_hieu AS sh, c.title AS ten LIMIT 5"
        ).data()

        for row in con_hieu_luc:
            ten = " ".join((row["ten"] or "").split())[:60]
            cau_hoi.append(
                _q(idx, "hieu-luc",
                   cau_hoi=f"Quy chế nào đang có hiệu lực về: {ten}?",
                   tu_khoa=ten,
                   cypher_tham_so=json.dumps({"loai": "Quy chế"}, ensure_ascii=False),
                   loai_truy_van="quy_che_con_hieu_luc",
                   nguon_dap_an="nguoi", DAP_AN="")
            )
            idx += 1

        # --- multi-hop: chỗ KG phải thắng BM25 rõ rệt (§6.5) ---
        chuoi = s.run(
            "MATCH (x:Document)-[:BASED_ON*2..3]->(b:Document) "
            "WHERE x.is_stub = false AND x.authority_level <= 2 "
            "AND b.authority_level >= 4 "
            "WITH x, count(DISTINCT b) AS n WHERE n >= 2 "
            "RETURN x.so_hieu AS sh, x.so_hieu_norm AS key, left(x.title, 60) AS ten "
            "ORDER BY n DESC LIMIT 16"
        ).data()

        for row in chuoi:
            cau_hoi.append(
                _q(idx, "multi-hop",
                   cau_hoi=f"{row['sh']} dựa trên những Luật / Nghị định gốc nào?",
                   tu_khoa=f"{row['sh']} {row['ten']}",
                   cypher_tham_so=json.dumps({"key": row["key"]}, ensure_ascii=False),
                   loai_truy_van="can_cu_goc",
                   nguon_dap_an="nguoi", DAP_AN="")
            )
            idx += 1

    return cau_hoi[:so_luong]


# ============================================================
# ĐÁP ÁN TỰ SINH TỪ METADATA
# ============================================================

_GOLD_METADATA = {
    "theo_co_quan": (
        "MATCH (d:Document)-[:ISSUED_BY]->(o:Organization {name: $ten}) "
        "WHERE d.is_stub = false AND d.status = 'CON_HIEU_LUC' "
        "RETURN d.so_hieu_norm AS key"
    ),
    "theo_linh_vuc": (
        "MATCH (d:Document)-[:HAS_TOPIC]->(t:Topic {name: $ten}) "
        "WHERE d.is_stub = false AND d.status = 'CON_HIEU_LUC' "
        "RETURN d.so_hieu_norm AS key"
    ),
}


def dien_dap_an_metadata(driver, cau_hoi: list[dict]) -> int:
    """
    Điền `DAP_AN` cho các câu suy được từ metadata.

    An toàn về mặt phương pháp: `ISSUED_BY` / `HAS_TOPIC` / `status` đều lấy
    thẳng từ metadata crawler ở Bước 0, **không** phải kết quả trích xuất của
    Bước 2–3 đang được đem ra chấm.
    """

    n = 0

    with driver.session(database=config.NEO4J_DATABASE) as s:
        for q in cau_hoi:
            if q["nguon_dap_an"] != "metadata" or q["DAP_AN"]:
                continue

            cypher = _GOLD_METADATA.get(q["loai_truy_van"])

            if not cypher:
                continue

            params = json.loads(q["cypher_tham_so"])
            keys = [r["key"] for r in s.run(cypher, **params)]

            q["DAP_AN"] = ";".join(sorted(keys))
            n += 1

    return n


# ============================================================
# SỐ ĐO (§6.4)
# ============================================================

def _dcg(rel: list[int]) -> float:
    return sum(r / math.log2(i + 2) for i, r in enumerate(rel))


def do_mot_cau(ket_qua: list[str], gold: set[str], ks=K_MAC_DINH) -> dict:
    """P@k, R@k, MRR, nDCG@k cho một câu hỏi."""

    rel = [1 if key in gold else 0 for key in ket_qua]
    so_do: dict = {}

    for k in ks:
        top = rel[:k]
        so_do[f"P@{k}"] = sum(top) / k
        so_do[f"R@{k}"] = sum(top) / len(gold) if gold else 0.0
        so_do[f"nDCG@{k}"] = (
            _dcg(top) / _dcg(sorted(rel, reverse=True)[:k])
            if any(rel[:k]) or any(rel)
            else 0.0
        )

    hang_dau = next((i + 1 for i, r in enumerate(rel) if r), 0)
    so_do["MRR"] = 1 / hang_dau if hang_dau else 0.0

    return so_do


def chay(
    driver,
    cau_hoi: list[dict],
    out_dir: Path,
    k_max: int = 50,
) -> dict:
    """Chạy cả ba hệ trên mọi câu có đáp án, ghi kết quả thô + số đo."""

    co_gold = [q for q in cau_hoi if (q.get("DAP_AN") or "").strip()]
    thieu_gold = len(cau_hoi) - len(co_gold)

    chi_tiet_path = out_dir / "retrieval_runs.jsonl"
    tich: dict[str, dict[str, list[float]]] = {
        he: defaultdict(list) for he in HE
    }
    theo_nhom: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )

    with chi_tiet_path.open("w", encoding="utf-8") as handle:
        for q in co_gold:
            gold = {x.strip() for x in q["DAP_AN"].split(";") if x.strip()}

            for ten_he, ham in HE.items():
                try:
                    ket_qua = [key for key, _ in ham(driver, q, k_max)]
                except Exception as exc:  # truy vấn hỏng thì ghi lại, đừng chết
                    handle.write(
                        json.dumps(
                            {"id": q["id"], "he": ten_he, "loi": str(exc)[:200]},
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    continue

                so_do = do_mot_cau(ket_qua, gold)

                handle.write(
                    json.dumps(
                        {
                            "id": q["id"],
                            "nhom": q["nhom"],
                            "he": ten_he,
                            "cau_hoi": q["cau_hoi"],
                            "so_ket_qua": len(ket_qua),
                            "top10": ket_qua[:10],
                            "gold": sorted(gold),
                            "so_do": {k: round(v, 4) for k, v in so_do.items()},
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

                for ten, gia_tri in so_do.items():
                    tich[ten_he][ten].append(gia_tri)
                    theo_nhom[(q["nhom"], ten_he)][ten].append(gia_tri)

    def tb(d: dict[str, list[float]]) -> dict:
        return {k: round(sum(v) / len(v), 4) for k, v in d.items() if v}

    return {
        "so_cau_hoi": len(cau_hoi),
        "co_dap_an": len(co_gold),
        "thieu_dap_an": thieu_gold,
        "tong_the": {he: tb(tich[he]) for he in HE},
        "theo_nhom": {
            f"{nhom}|{he}": tb(v) for (nhom, he), v in sorted(theo_nhom.items())
        },
    }


# ============================================================
# ĐỌC / GHI BỘ CÂU HỎI
# ============================================================

def doc_cau_hoi(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def ghi_cau_hoi(path: Path, cau_hoi: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_COT)
        writer.writeheader()

        for q in cau_hoi:
            writer.writerow({c: q.get(c, "") for c in _COT})


def xuat_bao_cao(ket_qua: dict, out_dir: Path) -> Path:
    lines = [
        "# §6.3–6.5 — So sánh BM25 / KG / Hybrid",
        "",
        f"Bộ câu hỏi: **{ket_qua['so_cau_hoi']}** câu, "
        f"**{ket_qua['co_dap_an']}** câu đã có đáp án.",
    ]

    if ket_qua["thieu_dap_an"]:
        lines += [
            "",
            f"> ⚠️ {ket_qua['thieu_dap_an']} câu chưa có đáp án nên bị bỏ qua. "
            "Điền cột `DAP_AN` trong `queries.csv` rồi chạy lại.",
        ]

    cot = ["P@1", "P@5", "R@5", "R@10", "MRR", "nDCG@10"]

    lines += ["", "## Tổng thể", "", "| Hệ | " + " | ".join(cot) + " |",
              "|---" * (len(cot) + 1) + "|"]

    for he in ("bm25", "kg", "hybrid"):
        m = ket_qua["tong_the"].get(he, {})
        lines.append(
            f"| **{he.upper()}** | "
            + " | ".join(f"{m.get(c, 0):.3f}" for c in cot)
            + " |"
        )

    nhom_co_diem = {k.split("|")[0] for k in ket_qua["theo_nhom"]}
    thieu = [n for n in NHOM if n not in nhom_co_diem]

    lines += [
        "",
        "## Theo nhóm câu hỏi",
        "",
        "§6.5 yêu cầu tách riêng nhóm **multi-hop** — đây là chỗ KG/Hybrid phải",
        "thắng BM25 rõ rệt; nếu không thì phải giải thích tại sao.",
        "",
        "| Nhóm | Hệ | " + " | ".join(cot) + " |",
        "|---" * (len(cot) + 2) + "|",
    ]

    for khoa in sorted(ket_qua["theo_nhom"]):
        nhom, he = khoa.split("|")
        m = ket_qua["theo_nhom"][khoa]
        lines.append(
            f"| {nhom} | {he} | "
            + " | ".join(f"{m.get(c, 0):.3f}" for c in cot)
            + " |"
        )

    if thieu:
        lines += [
            "",
            "> ⬜ Chưa có câu nào được chấm ở nhóm: "
            + ", ".join(f"**{n}**" for n in thieu)
            + ". Hai nhóm `multi-hop` và `hieu-luc` **không tự sinh đáp án "
            "được** — suy đáp án từ chính graph rồi đem chấm graph là lập luận "
            "vòng tròn. Phải người đọc văn bản rồi điền cột `DAP_AN`.",
        ]

    lines.append("")

    path = out_dir / "retrieval.md"
    path.write_text("\n".join(lines), encoding="utf-8")

    return path
