"""
Bước 5 — nạp graph vào Neo4j và bộ Cypher mẫu.

Đọc thẳng các file JSONL ở `data/kg/` nên chạy được ở máy khác, không cần
session — miễn có `data/kg/` là nạp lại được toàn bộ graph.

Không có Neo4j chạy cũng không sao: lệnh vẫn sinh `data/kg/schema.cypher` (ràng
buộc + chỉ mục) và `data/kg/queries.cypher` (bộ truy vấn mẫu theo §6.3), để
chép vào Neo4j Browser chạy tay.

    docker run -d --name neo4j -p 7474:7474 -p 7687:7687 \
        -e NEO4J_AUTH=neo4j/12345678 neo4j:5

    python run.py kg load
"""

from __future__ import annotations

import json
from pathlib import Path

from ..core import config
from ..core.console import say

BATCH = 500


# ============================================================
# LƯỢC ĐỒ
# ============================================================

# Khoá chính của từng nhãn. Ràng buộc duy nhất là thứ giữ cho `MERGE` không
# nhân đôi node khi nạp lại lần hai.
SCHEMA_CYPHER = """
// --- Ràng buộc duy nhất (khoá chính của từng nhãn) ---
CREATE CONSTRAINT doc_key IF NOT EXISTS
  FOR (d:Document) REQUIRE d.so_hieu_norm IS UNIQUE;
CREATE CONSTRAINT org_key IF NOT EXISTS
  FOR (o:Organization) REQUIRE o.orgId IS UNIQUE;
CREATE CONSTRAINT topic_key IF NOT EXISTS
  FOR (t:Topic) REQUIRE t.topicId IS UNIQUE;
CREATE CONSTRAINT content_key IF NOT EXISTS
  FOR (c:NormativeContent) REQUIRE c.contentId IS UNIQUE;
CREATE CONSTRAINT article_key IF NOT EXISTS
  FOR (a:Article) REQUIRE a.articleId IS UNIQUE;
CREATE CONSTRAINT person_key IF NOT EXISTS
  FOR (p:Person) REQUIRE p.personId IS UNIQUE;

// --- Chỉ mục cho truy vấn hay dùng ---
CREATE INDEX doc_status IF NOT EXISTS FOR (d:Document) ON (d.status);
CREATE INDEX doc_level IF NOT EXISTS FOR (d:Document) ON (d.authority_level);
CREATE INDEX doc_type IF NOT EXISTS FOR (d:Document) ON (d.documentType);

// --- Tìm kiếm toàn văn, làm baseline BM25 ngay trong Neo4j (§6.4) ---
CREATE FULLTEXT INDEX doc_text IF NOT EXISTS
  FOR (d:Document) ON EACH [d.title];
CREATE FULLTEXT INDEX article_text IF NOT EXISTS
  FOR (a:Article) ON EACH [a.heading, a.text];
""".strip()


