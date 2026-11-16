"""
Các hệ truy hồi đối chứng cho 20 kịch bản — mỗi hệ nhận một case
(`Query`, dùng `question` và `id_field`) và trả danh sách ID theo thứ hạng,
hoặc None khi hệ đó không có cách trả lời loại đáp án này.

    bm25        nguyên câu hỏi -> full-text index theo đơn vị đáp án (bm25.py)
    bm25_full   như bm25 nhưng tìm thêm trong TOÀN VĂN các Điều rồi gộp lên
                văn bản / nội dung kèm theo chứa Điều đó (RRF với bm25)
    vector      embedding câu hỏi -> vector index `article_embedding` trên
                Article, gộp lên đơn vị đáp án theo điểm cao nhất
    hybrid      RRF(bm25_full, vector) — từ khoá + ngữ nghĩa
    hybrid_kg   §6.4 Ontology: hybrid lọc văn bản hạt giống, KG mở rộng một
                bước theo quan hệ căn cứ / thay thế / sửa đổi / bãi bỏ
    hybrid_rerank  RRF ở mức Điều, 16 Điều đầu được reranker xếp lại
                (core/llm/rerank.py) rồi mới gộp lên đơn vị đáp án

Gộp bằng Reciprocal Rank Fusion (chỉ dùng thứ hạng) vì điểm BM25 và cosine
không cùng thang đo.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from . import bm25, db  # noqa: F401  (db nạp .env trước khi đọc biến LKG_EMBED_*)
from .query import Query

RRF_K = 60
ARTICLE_CANDIDATES = 500

# Điều -> văn bản chứa nó: trực tiếp (Điều "vỏ bọc") hoặc qua nội dung kèm theo.
_ART_TO_DOC = "(d:Document)-[:HAS_ARTICLE|PROMULGATES*1..2]->(node)"
_ART_TO_CONTENT = "(d:NormativeContent)-[:HAS_ARTICLE]->(node)"


def rrf(*rankings: list[str]) -> list[str]:
    score: dict[str, float] = {}
    for ranking in rankings:
        for pos, key in enumerate(ranking):
            score[key] = score.get(key, 0.0) + 1.0 / (RRF_K + pos + 1)
    return sorted(score, key=lambda k: -score[k])


def _rollup(session, call: str, params: dict, field: str) -> list[str]:
    """Điều khớp (theo `call`) -> đơn vị đáp án, xếp theo điểm Điều cao nhất."""

    if field == "articleId":
        cypher = f"{call} RETURN node.articleId AS id ORDER BY score DESC"
    else:
        path, prop = (_ART_TO_DOC, "documentNumber") if field == "documentNumber" else (_ART_TO_CONTENT, "contentId")
        cypher = f"{call} MATCH {path} RETURN d.{prop} AS id, max(score) AS s ORDER BY s DESC"
    return [r["id"] for r in session.run(cypher, **params) if r["id"] is not None]


def bm25_full(session, query: Query, limit: int) -> list[str] | None:
    base = bm25.search(session, query, limit)
    if base is None:
        return None
    call = ("CALL db.index.fulltext.queryNodes('article_text', $q, {limit: $n}) YIELD node, score")
    articles = _rollup(session, call, {"q": bm25.lucene_query(query.question), "n": ARTICLE_CANDIDATES}, query.id_field)
    if query.id_field == "articleId":
        return articles[:limit]
    return rrf(base, articles)[:limit]


# ------------------------------------------------------------------ vector

_EMBED_MODEL = os.getenv("LKG_EMBED_MODEL", "gemini-embedding-001")
_EMBED_DIM = int(os.getenv("LKG_EMBED_DIMENSIONS", "768"))
_VECTOR_INDEX = os.getenv("LKG_VECTOR_INDEX_NAME", "article_embedding")
_CACHE = Path(__file__).resolve().parent / "reports" / "query_embeddings.json"


def _gemini_keys() -> list[str]:
    """Cùng ba nguồn key như legal_knowledge_graph (LKG_GEMINI_*, GEMINI_*, GEMMA_*), bỏ trùng."""

    keys: list[str] = []
    for prefix in ("LKG_GEMINI_API_KEY", "GEMINI_API_KEY", "GEMMA_API_KEY"):
        names = sorted((n for n in os.environ if n == prefix or n.startswith(prefix + "_")),
                       key=lambda n: (len(n), n))
        for name in names:
            for k in os.environ[name].split(","):
                if k.strip() and k.strip() not in keys:
                    keys.append(k.strip())
    return keys


def embed_question(question: str) -> list[float]:
    """Embedding RETRIEVAL_QUERY cùng model/số chiều với lúc backfill Article.
    Lưu đệm ra file để chạy lại không tốn quota."""

    cache_key = f"{_EMBED_MODEL}|{_EMBED_DIM}|{question}"
    try:
        cache = json.loads(_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    if cache_key in cache:
        return cache[cache_key]

    from google import genai
    from google.genai import types

    cfg = types.EmbedContentConfig(task_type="RETRIEVAL_QUERY", output_dimensionality=_EMBED_DIM)
    last_error: Exception | None = None
    for attempt in range(3):
        for key in _gemini_keys():
            try:
                client = genai.Client(api_key=key)  # giữ tham chiếu: client tạm bị thu hồi sẽ đóng kết nối giữa chừng
                resp = client.models.embed_content(model=_EMBED_MODEL, contents=[question], config=cfg)
                vector = list(resp.embeddings[0].values)
                cache[cache_key] = vector
                _CACHE.parent.mkdir(parents=True, exist_ok=True)
                _CACHE.write_text(json.dumps(cache), encoding="utf-8")
                return vector
            except Exception as exc:  # key hết quota / lỗi mạng: thử key kế
                last_error = exc
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Không embed được câu hỏi: {last_error}")


def vector(session, query: Query, limit: int) -> list[str] | None:
    if bm25.INDEX_BY_FIELD.get(query.id_field or "") is None or not query.question:
        return None
    call = "CALL db.index.vector.queryNodes($index, $n, $vec) YIELD node, score"
    params = {"index": _VECTOR_INDEX, "n": ARTICLE_CANDIDATES, "vec": embed_question(query.question)}
    if query.id_field == "contentId":
        # Nội dung kèm theo không có embedding riêng: gộp từ các Điều của nó.
        return _rollup(session, call, params, "contentId")[:limit]
    return _rollup(session, call, params, query.id_field)[:limit]


def hybrid(session, query: Query, limit: int) -> list[str] | None:
    full = bm25_full(session, query, limit)
    vec = vector(session, query, limit)
    if full is None or vec is None:
        return None
    return rrf(full, vec)[:limit]


_EXPAND = """
    MATCH (s:Document) WHERE s.documentNumber IN $seeds
    MATCH (s)-[:BASED_ON|REPLACES|AMENDS|REPEALS]-(n:Document)
    WITH n, count(DISTINCT s) AS links
    RETURN n.documentNumber AS id ORDER BY links DESC, id
