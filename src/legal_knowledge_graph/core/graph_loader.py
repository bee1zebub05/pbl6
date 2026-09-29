"""
Ghi một GraphModel (dựng ở graph_model.py) vào Neo4j — instance RIÊNG, tách
biệt hoàn toàn khỏi Neo4j của pipeline tự động (xem README.md).

Idempotent: mọi thứ dùng MERGE, chạy lại bao nhiêu lần cũng không nhân đôi
node/cạnh (trừ property cập nhật theo lần chạy mới nhất — đúng ý "gán lại
thì ghi đè").

Thứ tự nạp (xem lý do trong README §6):
  1) constraint + index
  2) Topic + TargetGroup + Organization (từ reference/ + phát sinh trong
     samples/, kể cả org được nhắc/parentOrg mà bản thân nó không phải cơ
     quan ban hành ai)
  3) PART_OF
  4) Document THẬT (isStub=false) cho mọi file
  5) ISSUED_BY, HAS_TOPIC, APPLIES_TO, MENTIONS
  6) Person + SIGNED_BY
  7) NormativeContent + PROMULGATES, Article + HAS_ARTICLE
  8) CUỐI CÙNG: citations -> tạo Document stub (nếu cần) rồi tạo 5 loại
     quan hệ BASED_ON/REFERENCES/REPLACES/AMENDS/REPEALS
"""

from __future__ import annotations

from . import config, neo4j_session
from .graph_model import GraphModel

RELATION_TYPES = ("BASED_ON", "REFERENCES", "REPLACES", "AMENDS", "REPEALS")

SCHEMA_CYPHER = """
CREATE CONSTRAINT doc_key IF NOT EXISTS FOR (d:Document) REQUIRE d.normalizedNumber IS UNIQUE;
CREATE CONSTRAINT org_key IF NOT EXISTS FOR (o:Organization) REQUIRE o.orgId IS UNIQUE;
CREATE CONSTRAINT topic_key IF NOT EXISTS FOR (t:Topic) REQUIRE t.topicId IS UNIQUE;
CREATE CONSTRAINT target_group_key IF NOT EXISTS FOR (g:TargetGroup) REQUIRE g.targetGroupId IS UNIQUE;
CREATE CONSTRAINT content_key IF NOT EXISTS FOR (c:NormativeContent) REQUIRE c.contentId IS UNIQUE;
CREATE CONSTRAINT article_key IF NOT EXISTS FOR (a:Article) REQUIRE a.articleId IS UNIQUE;
CREATE CONSTRAINT person_key IF NOT EXISTS FOR (p:Person) REQUIRE p.personId IS UNIQUE;
CREATE INDEX doc_status IF NOT EXISTS FOR (d:Document) ON (d.status);
CREATE INDEX doc_level IF NOT EXISTS FOR (d:Document) ON (d.authorityLevel);
CREATE INDEX doc_type IF NOT EXISTS FOR (d:Document) ON (d.documentType);
CREATE FULLTEXT INDEX doc_text IF NOT EXISTS FOR (d:Document) ON EACH [d.title, d.summary];
CREATE FULLTEXT INDEX article_text IF NOT EXISTS FOR (a:Article) ON EACH [a.heading, a.text];
CREATE FULLTEXT INDEX content_text IF NOT EXISTS FOR (c:NormativeContent) ON EACH [c.title];
"""

# Vector index cho retrieval ngữ nghĩa (core/nlq/retrieval.py,
# core/nlq/embed_articles.py) — TẠO ở đây (rẻ, idempotent, chạy mỗi lần
# build như mọi index khác), nhưng ĐỔ DỮ LIỆU (embedding thật, tốn quota
# Gemini) không bao giờ nằm trong build/all — chỉ qua CLI riêng
# `embed-articles`, chạy tay. Đổi dimension sau này phải DROP INDEX rồi
# embed lại toàn bộ — "IF NOT EXISTS" không tự sửa dimension cũ.
VECTOR_INDEX_CYPHER = """
CREATE VECTOR INDEX {index_name} IF NOT EXISTS
FOR (a:Article) ON (a.embedding)
OPTIONS {{indexConfig: {{
  `vector.dimensions`: {dimensions},
  `vector.similarity_function`: 'cosine'
}}}}
"""


def _split_cypher(script: str) -> list[str]:
    # Bỏ dòng chú thích "//" TRƯỚC khi ghép/split theo ";" — làm ngược lại
    # (split trước, xoá chú thích sau) từng khiến pipeline tự động mất
    # constraint/index một cách âm thầm (xem src/vanban/kg/neo4j_load.py).
    lines = [ln for ln in script.splitlines() if ln.strip() and not ln.strip().startswith("//")]
    joined = "\n".join(lines)
    return [s.strip() for s in joined.split(";") if s.strip()]