QUERIES_CYPHER = """
// ============================================================
// Bộ truy vấn mẫu — §6.3 Ontology
// ============================================================

// --- single-hop: văn bản còn hiệu lực của một đơn vị ---
MATCH (d:Document)-[:ISSUED_BY]->(o:Organization {name: 'Trường Đại học Bách khoa'})
WHERE d.status = 'CON_HIEU_LUC'
RETURN d.so_hieu, d.title, d.issueDate
ORDER BY d.issueDate DESC;

// --- single-hop: văn bản theo lĩnh vực ---
MATCH (d:Document)-[:HAS_TOPIC]->(t:Topic {name: 'Công tác sinh viên'})
WHERE d.status = 'CON_HIEU_LUC'
RETURN d.so_hieu, d.title, d.authority_level
ORDER BY d.authority_level DESC;

// --- multi-hop: truy ngược lên văn bản gốc thẩm quyền cao nhất (§3) ---
MATCH path = (d:Document {so_hieu_norm: '1425/QD-DHDN'})-[:BASED_ON*1..3]->(b:Document)
RETURN b.so_hieu, b.title, b.authority_level, length(path) AS bac
ORDER BY b.authority_level DESC, bac;

// --- multi-hop: chuỗi kế thừa trong một lĩnh vực ---
MATCH (d:Document)-[:HAS_TOPIC]->(t:Topic {name: 'Đào tạo'})
MATCH (d)-[:BASED_ON*1..2]->(b:Document)
WHERE b.authority_level >= 4
RETURN DISTINCT b.so_hieu, b.title, b.authority_level
ORDER BY b.authority_level DESC;

// --- hiệu lực: văn bản nào đang thay thế văn bản này ---
MATCH (new:Document)-[:REPLACES]->(old:Document {so_hieu_norm: '8/2014/TT-BGDDT'})
RETURN new.so_hieu, new.title, new.issueDate;

// --- hiệu lực: văn bản còn hiệu lực nhưng đã bị sửa đổi ---
MATCH (a:Document)-[:AMENDS]->(b:Document)
WHERE b.status = 'CON_HIEU_LUC'
RETURN b.so_hieu, b.title, collect(a.so_hieu) AS cac_van_ban_sua_doi;

// --- NormativeContent: hỏi vào nội dung, không hỏi vào quyết định bọc ngoài ---
MATCH (d:Document)-[:PROMULGATES]->(c:NormativeContent)
WHERE c.contentType = 'Quy chế' AND c.status = 'CON_HIEU_LUC'
RETURN c.title, d.so_hieu, d.issueDate
ORDER BY d.issueDate DESC;

// --- Article: retrieval cấp điều khoản (§2.7) ---
CALL db.index.fulltext.queryNodes('article_text', 'học bổng khuyến khích')
YIELD node, score
MATCH (node)<-[:HAS_ARTICLE]-(parent)
OPTIONAL MATCH (parent)<-[:PROMULGATES]-(doc:Document)
RETURN node.number, node.heading, coalesce(doc.so_hieu, parent.so_hieu_norm) AS van_ban, score
ORDER BY score DESC LIMIT 10;

// --- baseline BM25 cấp văn bản, để đối chứng với KG (§6.4) ---
CALL db.index.fulltext.queryNodes('doc_text', 'công tác sinh viên')
YIELD node, score
RETURN node.so_hieu, node.title, score
ORDER BY score DESC LIMIT 10;

// --- hybrid: BM25 lọc ứng viên rồi mở rộng theo quan hệ (§6.4) ---
CALL db.index.fulltext.queryNodes('doc_text', 'đánh giá rèn luyện')
YIELD node, score
WITH node, score ORDER BY score DESC LIMIT 5
MATCH (node)-[:BASED_ON|REFERENCES*0..2]->(mo_rong:Document)
RETURN DISTINCT mo_rong.so_hieu, mo_rong.title, mo_rong.authority_level
ORDER BY mo_rong.authority_level DESC;

// --- kiểm tra sau khi nạp ---
MATCH (n) RETURN labels(n)[0] AS nhan, count(*) AS so_luong ORDER BY so_luong DESC;
MATCH ()-[r]->() RETURN type(r) AS quan_he, count(*) AS so_luong ORDER BY so_luong DESC;
""".strip()


# ============================================================
# CÂU LỆNH NẠP
# ============================================================

