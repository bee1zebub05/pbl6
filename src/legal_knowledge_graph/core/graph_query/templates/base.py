"""
Nền chung của kho template Cypher: kiểu dữ liệu, bảng slot ↔ $param, các
mảnh Cypher dùng lại và factory cho những khuôn lặp lại.

Một template tự khai đủ để chatbot dùng mà không cần bảng nào khác:
- `action`: hành động người dùng muốn (router LLM trích ra);
- `params`: tham số Cypher; slot tương ứng suy ra qua PARAM_TO_SLOT, slot
  bắt buộc = tham số bắt buộc không có mặc định (TemplateSelector tự dựng
  luật chọn từ đây — thêm template là đủ, không phải sửa bảng nào);
- `level` (1 đơn giản → 5 phức tạp) và `audience` (ai hay hỏi) để sắp xếp và
  báo cáo kho template;
- `example_params`: tham số THẬT lấy từ graph, dùng cho kiểm thử live.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, get_args

# Loại resolver hợp lệ — bảng điều phối ở core/chat/adapters/neo4j_adapters.py phải
# phủ đủ (tests/test_template_selector.py kiểm). `int_limit` và `year` trả int.
ResolverKind = Literal[
    "org", "topic", "target_group", "doc_number", "person", "status", "content_type",
    "doc_type", "fulltext_phrase", "int_limit", "year", "article_number", "text",
]
RESOLVER_KINDS: frozenset[str] = frozenset(get_args(ResolverKind))

# Slot (tên router LLM trích) -> $param của Cypher. Nguồn duy nhất.
SLOT_TO_PARAM: dict[str, str] = {
    "org": "orgId",
    "topic": "topicId",
    "target_group": "targetGroupId",
    "doc_number": "normalizedNumber",
    "person": "personId",
    "position": "position",
    "status": "status",
    "doc_type": "documentType",
    "content_type": "contentType",
    "year": "year",
    "since_year": "sinceYear",
    "article_number": "articleNumber",
    "phrase": "luceneQuery",
    "limit": "limit",
}
PARAM_TO_SLOT: dict[str, str] = {v: k for k, v in SLOT_TO_PARAM.items()}
INT_SLOTS = frozenset({"year", "since_year", "limit"})

# Tham số nội bộ, không phải slot người dùng nêu (luôn dùng mặc định).
INTERNAL_PARAMS = frozenset({"seedLimit"})

# Nhóm người hay hỏi (audience)
SV, PH, GV, QL, DL = "sinh viên", "phụ huynh", "giảng viên", "cán bộ quản lý/pháp chế", "quản trị dữ liệu"

DEFAULT_LIMIT = 50
DEFAULT_LIMIT_SHORT = 20
DEFAULT_TOP_N = 10


@dataclass(frozen=True)
class ParamSpec:
    name: str
    resolver: ResolverKind
    required: bool = True
    default: str | int | None = None  # giá trị điền thẳng vào $param khi câu hỏi không nêu


@dataclass(frozen=True)
class Template:
    name: str
    action: str
    level: int
    audience: tuple[str, ...]
    description: str
    nl_examples: tuple[str, ...]
    cypher: str
    params: tuple[ParamSpec, ...] = ()
    example_params: dict[str, Any] = field(default_factory=dict)
    # Số slot tối thiểu (không tính limit) — cho template lọc tổng quát nhiều
    # điều kiện tuỳ chọn, để nó không giành câu chỉ có một điều kiện.
    min_slots: int = 0


# ============================================================
# Tham số dùng lại
# ============================================================

def p_required(name: str, resolver: ResolverKind) -> ParamSpec:
    return ParamSpec(name, resolver)


def p_optional(name: str, resolver: ResolverKind) -> ParamSpec:
    return ParamSpec(name, resolver, required=False)


P_DOC = p_required("normalizedNumber", "doc_number")
P_ORG = p_required("orgId", "org")
P_PERSON = p_required("personId", "person")
P_PHRASE = p_required("luceneQuery", "fulltext_phrase")
P_STATUS = p_optional("status", "status")
P_LIMIT = ParamSpec("limit", "int_limit", required=False, default=DEFAULT_LIMIT)
P_LIMIT_SHORT = ParamSpec("limit", "int_limit", required=False, default=DEFAULT_LIMIT_SHORT)
P_TOP_N = ParamSpec("limit", "int_limit", required=False, default=DEFAULT_TOP_N)

# ============================================================
# Mảnh Cypher dùng lại
# ============================================================

# ĐHBK bị tách thành nhiều node cơ quan khi gán tay ("Trường Đại học Bách
# khoa" và "Trường Đại học Bách khoa, Đại học Đà Nẵng"): khớp cả orgId con có
# cùng tiền tố để không bỏ sót văn bản (xem docs/GRAPHREPORT.md).
ORG_IS = "(o.orgId = $orgId OR o.orgId STARTS WITH $orgId + '_')"
# Cùng ý cho trường hợp đã có node cơ quan o: các node "biến thể" v của nó.
VARIANT_OF_O = "(v.orgId = o.orgId OR v.orgId STARTS WITH o.orgId + '_')"

DOC_COLUMNS = ("d.documentNumber AS documentNumber, d.title AS title, d.documentType AS documentType, "
               "d.status AS status, d.issueDate AS issueDate")

# Điều của văn bản: trực tiếp (Điều vỏ bọc) hoặc qua nội dung ban hành kèm theo.
DOC_TO_ARTICLE = "(d)-[:PROMULGATES|HAS_ARTICLE*1..2]->(a:Article)"
ARTICLE_TO_DOC = "(d:Document)-[:PROMULGATES|HAS_ARTICLE*1..2]->(node)"

ARTICLE_ORDER = "coalesce(toInteger(replace(a.number, 'Điều ', '')), 9999)"

# Bộ lọc tuỳ chọn trên Document d — mỗi $param NULL thì điều kiện bỏ qua.
_FILTERS: dict[str, str] = {
    "orgId": f"($orgId IS NULL OR EXISTS {{ MATCH (d)-[:ISSUED_BY]->(o:Organization) WHERE {ORG_IS} }})",
    "topicId": "($topicId IS NULL OR EXISTS { MATCH (d)-[:HAS_TOPIC]->(:Topic {topicId: $topicId}) })",
    "targetGroupId": ("($targetGroupId IS NULL OR EXISTS "
                      "{ MATCH (d)-[:APPLIES_TO]->(:TargetGroup {targetGroupId: $targetGroupId}) })"),
    "documentType": "($documentType IS NULL OR d.documentType = $documentType)",
    "status": "($status IS NULL OR d.status = $status)",
    "year": "($year IS NULL OR substring(d.issueDate, 0, 4) = toString($year))",
    "sinceYear": "($sinceYear IS NULL OR substring(d.issueDate, 0, 4) >= toString($sinceYear))",
}

_FILTER_RESOLVERS: dict[str, ResolverKind] = {
    "orgId": "org", "topicId": "topic", "targetGroupId": "target_group", "documentType": "doc_type",
    "status": "status", "year": "year", "sinceYear": "year",
}


def doc_filters(*params: str) -> str:
    """Mệnh đề WHERE ghép từ các bộ lọc tuỳ chọn đã chọn."""

    return "\n      AND ".join(_FILTERS[p] for p in params)


def filter_params(*params: str) -> tuple[ParamSpec, ...]:
    return tuple(p_optional(p, _FILTER_RESOLVERS[p]) for p in params)


ALL_FILTERS = ("orgId", "topicId", "targetGroupId", "documentType", "year", "status")


# ============================================================
# Factory cho khuôn lặp lại
# ============================================================

def list_documents_by(*, name: str, level: int, audience: tuple[str, ...], description: str,
                      nl_examples: tuple[str, ...], match: str, key: ParamSpec,
                      example_params: dict[str, Any]) -> Template:
    """Khuôn 'liệt kê văn bản theo MỘT khoá (cơ quan / lĩnh vực / loại...) +
    lọc hiệu lực tuỳ chọn'. `match` là mẫu MATCH/WHERE riêng của khoá."""

    cypher = f"""
        MATCH (d:Document {{isStub: false}})
        {match}
        WITH DISTINCT d
        WHERE $status IS NULL OR d.status = $status
        RETURN {DOC_COLUMNS}
        ORDER BY d.issueDate IS NULL, d.issueDate DESC
        LIMIT $limit
    """
    return Template(
        name=name, action="list_documents", level=level, audience=audience, description=description,
        nl_examples=nl_examples, cypher=cypher, params=(key, P_STATUS, P_LIMIT), example_params=example_params,
    )


