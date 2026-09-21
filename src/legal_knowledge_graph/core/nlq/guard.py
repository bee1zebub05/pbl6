"""
An toàn cho Cypher — chủ yếu phục vụ nhánh FREEFORM (Stage B, chưa xây ở
Phase này) vì đó là Cypher do LLM tự viết. Nhánh template không cần
blocklist/whitelist (Cypher đã hand-vetted trong templates.py), nhưng vẫn
đi qua execute.py's timeout giống nhau (defense in depth — tham số cực
đoan vẫn có thể làm 1 template chạy chậm).

Không có RBAC ở Neo4j Community Edition (đã xác minh: docker-compose.yml
dùng image `neo4j:5`, không phải `-enterprise`, không cài APOC) -> an toàn
phải làm 100% ở code, không dựa vào DB.
"""

from __future__ import annotations

import re

from . import execute, schema_context


class GuardRejected(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


_MULTI_STATEMENT = re.compile(r";\s*\S")

_BLOCKED = re.compile(
    r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DETACH|DROP|LOAD\s+CSV|FOREACH"
    r"|CALL\s+apoc\.\w+|CALL\s+dbms\.\w+|CALL\s+db\.create\w*|CALL\s+db\.drop\w*"
    r"|CALL\s+gds\.\w+)\b",
    re.IGNORECASE,
)

# Loại bỏ lời gọi procedure (vd CALL db.index.fulltext.queryNodes(...))
# TRƯỚC khi quét label/property — namespace của procedure (db.index....)
# có hình dạng giống hệt property access, nếu không loại sẽ báo nhầm.
_PROCEDURE_CALL = re.compile(r"CALL\s+[\w.]+\([^)]*\)", re.IGNORECASE)

_LABEL_OR_RELTYPE = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")
_PROPERTY_ACCESS = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*\.([a-zA-Z_][a-zA-Z0-9_]*)\b")

_KNOWN_LABELS_AND_RELTYPES = schema_context.all_labels() | schema_context.all_relationship_types()
_KNOWN_PROPERTIES = schema_context.all_properties_flat()


def check_blocklist(cypher: str) -> None:
    if _MULTI_STATEMENT.search(cypher):
        raise GuardRejected("Cypher có nhiều statement (dấu ';' kèm nội dung sau) — không cho phép")
    if _BLOCKED.search(cypher):
        raise GuardRejected("Cypher chứa từ khoá ghi/xoá/admin bị cấm (CREATE/MERGE/SET/DELETE/...)")


def check_labels_and_properties(cypher: str) -> None:
    """Chặn label/relationship-type/property không có thật trong schema —
    lỗ hổng mà EXPLAIN KHÔNG bắt được (Neo4j không báo lỗi khi truy cập
    property không tồn tại, chỉ âm thầm trả null). Best-effort bằng regex,
    không phải parser Cypher đầy đủ — đủ dùng cho schema nhỏ, ổn định này."""

    scan_text = _PROCEDURE_CALL.sub(" ", cypher)

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


def dry_run_explain(cypher: str, params: dict) -> None:
    try:
        execute.explain(cypher, params)
    except Exception as exc:
        raise GuardRejected(f"EXPLAIN thất bại — Cypher sai cú pháp/plan: {exc}") from exc


def guard_freeform_cypher(cypher: str, params: dict, row_cap: int) -> str:
    """Chạy toàn bộ chuỗi kiểm tra cho Cypher freeform (Stage B). Trả về
    Cypher đã ép LIMIT nếu qua hết mọi bước; raise GuardRejected ngay khi
    có bước nào chặn — KHÔNG chạy thử "một phần"."""

    check_blocklist(cypher)
    check_labels_and_properties(cypher)
    capped = enforce_limit(cypher, row_cap)
    dry_run_explain(capped, params)
    return capped
