"""Nhóm 1 — Tra cứu danh sách văn bản (lọc theo cơ quan, lĩnh vực, đối tượng,
loại, năm, người ký...). Câu hỏi phổ biến nhất của mọi nhóm người dùng."""

from __future__ import annotations

from .base import (ALL_FILTERS, DOC_COLUMNS, GV, ORG_IS, P_LIMIT, P_LIMIT_SHORT, P_ORG, P_PERSON, P_PHRASE, PH,
                   QL, SV, Template, doc_filters, filter_params, list_documents_by, p_optional, p_required)

TEMPLATES: list[Template] = [
    # ---------------------------------------------------------------- mức 1
    list_documents_by(
        name="TPL_DOCS_BY_ORG_STATUS", level=1, audience=(SV, PH, GV),
        description="Liệt kê văn bản do một cơ quan / đơn vị ban hành, có thể lọc theo tình trạng hiệu lực.",
        nl_examples=("Văn bản nào do Trường Đại học Bách khoa ban hành còn hiệu lực?",
                     "Bộ Giáo dục và Đào tạo đã ban hành những văn bản nào?"),
        match=f"MATCH (d)-[:ISSUED_BY]->(o:Organization) WHERE {ORG_IS}",
        key=P_ORG, example_params={"orgId": "Trường Đại học Bách khoa", "status": "CON_HIEU_LUC"},
    ),
    list_documents_by(
        name="TPL_DOCS_BY_TOPIC", level=1, audience=(SV, PH, GV),
        description="Liệt kê văn bản thuộc một lĩnh vực nghiệp vụ (Đào tạo, Tuyển sinh, Công tác sinh viên...).",
        nl_examples=("Văn bản nào thuộc lĩnh vực Đào tạo?", "Có văn bản nào về Tuyển sinh không?"),
        match="MATCH (d)-[:HAS_TOPIC]->(:Topic {topicId: $topicId})",
        key=p_required("topicId", "topic"), example_params={"topicId": "Tuyển sinh"},
    ),
    list_documents_by(
        name="TPL_DOCS_BY_TARGET_GROUP", level=1, audience=(SV, PH, GV),
        description="Liệt kê văn bản áp dụng cho một nhóm đối tượng (Người học, cán bộ giảng viên...).",
        nl_examples=("Văn bản nào áp dụng cho sinh viên?", "Quy định nào áp dụng cho giảng viên?"),
        match="MATCH (d)-[:APPLIES_TO]->(:TargetGroup {targetGroupId: $targetGroupId})",
        key=p_required("targetGroupId", "target_group"), example_params={"targetGroupId": "Người học"},
    ),
    list_documents_by(
        name="TPL_DOCS_BY_TYPE", level=1, audience=(GV, QL),
        description="Liệt kê văn bản theo loại (Luật, Nghị định, Thông tư, Quyết định...).",
        nl_examples=("Trong kho có những Luật nào?", "Liệt kê các Nghị định còn hiệu lực"),
        match="WHERE d.documentType = $documentType",
        key=p_required("documentType", "doc_type"), example_params={"documentType": "Luật"},
    ),
    list_documents_by(
        name="TPL_DOCS_BY_YEAR", level=1, audience=(GV, QL),
        description="Liệt kê văn bản ban hành trong một năm cụ thể.",
        nl_examples=("Năm 2024 có những văn bản nào được ban hành?", "Văn bản ban hành năm 2021"),
        match="WHERE substring(d.issueDate, 0, 4) = toString($year)",
        key=p_required("year", "year"), example_params={"year": 2024},
    ),
    Template(
        name="TPL_DOCS_RECENT", action="recent_documents", level=1, audience=(SV, PH, GV),
        description="Các văn bản mới ban hành gần đây nhất trong kho.",
        nl_examples=("Có văn bản nào mới ban hành gần đây không?", "10 văn bản mới nhất"),
        cypher=f"""
            MATCH (d:Document {{isStub: false}}) WHERE d.issueDate IS NOT NULL
            RETURN {DOC_COLUMNS}
            ORDER BY d.issueDate IS NULL, d.issueDate DESC
            LIMIT $limit
        """,
        params=(P_LIMIT_SHORT,), example_params={"limit": 10},
    ),
    Template(
        name="TPL_DOCS_BY_SIGNER", action="documents_signed_by", level=1, audience=(GV, QL),
        description="Liệt kê văn bản do một người cụ thể ký.",
        nl_examples=("Thầy Đoàn Quang Vinh đã ký những văn bản nào?", "Văn bản do Nguyễn Ngọc Vũ ký"),
        cypher=f"""
            MATCH (d:Document)-[:SIGNED_BY]->(:Person {{personId: $personId}})
            RETURN {DOC_COLUMNS}
            ORDER BY d.issueDate IS NULL, d.issueDate DESC
            LIMIT $limit
        """,
        params=(P_PERSON, P_LIMIT), example_params={"personId": "Đoàn Quang Vinh"},
    ),
    # ---------------------------------------------------------------- mức 2
    Template(
        name="TPL_DOCS_SIGNED_BY_POSITION", action="documents_signed_by", level=2, audience=(GV, QL),
        description="Liệt kê văn bản do người giữ một chức danh ký (Hiệu trưởng, Bộ trưởng...), có thể lọc cơ quan. "
                    "Lưu ý dữ liệu: chức danh gộp theo người, không theo từng lần ký.",
        nl_examples=("Những văn bản nào do Hiệu trưởng ký?", "Văn bản Bộ trưởng ký ban hành"),
        cypher=f"""
            MATCH (d:Document)-[:SIGNED_BY]->(p:Person)
            WHERE any(pos IN p.position WHERE toLower(pos) = toLower($position))
              AND {doc_filters("orgId")}
            RETURN {DOC_COLUMNS}, p.fullName AS signer
            ORDER BY d.issueDate IS NULL, d.issueDate DESC
            LIMIT $limit
        """,
        params=(p_required("position", "text"), p_optional("orgId", "org"), P_LIMIT),
        example_params={"position": "Hiệu trưởng", "orgId": "Trường Đại học Bách khoa"},
    ),
    Template(
        name="TPL_DOCS_FILTERED", action="list_documents", level=2, audience=(SV, PH, GV),
        description="Liệt kê văn bản thoả ĐỒNG THỜI nhiều điều kiện: cơ quan, lĩnh vực, nhóm đối tượng, loại, "
                    "năm ban hành, hiệu lực (dùng khi câu hỏi có từ hai điều kiện trở lên).",
        nl_examples=("Văn bản về Công tác sinh viên do Trường Đại học Bách khoa ban hành",
                     "Thông tư nào về Đào tạo áp dụng cho người học?"),
        cypher=f"""
            MATCH (d:Document {{isStub: false}})
            WHERE {doc_filters(*ALL_FILTERS)}
            RETURN {DOC_COLUMNS}
            ORDER BY d.issueDate IS NULL, d.issueDate DESC
            LIMIT $limit
        """,
        params=(*filter_params(*ALL_FILTERS), P_LIMIT), min_slots=2,
        example_params={"orgId": "Trường Đại học Bách khoa", "topicId": "Công tác sinh viên"},
    ),
    Template(
        name="TPL_DOCS_SINCE_YEAR", action="list_documents", level=2, audience=(GV, QL),
        description="Liệt kê văn bản ban hành từ một năm trở lại đây, có thể lọc thêm cơ quan / lĩnh vực / hiệu lực.",
        nl_examples=("Từ năm 2023 đến nay ĐHBK ban hành những văn bản nào?", "Văn bản về Đào tạo từ 2022"),
        cypher=f"""
            MATCH (d:Document {{isStub: false}})
            WHERE substring(d.issueDate, 0, 4) >= toString($sinceYear)
              AND {doc_filters("orgId", "topicId", "status")}
            RETURN {DOC_COLUMNS}
            ORDER BY d.issueDate IS NULL, d.issueDate DESC
            LIMIT $limit
        """,
        params=(p_required("sinceYear", "year"), *filter_params("orgId", "topicId", "status"), P_LIMIT),
        example_params={"sinceYear": 2023, "orgId": "Trường Đại học Bách khoa"},
    ),
    Template(
        name="TPL_COUNT_DOCS", action="count_documents", level=2, audience=(SV, PH, GV),
        description="Đếm số văn bản thoả các điều kiện (cơ quan, lĩnh vực, đối tượng, loại, năm, hiệu lực).",
        nl_examples=("ĐHBK có bao nhiêu văn bản về Đào tạo?", "Kho có bao nhiêu Thông tư còn hiệu lực?"),
        cypher=f"""
            MATCH (d:Document {{isStub: false}})
            WHERE {doc_filters(*ALL_FILTERS)}
            RETURN count(d) AS total
        """,
        params=filter_params(*ALL_FILTERS),
        example_params={"orgId": "Trường Đại học Bách khoa", "topicId": "Đào tạo"},
    ),
    Template(
        name="TPL_DOCUMENT_FULLTEXT_SEARCH", action="search_documents", level=2, audience=(SV, PH, GV),
        description="Tìm văn bản có tiêu đề hoặc tóm tắt chứa một cụm từ.",
        nl_examples=("Văn bản nào có tên chứa 'Chiến lược'?", "Tìm văn bản về ký túc xá"),
        cypher="""
            CALL db.index.fulltext.queryNodes('doc_text', $luceneQuery) YIELD node, score
            RETURN node.documentNumber AS documentNumber, node.title AS title, node.status AS status,
                   node.issueDate AS issueDate, score
            ORDER BY score DESC
            LIMIT $limit
        """,
        params=(P_PHRASE, P_LIMIT_SHORT), example_params={"luceneQuery": "ký túc xá"},
    ),
    Template(
        name="TPL_LATEST_DOC_ABOUT", action="latest_document_about", level=2, audience=(SV, PH, GV),
        description="Văn bản MỚI NHẤT (còn hiệu lực) về một chủ đề — ví dụ quy định học phí / học bổng hiện hành.",
        nl_examples=("Quy định mới nhất về học bổng là văn bản nào?", "Văn bản hiện hành về học phí"),
        # Chỉ xét văn bản đủ liên quan (điểm >= 60% điểm cao nhất) rồi mới xếp
        # theo ngày — xếp thẳng theo ngày thì văn bản mới mà ít liên quan lên đầu.
        cypher="""
            CALL db.index.fulltext.queryNodes('doc_text', $luceneQuery) YIELD node, score
            WHERE node.isStub = false AND coalesce(node.status, 'CON_HIEU_LUC') = 'CON_HIEU_LUC'
              AND NOT EXISTS { MATCH (:Document)-[:REPLACES|REPEALS]->(node) }
            WITH collect({node: node, score: score}) AS hits
            WITH hits, reduce(best = 0.0, h IN hits | CASE WHEN h.score > best THEN h.score ELSE best END) AS best
            UNWIND hits AS h
            WITH h.node AS node, h.score AS score, best WHERE h.score >= 0.6 * best
            RETURN node.documentNumber AS documentNumber, node.title AS title, node.status AS status,
                   node.issueDate AS issueDate, score
            ORDER BY node.issueDate IS NULL, node.issueDate DESC, score DESC
            LIMIT $limit
        """,
        params=(P_PHRASE, P_LIMIT_SHORT), example_params={"luceneQuery": "học phí", "limit": 5},
    ),
    Template(
        name="TPL_DOCS_MENTIONING_ORG", action="documents_mentioning_org", level=2, audience=(GV, QL),
        description="Văn bản có nhắc tới / giao trách nhiệm cho một đơn vị (không phải đơn vị ban hành).",
        nl_examples=("Văn bản nào giao nhiệm vụ cho Phòng Tổ chức Hành chính?",
                     "Những văn bản nào có nhắc tới Kiểm toán nhà nước?"),
        cypher=f"""
            MATCH (d:Document)-[:MENTIONS]->(o:Organization)
            WHERE {ORG_IS}
            RETURN DISTINCT {DOC_COLUMNS}
            ORDER BY issueDate IS NULL, issueDate DESC
            LIMIT $limit
        """,
        params=(P_ORG, P_LIMIT), example_params={"orgId": "Phòng Tổ chức Hành chính"},
    ),
    # ---------------------------------------------------------------- mức 3
    Template(
        name="TPL_SUPERSEDED_DOCS", action="superseded_documents", level=3, audience=(GV, QL),
        description="Văn bản KHÔNG còn áp dụng: hết hiệu lực, hoặc đã bị văn bản khác thay thế / bãi bỏ "
                    "(kèm văn bản thay thế), có thể lọc theo cơ quan.",
        nl_examples=("Những văn bản nào của ĐHBK đã bị thay thế?", "Văn bản nào không còn áp dụng nữa?"),
        cypher=f"""
            MATCH (d:Document)
            WHERE {doc_filters("orgId")}
            OPTIONAL MATCH (n:Document)-[r:REPLACES|REPEALS]->(d)
            WITH d, collect(DISTINCT n.documentNumber + ' (' + type(r) + ')') AS supersededBy
            WHERE d.status = 'HET_HIEU_LUC' OR size(supersededBy) > 0
            RETURN d.documentNumber AS documentNumber, d.title AS title, d.status AS status,
                   d.isStub AS isStub, supersededBy
            ORDER BY documentNumber
            LIMIT $limit
        """,
        params=(p_optional("orgId", "org"), P_LIMIT), example_params={"orgId": "Trường Đại học Bách khoa"},
    ),
]
