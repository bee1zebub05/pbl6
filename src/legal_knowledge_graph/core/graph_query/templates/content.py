"""Nhóm 4 — Tìm theo NỘI DUNG quy định: các Điều nói về học phí, học bổng,
kỷ luật, tốt nghiệp...; quy chế / quy định ban hành kèm theo; kết hợp tìm
nội dung với lọc theo hiệu lực, cơ quan, đối tượng, lĩnh vực và căn cứ."""

from __future__ import annotations

from .base import (GV, ORG_IS, P_LIMIT, P_LIMIT_SHORT, P_PHRASE, PH, QL, SV, ParamSpec, Template,
                   fulltext_articles, p_optional, p_required)

TEMPLATES: list[Template] = [
    # ---------------------------------------------------------------- mức 1
    Template(
        name="TPL_NORMATIVE_CONTENT_BY_TYPE", action="list_contents", level=1, audience=(SV, GV),
        description="Liệt kê nội dung ban hành kèm theo theo loại (Quy chế, Quy định, Nội quy...), lọc hiệu lực tuỳ chọn.",
        nl_examples=("Có những Quy chế nào còn hiệu lực?", "Danh sách các Quy định đã ban hành"),
        cypher="""
            MATCH (d:Document)-[:PROMULGATES]->(c:NormativeContent)
            WHERE c.contentType = $contentType AND ($status IS NULL OR c.status = $status)
            RETURN c.contentId AS contentId, c.title AS title, c.status AS status, d.documentNumber AS documentNumber,
                   d.issueDate AS issueDate
            ORDER BY issueDate IS NULL, issueDate DESC
            LIMIT $limit
        """,
        params=(p_required("contentType", "content_type"), p_optional("status", "status"), P_LIMIT),
        example_params={"contentType": "Quy chế", "status": "CON_HIEU_LUC"},
    ),
    # ---------------------------------------------------------------- mức 2
    Template(
        name="TPL_CONTENT_TITLE_SEARCH", action="search_contents", level=2, audience=(SV, PH, GV),
        description="Tìm Quy chế / Quy định / Nội quy theo tên (ví dụ 'Quy chế đào tạo', 'Quy chế công tác sinh viên').",
        nl_examples=("Quy chế công tác sinh viên là văn bản nào?", "Tìm quy định về văn hoá học đường"),
        cypher="""
            CALL db.index.fulltext.queryNodes('content_text', $luceneQuery) YIELD node, score
            MATCH (d:Document)-[:PROMULGATES]->(node)
            RETURN node.title AS title, node.contentType AS contentType, node.status AS status,
                   d.documentNumber AS documentNumber, d.issueDate AS issueDate, score
            ORDER BY score DESC, issueDate DESC
            LIMIT $limit
        """,
        params=(P_PHRASE, P_LIMIT_SHORT), example_params={"luceneQuery": "công tác sinh viên"},
    ),
    # ---------------------------------------------------------------- mức 3
    fulltext_articles(
        name="TPL_ARTICLE_FULLTEXT_SEARCH", level=3, audience=(SV, PH, GV),
        description="Tìm các Điều có nội dung chứa một cụm từ (học bổng, học phí, kỷ luật, thôi học...) trong toàn kho.",
        nl_examples=("Điều nào quy định về học bổng khuyến khích học tập?", "Quy định về thôi học nằm ở đâu?"),
        example_params={"luceneQuery": "học bổng khuyến khích học tập"},
    ),
    fulltext_articles(
        name="TPL_ARTICLE_SEARCH_ACTIVE", level=3, audience=(SV, PH, GV),
        description="Tìm Điều về một nội dung CHỈ trong văn bản đang có hiệu lực (theo tình trạng hiệu lực yêu cầu).",
        nl_examples=("Quy định hiện hành về học phí nằm ở điều nào?",
                     "Điều nào còn hiệu lực nói về kỷ luật sinh viên?"),
        extra_where="d.status = $status", extra_params=(p_required("status", "status"),),
        example_params={"luceneQuery": "học phí", "status": "CON_HIEU_LUC"},
    ),
    fulltext_articles(
        name="TPL_ARTICLE_SEARCH_BY_ORG", level=3, audience=(SV, PH, GV),
        description="Tìm Điều về một nội dung trong văn bản của MỘT cơ quan (ví dụ quy định của ĐHBK về ký túc xá).",
        nl_examples=("Trường Đại học Bách khoa quy định gì về ký túc xá?", "Quy định của Bộ GD&ĐT về học bổng"),
        extra_where=f"EXISTS {{ MATCH (d)-[:ISSUED_BY]->(o:Organization) WHERE {ORG_IS} }}",
        extra_params=(p_required("orgId", "org"),),
        example_params={"luceneQuery": "ký túc xá", "orgId": "Trường Đại học Bách khoa"},
    ),
    fulltext_articles(
        name="TPL_ARTICLE_SEARCH_FOR_GROUP", level=3, audience=(SV, PH, GV),
        description="Tìm Điều về một nội dung trong văn bản áp dụng cho MỘT nhóm đối tượng (ví dụ sinh viên).",
        nl_examples=("Sinh viên bị kỷ luật thế nào?", "Quy định về khen thưởng áp dụng cho giảng viên"),
        extra_where="EXISTS { MATCH (d)-[:APPLIES_TO]->(:TargetGroup {targetGroupId: $targetGroupId}) }",
        extra_params=(p_required("targetGroupId", "target_group"),),
        example_params={"luceneQuery": "kỷ luật", "targetGroupId": "Người học"},
    ),
    fulltext_articles(
        name="TPL_ARTICLE_SEARCH_BY_TOPIC", level=3, audience=(GV, QL),
        description="Tìm Điều về một nội dung trong văn bản thuộc MỘT lĩnh vực.",
        nl_examples=("Trong lĩnh vực Tài chính, kế toán, điều nào nói về công tác phí?",
                     "Quy định về đánh giá trong lĩnh vực Đào tạo"),
        extra_where="EXISTS { MATCH (d)-[:HAS_TOPIC]->(:Topic {topicId: $topicId}) }",
        extra_params=(p_required("topicId", "topic"),),
        example_params={"luceneQuery": "công tác phí", "topicId": "Tài chính, kế toán"},
    ),
    # ---------------------------------------------------------------- mức 4
    Template(
        name="TPL_HYBRID_FULLTEXT_EXPAND", action="legal_basis", level=4, audience=(GV, QL),
        description="Văn bản về một chủ đề (tìm theo cụm từ) dựa trên những căn cứ pháp lý / văn bản gốc thẩm "
                    "quyền cao nào (tìm full-text rồi mở rộng theo quan hệ căn cứ).",
        nl_examples=("Những văn bản gốc thẩm quyền cao nào làm căn cứ cho các văn bản về Đại học Đà Nẵng?",
                     "Các quy định về học phí dựa trên luật nào?"),
        cypher="""
            CALL db.index.fulltext.queryNodes('doc_text', $luceneQuery) YIELD node, score
            WITH node, score ORDER BY score DESC LIMIT $seedLimit
            MATCH (node)-[:BASED_ON|REFERENCES*0..2]->(expanded:Document)
            RETURN DISTINCT expanded.documentNumber AS documentNumber, expanded.title AS title,
                   expanded.authorityLevel AS level, expanded.isStub AS isStub
            ORDER BY level DESC
            LIMIT $limit
        """,
        params=(P_PHRASE, ParamSpec("seedLimit", "int_limit", required=False, default=10), P_LIMIT),
        example_params={"luceneQuery": "học phí"},
    ),
]

