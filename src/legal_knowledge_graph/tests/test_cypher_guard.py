"""Kiểm duyệt Cypher do agent viết (không cần Neo4j: chỉ các bước trước EXPLAIN)."""

import pytest

from core.graph_query.cypher_guard import GuardRejected, check_blocklist, check_labels_and_properties


def _check(cypher):
    check_blocklist(cypher)
    check_labels_and_properties(cypher)


@pytest.mark.parametrize("cypher", [
    "CREATE (n:Document)",
    "MATCH (d:Document) SET d.title = 'x'",
    "MATCH (d:Document) DETACH DELETE d",
    "CALL dbms.listConfig() YIELD name RETURN name",
    "CALL `dbms`.`listConfig`() YIELD name RETURN name",
    "CALL/**/dbms.listConfig() YIELD name RETURN name",
    "CALL db.clearQueryCaches()",
    "SHOW USERS",
    "TERMINATE TRANSACTIONS 'neo4j-transaction-1'",
    "MATCH (a:Article) RETURN a.text AS t UNION MATCH (a:Article) RETURN a.heading AS t",
    "MATCH (a:Article) RETURN a['embedding'] AS e",
    "MATCH (a:Article) RETURN a.embedding AS e",
    "MATCH (d:Document) RETURN d; MATCH (a:Article) RETURN a",
])
def test_dangerous_or_unsupported_cypher_is_rejected(cypher):
    with pytest.raises(GuardRejected):
        _check(cypher)


@pytest.mark.parametrize("cypher", [
    "MATCH (d:Document) WHERE d.title CONTAINS 'set' RETURN d.title AS title",
    "MATCH (d:Document) WHERE d.title CONTAINS 'a; b' RETURN d.title AS title",
    "MATCH (d:Document) WHERE d.title STARTS WITH 'Quy' RETURN d.title AS title",
    "CALL db.index.fulltext.queryNodes('article_text', 'học phí') YIELD node RETURN node.heading AS heading",
    "MATCH (d:Document) CALL (d) { MATCH (d)-[:HAS_TOPIC]->(t:Topic) RETURN t } RETURN t.name AS name",
    "MATCH (a:Article) RETURN vector.similarity.cosine([1.0], [1.0]) AS s",
    "MATCH (d:Document) // chú thích có chữ DELETE\nRETURN d.title AS title",
])
def test_ordinary_read_queries_pass(cypher):
    _check(cypher)
