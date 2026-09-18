"""
Ba hệ truy hồi: BM25, KG, HYBRID.

Đây là **động cơ tìm kiếm**, không phải phần đo đạc. Trước đây nó nằm trong
`eval/retrieval.py` cùng với bộ câu hỏi và các số đo — nghĩa là muốn trả lời một
câu hỏi thật thì phải import cả thư mục đánh giá. Tách ra để `eval/` chỉ còn
việc chấm điểm, còn ai cần truy hồi thì gọi thẳng vào đây.

Dùng full-text index sẵn có của Neo4j làm BM25 thay vì dựng một hệ riêng: cả ba
hệ khi đó đọc **đúng một kho, đúng một bản text** — chênh lệch đo được là do
cách truy vấn chứ không do khác dữ liệu. Neo4j chấm điểm bằng Lucene, tức đúng
BM25.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict

from ..core import config

_KG_CYPHER = {
    "theo_co_quan": (
        "MATCH (d:Document)-[:ISSUED_BY]->(o:Organization {name: $ten}) "
        "WHERE d.is_stub = false AND d.status = 'CON_HIEU_LUC' "
        "RETURN d.so_hieu_norm AS key, d.authority_level AS diem "
        "ORDER BY d.issueDate DESC LIMIT 50"
    ),
    "theo_linh_vuc": (
        "MATCH (d:Document)-[:HAS_TOPIC]->(t:Topic {name: $ten}) "
        "WHERE d.is_stub = false AND d.status = 'CON_HIEU_LUC' "
        "RETURN d.so_hieu_norm AS key, d.authority_level AS diem "
        "ORDER BY d.authority_level DESC LIMIT 50"
    ),
    "thay_the": (
        "MATCH (a:Document)-[:REPLACES]->(b:Document {so_hieu_norm: $key}) "
        "RETURN a.so_hieu_norm AS key, 1.0 AS diem"
    ),
    "quy_che_con_hieu_luc": (
        "MATCH (d:Document)-[:PROMULGATES]->(c:NormativeContent) "
        "WHERE c.contentType = $loai AND c.status = 'CON_HIEU_LUC' "
        "RETURN d.so_hieu_norm AS key, 1.0 AS diem LIMIT 50"
    ),
    "can_cu_goc": (
        "MATCH (x:Document {so_hieu_norm: $key})-[:BASED_ON*1..3]->(b:Document) "
        "WHERE b.authority_level >= 4 "
        "RETURN DISTINCT b.so_hieu_norm AS key, "
        "toFloat(b.authority_level) AS diem ORDER BY diem DESC LIMIT 50"
    ),
}

# Lucene nuốt các ký tự này như cú pháp truy vấn -> phải bỏ đi, không thì
# `10/2016/TT-BGDĐT` làm vỡ cả câu.
_LUCENE_DAC_BIET = re.compile(r'[+\-!(){}\[\]^"~*?:\\/&|]')


def _bm25(driver, tu_khoa: str, k: int = 50) -> list[tuple[str, float]]:
    sach = _LUCENE_DAC_BIET.sub(" ", tu_khoa).strip()

    if not sach:
        return []

    with driver.session(database=config.NEO4J_DATABASE) as s:
        rows = s.run(
            "CALL db.index.fulltext.queryNodes('doc_text', $q) YIELD node, score "
            "WHERE node.is_stub = false "
            "RETURN node.so_hieu_norm AS key, score LIMIT $k",
            q=sach,
            k=k,
        ).data()

    return [(r["key"], r["score"]) for r in rows]


def _kg(driver, q: dict, k: int = 50) -> list[tuple[str, float]]:
    cypher = _KG_CYPHER.get(q["loai_truy_van"])

    if not cypher:
        return []

    params = json.loads(q["cypher_tham_so"] or "{}")

    with driver.session(database=config.NEO4J_DATABASE) as s:
        rows = s.run(cypher, **params).data()

    return [(r["key"], float(r["diem"] or 0)) for r in rows][:k]


def _hybrid(driver, q: dict, k: int = 50) -> list[tuple[str, float]]:
    """
    BM25 lọc ứng viên -> KG mở rộng theo quan hệ -> trộn bằng RRF.

    Reciprocal Rank Fusion thay vì cộng điểm thô: điểm Lucene và bậc thẩm quyền
    không cùng thang đo, cộng thẳng thì hệ nào có thang lớn hơn sẽ nuốt hệ kia.
    RRF chỉ dùng **thứ hạng**, nên miễn nhiễm với chuyện đó.
    """

    bm = _bm25(driver, q["tu_khoa"], k)
    kg = _kg(driver, q, k)

    diem: dict[str, float] = defaultdict(float)

    for hang, (key, _) in enumerate(bm, start=1):
        diem[key] += 1 / (60 + hang)

    for hang, (key, _) in enumerate(kg, start=1):
        diem[key] += 1 / (60 + hang)

    # Mở rộng một bậc từ top-5 của BM25 theo quan hệ — đây là phần "KG mở rộng"
    # mà §6.4 mô tả, và là chỗ hybrid ăn điểm ở nhóm multi-hop.
    hat_giong = [key for key, _ in bm[:5]]

    if hat_giong:
        with driver.session(database=config.NEO4J_DATABASE) as s:
            rows = s.run(
                "MATCH (d:Document)-[:BASED_ON|REFERENCES]->(b:Document) "
                "WHERE d.so_hieu_norm IN $keys AND b.is_stub = false "
                "RETURN DISTINCT b.so_hieu_norm AS key",
                keys=hat_giong,
            ).data()

        for hang, row in enumerate(rows, start=1):
            diem[row["key"]] += 0.5 / (60 + hang)

    return sorted(diem.items(), key=lambda x: -x[1])[:k]


HE = {"bm25": lambda d, q, k: _bm25(d, q["tu_khoa"], k), "kg": _kg, "hybrid": _hybrid}