# Mỗi câu nhận `$rows` là một lô bản ghi đọc từ JSONL. `MERGE` theo khoá chính
# rồi `SET` phần còn lại -> nạp lại lần hai không nhân đôi node.
LOADERS: tuple[tuple[str, str, str], ...] = (
    (
        "documents.jsonl",
        "Document",
        """
        UNWIND $rows AS row
        MERGE (d:Document {so_hieu_norm: row.so_hieu_norm})
        SET d.so_hieu = row.so_hieu,
            d.title = row.title,
            d.documentType = row.documentType,
            d.authority_level = row.authority_level,
            d.status = row.status,
            d.issueDate = row.issueDate,
            d.effectiveDate = row.effectiveDate,
            d.expiryDate = row.expiryDate,
            d.fileUrl = row.fileUrl,
            d.is_stub = row.is_stub,
            d.header_check = row.header_check,
            d.clean_path = row.clean_path
        """,
    ),
    (
        "organizations.jsonl",
        "Organization",
        """
        UNWIND $rows AS row
        MERGE (o:Organization {orgId: row.orgId})
        SET o.name = row.name, o.orgType = row.orgType
        """,
    ),
    (
        "organizations.jsonl",
        "PART_OF",
        """
        UNWIND $rows AS row
        WITH row WHERE row.parentOrg IS NOT NULL
        MATCH (o:Organization {orgId: row.orgId})
        MERGE (p:Organization {orgId: row.parentOrg})
        MERGE (o)-[:PART_OF]->(p)
        """,
    ),
    (
        "topics.jsonl",
        "Topic",
        """
        UNWIND $rows AS row
        MERGE (t:Topic {topicId: row.topicId})
        SET t.name = row.name
        """,
    ),
    (
        "documents.jsonl",
        "ISSUED_BY",
        """
        UNWIND $rows AS row
        WITH row WHERE row.orgId IS NOT NULL
        MATCH (d:Document {so_hieu_norm: row.so_hieu_norm})
        MATCH (o:Organization {orgId: row.orgId})
        MERGE (d)-[:ISSUED_BY]->(o)
        """,
    ),
    (
        "documents.jsonl",
        "HAS_TOPIC",
        """
        UNWIND $rows AS row
        UNWIND row.topics AS topic
        MATCH (d:Document {so_hieu_norm: row.so_hieu_norm})
        MATCH (t:Topic {name: topic})
        MERGE (d)-[:HAS_TOPIC]->(t)
        """,
    ),
    (
        "normative_contents.jsonl",
        "NormativeContent",
        """
        UNWIND $rows AS row
        MERGE (c:NormativeContent {contentId: row.contentId})
        SET c.contentType = row.contentType,
            c.title = row.title,
            c.status = row.status
        WITH c, row
        MATCH (d:Document {so_hieu_norm: row.promulgatedBy})
        MERGE (d)-[:PROMULGATES]->(c)
        """,
    ),
    (
        "articles.jsonl",
        "Article",
        """
        UNWIND $rows AS row
        MERGE (a:Article {articleId: row.articleId})
        SET a.number = row.number,
            a.heading = row.heading,
            a.text = row.text,
            a.is_thi_hanh = row.is_thi_hanh
        """,
    ),
    # `HAS_ARTICLE` chạy hai câu chứ không một câu có subquery: cha của một
    # Điều là `NormativeContent` hoặc `Document` tuỳ văn bản (xem đầu file
    # `normative.py`), mà gộp hai trường hợp bằng `CALL {}` thì vừa dính cảnh
    # báo deprecated của Neo4j 5, vừa khó đọc hơn hai câu tách bạch.
    (
        "articles.jsonl",
        "HAS_ARTICLE (NormativeContent)",
        """
        UNWIND $rows AS row
        WITH row WHERE row.parentLabel = 'NormativeContent'
        MATCH (a:Article {articleId: row.articleId})
        MATCH (c:NormativeContent {contentId: row.parentId})
        MERGE (c)-[:HAS_ARTICLE]->(a)
        """,
    ),
    (
        "articles.jsonl",
        "HAS_ARTICLE (Document)",
        """
        UNWIND $rows AS row
        WITH row WHERE row.parentLabel = 'Document'
        MATCH (a:Article {articleId: row.articleId})
        MATCH (d:Document {so_hieu_norm: row.parentId})
        MERGE (d)-[:HAS_ARTICLE]->(a)
        """,
    ),
    # --- Person + MENTIONS: do `scripts/xuat_person_donvi.py` sinh ra ---------
    # Ba file dưới là TUỲ CHỌN. Vòng nạp bỏ qua file không tồn tại, nên chưa
    # chạy script đó thì `kg load` vẫn chạy đúng như trước, không lỗi.
    (
        "persons.jsonl",
        "Person",
        """
        UNWIND $rows AS row
        MERGE (p:Person {personId: row.personId})
        SET p.fullName = row.fullName,
            p.position = row.position,
            p.academicTitle = row.academicTitle,
            p.so_van_ban = row.so_van_ban
        """,
    ),
    (
        "signed_by.jsonl",
        "SIGNED_BY",
        """
        UNWIND $rows AS row
        MATCH (d:Document {so_hieu_norm: row.so_hieu_norm})
        MATCH (p:Person {personId: row.personId})
        MERGE (d)-[:SIGNED_BY]->(p)
        """,
    ),
    # Đơn vị được NHẮC TỚI trong thân văn bản. Dùng `MERGE` chứ không `MATCH`
    # cho Organization: phần lớn Khoa/Phòng chưa từng ban hành văn bản nào
    # trong kho nên chưa có node — `MATCH` thì rơi hết, không tạo được cạnh nào.
    (
        "mentions.jsonl",
        "MENTIONS",
        """
        UNWIND $rows AS row
        MATCH (d:Document {so_hieu_norm: row.so_hieu_norm})
        MERGE (o:Organization {orgId: row.orgId})
        ON CREATE SET o.name = row.name, o.orgType = row.orgType
        MERGE (d)-[m:MENTIONS]->(o)
        SET m.so_lan = row.so_lan
        """,
    ),
)

# Quan hệ Document->Document nằm chung một file, mỗi dòng mang sẵn nhãn trong
# trường `type`. Cypher không cho đặt tên quan hệ bằng biến nên phải chạy từng
# loại một.
RELATION_TYPES = ("BASED_ON", "REFERENCES", "REPLACES", "AMENDS", "REPEALS")

RELATION_CYPHER = """
UNWIND $rows AS row
MATCH (a:Document {{so_hieu_norm: row.source}})
MATCH (b:Document {{so_hieu_norm: row.target}})
MERGE (a)-[r:{rel}]->(b)
SET r.hits = row.hits,
    r.zone = row.zone,
    r.in_thi_hanh = row.in_thi_hanh,
    r.context = row.context,
    r.source_header_check = row.source_header_check
"""


