"""Nhóm 6 — Thống kê và phân tích toàn kho: phân bố theo hiệu lực / loại /
năm / lĩnh vực / cấp thẩm quyền, văn bản nền tảng được căn cứ nhiều nhất,
văn bản còn thiếu trong kho, chuỗi thay thế dài nhất, dòng căn cứ giữa các
cơ quan. Ít được hỏi hơn, chủ yếu phục vụ quản lý và quản trị dữ liệu."""

from __future__ import annotations

from .base import DL, GV, P_LIMIT_SHORT, P_TOP_N, PH, QL, SV, ParamSpec, Template, doc_filters, filter_params

TEMPLATES: list[Template] = [
    # ---------------------------------------------------------------- mức 1
    Template(
        name="TPL_DOC_DISTRIBUTION_BY_STATUS", action="status_distribution", level=1, audience=(PH, GV),
        description="Thống kê toàn kho: bao nhiêu văn bản còn / hết hiệu lực.",
        nl_examples=("Có bao nhiêu văn bản còn hiệu lực, bao nhiêu hết hiệu lực?",
                     "Phân bố văn bản theo tình trạng hiệu lực?"),
        cypher="""
            MATCH (d:Document) WHERE d.isStub = false
            RETURN d.status AS status, count(*) AS total
            ORDER BY total DESC
        """,
    ),
    Template(
        name="TPL_DOC_COUNT_BY_TYPE", action="stats_by_type", level=1, audience=(PH, GV),
        description="Số văn bản theo từng loại (Luật, Nghị định, Thông tư, Quyết định...).",
        nl_examples=("Kho có bao nhiêu văn bản mỗi loại?", "Có bao nhiêu Luật, bao nhiêu Thông tư?"),
        cypher="""
            MATCH (d:Document {isStub: false})
            RETURN d.documentType AS documentType, count(*) AS total
            ORDER BY total DESC
        """,
    ),
    Template(
        name="TPL_DOC_COUNT_BY_TOPIC", action="stats_by_topic", level=1, audience=(SV, PH, GV),
        description="Số văn bản theo từng lĩnh vực, có thể giới hạn trong một cơ quan.",
        nl_examples=("Lĩnh vực nào có nhiều văn bản nhất?", "Số văn bản theo lĩnh vực của Đại học Đà Nẵng"),
        cypher=f"""
            MATCH (d:Document)-[:HAS_TOPIC]->(t:Topic)
            WHERE {doc_filters("orgId")}
            RETURN t.name AS topic, count(DISTINCT d) AS total
            ORDER BY total DESC
        """,
        params=filter_params("orgId"),
    ),
    # ---------------------------------------------------------------- mức 2
    Template(
        name="TPL_DOC_COUNT_BY_YEAR", action="stats_by_year", level=2, audience=(GV, QL),
        description="Số văn bản ban hành theo từng năm, có thể lọc theo cơ quan hoặc lĩnh vực.",
        nl_examples=("Mỗi năm ĐHBK ban hành bao nhiêu văn bản?", "Số văn bản về Đào tạo theo từng năm"),
        cypher=f"""
            MATCH (d:Document {{isStub: false}})
            WHERE d.issueDate IS NOT NULL AND {doc_filters("orgId", "topicId")}
            RETURN substring(d.issueDate, 0, 4) AS year, count(*) AS total
            ORDER BY year DESC
        """,
        params=filter_params("orgId", "topicId"), example_params={"orgId": "Trường Đại học Bách khoa"},
    ),
    Template(
        name="TPL_DOC_COUNT_BY_AUTHORITY_LEVEL", action="stats_by_authority_level", level=2, audience=(GV, QL),
        description="Số văn bản theo cấp thẩm quyền (6 Hiến pháp, 5 Luật, 4 Nghị định, 3 Thông tư/Bộ, "
                    "2 Đại học vùng, 1 Trường thành viên).",
        nl_examples=("Kho có bao nhiêu văn bản cấp trường, bao nhiêu văn bản cấp Bộ?",
                     "Phân bố văn bản theo cấp thẩm quyền"),
        cypher="""
            MATCH (d:Document {isStub: false})
            RETURN d.authorityLevel AS authorityLevel, count(*) AS total,
                   collect(DISTINCT d.documentType)[0..5] AS documentTypes
            ORDER BY authorityLevel DESC
        """,
    ),
    Template(
        name="TPL_CITATION_RELATION_COUNTS", action="relation_counts", level=2, audience=(QL, DL),
        description="Đếm số quan hệ căn cứ / trích dẫn / thay thế / sửa đổi / bãi bỏ trong toàn kho.",
        nl_examples=("Có bao nhiêu quan hệ trích dẫn trong đồ thị?", "Đếm số lượng từng loại quan hệ hiệu lực"),
        cypher="""
            MATCH ()-[r]->() WHERE type(r) IN ['BASED_ON','REFERENCES','REPLACES','AMENDS','REPEALS']
            RETURN type(r) AS relationType, count(*) AS total
            ORDER BY total DESC
        """,
    ),
    # ---------------------------------------------------------------- mức 3
    Template(
        name="TPL_AMENDS_TARGET_STILL_ACTIVE", action="amended_still_active", level=3, audience=(GV, QL),
        description="Văn bản bị sửa đổi một phần nhưng tổng thể vẫn còn hiệu lực, kèm các văn bản đã sửa.",
        nl_examples=("Những văn bản nào bị sửa đổi nhưng vẫn còn hiệu lực?", "Văn bản nào đã bị sửa đổi một phần?"),
        cypher="""
            MATCH (a:Document)-[:AMENDS]->(b:Document)
            WHERE b.status = $status
            RETURN b.documentNumber AS target, b.title AS title, collect(a.documentNumber) AS amenders
            ORDER BY target
            LIMIT $limit
        """,
        params=(ParamSpec("status", "status", required=False, default="CON_HIEU_LUC"), P_LIMIT_SHORT),
    ),
    Template(
        name="TPL_MOST_CITED_DOCS", action="most_cited", level=3, audience=(GV, QL),
        description="Văn bản nền tảng: được nhiều văn bản khác lấy làm căn cứ nhất.",
        nl_examples=("Văn bản nào được căn cứ nhiều nhất?", "Những văn bản pháp lý quan trọng nhất trong kho là gì?"),
        cypher="""
            MATCH (t:Document)<-[r:BASED_ON]-(:Document)
            RETURN t.documentNumber AS documentNumber, t.title AS title, t.documentType AS documentType,
                   t.isStub AS isStub, count(r) AS citedBy
            ORDER BY citedBy DESC
            LIMIT $limit
        """,
        params=(P_TOP_N,),
    ),
    # ---------------------------------------------------------------- mức 4
    Template(
        name="TPL_MISSING_CITED_DOCS", action="missing_documents", level=4, audience=(QL, DL),
        description="Văn bản được viện dẫn nhiều nhưng CHƯA có toàn văn trong kho (node stub) — nên bổ sung.",
        nl_examples=("Văn bản nào hay được nhắc tới nhưng kho chưa có?", "Kho đang thiếu những văn bản quan trọng nào?"),
        cypher="""
            MATCH (t:Document {isStub: true})<-[r]-(:Document)
            RETURN t.documentNumber AS documentNumber, count(r) AS mentions,
                   collect(DISTINCT type(r)) AS relationTypes
            ORDER BY mentions DESC
            LIMIT $limit
        """,
        params=(P_TOP_N,),
    ),
    Template(
        name="TPL_LONGEST_REPLACEMENT_CHAINS", action="longest_chains", level=4, audience=(QL, DL),
        description="Những chuỗi thay thế / sửa đổi dài nhất — chính sách được cập nhật qua nhiều đời nhất.",
        nl_examples=("Quy định nào đã được thay thế, sửa đổi qua nhiều đời nhất?",
                     "Chuỗi văn bản thay thế nhau dài nhất trong kho"),
        cypher="""
            MATCH path = (newest:Document)-[:REPLACES|AMENDS*2..6]->(oldest:Document)
            WHERE NOT EXISTS { MATCH (:Document)-[:REPLACES|AMENDS]->(newest) }
              AND NOT EXISTS { MATCH (oldest)-[:REPLACES|AMENDS]->(:Document) }
              // bỏ node stub có số hiệu hỏng (mất phần số, ví dụ "/QĐ-ĐHĐN")
              AND all(n IN nodes(path) WHERE NOT n.documentNumber STARTS WITH '/')
            RETURN [n IN nodes(path) | n.documentNumber] AS chain, length(path) AS length,
                   newest.title AS currentTitle
            ORDER BY length DESC
            LIMIT $limit
        """,
        params=(P_TOP_N,),
    ),
    # ---------------------------------------------------------------- mức 5
    Template(
        name="TPL_ORG_CITATION_FLOW", action="org_citation_flow", level=5, audience=(QL, DL),
        description="Dòng căn cứ giữa các cơ quan: văn bản của cơ quan A căn cứ vào văn bản của cơ quan B bao nhiêu lần.",
        nl_examples=("Văn bản của ĐHBK chủ yếu căn cứ vào văn bản của cơ quan nào?",
                     "Các cơ quan dựa vào văn bản của nhau như thế nào?"),
        cypher=f"""
            MATCH (src:Organization)<-[:ISSUED_BY]-(d:Document)-[:BASED_ON]->(t:Document)-[:ISSUED_BY]->(dst:Organization)
            WHERE {doc_filters("orgId")}
            RETURN src.name AS fromOrg, dst.name AS basedOnOrg, count(*) AS citations
            ORDER BY citations DESC
            LIMIT $limit
        """,
        params=(*filter_params("orgId"), P_LIMIT_SHORT), example_params={"orgId": "Trường Đại học Bách khoa"},
    ),
]
