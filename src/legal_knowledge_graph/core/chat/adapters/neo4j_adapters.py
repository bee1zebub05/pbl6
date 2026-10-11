"""
Hai port Neo4j của chatbot — chạy Cypher (QueryExecutor) và resolve thực thể
(EntityResolver) — trên driver dùng chung `core.db.Neo4jConnection`. Logic
thật nằm ở core/db.py, graph_query/cypher_guard.py, graph_query/entity_resolver.py;
ở đây chỉ nối và ghi log/trace.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from ... import config, db
from ...db import ExecutionResult, Neo4jConnection
from ...graph_query import cypher_guard, entity_resolver
from ...graph_query.templates.base import DEFAULT_LIMIT
from ...observability import debug_enabled, log_event, preview_rows, traceable
from ..ports import EntityResolver, QueryExecutor


def _trace_output(result: tuple[str, ExecutionResult] | ExecutionResult) -> dict:
    exec_result = result[1] if isinstance(result, tuple) else result
    cypher = {"cypher": result[0]} if isinstance(result, tuple) else {}
    return {
        **cypher,
        "row_count": len(exec_result.rows),
        "elapsed_ms": round(exec_result.elapsed_ms, 1),
        "rows_preview": preview_rows(exec_result.rows, 20),
    }


class Neo4jQueryExecutor(QueryExecutor):
    def __init__(self, connection: Neo4jConnection):
        self._conn = connection

    def _log(self, label: str, cypher: str, params: dict, result: ExecutionResult) -> None:
        log_event("cypher", label=label, rows=len(result.rows), ms=round(result.elapsed_ms, 1))
        if debug_enabled():
            log_event("cypher", level=logging.DEBUG, label=label, cypher=cypher.strip(), params=params,
                      rows_preview=preview_rows(result.rows, 5))

    @traceable(name="neo4j.run_template", run_type="tool", process_outputs=_trace_output)
    def run(self, cypher: str, params: dict[str, Any], *, label: str) -> ExecutionResult:
        with self._conn.session() as s:
            result = db.run_in_session(s, cypher, params, timeout_seconds=config.CYPHER_TIMEOUT_SECONDS)
        self._log(label, cypher, params, result)
        return result

    @traceable(name="neo4j.run_guarded", run_type="tool", process_outputs=_trace_output)
    def run_guarded(self, cypher: str) -> tuple[str, ExecutionResult]:
        with self._conn.session() as s:
            try:
                capped = cypher_guard.guard_freeform_cypher(cypher, {}, row_cap=config.CYPHER_ROW_CAP, session_=s)
            except cypher_guard.GuardRejected as exc:
                log_event("guard", blocked=True, reason=exc.reason)
                if debug_enabled():
                    log_event("guard", level=logging.DEBUG, cypher=cypher)
                raise
            result = db.run_in_session(s, capped, {}, timeout_seconds=config.CYPHER_TIMEOUT_SECONDS)
        self._log("freeform", capped, {}, result)
        return capped, result


class Neo4jEntityResolver(EntityResolver):
    """Định tuyến resolver_kind -> hàm trong graph_query/entity_resolver.py (một bảng duy nhất)."""

    def __init__(self, connection: Neo4jConnection):
        self._conn = connection
        self.table: dict[str, Callable[[Any], entity_resolver.Resolution]] = {
            "org": self._with_session(entity_resolver.resolve_organization),
            "doc_number": self._with_session(entity_resolver.resolve_document_number),
            "person": self._with_session(entity_resolver.resolve_person),
            "topic": entity_resolver.resolve_topic,
            "target_group": entity_resolver.resolve_target_group,
            "status": entity_resolver.resolve_status,
            "content_type": entity_resolver.resolve_content_type,
            "doc_type": entity_resolver.resolve_doc_type,
            "year": entity_resolver.resolve_year,
            "article_number": entity_resolver.resolve_article_number,
            "text": entity_resolver.resolve_text,
            "fulltext_phrase": lambda r: entity_resolver.Resolved(entity_resolver.resolve_fulltext_phrase(str(r))),
            "int_limit": lambda r: entity_resolver.Resolved(
                entity_resolver.resolve_int_limit(r, default=DEFAULT_LIMIT, cap=config.CYPHER_ROW_CAP)
            ),
        }

    def _with_session(self, fn):
        def run(raw):
            with self._conn.session() as s:
                return fn(raw, s)
        return run

    def _dispatch(self, kind: str, raw: Any) -> entity_resolver.Resolution:
        if kind not in self.table:
            raise ValueError(f"resolver không hợp lệ: {kind}")
        return self.table[kind](raw)

    @traceable(name="resolve_entity", run_type="tool")
    def resolve(self, resolver_kind: str, raw: Any) -> entity_resolver.Resolution:
        result = self._dispatch(resolver_kind, raw)
        outcome = type(result).__name__
        fields: dict[str, Any] = {"resolver": resolver_kind, "raw": raw, "outcome": outcome}
        if isinstance(result, entity_resolver.Resolved):
            fields["value"] = result.value
        elif isinstance(result, entity_resolver.Ambiguous):
            fields["candidates"] = list(result.candidates)
        log_event("resolve", **fields)
        return result
