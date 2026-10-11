"""
Facade của chatbot — API, CLI và bộ eval chỉ gọi `ChatService.ask()`. Lo
phần quanh một lượt hỏi: gắn thread_id/turn_id, mở trace gốc trên LangSmith,
log turn.start/turn.end, đổi state cuối của graph thành ChatResponse.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from langchain_core.messages import HumanMessage

from ..observability import (annotate_current_trace, current_trace_id, llm_calls_in_turn, log_event,
                             traceable, turn_context)
from .models import TURN_RESET, ChatResponse, ClarificationOut, GraphContext
from .prompts import ERROR_ANSWER


def _trace_summary(output: Any) -> dict:
    state, _ = output
    return {k: state.get(k) for k in ("kind", "intent", "action", "template", "answer")}


class ChatService:
    def __init__(self, graph, model_name: str, max_question_chars: int):
        self._graph = graph
        self._model_name = model_name
        self._max_chars = max_question_chars

    def ask(self, question: str, thread_id: str | None = None) -> ChatResponse:
        question = (question or "").strip()[: self._max_chars]
        if not question:
            raise ValueError("Câu hỏi rỗng")
        thread_id = thread_id or uuid.uuid4().hex

        with turn_context(thread_id) as turn_id:
            log_event("turn.start", question=question)
            started = time.perf_counter()
            try:
                state, trace_id = self._run(question, thread_id, turn_id)
            except Exception as exc:  # lỗi ngoài node (checkpointer, cấu hình graph...)
                log_event("error", level=logging.ERROR, node="graph", error_type=type(exc).__name__,
                          message=str(exc)[:500])
                state, trace_id = {"kind": "error", "answer": ERROR_ANSWER, "error": str(exc)}, None
            elapsed_ms = (time.perf_counter() - started) * 1000
            response = self._to_response(state, thread_id, turn_id, trace_id, elapsed_ms, llm_calls_in_turn())
            log_event("turn.end", kind=response.kind, intent=response.intent, action=response.action,
                      template=response.template, ms=round(elapsed_ms, 1), llm_calls=response.llm_calls,
                      trace_id=trace_id)
        return response

    @traceable(name="legal_chat", process_outputs=_trace_summary)
    def _run(self, question: str, thread_id: str, turn_id: str) -> tuple[dict, str | None]:
        state = self._graph.invoke(
            {"messages": [HumanMessage(question)], **TURN_RESET},
            config={"configurable": {"thread_id": thread_id},
                    "metadata": {"thread_id": thread_id, "turn_id": turn_id, "model": self._model_name}},
        )
        annotate_current_trace(
            tags=[state.get("kind"), state.get("intent"), state.get("action"),
                  state.get("template") or ("agent" if state.get("kind") == "agent_answer" else None)],
            metadata={"thread_id": thread_id, "turn_id": turn_id, "model": self._model_name},
        )
        return state, current_trace_id()

    @staticmethod
    def _to_response(state: dict, thread_id: str, turn_id: str, trace_id: str | None,
                     elapsed_ms: float, llm_calls: int) -> ChatResponse:
        clar = state.get("clarification")
        return ChatResponse(
            thread_id=thread_id,
            turn_id=turn_id,
            trace_id=trace_id,
            kind=state.get("kind") or "error",
            intent=state.get("intent") or None,
            answer=state.get("answer") or ERROR_ANSWER,
            clarification=ClarificationOut(**clar) if clar else None,
            action=state.get("action"),
            template=state.get("template"),
            cypher=state.get("cypher"),
            params=state.get("params"),
            rows=state.get("rows"),
            retrieval=GraphContext.model_validate(state.get("graph_context") or {}).hits() or None,
            retrieval_reason=state.get("retrieval_reason"),
            sources=state.get("sources") or [],
            elapsed_ms=round(elapsed_ms, 1),
            llm_calls=llm_calls,
        )
