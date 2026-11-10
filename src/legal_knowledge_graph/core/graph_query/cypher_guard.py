"""
An toàn cho Cypher — chủ yếu phục vụ tool `run_cypher` của agent chatbot
(core/chat/agent.py) vì đó là Cypher do LLM tự viết. Nhánh template không cần
blocklist/whitelist (Cypher đã kiểm duyệt tay trong templates/), nhưng vẫn
đi qua timeout của core/db.py giống nhau (defense in depth — tham số cực
đoan vẫn có thể làm 1 template chạy chậm).

Không có RBAC ở Neo4j Community Edition (docker-compose.yml dùng image
`neo4j:5`, không cài APOC), nên lớp ở đây đi cùng phiên READ của
Neo4jConnection.session(read_only=True): lọt qua regex thì DB vẫn từ chối ghi.
"""

from __future__ import annotations

import re

from .. import db
from . import schema


class GuardRejected(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


# Chuỗi và chú thích không phải mã: bỏ trước khi quét để không chặn nhầm
# `CONTAINS 'set'`, và để `CALL/**/dbms...` không né được kiểm tra.
_STRING_OR_COMMENT = re.compile(r"""'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*"|//[^\n]*|/\*.*?\*/""", re.S)

_MULTI_STATEMENT = re.compile(r";\s*\S")

_BLOCKED = re.compile(
    r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DETACH|DROP|LOAD\s+CSV|FOREACH"
    r"|SHOW|TERMINATE|ALTER|GRANT|DENY|REVOKE|RENAME|START|STOP|USE|UNION)\b",
    re.IGNORECASE,
)

# Chỉ cho gọi đúng các procedure tìm kiếm. `CALL (d) { ... }` là subquery, không có tên.
_ALLOWED_PROCEDURES = frozenset({"db.index.fulltext.queryNodes", "db.index.vector.queryNodes"})
_CALL = re.compile(r"\bCALL\b\s*([`\w.]*)", re.IGNORECASE)
_EMBEDDING = re.compile(r"\bembedding\b", re.IGNORECASE)

# Loại bỏ lời gọi procedure (vd CALL db.index.fulltext.queryNodes(...))
# TRƯỚC khi quét label/property — namespace của procedure (db.index....)
# có hình dạng giống hệt property access, nếu không loại sẽ báo nhầm.
_PROCEDURE_CALL = re.compile(r"CALL\s+[\w.]+\([^)]*\)", re.IGNORECASE)

# Hàm có namespace (vector.similarity.cosine, date.truncate): không phải truy cập property.
_NAMESPACED_FUNCTION = re.compile(r"\b[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)+\s*\(")

_LABEL_OR_RELTYPE = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")
_PROPERTY_ACCESS = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*\.([a-zA-Z_][a-zA-Z0-9_]*)\b")

_KNOWN_LABELS_AND_RELTYPES = schema.all_labels() | schema.all_relationship_types()
_KNOWN_PROPERTIES = schema.all_properties_flat()


def _code_only(cypher: str) -> str:
    return _STRING_OR_COMMENT.sub(lambda m: "''" if m.group(0)[0] in "'\"" else " ", cypher)


def check_blocklist(cypher: str) -> None:
    if _EMBEDDING.search(cypher):
        raise GuardRejected("Không đọc property embedding — chỉ dùng được qua tìm kiếm, không phải dữ liệu trả lời")
    code = _code_only(cypher)
    if _MULTI_STATEMENT.search(code):
        raise GuardRejected("Cypher có nhiều statement (dấu ';' kèm nội dung sau) — không cho phép")
    if _BLOCKED.search(code):
        raise GuardRejected("Cypher chứa từ khoá bị cấm (ghi/xoá/quản trị, SHOW, USE, UNION...)")
    for match in _CALL.finditer(code):
        name = match.group(1).replace("`", "")
        if name and name not in _ALLOWED_PROCEDURES:
            raise GuardRejected(f"Không được gọi procedure '{name}'")


def check_labels_and_properties(cypher: str) -> None:
    """Chặn label/relationship-type/property không có thật trong schema —
    lỗ hổng mà EXPLAIN KHÔNG bắt được (Neo4j không báo lỗi khi truy cập
    property không tồn tại, chỉ âm thầm trả null). Best-effort bằng regex,
    không phải parser Cypher đầy đủ — đủ dùng cho schema nhỏ, ổn định này."""

    scan_text = _NAMESPACED_FUNCTION.sub("(", _PROCEDURE_CALL.sub(" ", _code_only(cypher)))

    for token in _LABEL_OR_RELTYPE.findall(scan_text):
        if token not in _KNOWN_LABELS_AND_RELTYPES:
            raise GuardRejected(f"Label/relationship-type '{token}' không tồn tại trong schema")

    for prop in _PROPERTY_ACCESS.findall(scan_text):
        if prop not in _KNOWN_PROPERTIES:
            raise GuardRejected(f"Property '{prop}' không tồn tại trong schema")


def enforce_limit(cypher: str, cap: int) -> str:
    """Đảm bảo Cypher có LIMIT <= cap ở cuối. Có sẵn LIMIT lớn hơn cap thì
    kẹp xuống; chưa có thì thêm mới."""

    stripped = cypher.rstrip().rstrip(";").rstrip()
    match = re.search(r"LIMIT\s+(\d+)\s*$", stripped, re.IGNORECASE)
    if match:
        existing = int(match.group(1))
        if existing <= cap:
            return stripped
        return stripped[: match.start()] + f"LIMIT {cap}"
    return f"{stripped}\nLIMIT {cap}"


def dry_run_explain(cypher: str, params: dict, session_) -> None:
    try:
        db.explain(cypher, params, session_)
    except Exception as exc:
        raise GuardRejected(f"EXPLAIN thất bại — Cypher sai cú pháp/plan: {exc}") from exc


def guard_freeform_cypher(cypher: str, params: dict, row_cap: int, session_) -> str:
    """Chạy toàn bộ chuỗi kiểm tra cho Cypher do agent tự viết. Trả về
    Cypher đã ép LIMIT nếu qua hết mọi bước; raise GuardRejected ngay khi
    có bước nào chặn — KHÔNG chạy thử "một phần".

    session_: dùng LẠI session của caller cho bước EXPLAIN — caller sẽ
    chạy Cypher thật (đã qua guard) trên cùng session này ngay sau đó."""

    check_blocklist(cypher)
    check_labels_and_properties(cypher)
    capped = enforce_limit(cypher, row_cap)
    dry_run_explain(capped, params, session_)
    return capped
