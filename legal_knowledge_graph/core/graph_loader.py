"""
Ghi một GraphModel (dựng ở graph_model.py) vào Neo4j — instance RIÊNG, tách
biệt hoàn toàn khỏi Neo4j của pipeline tự động (xem README.md).

Idempotent: mọi thứ dùng MERGE, chạy lại bao nhiêu lần cũng không nhân đôi
node/cạnh (trừ property cập nhật theo lần chạy mới nhất — đúng ý "gán lại
thì ghi đè").

Thứ tự nạp (xem lý do trong README §6):
  1) constraint + index
  2) Topic + Organization (từ reference/ + phát sinh trong samples/, kể cả
     org được nhắc/parentOrg mà bản thân nó không phải cơ quan ban hành ai)
  3) PART_OF
  4) Document THẬT (isStub=false) cho mọi file
  5) ISSUED_BY, HAS_TOPIC, MENTIONS
  6) Person + SIGNED_BY
  7) NormativeContent + PROMULGATES, Article + HAS_ARTICLE
  8) CUỐI CÙNG: citations -> tạo Document stub (nếu cần) rồi tạo 5 loại
     quan hệ BASED_ON/REFERENCES/REPLACES/AMENDS/REPEALS
"""

from __future__ import annotations

from neo4j import GraphDatabase

from . import config
from .graph_model import GraphModel

RELATION_TYPES = ("BASED_ON", "REFERENCES", "REPLACES", "AMENDS", "REPEALS")

