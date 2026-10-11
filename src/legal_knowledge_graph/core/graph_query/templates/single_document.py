"""Nhóm 2 — Hỏi về MỘT văn bản cụ thể (theo số hiệu): nội dung, hiệu lực,
người ký, phạm vi áp dụng, danh mục Điều, toàn văn một Điều..."""

from __future__ import annotations

from .base import (ARTICLE_ORDER, ARTICLE_TO_DOC, DOC_TO_ARTICLE, GV, P_DOC, P_LIMIT, P_LIMIT_SHORT, P_PHRASE, PH,
                   QL, SV, Template, p_required)

_EX = {"normalizedNumber": "4511/QĐ-ĐHBK"}

TEMPLATES: list[Template] = [
    # ---------------------------------------------------------------- mức 1
    Template(
        name="TPL_DOCUMENT_DETAIL", action="document_detail", level=1, audience=(SV, PH, GV),
        description="Thông tin tổng quan một văn bản: tiêu đề, loại, cơ quan, người ký, ngày, hiệu lực, tóm tắt, lĩnh vực.",
        nl_examples=("Văn bản 4511/QĐ-ĐHBK nói gì?", "Cho biết thông tin về 08/2021/TT-BGDĐT"),
        cypher="""
            MATCH (d:Document {normalizedNumber: $normalizedNumber})
            OPTIONAL MATCH (d)-[:ISSUED_BY]->(org:Organization)
            OPTIONAL MATCH (d)-[:SIGNED_BY]->(p:Person)
            OPTIONAL MATCH (d)-[:HAS_TOPIC]->(t:Topic)
            RETURN d.documentNumber AS documentNumber, d.title AS title, d.documentType AS documentType,
                   d.status AS status, d.issueDate AS issueDate, d.effectiveDate AS effectiveDate,
                   d.summary AS summary, org.name AS issuedBy, p.fullName AS signedBy,
                   collect(DISTINCT t.name) AS topics, d.isStub AS isStub
            LIMIT 1
        """,
        params=(P_DOC,), example_params=_EX,
    ),
    Template(
        name="TPL_DOC_STATUS", action="document_status", level=1, audience=(SV, PH, GV),
        description="Văn bản còn hiệu lực không: tình trạng, ngày hiệu lực / hết hiệu lực, và đã bị văn bản nào "
                    "thay thế, bãi bỏ hoặc sửa đổi chưa.",
        nl_examples=("Quyết định 1345/QĐ-ĐHBK còn hiệu lực không?", "08/2021/TT-BGDĐT có còn áp dụng không?"),
        cypher="""
            MATCH (d:Document {normalizedNumber: $normalizedNumber})
            OPTIONAL MATCH (n:Document)-[r:REPLACES|REPEALS|AMENDS]->(d)
            WITH d, [x IN collect(DISTINCT CASE WHEN n IS NULL THEN NULL
                        ELSE {documentNumber: n.documentNumber, relation: type(r), issueDate: n.issueDate} END)
                     WHERE x IS NOT NULL] AS affectedBy
            RETURN d.documentNumber AS documentNumber, d.title AS title, d.status AS status,
                   d.effectiveDate AS effectiveDate, d.expiryDate AS expiryDate, d.isStub AS isStub, affectedBy,
                   CASE
                     WHEN any(x IN affectedBy WHERE x.relation IN ['REPLACES', 'REPEALS'])
                       THEN 'KHÔNG CÒN ÁP DỤNG: đã bị văn bản khác thay thế hoặc bãi bỏ'
                     WHEN d.status = 'HET_HIEU_LUC' THEN 'HẾT HIỆU LỰC'
                     WHEN d.status = 'CHUA_HIEU_LUC' THEN 'CHƯA CÓ HIỆU LỰC'
                     WHEN any(x IN affectedBy WHERE x.relation = 'AMENDS')
                       THEN 'CÒN HIỆU LỰC nhưng đã được sửa đổi, bổ sung một phần'
                     WHEN d.status = 'CON_HIEU_LUC' THEN 'CÒN HIỆU LỰC'
                     ELSE 'CHƯA RÕ (kho không ghi tình trạng hiệu lực)'
                   END AS conclusion
        """,
        params=(P_DOC,), example_params={"normalizedNumber": "1345/QĐ-ĐHBK"},
    ),
    Template(
        name="TPL_DOC_SIGNER", action="document_signer", level=1, audience=(SV, PH, GV),
        description="Ai ký văn bản, với chức danh và học hàm học vị.",
        nl_examples=("Ai ký Quyết định 1001/QĐ-ĐHBK?", "Người ký 08/2021/TT-BGDĐT là ai?"),
        cypher="""
            MATCH (d:Document {normalizedNumber: $normalizedNumber})-[:SIGNED_BY]->(p:Person)
            OPTIONAL MATCH (d)-[:ISSUED_BY]->(o:Organization)
            RETURN d.documentNumber AS documentNumber, p.fullName AS signer, p.academicTitle AS academicTitle,
                   p.position AS positions, o.name AS issuedBy, d.issueDate AS issueDate
        """,
        params=(P_DOC,), example_params={"normalizedNumber": "1001/QĐ-ĐHBK"},
    ),
    Template(
        name="TPL_DOC_TOPICS_TARGETS", action="document_applies_to", level=1, audience=(SV, PH, GV),
        description="Văn bản áp dụng cho ai (nhóm đối tượng) và thuộc lĩnh vực nào.",
        nl_examples=("Quy định 4511/QĐ-ĐHBK áp dụng cho ai?", "1001/QĐ-ĐHBK thuộc lĩnh vực gì?"),
        cypher="""
            MATCH (d:Document {normalizedNumber: $normalizedNumber})
            OPTIONAL MATCH (d)-[:APPLIES_TO]->(g:TargetGroup)
            OPTIONAL MATCH (d)-[:HAS_TOPIC]->(t:Topic)
            RETURN d.documentNumber AS documentNumber, d.title AS title,
                   collect(DISTINCT g.name) AS appliesTo, collect(DISTINCT t.name) AS topics
        """,
        params=(P_DOC,), example_params=_EX,
    ),
    # ---------------------------------------------------------------- mức 2
    Template(
        name="TPL_DOC_ISSUER_HIERARCHY", action="document_issuer", level=2, audience=(PH, GV),
        description="Cơ quan ban hành văn bản, cấp thẩm quyền, và các cơ quan cấp trên của cơ quan đó.",
        nl_examples=("Văn bản 4511/QĐ-ĐHBK do cơ quan nào ban hành, cấp nào?",
                     "08/2021/TT-BGDĐT thuộc thẩm quyền cấp nào?"),
        cypher="""
            MATCH (d:Document {normalizedNumber: $normalizedNumber})-[:ISSUED_BY]->(o:Organization)
            OPTIONAL MATCH path = (o)-[:PART_OF*1..4]->(parent:Organization)
            WITH d, o, path ORDER BY length(path) DESC LIMIT 1
            RETURN d.documentNumber AS documentNumber, d.documentType AS documentType,
                   d.authorityLevel AS authorityLevel, o.name AS issuedBy,
                   CASE WHEN path IS NULL THEN [] ELSE [n IN tail(nodes(path)) | n.name] END AS parentOrgs
        """,
        params=(P_DOC,), example_params=_EX,
    ),
    Template(
        name="TPL_DOC_ARTICLE_LIST", action="document_articles", level=2, audience=(SV, GV),
        description="Mục lục văn bản: danh sách các Điều kèm tiêu đề (cả Điều của quy chế / quy định ban hành kèm theo).",
        nl_examples=("Quy chế 1001/QĐ-ĐHBK gồm những Điều nào?", "Văn bản 1559/QĐ-BGDĐT có bao nhiêu Điều?"),
        cypher=f"""
            MATCH (d:Document {{normalizedNumber: $normalizedNumber}})
            MATCH {DOC_TO_ARTICLE}
            OPTIONAL MATCH (c:NormativeContent)-[:HAS_ARTICLE]->(a)
            RETURN a.number AS number, a.heading AS heading, coalesce(c.title, d.title) AS belongsTo,
                   a.articleId AS articleId
            ORDER BY c.contentId IS NOT NULL, {ARTICLE_ORDER}
            LIMIT $limit
        """,
        params=(P_DOC, P_LIMIT), example_params={"normalizedNumber": "1001/QĐ-ĐHBK"},
    ),
    Template(
        name="TPL_DOC_ARTICLE_TEXT", action="article_text", level=2, audience=(SV, PH, GV),
        description="Toàn văn một Điều cụ thể của một văn bản (ví dụ Điều 5 của Quy chế X).",
        nl_examples=("Điều 5 của Quyết định 1001/QĐ-ĐHBK nói gì?", "Cho xem Điều 2 văn bản 4511/QĐ-ĐHBK"),
        cypher=f"""
            MATCH (d:Document {{normalizedNumber: $normalizedNumber}})
            MATCH {DOC_TO_ARTICLE}
            WHERE a.number = $articleNumber
            OPTIONAL MATCH (c:NormativeContent)-[:HAS_ARTICLE]->(a)
            RETURN a.articleId AS articleId, a.number AS number, a.heading AS heading, a.text AS text,
                   coalesce(c.title, d.title) AS belongsTo, d.status AS status
            ORDER BY c.contentId IS NULL
        """,
        params=(P_DOC, p_required("articleNumber", "article_number")),
        example_params={"normalizedNumber": "1001/QĐ-ĐHBK", "articleNumber": "Điều 5"},
    ),
    Template(
        name="TPL_DOC_SCOPE_ARTICLES", action="document_scope", level=2, audience=(SV, PH, GV),
        description="Phạm vi điều chỉnh và đối tượng áp dụng của một văn bản (toàn văn các Điều tương ứng).",
        nl_examples=("Phạm vi điều chỉnh của 08/2021/TT-BGDĐT là gì?", "Quy chế 1001/QĐ-ĐHBK áp dụng với những ai?"),
        cypher=f"""
            MATCH (d:Document {{normalizedNumber: $normalizedNumber}})
            MATCH {DOC_TO_ARTICLE}
            WHERE toLower(a.heading) CONTAINS 'phạm vi' OR toLower(a.heading) CONTAINS 'đối tượng'
            RETURN a.articleId AS articleId, a.number AS number, a.heading AS heading, a.text AS text
            ORDER BY {ARTICLE_ORDER}
        """,
        params=(P_DOC,), example_params={"normalizedNumber": "08/2021/TT-BGDĐT"},
    ),
    Template(
        name="TPL_DOC_IMPLEMENTATION_CLAUSES", action="document_implementation", level=2, audience=(GV, QL),
        description="Điều khoản thi hành của văn bản: hiệu lực thi hành, trách nhiệm thi hành, văn bản bị thay thế.",
        nl_examples=("Văn bản 4511/QĐ-ĐHBK có hiệu lực từ khi nào, ai chịu trách nhiệm thi hành?",
                     "Điều khoản thi hành của 08/2021/TT-BGDĐT"),
        cypher=f"""
            MATCH (d:Document {{normalizedNumber: $normalizedNumber}})
            MATCH {DOC_TO_ARTICLE}
            WHERE a.isImplementationClause = true
            RETURN a.articleId AS articleId, a.number AS number, a.heading AS heading, a.text AS text
            ORDER BY {ARTICLE_ORDER}
        """,
        params=(P_DOC,), example_params=_EX,
    ),
    Template(
        name="TPL_DOC_PROMULGATED_CONTENT", action="document_contents", level=2, audience=(SV, GV),
        description="Văn bản ban hành kèm theo nội dung nào (Quy chế / Quy định...), mỗi nội dung có bao nhiêu Điều.",
        nl_examples=("Quyết định 1001/QĐ-ĐHBK ban hành kèm theo quy chế gì?",
                     "Thông tư 08/2021/TT-BGDĐT ban hành văn bản nào kèm theo?"),
        cypher="""
            MATCH (d:Document {normalizedNumber: $normalizedNumber})-[:PROMULGATES]->(c:NormativeContent)
            RETURN c.contentId AS contentId, c.contentType AS contentType, c.title AS title, c.status AS status,
                   COUNT { (c)-[:HAS_ARTICLE]->() } AS articleCount
        """,
        params=(P_DOC,), example_params={"normalizedNumber": "1001/QĐ-ĐHBK"},
    ),
    Template(
        name="TPL_DOC_MENTIONED_ORGS", action="document_mentions", level=2, audience=(GV, QL),
        description="Các đơn vị / tổ chức được nhắc tới trong văn bản (thường là đơn vị có trách nhiệm thi hành).",
        nl_examples=("Văn bản 4757/QĐ-ĐHĐN giao trách nhiệm cho những đơn vị nào?",
                     "Những đơn vị nào được nhắc tới trong 4511/QĐ-ĐHBK?"),
        cypher="""
            MATCH (d:Document {normalizedNumber: $normalizedNumber})-[:MENTIONS]->(o:Organization)
            RETURN o.name AS organization, o.orgType AS orgType
            ORDER BY organization
            LIMIT $limit
        """,
        params=(P_DOC, P_LIMIT), example_params={"normalizedNumber": "4757/QĐ-ĐHĐN"},
    ),
    # ---------------------------------------------------------------- mức 3
    Template(
        name="TPL_DOC_ARTICLE_SEARCH", action="search_articles", level=3, audience=(SV, PH, GV),
        description="Trong MỘT văn bản cụ thể, tìm các Điều nói về một nội dung (ví dụ học bổng trong Quy chế X).",
        nl_examples=("Trong Quy chế 1001/QĐ-ĐHBK, điều nào nói về khen thưởng?",
                     "08/2021/TT-BGDĐT quy định gì về thôi học?"),
        cypher=f"""
            CALL db.index.fulltext.queryNodes('article_text', $luceneQuery) YIELD node, score
            MATCH {ARTICLE_TO_DOC}
            WHERE d.normalizedNumber = $normalizedNumber
            RETURN node.articleId AS articleId, node.number AS number, node.heading AS heading,
                   node.text AS text, score
            ORDER BY score DESC
            LIMIT $limit
        """,
        params=(P_PHRASE, P_DOC, P_LIMIT_SHORT),
        example_params={"luceneQuery": "khen thưởng", "normalizedNumber": "1001/QĐ-ĐHBK"},
    ),
]
