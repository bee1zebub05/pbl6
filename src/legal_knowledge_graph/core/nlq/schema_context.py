"""
Mô tả schema TĨNH của graph — viết tay, KHÔNG introspect Neo4j lúc chạy
(ổn định, review được như reference/*_seed.json và schema/document.schema.json).

Dùng ở 2 chỗ:
  1. Prompt Stage B (freeform.py) — cho Gemini biết chính xác node/
     relationship/property/enum nào tồn tại, tránh bịa.
  2. Whitelist của guard.py bước 7 — chặn Cypher freeform dùng label/
     property không có thật (EXPLAIN không bắt được lỗi này, xem
     README §NLQ).

Nếu core/graph_loader.py đổi property/label thì phải sửa file này theo —
không có cơ chế tự đồng bộ, cố tình để plain data đơn giản, dễ review.
"""

from __future__ import annotations

# label -> tập property thật sự tồn tại trên node (đúng những gì
# core/graph_loader.py SET, không phải tên field trong JSON đầu vào).
NODE_PROPERTIES: dict[str, set[str]] = {
    "Document": {
        "normalizedNumber", "documentNumber", "title", "documentType",
        "status", "issueDate", "effectiveDate", "expiryDate", "fileUrl",
        "summary", "authorityLevel", "levelNote", "isStub",
    },
    "Organization": {"orgId", "name", "orgType"},
    "Person": {"personId", "fullName", "academicTitle", "position"},
    "Topic": {"topicId", "name"},
    "TargetGroup": {"targetGroupId", "name"},
    "NormativeContent": {"contentId", "title", "contentType", "status"},
    "Article": {"articleId", "number", "heading", "text", "isImplementationClause"},
}

# (relationshipType, fromLabel, toLabel, mô tả, property trên cạnh nếu có)
RELATIONSHIPS: list[tuple[str, str, str, str, tuple[str, ...]]] = [
    ("ISSUED_BY", "Document", "Organization", "Cơ quan ban hành văn bản", ()),
    ("SIGNED_BY", "Document", "Person", "Người ký văn bản", ()),
    ("HAS_TOPIC", "Document", "Topic", "Văn bản thuộc lĩnh vực", ()),
    ("APPLIES_TO", "Document", "TargetGroup", "Văn bản áp dụng cho nhóm đối tượng", ()),
    ("MENTIONS", "Document", "Organization", "Tổ chức được nhắc tới (không phải bên ban hành/ký)", ()),
    ("PART_OF", "Organization", "Organization", "Đơn vị con -> đơn vị cha trực tiếp", ()),
    ("PROMULGATES", "Document", "NormativeContent", "Văn bản ban hành kèm theo nội dung quy phạm", ()),
    ("HAS_ARTICLE", "Document", "Article", "Điều vỏ bọc cấp Document", ()),
    ("HAS_ARTICLE", "NormativeContent", "Article", "Điều bên trong nội dung kèm theo", ()),
    ("BASED_ON", "Document", "Document", "Viện dẫn làm căn cứ pháp lý (source dựa trên target)", ("context",)),
    ("REFERENCES", "Document", "Document", "Nhắc tới, không thuộc 4 loại quan hệ hiệu lực còn lại", ("context",)),
    ("REPLACES", "Document", "Document", "source THAY THẾ target (target coi như hết hiệu lực)", ("context",)),
    ("AMENDS", "Document", "Document", "source SỬA ĐỔI một phần target (target vẫn còn hiệu lực tổng thể)", ("context", "targetArticle")),
    ("REPEALS", "Document", "Document", "source BÃI BỎ target", ("context",)),
]

ENUMS: dict[str, tuple[str, ...]] = {
    "Document.documentType": (
        "Luật", "Pháp lệnh", "Nghị định", "Thông tư", "Thông tư liên tịch",
        "Quyết định", "Nghị quyết", "Chỉ thị", "Hướng dẫn", "Kế hoạch",
        "Văn bản hợp nhất", "Lệnh", "Công văn", "Hiến pháp",
    ),
    "Document.status": ("CON_HIEU_LUC", "HET_HIEU_LUC", "CHUA_HIEU_LUC"),
    "Organization.orgType": (
        "quoc_hoi", "chinh_phu", "thu_tuong", "bo_nganh", "dai_hoc_vung",
        "truong_thanh_vien", "don_vi_truc_thuoc", "phong_ban",
    ),
    "NormativeContent.contentType": (
        "Quy định", "Quy chế", "Điều lệ", "Quy trình", "Nội quy", "Đề án",
        "Kế hoạch", "Hướng dẫn", "Chương trình",
    ),
}

