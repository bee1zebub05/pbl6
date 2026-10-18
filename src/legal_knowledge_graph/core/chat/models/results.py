"""Kết quả trung gian giữa các bước và lỗi nghiệp vụ (resolve / tham số template)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .graph_context import GraphContext

@dataclass(frozen=True)
class QueryResult:
    template: str | None
    cypher: str
    params: dict[str, Any]
    rows: list[dict]
    elapsed_ms: float


@dataclass(frozen=True)
class Clarification:
    question: str
    candidates: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentOutcome:
    answer: str
    cypher: str | None
    rows: list[dict]
    context: GraphContext


class ResolutionFailed(Exception):
    """Một tham số không resolve được rõ ràng (mơ hồ hoặc không tồn tại) —
    KHÔNG chạy Cypher nào khi lỗi này xảy ra."""

    def __init__(self, param_name: str, slot: str | None, reason: str, candidates: tuple[str, ...] = ()):
        self.param_name = param_name
        self.slot = slot
        self.reason = reason
        self.candidates = candidates
        super().__init__(f"'{param_name}': {reason}")


class TemplateParamError(Exception):
    pass