def run_batched(session, cypher: str, rows: list[dict]) -> dict[str, int]:
    """Public — dùng chung bởi push() và core/nlq/embed_articles.py (backfill
    embedding lên node đã tồn tại, không đi qua toàn bộ pipeline JSON→graph)."""

    totals = {"nodes_created": 0, "relationships_created": 0, "properties_set": 0}
    for start in range(0, len(rows), config.BATCH_SIZE):
        chunk = rows[start:start + config.BATCH_SIZE]
        if not chunk:
            continue
        counters = session.run(cypher, rows=chunk).consume().counters
        totals["nodes_created"] += counters.nodes_created
        totals["relationships_created"] += counters.relationships_created
        totals["properties_set"] += counters.properties_set
    return totals


def _wipe(session) -> None:
    while True:
        result = session.run(
            "MATCH (n) WITH n LIMIT 10000 DETACH DELETE n RETURN count(*) AS n"
        )
        if result.single()["n"] == 0:
            break


def _push_topics(session, model: GraphModel) -> dict[str, int]:
    return run_batched(
        session,
        "UNWIND $rows AS row MERGE (t:Topic {topicId: row.topicId}) "
        "SET t.name = row.name",
        list(model.topics.values()),
    )


def _push_target_groups(session, model: GraphModel) -> dict[str, int]:
    return run_batched(
        session,
        "UNWIND $rows AS row MERGE (g:TargetGroup {targetGroupId: row.targetGroupId}) "
        "SET g.name = row.name",
        list(model.target_groups.values()),
    )


def _push_organizations(session, model: GraphModel) -> dict[str, dict[str, int]]:
    """Organization + PART_OF — 2 bước gắn liền (PART_OF cần Organization
    của cả 2 đầu đã tồn tại)."""

    report: dict[str, dict[str, int]] = {}
    report["Organization"] = run_batched(
        session,
        "UNWIND $rows AS row MERGE (o:Organization {orgId: row.orgId}) "
        "SET o.name = row.name, o.orgType = row.orgType",
        list(model.orgs.values()),
    )
    report["PART_OF"] = run_batched(
        session,
        "UNWIND $rows AS row "
        "MATCH (a:Organization {orgId: row.orgId}) "
        "MATCH (b:Organization {orgId: row.parentOrg}) "
        "MERGE (a)-[:PART_OF]->(b)",
        [o for o in model.orgs.values() if o.get("parentOrg")],
    )
    return report


def _push_documents(session, model: GraphModel) -> dict[str, dict[str, int]]:
    """Document thật + Document stub (cho citation target chưa map) +
    4 loại cạnh trực tiếp từ Document (ISSUED_BY/HAS_TOPIC/APPLIES_TO/
    MENTIONS) — stub PHẢI tạo trước cạnh quan hệ nên gộp chung 1 hàm,
    không tách citation stub ra khỏi nhóm Document."""

    report: dict[str, dict[str, int]] = {}
    report["Document"] = run_batched(
        session,
        "UNWIND $rows AS row MERGE (d:Document {normalizedNumber: row.normalizedNumber}) "
        "SET d += row, d.isStub = false",
        list(model.documents.values()),
    )

    # Stub cho citation target chưa map — chạy TRƯỚC khi tạo cạnh
    # quan hệ, và chỉ set isStub/documentNumber lúc TẠO MỚI (ON CREATE) để
    # không bao giờ hạ một Document thật đã tồn tại xuống thành stub.
    stub_targets = []
    seen = set()
    for c in model.citations:
        if c["target"] not in model.documents and c["target"] not in seen:
            seen.add(c["target"])
            stub_targets.append({"normalizedNumber": c["target"], "documentNumber": c["target_raw"]})
    report["Document (stub)"] = run_batched(
        session,
        "UNWIND $rows AS row MERGE (d:Document {normalizedNumber: row.normalizedNumber}) "
        "ON CREATE SET d.documentNumber = row.documentNumber, d.isStub = true",
        stub_targets,
    )

    report["ISSUED_BY"] = run_batched(
        session,
        "UNWIND $rows AS row "
        "MATCH (d:Document {normalizedNumber: row.doc}) "
        "MATCH (o:Organization {orgId: row.org}) "
        "MERGE (d)-[:ISSUED_BY]->(o)",
        model.issued_by,
    )

    report["HAS_TOPIC"] = run_batched(
        session,
        "UNWIND $rows AS row "
        "MATCH (d:Document {normalizedNumber: row.doc}) "
        "MATCH (t:Topic {topicId: row.topic}) "
        "MERGE (d)-[:HAS_TOPIC]->(t)",
        model.has_topic,
    )

    report["APPLIES_TO"] = run_batched(
        session,
        "UNWIND $rows AS row "
        "MATCH (d:Document {normalizedNumber: row.doc}) "
        "MATCH (g:TargetGroup {targetGroupId: row.group}) "
        "MERGE (d)-[:APPLIES_TO]->(g)",
        model.applies_to,
    )

    report["MENTIONS"] = run_batched(
        session,
        "UNWIND $rows AS row "
        "MATCH (d:Document {normalizedNumber: row.doc}) "
        "MATCH (o:Organization {orgId: row.org}) "
        "MERGE (d)-[:MENTIONS]->(o)",
        model.mentions,
    )
    return report