# tên index fulltext -> (label, các property được đánh index)
FULLTEXT_INDEXES: dict[str, tuple[str, tuple[str, ...]]] = {
    "doc_text": ("Document", ("title", "summary")),
    "article_text": ("Article", ("heading", "text")),
    "content_text": ("NormativeContent", ("title",)),
}

# Danh sách chủ đề KHÔNG có trong graph — dùng làm ví dụ âm (few-shot) cho
# prompt Stage B, để model tự nhận biết "unsupported" thay vì bịa Cypher.
OUT_OF_SCOPE_EXAMPLES: tuple[str, ...] = (
    "Trường thu học phí bao nhiêu?",  # không có node/property nào về học phí
    "Thời tiết Đà Nẵng hôm nay thế nào?",  # hoàn toàn ngoài domain
    "Điểm chuẩn ngành CNTT năm nay là bao nhiêu?",  # không có dữ liệu tuyển sinh/điểm số
    "Xoá văn bản 4511/QĐ-ĐHBK giúp tôi",  # yêu cầu ghi/xoá, không phải truy vấn đọc
)


def all_labels() -> set[str]:
    return set(NODE_PROPERTIES)


def all_relationship_types() -> set[str]:
    return {rel[0] for rel in RELATIONSHIPS}


def all_properties_flat() -> set[str]:
    """Hợp toàn bộ property của mọi label — dùng cho kiểm tra nhanh
    'token này có phải property hợp lệ ở ĐÂU ĐÓ không', xem guard.py."""

    flat: set[str] = set()
    for props in NODE_PROPERTIES.values():
        flat |= props
    for _, _, _, _, edge_props in RELATIONSHIPS:
        flat |= set(edge_props)
    return flat


def render_prompt_context() -> str:
    """Render thành văn bản đưa vào prompt Stage B (freeform.py)."""

    lines: list[str] = []
    lines.append("## Node label và property hợp lệ (KHÔNG được dùng property nào ngoài danh sách)")
    for label, props in NODE_PROPERTIES.items():
        lines.append(f"- {label}: {', '.join(sorted(props))}")

    lines.append("")
    lines.append("## Relationship hợp lệ (chiều mũi tên PHẢI đúng như liệt kê)")
    for rel_type, src, dst, desc, props in RELATIONSHIPS:
        prop_note = f" [property trên cạnh: {', '.join(props)}]" if props else ""
        lines.append(f"- ({src})-[:{rel_type}]->({dst}): {desc}{prop_note}")

    lines.append("")
    lines.append("## Giá trị enum hợp lệ (không được dùng giá trị khác)")
    for field, values in ENUMS.items():
        lines.append(f"- {field}: {', '.join(values)}")

    lines.append("")
    lines.append("## Fulltext index có sẵn (dùng CALL db.index.fulltext.queryNodes(tên, cụm))")
    for name, (label, props) in FULLTEXT_INDEXES.items():
        lines.append(f"- '{name}' trên {label}({', '.join(props)})")

    lines.append("")
    lines.append("## Chỉ được dùng: MATCH, OPTIONAL MATCH, WHERE, WITH, UNWIND, RETURN, "
                  "ORDER BY, LIMIT, CALL db.index.fulltext.queryNodes. "
                  "TUYỆT ĐỐI CẤM: CREATE, MERGE, SET, DELETE, REMOVE, DETACH, DROP, "
                  "LOAD CSV, FOREACH, CALL apoc.*, CALL dbms.*, CALL gds.*.")

    lines.append("")
    lines.append("## Ví dụ câu hỏi KHÔNG trả lời được bằng graph này (trả unsupported:true)")
    for ex in OUT_OF_SCOPE_EXAMPLES:
        lines.append(f'- "{ex}"')

    return "\n".join(lines)
