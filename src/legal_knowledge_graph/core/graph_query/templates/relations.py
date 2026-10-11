"""Nhóm 3 — Quan hệ giữa các văn bản: căn cứ pháp lý, trích dẫn, thay thế,
sửa đổi, bãi bỏ, chuỗi phiên bản. Từ 1 bước tới nhiều bước (multi-hop)."""

from __future__ import annotations

from .base import (GV, P_DOC, P_LIMIT, P_LIMIT_SHORT, PH, QL, RELATED_COLUMNS, SV, Template,
                   relation_of_document)

TEMPLATES: list[Template] = [
    # ---------------------------------------------------------------- mức 2
    relation_of_document(
        name="TPL_DOC_LEGAL_BASIS", action="document_legal_basis", level=2, audience=(GV, QL),
        description="Căn cứ pháp lý TRỰC TIẾP của một văn bản (các văn bản trong mục 'Căn cứ...').",
        nl_examples=("Quyết định 4511/QĐ-ĐHBK căn cứ vào những văn bản nào?", "Căn cứ pháp lý của 1001/QĐ-ĐHBK"),
        pattern="(x)-[r:BASED_ON]->(t:Document)", columns=RELATED_COLUMNS,
        example_params={"normalizedNumber": "4511/QĐ-ĐHBK"},
    ),
    relation_of_document(
        name="TPL_DOC_REFERENCES", action="document_references", level=2, audience=(GV, QL),
        description="Các văn bản được một văn bản NHẮC TỚI trong nội dung (không phải căn cứ, thay thế, sửa đổi).",
        nl_examples=("Văn bản 1214/QĐ-ĐHBK có nhắc tới văn bản nào khác?",
                     "Trong 1137/QĐ-BGDĐT dẫn chiếu những văn bản nào?"),
        pattern="(x)-[r:REFERENCES]->(t:Document)", columns=RELATED_COLUMNS,
        example_params={"normalizedNumber": "1214/QĐ-ĐHBK"},
    ),
    relation_of_document(
        name="TPL_DOC_CITED_BY", action="document_cited_by", level=2, audience=(GV, QL),
        description="Những văn bản lấy một văn bản làm căn cứ hoặc có nhắc tới nó (chiều ngược của căn cứ).",
        nl_examples=("Những văn bản nào căn cứ vào Thông tư 08/2021/TT-BGDĐT?",
                     "Có bao nhiêu văn bản dựa trên 10/2020/TT-BGDĐT?"),
        pattern="(t:Document)-[r:BASED_ON|REFERENCES]->(x)",
        columns=f"{RELATED_COLUMNS}, type(r) AS relation",
        example_params={"normalizedNumber": "08/2021/TT-BGDĐT"},
    ),
    relation_of_document(
        name="TPL_REPLACED_BY", action="replaced_by", level=2, audience=(SV, PH, GV),
        description="Văn bản cũ đã bị văn bản MỚI HƠN nào thay thế.",
        nl_examples=("Văn bản nào đã thay thế 42/2007/QĐ-BGDĐT?", "2529/QĐ-ĐHBK đã bị thay bởi văn bản nào?"),
        pattern="(t:Document)-[r:REPLACES]->(x)", columns=RELATED_COLUMNS,
        example_params={"normalizedNumber": "42/2007/QĐ-BGDĐT"},
    ),
    relation_of_document(
        name="TPL_DOC_AMENDED_BY", action="amended_by", level=2, audience=(SV, GV, QL),
        description="Văn bản đã bị những văn bản nào SỬA ĐỔI, BỔ SUNG (kèm Điều bị sửa nếu có).",
        nl_examples=("Thông tư 10/2016/TT-BGDĐT đã được sửa đổi bởi văn bản nào?",
                     "Quy định 2231/QĐ-ĐHBK có bị sửa đổi không?"),
        pattern="(t:Document)-[r:AMENDS]->(x)",
        columns=f"{RELATED_COLUMNS}, r.targetArticle AS targetArticle",
        example_params={"normalizedNumber": "10/2016/TT-BGDĐT"},
    ),
    relation_of_document(
        name="TPL_DOC_REPEALED_BY", action="repealed_by", level=2, audience=(GV, QL),
        description="Văn bản đã bị văn bản nào BÃI BỎ.",
        nl_examples=("Thông tư 30/2023/TT-BGDĐT bị bãi bỏ bởi văn bản nào?", "15/2018/TT-BGDĐT còn hay đã bị bãi bỏ?"),
        pattern="(t:Document)-[r:REPEALS]->(x)", columns=RELATED_COLUMNS,
        example_params={"normalizedNumber": "30/2023/TT-BGDĐT"},
    ),
    relation_of_document(
        name="TPL_DOC_WHAT_IT_AMENDS", action="what_it_amends", level=2, audience=(GV, QL),
        description="Một văn bản sửa đổi, bổ sung những văn bản nào (và Điều nào).",
        nl_examples=("Quyết định 1088/QĐ-ĐHBK sửa đổi văn bản nào?", "107/QĐ-ĐHBK sửa đổi những điều gì?"),
        pattern="(x)-[r:AMENDS]->(t:Document)",
        columns=f"{RELATED_COLUMNS}, r.targetArticle AS targetArticle",
        example_params={"normalizedNumber": "1088/QĐ-ĐHBK"},
    ),
    relation_of_document(
        name="TPL_DOC_WHAT_IT_REPEALS", action="what_it_repeals", level=2, audience=(GV, QL),
        description="Một văn bản bãi bỏ những văn bản nào.",
        nl_examples=("Thông tư 49/2026/TT-BGDĐT bãi bỏ những văn bản nào?", "78/2020/NĐ-CP bãi bỏ gì?"),
        pattern="(x)-[r:REPEALS]->(t:Document)", columns=RELATED_COLUMNS,
        example_params={"normalizedNumber": "49/2026/TT-BGDĐT"},
    ),
    # ---------------------------------------------------------------- mức 3
    Template(
        name="TPL_AMEND_REPLACE_CHAIN", action="what_it_replaced", level=3, audience=(GV, QL),
        description="Văn bản đã thay thế / sửa đổi những văn bản CŨ HƠN nào, qua nhiều đời (chuỗi lịch sử).",
        nl_examples=("4511/QĐ-ĐHBK đã thay thế những văn bản nào?",
                     "Chuỗi các văn bản cũ mà 3868/QĐ-ĐHBK đã thay thế"),
        cypher="""
            MATCH path = (x:Document {normalizedNumber: $normalizedNumber})-[:AMENDS|REPLACES*1..5]->(t:Document)
            WITH t, min(length(path)) AS depth, last(relationships(path)) AS r
            RETURN DISTINCT t.documentNumber AS documentNumber, t.title AS title, t.issueDate AS issueDate,
                   t.isStub AS isStub, type(r) AS relation, depth
            ORDER BY depth, issueDate IS NULL, issueDate DESC
            LIMIT $limit
        """,
        params=(P_DOC, P_LIMIT_SHORT), example_params={"normalizedNumber": "3868/QĐ-ĐHBK"},
    ),
    Template(
        name="TPL_DOC_LATEST_VERSION", action="latest_version", level=3, audience=(SV, PH, GV),
        description="Phiên bản HIỆN HÀNH của một văn bản: đi theo chuỗi thay thế tới văn bản mới nhất chưa bị thay.",
        nl_examples=("Bản mới nhất thay cho 2929/QĐ-ĐHBK là văn bản nào?",
                     "Quy định 760/QĐ-ĐHBK hiện nay đã được thay bằng bản nào?"),
        cypher="""
            MATCH (x:Document {normalizedNumber: $normalizedNumber})
            OPTIONAL MATCH path = (newer:Document)-[:REPLACES*1..6]->(x)
            WHERE NOT EXISTS { MATCH (:Document)-[:REPLACES]->(newer) }
            WITH x, newer, path ORDER BY length(path) DESC LIMIT 1
            RETURN x.documentNumber AS askedDocument, x.status AS askedStatus,
                   coalesce(newer.documentNumber, x.documentNumber) AS currentVersion,
                   coalesce(newer.title, x.title) AS currentTitle,
                   coalesce(newer.status, x.status) AS currentStatus,
                   CASE WHEN path IS NULL THEN 0 ELSE length(path) END AS replacements,
                   CASE WHEN path IS NULL THEN [] ELSE [n IN reverse(nodes(path)) | n.documentNumber] END AS chain
        """,
        params=(P_DOC,), example_params={"normalizedNumber": "2929/QĐ-ĐHBK"},
    ),
    Template(
        name="TPL_DOC_VERSION_HISTORY", action="version_history", level=3, audience=(GV, QL),
        description="Toàn bộ lịch sử phiên bản quanh một văn bản: các bản cũ hơn nó thay / sửa và các bản mới hơn "
                    "thay / sửa nó.",
        nl_examples=("Lịch sử các lần sửa đổi, thay thế của 2652/QĐ-ĐHBK", "Quy định 1345/QĐ-ĐHBK đã qua mấy phiên bản?"),
        cypher="""
            MATCH (x:Document {normalizedNumber: $normalizedNumber})
            CALL (x) {
                MATCH path = (x)-[:AMENDS|REPLACES*1..5]->(t:Document)
                RETURN t, -min(length(path)) AS position, 'cũ hơn' AS direction
                UNION
                MATCH path = (t:Document)-[:AMENDS|REPLACES*1..5]->(x)
                RETURN t, min(length(path)) AS position, 'mới hơn' AS direction
            }
            RETURN DISTINCT t.documentNumber AS documentNumber, t.title AS title, t.issueDate AS issueDate,
                   t.status AS status, direction, position
            ORDER BY position
            LIMIT $limit
        """,
        params=(P_DOC, P_LIMIT_SHORT), example_params={"normalizedNumber": "2652/QĐ-ĐHBK"},
    ),
    Template(
        name="TPL_DOC_ALL_RELATIONS", action="document_relations", level=3, audience=(GV, QL),
        description="Tổng hợp MỌI quan hệ của một văn bản theo từng loại, cả chiều đi lẫn chiều đến.",
        nl_examples=("Văn bản 4511/QĐ-ĐHBK liên quan tới những văn bản nào?",
                     "Tổng hợp quan hệ của 10/2016/TT-BGDĐT"),
        cypher="""
            MATCH (x:Document {normalizedNumber: $normalizedNumber})
            CALL (x) {
                MATCH (x)-[r:BASED_ON|REFERENCES|REPLACES|AMENDS|REPEALS]->(t:Document)
                RETURN type(r) AS relation, 'đi' AS direction, t
                UNION
                MATCH (t:Document)-[r:BASED_ON|REFERENCES|REPLACES|AMENDS|REPEALS]->(x)
                RETURN type(r) AS relation, 'đến' AS direction, t
            }
            RETURN relation, direction, count(t) AS total, collect(t.documentNumber)[0..10] AS documents
            ORDER BY direction, total DESC
        """,
        params=(P_DOC,), example_params={"normalizedNumber": "10/2016/TT-BGDĐT"},
    ),
    # ---------------------------------------------------------------- mức 4
    Template(
        name="TPL_DOC_LEGAL_BASIS_CHAIN", action="legal_basis_chain", level=4, audience=(GV, QL),
        description="Truy ngược chuỗi căn cứ nhiều tầng của một văn bản tới văn bản gốc có thẩm quyền cao nhất "
                    "(Quyết định trường -> Thông tư -> Nghị định -> Luật).",
        nl_examples=("Quyết định 1092/QĐ-ĐHBK suy cho cùng dựa trên Luật nào?",
                     "Chuỗi căn cứ pháp lý nhiều tầng của 4511/QĐ-ĐHBK"),
        cypher="""
            MATCH path = (x:Document {normalizedNumber: $normalizedNumber})-[:BASED_ON*1..3]->(t:Document)
            WITH t, min(length(path)) AS hops
            RETURN t.documentNumber AS documentNumber, t.title AS title, t.documentType AS documentType,
                   t.authorityLevel AS authorityLevel, t.isStub AS isStub, hops
            ORDER BY coalesce(authorityLevel, 0) DESC, hops
            LIMIT $limit
        """,
        params=(P_DOC, P_LIMIT_SHORT), example_params={"normalizedNumber": "1092/QĐ-ĐHBK"},
    ),
    Template(
        name="TPL_DOC_RELATED", action="related_documents", level=4, audience=(SV, GV),
        description="Văn bản liên quan tới một văn bản: cùng lĩnh vực, cùng nhóm đối tượng, chung căn cứ — xếp theo "
                    "mức độ liên quan.",
        nl_examples=("Ngoài 4511/QĐ-ĐHBK còn văn bản nào liên quan cần đọc thêm?",
                     "Văn bản tương tự 1001/QĐ-ĐHBK"),
        cypher="""
            MATCH (x:Document {normalizedNumber: $normalizedNumber})
            MATCH (t:Document {isStub: false}) WHERE t <> x
            WITH x, t,
                 COUNT { (x)-[:HAS_TOPIC]->(tp)<-[:HAS_TOPIC]-(t) } AS sharedTopics,
                 COUNT { (x)-[:APPLIES_TO]->(g)<-[:APPLIES_TO]-(t) } AS sharedGroups,
                 COUNT { (x)-[:BASED_ON]->(b)<-[:BASED_ON]-(t) } AS sharedBasis
            WITH t, sharedTopics, sharedGroups, sharedBasis, 2 * sharedTopics + sharedGroups + sharedBasis AS score
            WHERE score >= 3
            RETURN t.documentNumber AS documentNumber, t.title AS title, t.status AS status,
                   sharedTopics, sharedGroups, sharedBasis, score
            ORDER BY score DESC, t.issueDate DESC
            LIMIT $limit
        """,
        params=(P_DOC, P_LIMIT_SHORT), example_params={"normalizedNumber": "4511/QĐ-ĐHBK"},
    ),
    # ---------------------------------------------------------------- mức 5
    Template(
        name="TPL_DOCS_SHARING_BASIS", action="documents_sharing_basis", level=5, audience=(QL,),
        description="Những văn bản dùng CHUNG căn cứ pháp lý với một văn bản (ít nhất 2 căn cứ chung) — hữu ích "
                    "khi một căn cứ thay đổi cần rà soát văn bản bị ảnh hưởng.",
        nl_examples=("Văn bản nào có cùng căn cứ pháp lý với 4511/QĐ-ĐHBK?",
                     "Nếu căn cứ của 1001/QĐ-ĐHBK thay đổi thì văn bản nào khác bị ảnh hưởng?"),
        cypher="""
            MATCH (x:Document {normalizedNumber: $normalizedNumber})-[:BASED_ON]->(b:Document)<-[:BASED_ON]-(t:Document)
            WHERE t <> x
            WITH t, collect(DISTINCT b.documentNumber) AS sharedBasis
            WHERE size(sharedBasis) >= 2
            RETURN t.documentNumber AS documentNumber, t.title AS title, t.status AS status,
                   size(sharedBasis) AS sharedCount, sharedBasis
            ORDER BY sharedCount DESC
            LIMIT $limit
        """,
        params=(P_DOC, P_LIMIT), example_params={"normalizedNumber": "4511/QĐ-ĐHBK"},
    ),
]