def _push_people(session, model: GraphModel) -> dict[str, dict[str, int]]:
    report: dict[str, dict[str, int]] = {}
    report["Person"] = run_batched(
        session,
        "UNWIND $rows AS row MERGE (p:Person {personId: row.personId}) "
        "SET p.fullName = row.fullName, p.academicTitle = row.academicTitle, "
        "p.position = row.positions",
        list(model.persons.values()),
    )
    report["SIGNED_BY"] = run_batched(
        session,
        "UNWIND $rows AS row "
        "MATCH (d:Document {normalizedNumber: row.doc}) "
        "MATCH (p:Person {personId: row.person}) "
        "MERGE (d)-[:SIGNED_BY]->(p)",
        model.signed_by,
    )
    return report


def _push_normative_contents(session, model: GraphModel) -> dict[str, dict[str, int]]:
    report: dict[str, dict[str, int]] = {}
    report["NormativeContent"] = run_batched(
        session,
        "UNWIND $rows AS row MERGE (c:NormativeContent {contentId: row.contentId}) "
        "SET c.contentType = row.contentType, c.title = row.title, c.status = row.status",
        model.normative_contents,
    )
    report["PROMULGATES"] = run_batched(
        session,
        "UNWIND $rows AS row "
        "MATCH (d:Document {normalizedNumber: row.doc}) "
        "MATCH (c:NormativeContent {contentId: row.content}) "
        "MERGE (d)-[:PROMULGATES]->(c)",
        model.promulgates,
    )
    return report


def _push_articles(session, model: GraphModel) -> dict[str, dict[str, int]]:
    report: dict[str, dict[str, int]] = {}
    report["Article"] = run_batched(
        session,
        "UNWIND $rows AS row MERGE (a:Article {articleId: row.articleId}) "
        "SET a.number = row.number, a.heading = row.heading, a.text = row.text, "
        "a.isImplementationClause = row.isImplementationClause",
        model.articles,
    )
    report["HAS_ARTICLE (Document)"] = run_batched(
        session,
        "UNWIND $rows AS row "
        "MATCH (d:Document {normalizedNumber: row.parentId}) "
        "MATCH (a:Article {articleId: row.articleId}) "
        "MERGE (d)-[:HAS_ARTICLE]->(a)",
        [a for a in model.articles if a["parentLabel"] == "Document"],
    )
    report["HAS_ARTICLE (NormativeContent)"] = run_batched(
        session,
        "UNWIND $rows AS row "
        "MATCH (c:NormativeContent {contentId: row.parentId}) "
        "MATCH (a:Article {articleId: row.articleId}) "
        "MERGE (c)-[:HAS_ARTICLE]->(a)",
        [a for a in model.articles if a["parentLabel"] == "NormativeContent"],
    )
    return report


def _push_citations(session, model: GraphModel) -> dict[str, dict[str, int]]:
    report: dict[str, dict[str, int]] = {}
    for rel in RELATION_TYPES:
        rows = [c for c in model.citations if c["type"] == rel]
        report[rel] = run_batched(
            session,
            "UNWIND $rows AS row "
            "MATCH (a:Document {normalizedNumber: row.source}) "
            "MATCH (b:Document {normalizedNumber: row.target}) "
            f"MERGE (a)-[r:{rel}]->(b) "
            "SET r.context = row.context, r.targetArticle = row.targetArticle",
            rows,
        )
    return report


def push(model: GraphModel, wipe: bool = False) -> dict[str, dict[str, int]]:
    report: dict[str, dict[str, int]] = {}
    with neo4j_session.session() as session:
        if wipe:
            _wipe(session)

        for stmt in _split_cypher(SCHEMA_CYPHER):
            session.run(stmt)
        session.run(VECTOR_INDEX_CYPHER.format(
            index_name=config.NLQ_VECTOR_INDEX_NAME, dimensions=config.NLQ_EMBED_DIMENSIONS,
        ))

        report["Topic"] = _push_topics(session, model)
        report["TargetGroup"] = _push_target_groups(session, model)
        report.update(_push_organizations(session, model))
        report.update(_push_documents(session, model))
        report.update(_push_people(session, model))
        report.update(_push_normative_contents(session, model))
        report.update(_push_articles(session, model))
        report.update(_push_citations(session, model))

    return report
