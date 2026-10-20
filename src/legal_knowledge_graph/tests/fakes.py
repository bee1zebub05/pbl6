"""Bản giả của các port (core/chat/ports.py) — kiểm thử graph không cần Gemini/Neo4j."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Sequence

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import BaseTool

from core.chat.models import GraphContext
from core.chat.ports import M, ContextRetriever, EntityResolver, LLMProvider, QueryExecutor
from core.graph_query import entity_resolver
from core.db import ExecutionResult


class FakeLLM(LLMProvider):
    """Trả lời theo kịch bản: mỗi node một hàng đợi phản hồi. Ghi lại messages
    mỗi lần gọi (`prompts`: danh sách (node, messages)) để test kiểm đầu vào."""

    model_name = "fake"

    def __init__(self, script: dict[str, list[Any]] | None = None):
        self._queues: dict[str, deque] = defaultdict(deque)
        self.calls: list[str] = []
        self.prompts: list[tuple[str, list[BaseMessage]]] = []
        for node, responses in (script or {}).items():
            self.add(node, *responses)

    def add(self, node: str, *responses: Any) -> "FakeLLM":
        self._queues[node].extend(responses)
        return self

    def _next(self, node: str, messages: Sequence[BaseMessage]) -> Any:
        self.calls.append(node)
        self.prompts.append((node, list(messages)))
        if not self._queues[node]:
            raise AssertionError(f"FakeLLM: hết phản hồi kịch bản cho node '{node}'")
        item = self._queues[node].popleft()
        if isinstance(item, Exception):
            raise item
        return item

    def structured(self, schema: type[M], messages: Sequence[BaseMessage], *, node: str) -> M:
        result = self._next(node, messages)
        assert isinstance(result, schema), f"node {node}: kịch bản trả {type(result)}, cần {schema}"
        return result

    def text(self, messages: Sequence[BaseMessage], *, node: str) -> str:
        return self._next(node, messages)

    def invoke_with_tools(self, messages: Sequence[BaseMessage], tools: Sequence[BaseTool], *,
                          node: str) -> AIMessage:
        return self._next(node, messages)


class FakeExecutor(QueryExecutor):
    def __init__(self, rows: list[dict] | None = None, error: Exception | None = None):
        self.rows = rows if rows is not None else [{"documentNumber": "1001/QĐ-ĐHBK", "title": "Quy chế",
                                                    "status": "CON_HIEU_LUC"}]
        self.error = error
        self.calls: list[tuple[str, dict]] = []

    def run(self, cypher: str, params: dict[str, Any], *, label: str) -> ExecutionResult:
        self.calls.append((label, params))
        if self.error:
            raise self.error
        return ExecutionResult(rows=self.rows, elapsed_ms=1.0)

    def run_guarded(self, cypher: str) -> tuple[str, ExecutionResult]:
        self.calls.append(("freeform", {"cypher": cypher}))
        if self.error:
            raise self.error
        return cypher + "\nLIMIT 200", ExecutionResult(rows=self.rows, elapsed_ms=1.0)


class FakeResolver(EntityResolver):
    """Org: 'ĐHBK'/'Trường Đại học Bách khoa' -> truong_dai_hoc_bach_khoa, còn lại NotFound.
    Kiểu khác: trả nguyên giá trị (int_limit trả int như resolver thật)."""

    ORGS = {"ĐHBK": "truong_dai_hoc_bach_khoa", "Trường Đại học Bách khoa": "truong_dai_hoc_bach_khoa"}

    def resolve(self, resolver_kind: str, raw: Any) -> entity_resolver.Resolution:
        if resolver_kind == "org":
            return entity_resolver.Resolved(self.ORGS[raw]) if raw in self.ORGS else entity_resolver.NotFound()
        if resolver_kind in ("int_limit", "year"):
            return entity_resolver.Resolved(int(raw))
        return entity_resolver.Resolved(str(raw))


class FakeRetriever(ContextRetriever):
    """Trả ngữ cảnh cố định; ghi lại scope_docs, mode, phrase mỗi lần gọi để test kiểm."""

    def __init__(self, context: GraphContext | None = None):
        self.context = context or GraphContext()
        self.scopes: list[tuple[str, ...]] = []
        self.modes: list[str] = []
        self.phrases: list[str | None] = []

    def retrieve(self, question: str, *, scope_docs: Sequence[str] = (), mode: str = "full",
                 phrase: str | None = None) -> GraphContext:
        self.scopes.append(tuple(scope_docs))
        self.modes.append(mode)
        self.phrases.append(phrase)
        return self.context
