"""GraphRAG chạy THẬT trên Neo4j của module. Không tốn quota Gemini: embedding
câu hỏi được thay bằng embedding có sẵn của một Điều về học bổng. Tự bỏ qua
nếu Neo4j không chạy."""

import time

import pytest
from neo4j.exceptions import ServiceUnavailable

from core import config
from core.chat.container import build_graph_retriever
from core.db import Neo4jConnection
from core.graph_query import graph_context
from core.llm import embeddings
from core.normalize import normalize_document_number

SEED_COLUMNS = {"articleId", "number", "heading", "text", "docKey", "documentNumber", "container", "score"}


@pytest.fixture(scope="module")
def conn():
    c = Neo4jConnection()
    try:
        with c.session() as s:
            s.run("RETURN 1").consume()
    except ServiceUnavailable:
        pytest.skip("Neo4j (LKG) không chạy")
    return c


@pytest.fixture(scope="module")
def probe_vector(conn):
    with conn.session() as s:
        row = s.run("MATCH (a:Article) WHERE a.heading CONTAINS 'học bổng' AND a.embedding IS NOT NULL "
                    "RETURN a.embedding AS e LIMIT 1").single()
    assert row, "graph chưa có embedding Article (chạy lkg embed-articles)"
    return row["e"]


@pytest.fixture(scope="module")
def superseded_active(conn):
    """Văn bản status CON_HIEU_LUC nhưng đã bị văn bản MỚI HƠN thay thế / bãi bỏ."""

    with conn.session() as s:
        return [r["k"] for r in s.run(
            "MATCH (n:Document)-[:REPLACES|REPEALS]->(o:Document {status: 'CON_HIEU_LUC'}) "
            "WHERE n.issueDate >= o.issueDate RETURN DISTINCT o.normalizedNumber AS k LIMIT 20")]


def test_seed_queries_return_expected_columns(conn, probe_vector):
    with conn.session() as s:
        vector = graph_context.seed_vector(s, probe_vector, 5)
        fulltext = graph_context.seed_fulltext(s, "Học bổng khuyến khích học tập", 5)
    assert vector and fulltext
    assert set(vector[0]) == SEED_COLUMNS == set(fulltext[0])
    assert not any("thi hành" in (r["heading"] or "").lower() for r in vector + fulltext)


def test_scoped_articles_stay_inside_given_documents(conn, probe_vector):
    with conn.session() as s:
        rows = graph_context.scoped_articles(s, probe_vector, [normalize_document_number("1414/QĐ-ĐHBK")], 2)
    assert len(rows) == 2 and {r["documentNumber"] for r in rows} == {"1414/QĐ-ĐHBK"}


def test_expand_flags_superseded_documents_quickly(conn, superseded_active):
    assert superseded_active
    with conn.session() as s:
        start = time.perf_counter()
        rows = graph_context.expand_documents(s, superseded_active, 3)
        elapsed_ms = (time.perf_counter() - start) * 1000
    assert len(rows) == len(superseded_active)
    assert all(r["replacedBy"] or r["repealedBy"] for r in rows)
    assert elapsed_ms < 1000, f"expand {len(rows)} văn bản mất {elapsed_ms:.0f} ms"


def test_full_retrieve_without_quota(conn, probe_vector, monkeypatch):
    monkeypatch.setattr(embeddings, "embed_texts", lambda texts, **_: [probe_vector])
    retriever = build_graph_retriever(enabled=True)
    ctx = retriever.retrieve("Sinh viên được xét học bổng khuyến khích học tập thế nào?",
                             scope_docs=["1414/QĐ-ĐHBK"])
    assert ctx.documents[0].documentNumber == "1414/QĐ-ĐHBK"
    # 21 văn bản trong kho chưa có status — chỉ kiểm văn bản bị thay thế được hiệu chỉnh.
    assert all(d.effectiveStatus == "HET_HIEU_LUC" for d in ctx.documents if d.supersededBy)
    total = sum(len(a.text) + sum(len(n.text) for n in a.neighbors) for d in ctx.documents for a in d.articles)
    assert total <= config.GRAPH_RAG_CONTEXT_CHARS + config.GRAPH_RAG_ARTICLE_CHARS * 2
