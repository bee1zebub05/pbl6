"""
Truy vấn cho GraphRAG (local search) trên Article — chỉ chứa Cypher và hàm
chạy trên một session, không chứa thuật toán gộp/đóng gói (xem
core/chat/retrieval/graph_rag.py). Bốn bước:

  1. seed_vector / seed_fulltext — Điều hạt giống theo hai nguồn độc lập
     (vector index `article_embedding`, fulltext BM25 `article_text`).
  2. scoped_articles — Điều gần nghĩa nhất NẰM TRONG các văn bản cho trước
     (văn bản template vừa trả về); chấm cosine trực tiếp, không cần index.
  3. expand_documents — mở rộng theo quan hệ quanh văn bản chứa Điều: cơ quan
     ban hành, bị thay thế / bãi bỏ / sửa đổi bởi ai, căn cứ chính.
  4. neighbor_articles — Điều liền trước / liền sau trong cùng văn bản (hoặc
     cùng nội dung kèm theo), cho Điều hạt giống quá ngắn để tự đứng.

Mọi bước bỏ qua Điều "hiệu lực thi hành / trách nhiệm thi hành"
(isImplementationClause) — chúng gần nghĩa với hầu hết câu hỏi nhưng không
mang nội dung quy định.
"""

from __future__ import annotations

from .. import config
from .. import db
from .entity_resolver import keyword_query, resolve_fulltext_phrase
from .templates.base import ARTICLE_TO_DOC

# Cột chung của một Điều hạt giống: Điều + văn bản chứa nó + nội dung kèm
# theo chứa nó (nếu có). Biến: node (Article), d (Document).
_SEED_RETURN = """
    OPTIONAL MATCH (nc:NormativeContent)-[:HAS_ARTICLE]->(node)
    RETURN node.articleId AS articleId, node.number AS number, node.heading AS heading, node.text AS text,
           d.normalizedNumber AS docKey, d.documentNumber AS documentNumber, nc.title AS container, score
    ORDER BY score DESC
    LIMIT $k
"""

_NOT_IMPLEMENTATION = "NOT coalesce(node.isImplementationClause, false)"

SEED_VECTOR = f"""
    CALL db.index.vector.queryNodes($indexName, $candidates, $queryVector) YIELD node, score
    WHERE {_NOT_IMPLEMENTATION}
    MATCH {ARTICLE_TO_DOC}
    WITH DISTINCT node, score, d
    {_SEED_RETURN}
"""

SEED_FULLTEXT = f"""
    CALL db.index.fulltext.queryNodes('article_text', $luceneQuery, {{limit: $candidates}}) YIELD node, score
    WHERE {_NOT_IMPLEMENTATION}
    MATCH {ARTICLE_TO_DOC}
    WITH DISTINCT node, score, d
    {_SEED_RETURN}
"""

SCOPED_ARTICLES = f"""
    MATCH (d:Document) WHERE d.normalizedNumber IN $docKeys
    CALL (d) {{
        MATCH (d)-[:PROMULGATES|HAS_ARTICLE*1..2]->(node:Article)
        WHERE node.embedding IS NOT NULL AND {_NOT_IMPLEMENTATION}
        WITH node, vector.similarity.cosine(node.embedding, $queryVector) AS score
        ORDER BY score DESC
        LIMIT $perDoc
        RETURN node, score
    }}
    OPTIONAL MATCH (nc:NormativeContent)-[:HAS_ARTICLE]->(node)
    RETURN node.articleId AS articleId, node.number AS number, node.heading AS heading, node.text AS text,
           d.normalizedNumber AS docKey, d.documentNumber AS documentNumber, nc.title AS container, score
    ORDER BY score DESC
"""

# Văn bản liên quan dạng gọn — dùng cho mọi nhóm quan hệ ở EXPAND_DOCUMENTS.
_REF = "{documentNumber: t.documentNumber, title: t.title, status: t.status, issueDate: t.issueDate}"

