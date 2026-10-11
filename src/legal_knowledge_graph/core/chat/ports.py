"""
Interface trừu tượng — các điểm thay thế được của chatbot (DIP). Service chỉ
phụ thuộc vào các lớp này, không vào Gemini/Neo4j cụ thể; bản cài thật nằm ở
`adapters/`, bản giả cho kiểm thử nằm ở `tests/`. Ráp ở `container.py`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence, TypeVar

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from ..graph_query import entity_resolver
from ..db import ExecutionResult
from .models import GraphContext

M = TypeVar("M", bound=BaseModel)


class LLMProvider(ABC):
    """Mô hình ngôn ngữ. `node` chỉ dùng để ghi log/trace lời gọi thuộc node nào."""

    model_name: str = "unknown"

    @abstractmethod
    def structured(self, schema: type[M], messages: Sequence[BaseMessage], *, node: str) -> M:
        """Output ép theo Pydantic schema."""

    @abstractmethod
    def text(self, messages: Sequence[BaseMessage], *, node: str) -> str:
        """Output văn bản tự do."""

    @abstractmethod
    def invoke_with_tools(
        self, messages: Sequence[BaseMessage], tools: Sequence[BaseTool], *, node: str
    ) -> AIMessage:
        """Một lượt gọi có tool — trả AIMessage (có thể chứa tool_calls)."""


class QueryExecutor(ABC):
    """Chạy Cypher chỉ-đọc trên graph."""

    @abstractmethod
    def run(self, cypher: str, params: dict[str, Any], *, label: str) -> ExecutionResult:
        """Chạy Cypher đã kiểm duyệt (template). `label` = tên template, cho log."""

    @abstractmethod
    def run_guarded(self, cypher: str) -> tuple[str, ExecutionResult]:
        """Chạy Cypher do LLM viết: qua guard trước. Trả (Cypher đã ép LIMIT,
        kết quả). Bị chặn -> raise cypher_guard.GuardRejected."""


class EntityResolver(ABC):
    """Biến giá trị thô (tên cơ quan, số hiệu...) thành khoá thật trong graph."""

    @abstractmethod
    def resolve(self, resolver_kind: str, raw: Any) -> entity_resolver.Resolution:
        """resolver_kind: một giá trị của graph_query/templates/base.py::ResolverKind."""


class ContextRetriever(ABC):
    """GraphRAG: tìm Điều liên quan tới câu hỏi rồi mở rộng theo quan hệ trên graph."""

    @abstractmethod
    def retrieve(self, question: str, *, scope_docs: Sequence[str] = ()) -> GraphContext:
        """`scope_docs`: số hiệu văn bản (thô hoặc đã chuẩn hoá — câu hỏi nhắc tới, kết quả template) cần lấy thêm
        Điều gần nghĩa nhất bên trong và được ưu tiên trong ngữ cảnh."""
