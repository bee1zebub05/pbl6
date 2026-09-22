"""
Bộ Cypher MINH HOẠ hiệu năng trên data THẬT (`data/clean/json/v2/`, 418 văn
bản sau khi loại `_nghi_ngo/`) — KHÁC mục đích với `catalog.py`:

- `catalog.py`  : assert đúng số dòng trên bộ 17 mẫu cố định — regression
  test cho cơ chế validate/build/query.
- `benchmark_catalog.py` (file này): KHÔNG assert số dòng cố định
  (`expected_rows=None` ở mọi câu) — chỉ đo thời gian thật + đọc PROFILE thật
  trên graph thật, để xem hình dạng hiệu năng theo từng loại truy vấn.

Quan trọng: đây là bộ câu hỏi TỰ CHỌN để minh hoạ nhiều góc độ khác nhau
(phân bố dữ liệu, xếp hạng, từng loại quan hệ hiệu lực, multi-hop, cả 3
index full-text, hybrid hai chiều, phát hiện bất thường) — KHÔNG PHẢI bộ
câu hỏi đã được nhóm thẩm định là "chuẩn"/"đại diện đúng nhu cầu truy vấn
thật". Số đo (elapsed_ms, index_used) là số đo thật chạy trên graph thật;
chỉ có việc CHỌN câu hỏi nào để hỏi là chưa qua thẩm định của nhóm.
"""

from __future__ import annotations

from .catalog import Query