EXPAND_DOCUMENTS = f"""
    UNWIND $docKeys AS key
    MATCH (d:Document {{normalizedNumber: key}})
    CALL (d) {{
        OPTIONAL MATCH (d)-[:ISSUED_BY]->(o:Organization)
        RETURN collect(DISTINCT o.name) AS issuers
    }}
    CALL (d) {{
        OPTIONAL MATCH (t:Document)-[:REPLACES]->(d)
        WITH t ORDER BY t.issueDate DESC
        RETURN [x IN collect({_REF}) WHERE x.documentNumber IS NOT NULL][..$maxRelated] AS replacedBy
    }}
    CALL (d) {{
        OPTIONAL MATCH (t:Document)-[:REPEALS]->(d)
        WITH t ORDER BY t.issueDate DESC
        RETURN [x IN collect({_REF}) WHERE x.documentNumber IS NOT NULL][..$maxRelated] AS repealedBy
    }}
    CALL (d) {{
        OPTIONAL MATCH (t:Document)-[r:AMENDS]->(d)
        WITH t, r ORDER BY t.issueDate DESC
        RETURN [x IN collect({{documentNumber: t.documentNumber, title: t.title, status: t.status,
                               issueDate: t.issueDate, targetArticle: r.targetArticle}})
                WHERE x.documentNumber IS NOT NULL][..$maxRelated] AS amendedBy
    }}
    CALL (d) {{
        OPTIONAL MATCH (d)-[:BASED_ON]->(t:Document)
        WITH t ORDER BY t.isStub, t.issueDate DESC
        RETURN [x IN collect({_REF}) WHERE x.documentNumber IS NOT NULL][..$maxRelated] AS basedOn
    }}
    RETURN key AS docKey, d.documentNumber AS documentNumber, d.title AS title, d.documentType AS documentType,
           d.issueDate AS issueDate, d.status AS status, issuers, replacedBy, repealedBy, amendedBy, basedOn
"""

# Điều liền kề: cùng nút cha trực tiếp (Document hoặc NormativeContent), số
# Điều lệch đúng 1 — tránh lẫn "Điều 1" của quyết định với "Điều 1" của quy chế kèm theo.
_ARTICLE_NO = "toInteger(replace({v}.number, 'Điều ', ''))"

NEIGHBOR_ARTICLES = f"""
    UNWIND $articleIds AS id
    MATCH (p)-[:HAS_ARTICLE]->(a:Article {{articleId: id}})
    WITH id, p, {_ARTICLE_NO.format(v="a")} AS n
    WHERE n IS NOT NULL
    MATCH (p)-[:HAS_ARTICLE]->(nb:Article)
    WHERE {_ARTICLE_NO.format(v="nb")} IN [n - 1, n + 1]
    RETURN id AS articleId, nb.articleId AS neighborId, nb.number AS number, nb.heading AS heading, nb.text AS text
    ORDER BY id, {_ARTICLE_NO.format(v="nb")}
"""


def _run(session_, cypher: str, params: dict) -> list[dict]:
    return db.run_in_session(session_, cypher, params,
                                          timeout_seconds=config.CYPHER_TIMEOUT_SECONDS).rows


def seed_vector(session_, query_vector: list[float], k: int) -> list[dict]:
    # Xin dư ứng viên vì bước lọc Điều thi hành chạy SAU khi index trả kết quả.
    return _run(session_, SEED_VECTOR, {"indexName": config.VECTOR_INDEX_NAME, "candidates": k * 3,
                                        "queryVector": query_vector, "k": k})


def fulltext_query(question: str, phrase: str | None = None) -> str:
    """Truy vấn Lucene cho seed BM25. `phrase`: cụm nội dung router đã trích
    (slot phrase) — chính xác hơn từ khoá rút từ cả câu hỏi, nên được dùng thay khi có."""

    return resolve_fulltext_phrase(phrase) if phrase else keyword_query(question)


def seed_fulltext(session_, question: str, k: int, phrase: str | None = None) -> list[dict]:
    query = fulltext_query(question, phrase)
    if not query:
        return []
    return _run(session_, SEED_FULLTEXT, {"luceneQuery": query, "candidates": k * 3, "k": k})


def scoped_articles(session_, query_vector: list[float], doc_keys: list[str], per_doc: int) -> list[dict]:
    """`doc_keys`: khoá chuẩn hoá (Document.normalizedNumber)."""

    if not doc_keys:
        return []
    return _run(session_, SCOPED_ARTICLES, {"docKeys": doc_keys, "queryVector": query_vector, "perDoc": per_doc})


def expand_documents(session_, doc_keys: list[str], max_related: int) -> list[dict]:
    if not doc_keys:
        return []
    return _run(session_, EXPAND_DOCUMENTS, {"docKeys": doc_keys, "maxRelated": max_related})


def neighbor_articles(session_, article_ids: list[str]) -> list[dict]:
    if not article_ids:
        return []
    return _run(session_, NEIGHBOR_ARTICLES, {"articleIds": article_ids})
