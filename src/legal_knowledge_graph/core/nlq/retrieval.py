"""
Truy xuất ngữ nghĩa (vector) trên Article — chạy SONG SONG luồng Cypher
hiện có (Stage A/B), không thay thế. Đồng đội ghép output này với `rows`
của Cypher để làm ngữ cảnh cho LLM sinh câu trả lời cuối — việc đó ngoài
phạm vi module này.
"""

from __future__ import annotations

from .. import config
from . import execute, gemini_client

_CYPHER = """
    CALL db.index.vector.queryNodes($indexName, $k, $queryVector) YIELD node, score
    OPTIONAL MATCH (doc1:Document)-[:HAS_ARTICLE]->(node)
    OPTIONAL MATCH (doc2:Document)-[:PROMULGATES]->(:NormativeContent)-[:HAS_ARTICLE]->(node)
    WITH node, score, coalesce(doc1, doc2) AS doc
    RETURN node.articleId AS articleId, node.heading AS heading, node.text AS text,
           score, doc.documentNumber AS documentNumber, doc.status AS status
    ORDER BY score DESC
"""


def retrieve(question: str, session_, k: int | None = None) -> list[dict]:
    """Embed câu hỏi (task_type=RETRIEVAL_QUERY — bất đối xứng với
    RETRIEVAL_DOCUMENT lúc backfill, xem embed_articles.py), tìm k Article
    gần nghĩa nhất qua vector index, kèm Document cha + trạng thái hiệu
    lực. Xử lý CẢ 2 nhánh HAS_ARTICLE (trực tiếp / qua NormativeContent)
    — thiếu 1 nhánh sẽ mất documentNumber/status cho đúng nửa số Article."""

    top_k = k if k is not None else config.NLQ_RETRIEVAL_TOP_K
    query_vector = gemini_client.call_embed(
        [question], task_type="RETRIEVAL_QUERY", output_dimensionality=config.NLQ_EMBED_DIMENSIONS,
    )[0]

    result = execute.run_in_session(
        session_, _CYPHER,
        {"indexName": config.NLQ_VECTOR_INDEX_NAME, "k": top_k, "queryVector": query_vector},
        timeout_seconds=config.NLQ_QUERY_TIMEOUT_SECONDS,
    )
    return result.rows