def fulltext_articles(*, name: str, level: int, audience: tuple[str, ...], description: str,
                      nl_examples: tuple[str, ...], extra_where: str = "",
                      extra_params: tuple[ParamSpec, ...] = (), example_params: dict[str, Any]) -> Template:
    """Khuôn 'tìm Điều theo cụm từ (full-text) rồi lọc theo văn bản chứa nó'."""

    where = f"WHERE {extra_where}" if extra_where else ""
    cypher = f"""
        CALL db.index.fulltext.queryNodes('article_text', $luceneQuery) YIELD node, score
        MATCH {ARTICLE_TO_DOC}
        {where}
        RETURN DISTINCT node.articleId AS articleId, node.heading AS heading, d.documentNumber AS documentNumber,
               d.title AS title, d.status AS status, score
        ORDER BY score DESC
        LIMIT $limit
    """
    return Template(
        name=name, action="search_articles", level=level, audience=audience, description=description,
        nl_examples=nl_examples, cypher=cypher, params=(P_PHRASE, *extra_params, P_LIMIT_SHORT),
        example_params=example_params,
    )


def relation_of_document(*, name: str, action: str, level: int, audience: tuple[str, ...], description: str,
                         nl_examples: tuple[str, ...], pattern: str, columns: str,
                         example_params: dict[str, Any], order: str = "issueDate IS NULL, issueDate DESC") -> Template:
    """Khuôn 'một văn bản (doc_number) -> các văn bản nối qua một loại quan hệ'.
    `pattern` dùng biến x (văn bản hỏi), t (văn bản liên quan), r (cạnh)."""

    cypher = f"""
        MATCH (x:Document {{normalizedNumber: $normalizedNumber}})
        MATCH {pattern}
        RETURN {columns}
        ORDER BY {order}
        LIMIT $limit
    """
    return Template(
        name=name, action=action, level=level, audience=audience, description=description,
        nl_examples=nl_examples, cypher=cypher, params=(P_DOC, P_LIMIT), example_params=example_params,
    )


RELATED_COLUMNS = ("t.documentNumber AS documentNumber, t.title AS title, t.status AS status, "
                   "t.issueDate AS issueDate, t.isStub AS isStub, r.context AS context")