SCHEMA_CYPHER = """
CREATE CONSTRAINT doc_key IF NOT EXISTS FOR (d:Document) REQUIRE d.normalizedNumber IS UNIQUE;
CREATE CONSTRAINT org_key IF NOT EXISTS FOR (o:Organization) REQUIRE o.orgId IS UNIQUE;
CREATE CONSTRAINT topic_key IF NOT EXISTS FOR (t:Topic) REQUIRE t.topicId IS UNIQUE;
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


def _split_cypher(script: str) -> list[str]:
    # Bỏ dòng chú thích "//" TRƯỚC khi ghép/split theo ";" — làm ngược lại
    # (split trước, xoá chú thích sau) từng khiến pipeline tự động mất
    # constraint/index một cách âm thầm (xem src/vanban/kg/neo4j_load.py).
    lines = [ln for ln in script.splitlines() if ln.strip() and not ln.strip().startswith("//")]
    joined = "\n".join(lines)
    return [s.strip() for s in joined.split(";") if s.strip()]


def _run_batched(session, cypher: str, rows: list[dict]) -> dict[str, int]:
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


def push(model: GraphModel, wipe: bool = False) -> dict[str, dict[str, int]]:
    driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
    report: dict[str, dict[str, int]] = {}
    try:
        with driver.session(database=config.NEO4J_DATABASE) as session:
            if wipe:
                _wipe(session)

            for stmt in _split_cypher(SCHEMA_CYPHER):
                session.run(stmt)

            report["Topic"] = _run_batched(
                session,
                "UNWIND $rows AS row MERGE (t:Topic {topicId: row.topicId}) "
                "SET t.name = row.name",
                list(model.topics.values()),
            )

            report["Organization"] = _run_batched(
                session,
                "UNWIND $rows AS row MERGE (o:Organization {orgId: row.orgId}) "
                "SET o.name = row.name, o.orgType = row.orgType",
                list(model.orgs.values()),
            )

            report["PART_OF"] = _run_batched(
                session,
                "UNWIND $rows AS row "
                "MATCH (a:Organization {orgId: row.orgId}) "
                "MATCH (b:Organization {orgId: row.parentOrg}) "
                "MERGE (a)-[:PART_OF]->(b)",
                [o for o in model.orgs.values() if o.get("parentOrg")],
            )

            report["Document"] = _run_batched(
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
            report["Document (stub)"] = _run_batched(
                session,
                "UNWIND $rows AS row MERGE (d:Document {normalizedNumber: row.normalizedNumber}) "
                "ON CREATE SET d.documentNumber = row.documentNumber, d.isStub = true",
                stub_targets,
            )

            report["ISSUED_BY"] = _run_batched(
                session,
                "UNWIND $rows AS row "
                "MATCH (d:Document {normalizedNumber: row.doc}) "
                "MATCH (o:Organization {orgId: row.org}) "
                "MERGE (d)-[:ISSUED_BY]->(o)",
                model.issued_by,
            )

            report["HAS_TOPIC"] = _run_batched(
                session,
                "UNWIND $rows AS row "
                "MATCH (d:Document {normalizedNumber: row.doc}) "
                "MATCH (t:Topic {topicId: row.topic}) "
                "MERGE (d)-[:HAS_TOPIC]->(t)",
                model.has_topic,
            )

            report["MENTIONS"] = _run_batched(
                session,
                "UNWIND $rows AS row "
                "MATCH (d:Document {normalizedNumber: row.doc}) "
                "MATCH (o:Organization {orgId: row.org}) "
                "MERGE (d)-[:MENTIONS]->(o)",
                model.mentions,
            )

            report["Person"] = _run_batched(
                session,
                "UNWIND $rows AS row MERGE (p:Person {personId: row.personId}) "
                "SET p.fullName = row.fullName, p.academicTitle = row.academicTitle, "
                "p.position = row.positions",
                list(model.persons.values()),
            )

            report["SIGNED_BY"] = _run_batched(
                session,
                "UNWIND $rows AS row "
                "MATCH (d:Document {normalizedNumber: row.doc}) "
                "MATCH (p:Person {personId: row.person}) "
                "MERGE (d)-[:SIGNED_BY]->(p)",
                model.signed_by,
            )

            report["NormativeContent"] = _run_batched(
                session,
                "UNWIND $rows AS row MERGE (c:NormativeContent {contentId: row.contentId}) "
                "SET c.contentType = row.contentType, c.title = row.title, c.status = row.status",
                model.normative_contents,
            )

            report["PROMULGATES"] = _run_batched(
                session,
                "UNWIND $rows AS row "
                "MATCH (d:Document {normalizedNumber: row.doc}) "
                "MATCH (c:NormativeContent {contentId: row.content}) "
                "MERGE (d)-[:PROMULGATES]->(c)",
                model.promulgates,
            )

            report["Article"] = _run_batched(
                session,
                "UNWIND $rows AS row MERGE (a:Article {articleId: row.articleId}) "
                "SET a.number = row.number, a.heading = row.heading, a.text = row.text, "
                "a.isImplementationClause = row.isImplementationClause",
                model.articles,
            )

            report["HAS_ARTICLE (Document)"] = _run_batched(
                session,
                "UNWIND $rows AS row "
                "MATCH (d:Document {normalizedNumber: row.parentId}) "
                "MATCH (a:Article {articleId: row.articleId}) "
                "MERGE (d)-[:HAS_ARTICLE]->(a)",
                [a for a in model.articles if a["parentLabel"] == "Document"],
            )

            report["HAS_ARTICLE (NormativeContent)"] = _run_batched(
                session,
                "UNWIND $rows AS row "
                "MATCH (c:NormativeContent {contentId: row.parentId}) "
                "MATCH (a:Article {articleId: row.articleId}) "
                "MERGE (c)-[:HAS_ARTICLE]->(a)",
                [a for a in model.articles if a["parentLabel"] == "NormativeContent"],
            )

            for rel in RELATION_TYPES:
                rows = [c for c in model.citations if c["type"] == rel]
                report[rel] = _run_batched(
                    session,
                    "UNWIND $rows AS row "
                    "MATCH (a:Document {normalizedNumber: row.source}) "
                    "MATCH (b:Document {normalizedNumber: row.target}) "
                    f"MERGE (a)-[r:{rel}]->(b) "
                    "SET r.context = row.context, r.targetArticle = row.targetArticle",
                    rows,
                )
    finally:
        driver.close()

    return report
