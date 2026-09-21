"""
Danh sách Cypher test cho bộ 17 văn bản THẬT (rút gọn từ
data/clean/text_final/, xem samples/). Mỗi câu có số dòng KỲ VỌNG đã chạy
thật trên Neo4j để xác nhận (không phải suy đoán) — nếu sửa samples/ thì
phải chạy lại và cập nhật các con số ở đây, `runner.py` sẽ báo FAIL ngay nếu
lệch.

Đây là bộ "regression" cho chính cơ chế validate/build/query (assert đúng số
dòng), KHÔNG phải bộ đo hiệu năng trên data thật — xem `benchmark_catalog.py`
cho việc đó.

`expected_rows = None` nghĩa là không có số cố định để assert (kết quả phụ
thuộc thuật toán mở rộng đồ thị/xếp hạng) — `runner.py` khi đó chỉ kiểm tra
có >=1 dòng và in ra để soi tay, không tính PASS/FAIL theo số dòng.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Query:
    name: str
    cypher: str
    expected_rows: int | None
    kind: str  # lookup | multihop | fulltext | hybrid | sanity | distribution | ranking | anomaly
    note: str


QUERIES: list[Query] = [
    Query(
        name="Q1_single_hop_org_status",
        cypher="""
            MATCH (d:Document)-[:ISSUED_BY]->(:Organization {orgId: 'truong_dai_hoc_bach_khoa'})
            WHERE d.status = 'CON_HIEU_LUC'
            RETURN d.documentNumber AS documentNumber
        """,
        expected_rows=8,
        kind="lookup",
        note="8 văn bản do Trường ĐHBK ban hành, còn hiệu lực (1088, 1345, 1605, 1980, 2231, 2347, 3536, 800).",
    ),
    Query(
        name="Q2_single_hop_topic",
        cypher="""
            MATCH (d:Document)-[:HAS_TOPIC]->(:Topic {name: 'Thi đua, khen thưởng'})
            RETURN d.documentNumber AS documentNumber
        """,
        expected_rows=3,
        kind="lookup",
        note="3 văn bản thuộc lĩnh vực Thi đua, khen thưởng (1088, 1605, 2231).",
    ),
    Query(
        name="Q3_multihop_amends_replaces",
        cypher="""
            MATCH path = (d:Document {normalizedNumber: '4757/QD-DHDN'})-[:AMENDS|REPLACES*1..3]->(b:Document)
            RETURN b.documentNumber AS documentNumber, length(path) AS depth
            ORDER BY depth
        """,
        expected_rows=2,
        kind="multihop",
        note="Chuỗi hiệu lực thật 2 bước: 4757/QĐ-ĐHĐN --AMENDS--> 4481/QĐ-ĐHĐN --REPLACES--> 1341/QĐ-ĐHĐN (stub).",
    ),
    Query(
        name="Q4_replaces",
        cypher="""
            MATCH (new:Document)-[:REPLACES]->(:Document {normalizedNumber: '882/QD-DHDN'})
            RETURN new.documentNumber AS documentNumber
        """,
        expected_rows=1,
        kind="lookup",
        note="Văn bản thay thế 882/QĐ-ĐHĐN (stub) -> đúng 1280/QĐ-ĐHĐN.",
    ),
    Query(
        name="Q5_amends_target_still_active",
        cypher="""
            MATCH (a:Document)-[:AMENDS]->(b:Document)
            WHERE b.status = 'CON_HIEU_LUC'
            RETURN b.documentNumber AS target, collect(a.documentNumber) AS amenders
            ORDER BY target
        """,
        expected_rows=2,
        kind="lookup",
        note="AMENDS không làm văn bản gốc hết hiệu lực: 2231/QĐ-ĐHBK (sửa bởi 1088) và 4481/QĐ-ĐHĐN (sửa bởi 4757) đều vẫn CON_HIEU_LUC.",
    ),
    Query(
        name="Q6_repeals_count",
        cypher="MATCH ()-[:REPEALS]->() RETURN count(*) AS total",
        expected_rows=1,
        kind="lookup",
        note="Tổng 5 cạnh REPEALS thật (4 từ 30/2020/TT-BGDĐT + 1 từ 800/QĐ-ĐHBK) — đếm gộp một dòng.",
    ),
    Query(
        name="Q7_normative_content_by_type",
        cypher="""
            MATCH (:Document)-[:PROMULGATES]->(c:NormativeContent)
            WHERE c.contentType = 'Quy chế'
            RETURN c.contentId AS contentId, c.status AS status
            ORDER BY contentId
        """,
        expected_rows=2,
        kind="lookup",
        note="2 NormativeContent loại Quy chế (kèm theo 4481/QĐ-ĐHĐN và 4897/QĐ-ĐHĐN), cả hai còn hiệu lực (thừa kế status từ Document cha).",
    ),
    Query(
        name="Q8_article_fulltext",
        cypher="""
            CALL db.index.fulltext.queryNodes('article_text', '"trình độ tiếng Anh"') YIELD node, score
            RETURN node.articleId AS articleId, score
        """,
        expected_rows=3,
        kind="fulltext",
        note="3 Điều (trong và ngoài NormativeContent) của 1345/QĐ-ĐHBK chứa đúng cụm 'trình độ tiếng Anh'.",
    ),
    Query(
        name="Q9_document_fulltext",
        cypher="""
            CALL db.index.fulltext.queryNodes('doc_text', '"Chiến lược"') YIELD node, score
            RETURN node.documentNumber AS documentNumber, score
        """,
        expected_rows=2,
        kind="fulltext",
        note="Baseline kiểu BM25 cấp văn bản: 3982/QĐ-ĐHĐN (title) và 4897/QĐ-ĐHĐN (summary nhắc 'chiến lược đào tạo/KHCN') đều khớp.",
    ),
    Query(
        name="Q10_hybrid_fulltext_then_expand",
        cypher="""
            CALL db.index.fulltext.queryNodes('doc_text', '"Đại học Đà Nẵng"') YIELD node, score
            WITH node, score ORDER BY score DESC LIMIT 5
            MATCH (node)-[:BASED_ON|REFERENCES*0..2]->(expanded:Document)
            RETURN DISTINCT expanded.documentNumber AS documentNumber, expanded.authorityLevel AS level
            ORDER BY expanded.authorityLevel DESC
        """,
        expected_rows=None,
        kind="hybrid",
        note="BM25 lọc ứng viên rồi mở rộng theo quan hệ — không assert số dòng cố định, chỉ soi kết quả.",
    ),
    Query(
        name="Q11_stub_sanity",
        cypher="""
            MATCH (d:Document {isStub: true})
            RETURN d.normalizedNumber AS normalizedNumber,
                   COUNT { (d)<-[:BASED_ON|REFERENCES|REPLACES|AMENDS|REPEALS]-() } AS incoming
            ORDER BY incoming DESC
        """,
        expected_rows=33,
        kind="lookup",
        note="33 Document stub tự sinh từ citation trỏ tới văn bản chưa map (đúng thực tế: kho thật cũng có tỷ lệ stub cao — README gốc ghi 1,8 stub/văn bản thật).",
    ),
    Query(
        name="Q12_mentions_count",
        cypher="MATCH (:Document)-[:MENTIONS]->() RETURN count(*) AS total",
        expected_rows=1,
        kind="lookup",
        note="Tổng 20 cạnh MENTIONS (Phòng/Ban được nhắc tới trong 'Trách nhiệm thi hành' của các văn bản) — đếm gộp một dòng.",
    ),
    Query(
        name="Q14_applies_to_count",
        cypher="MATCH (:Document)-[:APPLIES_TO]->() RETURN count(*) AS total",
        expected_rows=1,
        kind="lookup",
        note="Tổng cạnh APPLIES_TO (7: 003 và 009 -> Người học, 012 -> Doanh nghiệp/đối tác nước ngoài, 002 -> 2 nhóm, 010 -> 2 nhóm) — đếm gộp một dòng.",
    ),
    Query(
        name="Q15_target_group_lookup",
        cypher="""
            MATCH (d:Document)-[:APPLIES_TO]->(:TargetGroup {targetGroupId: 'nguoi_hoc'})
            RETURN d.documentNumber AS documentNumber
        """,
        expected_rows=2,
        kind="lookup",
        note="2 văn bản áp dụng cho nhóm 'Người học' (2231/QĐ-ĐHBK, 1345/QĐ-ĐHBK).",
    ),
    Query(
        name="Q13a_label_counts",
        cypher="MATCH (n) RETURN labels(n)[0] AS label, count(*) AS total ORDER BY total DESC",
        expected_rows=None,
        kind="sanity",
        note="Đếm tổng theo nhãn — smoke test thuần, không có số cố định.",
    ),
    Query(
        name="Q13b_relation_counts",
        cypher="MATCH ()-[r]->() RETURN type(r) AS relationType, count(*) AS total ORDER BY total DESC",
        expected_rows=None,
        kind="sanity",
        note="Đếm tổng theo loại quan hệ — smoke test thuần, không có số cố định.",
    ),
]
