"""State của LangGraph: phần checkpoint qua các lượt và phần reset mỗi lượt."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

class ChatState(TypedDict, total=False):
    # Được checkpoint qua các lượt
    messages: Annotated[list[AnyMessage], add_messages]
    clarify_rounds: int
    # Reset mỗi lượt (xem TURN_RESET)
    question: str
    intent: str
    direct_reply: str
    action: str | None
    slots: dict | None
    route_kind: str | None        # template | clarify | agent (RouteDecision.kind)
    route_reason: str | None
    raw_params: dict | None       # tên $param -> giá trị thô, trước resolve
    template: str | None
    params: dict | None
    cypher: str | None
    rows: list[dict] | None
    retrieval_reason: str | None
    graph_context: dict | None    # GraphContext.model_dump() — field `retrieval` của API suy từ đây
    clarification: dict | None    # {"question", "candidates"} — chỉ kiểu nguyên thuỷ trong state
    pending_missing: tuple[str, ...] | None
    pending_candidates: tuple[str, ...] | None
    answer: str | None
    sources: list[dict] | None
    kind: str | None
    error: str | None


TURN_RESET: dict[str, Any] = {
    "question": "", "intent": "", "direct_reply": "", "action": None, "slots": None, "route_kind": None,
    "route_reason": None, "raw_params": None,
    "template": None, "params": None, "cypher": None, "rows": None,
    "retrieval_reason": None, "graph_context": None, "clarification": None, "pending_missing": None, "pending_candidates": None,
    "answer": None, "sources": None, "kind": None, "error": None,
}