QUERIES: list[Query] = [
    # ---- Nhóm 1: phân bố node (distribution) ----
    Query(
        name="B1_document_by_status",
        cypher="""
            MATCH (d:Document) WHERE d.isStub = false
            RETURN d.status AS status, count(*) AS total
            ORDER BY total DESC
        """,
        expected_rows=None,
        kind="distribution",
        note="Phân bố Document theo status (CON_HIEU_LUC/HET_HIEU_LUC/CHUA_HIEU_LUC/null).",
    ),
    Query(
        name="B2_document_by_type",
        cypher="""
            MATCH (d:Document) WHERE d.isStub = false
            RETURN d.documentType AS documentType, count(*) AS total
            ORDER BY total DESC
        """,
        expected_rows=None,
        kind="distribution",
        note="Phân bố Document theo documentType (Quyết định/Thông tư/Luật...).",
    ),
    Query(
        name="B3_document_by_authority_level",
        cypher="""
            MATCH (d:Document) WHERE d.isStub = false
            RETURN d.authorityLevel AS authorityLevel, count(*) AS total
            ORDER BY authorityLevel DESC
        """,
        expected_rows=None,
        kind="distribution",
        note="Phân bố Document theo bậc thẩm quyền suy ra (1-6).",
    ),
    Query(
        name="B4_normative_content_by_type",
        cypher="""
            MATCH (c:NormativeContent)
            RETURN c.contentType AS contentType, count(*) AS total
            ORDER BY total DESC
        """,
        expected_rows=None,
        kind="distribution",
        note="Phân bố nội dung kèm theo (Quy định/Quy chế/...).",
    ),
    # ---- Nhóm 2: xếp hạng theo quan hệ (ranking) ----
    Query(
        name="B5_top_organizations",
        cypher="""
            MATCH (o:Organization)<-[:ISSUED_BY]-(d:Document)
            RETURN o.name AS organization, count(d) AS total
            ORDER BY total DESC
            LIMIT 10
        """,
        expected_rows=None,
        kind="ranking",
        note="Top 10 cơ quan ban hành nhiều văn bản nhất.",
    ),
    Query(
        name="B6_top_persons",
        cypher="""
            MATCH (p:Person)<-[:SIGNED_BY]-(d:Document)
            RETURN p.fullName AS person, count(d) AS total
            ORDER BY total DESC
            LIMIT 10
        """,
        expected_rows=None,
        kind="ranking",
        note="Top 10 người ký nhiều văn bản nhất.",
    ),
    Query(
        name="B7_top_topics",
        cypher="""
            MATCH (t:Topic)<-[:HAS_TOPIC]-(d:Document)
            RETURN t.name AS topic, count(d) AS total
            ORDER BY total DESC
            LIMIT 10
        """,
        expected_rows=None,
        kind="ranking",
        note="Top 10 lĩnh vực có nhiều văn bản nhất.",
    ),
    # ---- Nhóm 3: từng loại quan hệ hiệu lực riêng lẻ ----
    Query(
        name="B8_citation_relation_counts",
        cypher="""
            MATCH ()-[r]->() WHERE type(r) IN ['BASED_ON','REFERENCES','REPLACES','AMENDS','REPEALS']
            RETURN type(r) AS relationType, count(*) AS total
            ORDER BY total DESC
        """,
        expected_rows=None,
        kind="distribution",
        note="Đếm riêng 5 loại quan hệ hiệu lực/trích dẫn — không gộp một cục như Q13b.",
    ),
    Query(
        name="B9_amends_target_article_completeness",
        cypher="""
            MATCH ()-[r:AMENDS]->()
            RETURN (r.targetArticle IS NOT NULL) AS hasTargetArticle, count(*) AS total
        """,
        expected_rows=None,
        kind="distribution",
        note="Bao nhiêu % cạnh AMENDS biết rõ Điều nào bị sửa (targetArticle khác null) — đo độ đầy đủ dữ liệu.",
    ),
    # ---- Nhóm 4: multi-hop ----
    Query(
        name="B10_amends_replaces_depth_distribution",
        cypher="""
            MATCH p=(:Document)-[:AMENDS|REPLACES*1..5]->(:Document)
            RETURN length(p) AS depth, count(*) AS total
            ORDER BY depth
        """,
        expected_rows=None,
        kind="distribution",
        note="Phân bố độ sâu chuỗi hiệu lực thật — chuỗi dài nhất bao nhiêu bước trên data thật.",
    ),
    # ---- Nhóm 5: full-text — cả 3 index ----
    Query(
        name="B11_fulltext_doc_text",
        cypher="""
            CALL db.index.fulltext.queryNodes('doc_text', '"Đại học Đà Nẵng"') YIELD node, score
            RETURN node.documentNumber AS documentNumber, score
            ORDER BY score DESC
            LIMIT 50
        """,
        expected_rows=None,
        kind="fulltext",
        note="Full-text cấp Document (title+summary) — cụm phổ biến trong kho.",
    ),
    Query(
        name="B12_fulltext_article_text",
        cypher="""
            CALL db.index.fulltext.queryNodes('article_text', '"trách nhiệm thi hành"') YIELD node, score
            RETURN node.articleId AS articleId, score
            ORDER BY score DESC
            LIMIT 50
        """,
        expected_rows=None,
        kind="fulltext",
        note="Full-text cấp Article — cụm gần như mọi văn bản đều có ở Điều thi hành.",
    ),
    Query(
        name="B13_fulltext_content_text",
        cypher="""
            CALL db.index.fulltext.queryNodes('content_text', '"Quy chế"') YIELD node, score
            RETURN node.contentId AS contentId, score
            ORDER BY score DESC
            LIMIT 50
        """,
        expected_rows=None,
        kind="fulltext",
        note="Full-text cấp NormativeContent — index này CHƯA từng đo trên data thật trước đây.",
    ),
    # ---- Nhóm 6: hybrid — 2 hướng ngược nhau ----
    Query(
        name="B14_hybrid_expand_outgoing",
        cypher="""
            CALL db.index.fulltext.queryNodes('doc_text', '"Đại học Đà Nẵng"') YIELD node, score
            WITH node, score ORDER BY score DESC LIMIT 10
            MATCH (node)-[:BASED_ON|REFERENCES*0..2]->(expanded:Document)
            RETURN DISTINCT expanded.documentNumber AS documentNumber, expanded.authorityLevel AS level
            ORDER BY level DESC
            LIMIT 50
        """,
        expected_rows=None,
        kind="hybrid",
        note="Hướng XUÔI: văn bản khớp full-text dựa trên những văn bản gốc thẩm quyền nào.",
    ),
    Query(
        name="B15_hybrid_expand_incoming",
        cypher="""
            CALL db.index.fulltext.queryNodes('doc_text', '"Đại học Đà Nẵng"') YIELD node, score
            WITH node, score ORDER BY score DESC LIMIT 10
            MATCH (citer:Document)-[:BASED_ON|REFERENCES|REPLACES|AMENDS|REPEALS*0..2]->(node)
            RETURN DISTINCT citer.documentNumber AS documentNumber, citer.authorityLevel AS level
            ORDER BY level DESC
            LIMIT 50
        """,
        expected_rows=None,
        kind="hybrid",
        note="Hướng NGƯỢC (khác B14): những văn bản nào trích dẫn tới văn bản khớp full-text.",
    ),
    # ---- Nhóm 7: bất thường / chất lượng dữ liệu ----
    Query(
        name="B16_top_cited_stubs",
        cypher="""
            MATCH (d:Document {isStub: true})
            RETURN d.normalizedNumber AS normalizedNumber,
                   COUNT { (d)<-[:BASED_ON|REFERENCES|REPLACES|AMENDS|REPEALS]-() } AS incoming
            ORDER BY incoming DESC
            LIMIT 10
        """,
        expected_rows=None,
        kind="anomaly",
        note="Top 10 văn bản stub (chưa map) bị trích dẫn nhiều nhất — ứng viên ưu tiên crawl/gán tay tiếp theo.",
    ),
    Query(
        name="B17_documents_without_citations",
        cypher="""
            MATCH (d:Document)
            WHERE d.isStub = false
              AND COUNT { (d)-[:BASED_ON|REFERENCES|REPLACES|AMENDS|REPEALS]->() } = 0
            RETURN d.documentNumber AS documentNumber
            LIMIT 100
        """,
        expected_rows=None,
        kind="anomaly",
        note="Văn bản thật (không stub) không có trích dẫn nào cả — nghi thiếu sót khi gán tay (VD Công văn/Kế hoạch không có Căn cứ thì hợp lý, còn lại nên soi lại).",
    ),
]