"""


def hybrid_kg(session, query: Query, limit: int, seeds: int = 5) -> list[str] | None:
    ranked = hybrid(session, query, limit)
    if ranked is None or query.id_field != "documentNumber":
        return ranked  # mở rộng theo quan hệ chỉ áp dụng cho đáp án là văn bản
    head = ranked[:seeds]
    expanded = [r["id"] for r in session.run(_EXPAND, seeds=head) if r["id"]]
    out: list[str] = []
    for key in head + expanded + ranked[seeds:]:
        if key not in out:
            out.append(key)
    return out[:limit]


RERANK_POOL = int(os.getenv("LKG_RERANK_CANDIDATES", "16"))

_ARTICLE_ROWS = """
    UNWIND $ids AS id MATCH (a:Article {articleId: id})
    OPTIONAL MATCH (d:Document)-[:HAS_ARTICLE|PROMULGATES*1..2]->(a)
    RETURN a.articleId AS articleId, a.heading AS heading, a.text AS text,
           head(collect(d.documentNumber)) AS documentNumber
"""
_ART_TO_UNIT = {
    "documentNumber": "UNWIND $ids AS id MATCH (d:Document)-[:HAS_ARTICLE|PROMULGATES*1..2]->(a:Article {articleId: id})"
                      " RETURN id, d.documentNumber AS unit",
    "contentId": "UNWIND $ids AS id MATCH (d:NormativeContent)-[:HAS_ARTICLE]->(a:Article {articleId: id})"
                 " RETURN id, d.contentId AS unit",
}


def hybrid_rerank(session, query: Query, limit: int) -> list[str] | None:
    """Như chatbot khi bật LKG_RERANK_PROVIDER: RRF(fulltext Điều, vector Điều)
    ở mức Điều, đưa RERANK_POOL Điều đầu vào reranker, rồi gộp lên đơn vị đáp
    án; phần còn lại nối thêm theo thứ hạng của `hybrid`. Mặc định dùng Gemini
    (LKG_RERANK_PROVIDER=cross_encoder để chạy bge-reranker tại máy)."""

    base = hybrid(session, query, limit)
    if base is None:
        return None
    from legal_knowledge_graph.core.llm import rerank

    scorer = rerank.build_scorer(os.getenv("LKG_RERANK_PROVIDER") or "gemini")
    full = ("CALL db.index.fulltext.queryNodes('article_text', $q, {limit: $n}) YIELD node, score",
            {"q": bm25.lucene_query(query.question), "n": RERANK_POOL * 4})
    vec = ("CALL db.index.vector.queryNodes($index, $n, $vec) YIELD node, score",
           {"index": _VECTOR_INDEX, "n": RERANK_POOL * 4, "vec": embed_question(query.question)})
    pool = rrf(*(_rollup(session, call, params, "articleId") for call, params in (full, vec)))[:RERANK_POOL]
    rows = {r["articleId"]: dict(r) for r in session.run(_ARTICLE_ROWS, ids=pool)}
    pool = [a for a in pool if a in rows]
    scores = scorer(query.question, [rerank.passage(rows[a]) for a in pool])
    ranked = [a for _, a in sorted(zip(scores, pool), key=lambda p: -p[0])]
    if query.id_field == "articleId":
        units = ranked
    else:
        to_unit: dict[str, str] = {}
        for r in session.run(_ART_TO_UNIT[query.id_field], ids=ranked):
            to_unit.setdefault(r["id"], r["unit"])
        units = [to_unit[a] for a in ranked if to_unit.get(a)]
    out: list[str] = []
    for key in units + base:
        if key not in out:
            out.append(key)
    return out[:limit]


SYSTEMS = {
    "bm25": bm25.search,
    "bm25_full": bm25_full,
    "vector": vector,
    "hybrid": hybrid,
    "hybrid_kg": hybrid_kg,
    "hybrid_rerank": hybrid_rerank,
}