def _tach_cypher(script: str) -> list[str]:
    """
    Tách một script Cypher thành từng câu, **bỏ dòng chú thích trước**.

    Bỏ chú thích trước khi lọc chứ không phải sau: cắt theo `;` thì mỗi câu có
    dòng `// ...` phía trên sẽ *bắt đầu* bằng chú thích, và phép lọc
    `startswith("//")` nuốt sạch cả câu lệnh thật đứng ngay dưới. Lỗi này im
    lặng hoàn toàn — Neo4j không báo gì vì câu lệnh có được gửi đi đâu — và đã
    làm mất 3 thứ: ràng buộc duy nhất trên `Document`, chỉ mục `doc_status`, và
    full-text index `doc_text`. Mất cái cuối thì baseline BM25 của §6.4 trả về
    rỗng cho mọi câu hỏi.
    """

    cau = []

    for khoi in script.split(";"):
        sach = "\n".join(
            dong for dong in khoi.splitlines() if not dong.strip().startswith("//")
        ).strip()

        if sach:
            cau.append(sach)

    return cau


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []

    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_cypher_files(out_dir: Path | None = None) -> dict[str, Path]:
    """Ghi lược đồ + bộ truy vấn mẫu ra file, không cần Neo4j."""

    out_dir = out_dir or config.KG_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    schema = out_dir / "schema.cypher"
    queries = out_dir / "queries.cypher"

    schema.write_text(SCHEMA_CYPHER + "\n", encoding="utf-8")
    queries.write_text(QUERIES_CYPHER + "\n", encoding="utf-8")

    say(f"  Lược đồ      -> {schema}")
    say(f"  Truy vấn mẫu -> {queries}")

    return {"schema": schema, "queries": queries}


def load(
    uri: str | None = None,
    user: str | None = None,
    password: str | None = None,
    out_dir: Path | None = None,
    wipe: bool = False,
) -> dict[str, int]:
    """Nạp toàn bộ `data/kg/*.jsonl` vào Neo4j."""

    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise RuntimeError(
            "Chưa cài driver Neo4j.  pip install neo4j"
        ) from exc

    out_dir = out_dir or config.KG_DIR
    uri = uri or config.NEO4J_URI
    auth = (user or config.NEO4J_USER, password or config.NEO4J_PASSWORD)

    tally: dict[str, int] = {}

    with GraphDatabase.driver(uri, auth=auth) as driver:
        driver.verify_connectivity()

        with driver.session(database=config.NEO4J_DATABASE) as session:
            if wipe:
                say("  Xoá graph cũ...")
                # Xoá theo lô: `DETACH DELETE` cả chục nghìn node một lượt là
                # vỡ heap mặc định của Neo4j.
                while True:
                    result = session.run(
                        "MATCH (n) WITH n LIMIT 10000 DETACH DELETE n "
                        "RETURN count(*) AS n"
                    ).single()

                    if not result or not result["n"]:
                        break

            say("  Tạo ràng buộc + chỉ mục...")

            for statement in _tach_cypher(SCHEMA_CYPHER):
                session.run(statement)

            for filename, label, cypher in LOADERS:
                rows = _read(out_dir / filename)

                if not rows:
                    continue

                # Đếm theo counters của Neo4j chứ không theo số dòng gửi lên:
                # một câu như `HAS_ARTICLE (Document)` nhận cả file nhưng chỉ
                # khớp phần có `parentLabel` tương ứng.
                made = 0

                for start in range(0, len(rows), BATCH):
                    counters = session.run(
                        cypher, rows=rows[start : start + BATCH]
                    ).consume().counters
                    made += counters.nodes_created + counters.relationships_created

                tally[label] = tally.get(label, 0) + made
                say(f"    {label:<32} {made:>6,}")

            relations = _read(out_dir / "relations.jsonl")

            for rel in RELATION_TYPES:
                subset = [row for row in relations if row.get("type") == rel]

                if not subset:
                    continue

                cypher = RELATION_CYPHER.format(rel=rel)

                made = 0

                for start in range(0, len(subset), BATCH):
                    counters = session.run(
                        cypher, rows=subset[start : start + BATCH]
                    ).consume().counters
                    made += counters.relationships_created

                tally[rel] = made
                say(f"    {rel:<32} {made:>6,}  ({len(subset):,} cạnh trong file)")

            counts = session.run(
                "MATCH (n) RETURN labels(n)[0] AS nhan, count(*) AS n ORDER BY n DESC"
            ).data()

    say("\n  Trong Neo4j sau khi nạp:")

    for row in counts:
        say(f"    {str(row['nhan']):<20} {row['n']:>6,}")

    return tally
