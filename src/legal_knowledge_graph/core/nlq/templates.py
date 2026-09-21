"""
Thư viện 14 template Cypher cho nhánh "template-first" của NLQ — mỗi
template lấy nguyên Cypher ĐÃ TEST trong core/query/catalog.py hoặc
core/query/benchmark_catalog.py, chỉ thay literal cụ thể bằng $param.

LLM (Stage A, xem match_template.py) KHÔNG được tự viết Cypher ở nhánh
này — nó chỉ chọn 1 TEMPLATES[name] và trích tham số thô (raw string).
resolve.py mới là nơi biến tham số thô thành giá trị thật (orgId,
normalizedNumber...) trước khi điền vào $param.

Cố tình KHÔNG đưa vào v1 (xem plan): B2/B3/B4/B7/B10 (gần trùng #14/#13),
B9/B16/B17 (câu kiểm tra chất lượng dữ liệu cho người bảo trì, không phải
câu hỏi nghiệp vụ), Q6/Q11/Q12/Q13a/Q13b/Q14 (sanity/đếm thuần).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Các loại resolver hợp lệ — khớp tên hàm resolve_<kind> trong resolve.py.
ResolverKind = str  # "org" | "topic" | "target_group" | "doc_number" |
                     # "status" | "content_type" | "fulltext_phrase" | "int_limit"


@dataclass(frozen=True)
class ParamSpec:
    name: str
    resolver: ResolverKind
    required: bool = True
    default_raw: str | None = None  # giá trị thô mặc định nếu Stage A không trích được (vd "50" cho limit)


@dataclass(frozen=True)
class Template:
    name: str
    description: str  # đưa vào prompt Stage A để Gemini chọn
    nl_examples: tuple[str, ...]
    cypher: str
    params: tuple[ParamSpec, ...] = field(default_factory=tuple)


TEMPLATES: dict[str, Template] = {
    t.name: t
    for t in [
        Template(
            name="TPL_DOCS_BY_ORG_STATUS",
            description="Tra văn bản do một cơ quan/đơn vị cụ thể ban hành, có thể lọc theo tình trạng hiệu lực.",
            nl_examples=(
                "Văn bản nào do Trường Đại học Bách khoa ban hành?",
                "Văn bản còn hiệu lực của Đại học Đà Nẵng",
                "Bộ Giáo dục và Đào tạo đã ban hành những văn bản nào?",
            ),
            cypher="""
                MATCH (d:Document)-[:ISSUED_BY]->(:Organization {orgId: $orgId})
                WHERE $status IS NULL OR d.status = $status
                RETURN d.documentNumber AS documentNumber, d.title AS title,
                       d.status AS status, d.issueDate AS issueDate
                ORDER BY d.issueDate DESC
                LIMIT $limit
            """,
            params=(
                ParamSpec("orgId", "org"),
                ParamSpec("status", "status", required=False, default_raw=None),
                ParamSpec("limit", "int_limit", required=False, default_raw="50"),
            ),
        ),
        Template(
            name="TPL_DOCS_BY_TOPIC",
            description="Tra văn bản thuộc một lĩnh vực nghiệp vụ cụ thể (trong 18 lĩnh vực chuẩn).",
            nl_examples=(
                "Văn bản nào thuộc lĩnh vực Đào tạo?",
                "Danh sách văn bản về Tuyển sinh",
                "Có văn bản nào về Thi đua, khen thưởng không?",
            ),
            cypher="""
                MATCH (d:Document)-[:HAS_TOPIC]->(:Topic {topicId: $topicId})
                WHERE $status IS NULL OR d.status = $status
                RETURN d.documentNumber AS documentNumber, d.title AS title, d.status AS status
                ORDER BY d.issueDate DESC
                LIMIT $limit
            """,
            params=(
                ParamSpec("topicId", "topic"),
                ParamSpec("status", "status", required=False, default_raw=None),
                ParamSpec("limit", "int_limit", required=False, default_raw="50"),
            ),
        ),
        Template(
            name="TPL_DOCS_BY_TARGET_GROUP",
            description="Tra văn bản áp dụng cho một nhóm đối tượng cụ thể (trong 8 nhóm chuẩn, VD Người học).",
            nl_examples=(
                "Văn bản nào áp dụng cho sinh viên?",
                "Văn bản nào liên quan tới cán bộ, giảng viên?",
            ),
            cypher="""
                MATCH (d:Document)-[:APPLIES_TO]->(:TargetGroup {targetGroupId: $targetGroupId})
                RETURN d.documentNumber AS documentNumber, d.title AS title
                ORDER BY d.issueDate DESC
                LIMIT $limit
            """,
            params=(
                ParamSpec("targetGroupId", "target_group"),
                ParamSpec("limit", "int_limit", required=False, default_raw="50"),
            ),
        ),
        Template(
            name="TPL_DOCUMENT_DETAIL",
            description="Tra thông tin chi tiết MỘT văn bản cụ thể theo số hiệu (cơ quan ban hành, người ký, lĩnh vực, tóm tắt).",
            nl_examples=(
                "Văn bản 4511/QĐ-ĐHBK nói gì?",
                "Cho biết thông tin về 30/2020/TT-BGDĐT",
                "1345/QĐ-ĐHBK do ai ký?",
            ),
            cypher="""
                MATCH (d:Document {normalizedNumber: $normalizedNumber})
                OPTIONAL MATCH (d)-[:ISSUED_BY]->(org:Organization)
                OPTIONAL MATCH (d)-[:SIGNED_BY]->(p:Person)
                OPTIONAL MATCH (d)-[:HAS_TOPIC]->(t:Topic)
                RETURN d.documentNumber AS documentNumber, d.title AS title,
                       d.documentType AS documentType, d.status AS status,
                       d.issueDate AS issueDate, d.effectiveDate AS effectiveDate,
                       d.summary AS summary, org.name AS issuedBy, p.fullName AS signedBy,
                       collect(DISTINCT t.name) AS topics
                LIMIT 1
            """,
            params=(ParamSpec("normalizedNumber", "doc_number"),),
        ),
        Template(
            name="TPL_AMEND_REPLACE_CHAIN",
            description="Cho một văn bản cụ thể, tìm các văn bản CŨ HƠN mà CHÍNH NÓ đã sửa đổi/thay thế (chiều: văn bản input -> văn bản cũ hơn nó thay thế), có thể qua nhiều đời (multi-hop). KHÔNG dùng cho chiều ngược lại (tìm văn bản nào đã thay thế nó — dùng TPL_REPLACED_BY).",
            nl_examples=(
                "4511/QĐ-ĐHBK đã thay thế/sửa đổi những văn bản nào?",
                "Chuỗi các văn bản cũ mà 4757/QĐ-ĐHĐN đã thay thế, qua bao nhiêu đời?",
            ),
            cypher="""
                MATCH path = (d:Document {normalizedNumber: $normalizedNumber})-[:AMENDS|REPLACES*1..5]->(b:Document)
                RETURN b.documentNumber AS documentNumber, length(path) AS depth
                ORDER BY depth
                LIMIT $limit
            """,
            params=(
                ParamSpec("normalizedNumber", "doc_number"),
                ParamSpec("limit", "int_limit", required=False, default_raw="20"),
            ),
        ),
        Template(
            name="TPL_REPLACED_BY",
            description="Cho một văn bản CŨ, tìm văn bản MỚI HƠN nào đã thay thế nó (chiều: văn bản input bị thay thế -> văn bản mới hơn). KHÔNG dùng cho chiều ngược lại (văn bản này đã thay thế cái gì — dùng TPL_AMEND_REPLACE_CHAIN).",
            nl_examples=(
                "Văn bản nào đã thay thế 882/QĐ-ĐHĐN?",
                "2529/QĐ-ĐHBK đã bị thay bởi văn bản nào?",
                "Bản mới nhất của 882/QĐ-ĐHĐN là gì?",
            ),
            cypher="""
                MATCH (moi:Document)-[:REPLACES]->(:Document {normalizedNumber: $normalizedNumber})
                RETURN moi.documentNumber AS documentNumber, moi.status AS status
            """,
            params=(ParamSpec("normalizedNumber", "doc_number"),),
        ),
        Template(
            name="TPL_AMENDS_TARGET_STILL_ACTIVE",
            description="Liệt kê văn bản bị sửa đổi (AMENDS) một phần nhưng tổng thể vẫn còn hiệu lực, kèm những văn bản đã sửa nó.",
            nl_examples=(
                "Những văn bản nào bị sửa đổi nhưng vẫn còn hiệu lực?",
                "Văn bản nào đã bị sửa đổi một phần?",
            ),
            cypher="""
                MATCH (a:Document)-[:AMENDS]->(b:Document)
                WHERE b.status = $status
                RETURN b.documentNumber AS target, collect(a.documentNumber) AS amenders
                ORDER BY target
                LIMIT $limit
            """,
            params=(
                ParamSpec("status", "status", required=False, default_raw="CON_HIEU_LUC"),
                ParamSpec("limit", "int_limit", required=False, default_raw="50"),
            ),
        ),
        Template(
            name="TPL_CITATION_RELATION_COUNTS",
            description="Đếm số lượng từng loại quan hệ trích dẫn/hiệu lực (BASED_ON/REFERENCES/REPLACES/AMENDS/REPEALS) trong toàn graph.",
            nl_examples=(
                "Có bao nhiêu quan hệ trích dẫn trong đồ thị?",
                "Đếm số lượng từng loại quan hệ hiệu lực",
            ),
            cypher="""
                MATCH ()-[r]->() WHERE type(r) IN ['BASED_ON','REFERENCES','REPLACES','AMENDS','REPEALS']
                RETURN type(r) AS relationType, count(*) AS total
                ORDER BY total DESC
            """,
            params=(),
        ),
        Template(
            name="TPL_NORMATIVE_CONTENT_BY_TYPE",
            description="Liệt kê nội dung quy phạm kèm theo (Quy định/Quy chế/Nội quy...) theo một loại cụ thể.",
            nl_examples=(
                "Có những Quy chế nào còn hiệu lực?",
                "Danh sách các Quy định đã ban hành",
            ),
            cypher="""
                MATCH (:Document)-[:PROMULGATES]->(c:NormativeContent)
                WHERE c.contentType = $contentType
                RETURN c.contentId AS contentId, c.title AS title, c.status AS status
                ORDER BY contentId
                LIMIT $limit
            """,
            params=(
                ParamSpec("contentType", "content_type"),
                ParamSpec("limit", "int_limit", required=False, default_raw="50"),
            ),
        ),
        Template(
            name="TPL_ARTICLE_FULLTEXT_SEARCH",
            description="Tìm các Điều (Article) có chứa một cụm từ cụ thể (full-text, khớp từ khoá, không phải semantic search).",
            nl_examples=(
                "Điều nào nói về trình độ tiếng Anh?",
                "Tìm các Điều nhắc tới trách nhiệm thi hành",
            ),
            cypher="""
                CALL db.index.fulltext.queryNodes('article_text', $luceneQuery) YIELD node, score
                RETURN node.articleId AS articleId, node.heading AS heading, score
                ORDER BY score DESC
                LIMIT $limit
            """,
            params=(
                ParamSpec("luceneQuery", "fulltext_phrase"),
                ParamSpec("limit", "int_limit", required=False, default_raw="50"),
            ),
        ),
        Template(
            name="TPL_DOCUMENT_FULLTEXT_SEARCH",
            description="Tìm văn bản (theo tiêu đề/tóm tắt) có chứa một cụm từ cụ thể (full-text).",
            nl_examples=(
                "Văn bản nào nhắc tới Đại học Đà Nẵng?",
                "Tìm văn bản có từ 'Chiến lược' trong tiêu đề",
            ),
            cypher="""
                CALL db.index.fulltext.queryNodes('doc_text', $luceneQuery) YIELD node, score
                RETURN node.documentNumber AS documentNumber, node.title AS title, score
                ORDER BY score DESC
                LIMIT $limit
            """,
            params=(
                ParamSpec("luceneQuery", "fulltext_phrase"),
                ParamSpec("limit", "int_limit", required=False, default_raw="50"),
            ),
        ),
        Template(
            name="TPL_HYBRID_FULLTEXT_EXPAND",
            description="Tìm văn bản khớp full-text rồi mở rộng theo quan hệ BASED_ON/REFERENCES để xem văn bản đó dựa trên căn cứ gốc thẩm quyền nào.",
            nl_examples=(
                "Những văn bản gốc thẩm quyền cao nào liên quan tới Đại học Đà Nẵng?",
                "Văn bản về Chiến lược dựa trên những căn cứ pháp lý nào?",
            ),
            cypher="""
                CALL db.index.fulltext.queryNodes('doc_text', $luceneQuery) YIELD node, score
                WITH node, score ORDER BY score DESC LIMIT $seedLimit
                MATCH (node)-[:BASED_ON|REFERENCES*0..2]->(expanded:Document)
                RETURN DISTINCT expanded.documentNumber AS documentNumber, expanded.authorityLevel AS level
                ORDER BY level DESC
                LIMIT $limit
            """,
            params=(
                ParamSpec("luceneQuery", "fulltext_phrase"),
                ParamSpec("seedLimit", "int_limit", required=False, default_raw="10"),
                ParamSpec("limit", "int_limit", required=False, default_raw="50"),
            ),
        ),
        Template(
            name="TPL_TOP_ORGS_BY_DOC_COUNT",
            description="Xếp hạng cơ quan/đơn vị theo số lượng văn bản đã ban hành.",
            nl_examples=(
                "Cơ quan nào ban hành nhiều văn bản nhất?",
                "Top 10 đơn vị ban hành nhiều văn bản nhất",
            ),
            cypher="""
                MATCH (o:Organization)<-[:ISSUED_BY]-(d:Document)
                RETURN o.name AS organization, count(d) AS total
                ORDER BY total DESC
                LIMIT $limit
            """,
            params=(ParamSpec("limit", "int_limit", required=False, default_raw="10"),),
        ),
        Template(
            name="TPL_DOC_DISTRIBUTION_BY_STATUS",
            description="Phân bố toàn bộ văn bản thật theo tình trạng hiệu lực (thống kê tổng quan, không lọc theo tổ chức/lĩnh vực).",
            nl_examples=(
                "Phân bố văn bản theo tình trạng hiệu lực?",
                "Có bao nhiêu văn bản còn hiệu lực / hết hiệu lực?",
            ),
            cypher="""
                MATCH (d:Document) WHERE d.isStub = false
                RETURN d.status AS status, count(*) AS total
                ORDER BY total DESC
            """,
            params=(),
        ),
    ]
}


def catalog_text() -> str:
    """Render danh sách template thành văn bản đưa vào prompt Stage A."""

    lines: list[str] = []
    for tpl in TEMPLATES.values():
        required = [p.name for p in tpl.params if p.required]
        optional = [p.name for p in tpl.params if not p.required]
        lines.append(f"### {tpl.name}")
        lines.append(f"Mô tả: {tpl.description}")
        lines.append(f"Ví dụ câu hỏi khớp: {'; '.join(tpl.nl_examples)}")
        lines.append(f"Tham số bắt buộc: {', '.join(required) or '(không)'}")
        if optional:
            lines.append(f"Tham số tuỳ chọn: {', '.join(optional)}")
        lines.append("")
    return "\n".join(lines)
