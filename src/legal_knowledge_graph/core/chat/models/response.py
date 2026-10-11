"""Response trả ra API/CLI."""

from __future__ import annotations

from pydantic import BaseModel

class ClarificationOut(BaseModel):
    question: str
    candidates: list[str] = []


class ChatResponse(BaseModel):
    thread_id: str
    turn_id: str
    trace_id: str | None = None
    kind: str  # answer | agent_answer | direct | clarification | no_data | error
    intent: str | None = None
    answer: str
    clarification: ClarificationOut | None = None
    action: str | None = None
    template: str | None = None
    cypher: str | None = None
    params: dict | None = None
    rows: list[dict] | None = None
    retrieval: list[dict] | None = None
    retrieval_reason: str | None = None
    sources: list[dict] = []
    elapsed_ms: float
    llm_calls: int = 0
