"""Kiểu dữ liệu của một câu Cypher trong bộ đo, dùng chung cho cả ba catalog."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Query:
    name: str
    cypher: str
    expected_rows: int | None
    kind: str  # lookup | multihop | fulltext | hybrid | sanity | distribution | ranking | anomaly
    note: str
    # 2 field dưới CHỈ catalogs/scenarios.py dùng (mặc định None, không ảnh
    # hưởng các Query ở samples.py/benchmark.py) — cho phép runner.py chấm
    # precision/recall/F1 bằng cách so TẬP ID, không chỉ đếm số dòng. Thiết kế
    # để tái dùng khi có nguồn kết quả khác ngoài Cypher (BM25, semantic
    # retrieval...) — chỉ cần đưa list ID vào scoring.score_ids, không cần xây
    # evaluate riêng.
    id_field: str | None = None  # cột trong RETURN dùng làm "khoá" (vd "documentNumber")
    expected_ids: frozenset[str] | None = None  # ground-truth đã verify thật; None = chưa có/không áp dụng


def hybrid_expand_cypher(*, fulltext_query: str, seed_limit: int, final_limit: int | None = None) -> str:
    """Cypher hybrid fulltext(doc_text) -> mở rộng BASED_ON|REFERENCES, chiều
    XUÔI (node khớp full-text -> văn bản gốc thẩm quyền nó dựa trên) — dùng
    chung bởi Q10 (samples.py), B14 (benchmark.py) và S16 (scenarios.py), chỉ
    khác seed_limit/final_limit."""

    limit_clause = f"\n            LIMIT {final_limit}" if final_limit is not None else ""
    return f"""
            CALL db.index.fulltext.queryNodes('doc_text', {fulltext_query!r}) YIELD node, score
            WITH node, score ORDER BY score DESC LIMIT {seed_limit}
            MATCH (node)-[:BASED_ON|REFERENCES*0..2]->(expanded:Document)
            RETURN DISTINCT expanded.documentNumber AS documentNumber, expanded.authorityLevel AS level
            ORDER BY level DESC{limit_clause}
        """
