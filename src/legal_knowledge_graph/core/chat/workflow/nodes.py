"""
Node của LangGraph — mỗi method một node, chỉ gọi service rồi ánh xạ kết quả
vào state (SRP: nghiệp vụ nằm ở understanding/, retrieval/, answering/, agent.py; I/O nằm ở adapters/). Hàm định tuyến
(`after_*`) đặt cạnh node để đọc luồng ở một chỗ.

`@safe_node` là chỗ DUY NHẤT bắt lỗi hạ tầng (hết quota Gemini, Neo4j mất kết
nối...): node lỗi trả kind="error" + câu thông báo thân thiện, mọi hàm định
tuyến thấy kind="error" thì kết thúc lượt.
"""

from __future__ import annotations

import functools
import logging
import time
import traceback
from typing import Callable

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END

from ...graph_query.templates import retrieval_mode
from ...observability import log_event
from .. import session_log
from ..models import ChatState, GraphContext, QueryResult, ResolutionFailed, TemplateParamError
from ..ports import ContextRetriever
from ..prompts import ERROR_ANSWER, FALLBACK_REPLIES, SUGGESTIONS
from ..agent import AgentService
from ..answering.answer import AnswerService
from ..answering.clarification import ClarificationService
from ..answering.evidence import collect_sources, to_plain_text
from ..understanding.intent import IntentService
from ..understanding.router import RouterService
from ..retrieval.template_query import TemplateQueryService

NodeFn = Callable[["ChatNodes", ChatState], dict]

# Tên node — dùng chung cho builder và các hàm định tuyến.
INTENT, RESPOND_DIRECT, ROUTE, RUN_TEMPLATE = "intent", "respond_direct", "route", "run_template"
ASK_CLARIFY, RETRIEVE, ANSWER, AGENT = "ask_clarify", "retrieve", "answer", "agent"

_RESOLUTION = "clarify_resolution"


def safe_node(name: str) -> Callable[[NodeFn], NodeFn]:
    def decorator(fn: NodeFn) -> NodeFn:
        @functools.wraps(fn)
        def wrapper(self: "ChatNodes", state: ChatState) -> dict:
            started = time.perf_counter()
            try:
                update = fn(self, state)
            except Exception as exc:
                log_event("error", level=logging.ERROR, node=name, error_type=type(exc).__name__,
                          message=str(exc)[:500])
                log_event("error", level=logging.DEBUG, node=name, traceback=traceback.format_exc())
                session_log.error(name, exc)
                return {"kind": "error", "error": f"{type(exc).__name__}: {exc}", "answer": ERROR_ANSWER,
                        "messages": [AIMessage(ERROR_ANSWER)], "clarify_rounds": 0}
            session_log.step(f"[{name}] đầu ra node · {(time.perf_counter() - started) * 1000:.0f} ms",
                             **_session_view(update))
            return update
        return wrapper
    return decorator


def _session_view(update: dict) -> dict:
    """State node vừa ghi, gọn cho log phiên: bỏ `messages`, `answer`, `sources` (khối
    kết quả lượt đã in), ngữ cảnh GraphRAG chỉ giữ một dòng mỗi Điều (toàn văn đã
    nằm trong prompt answer)."""

    view = {k: v for k, v in update.items() if k not in ("messages", "answer", "sources")}
    if view.get("graph_context"):
        view["graph_context"] = [
            f"{h['documentNumber']} · {h['articleId']} · {h['heading'] or ''} · via {'+'.join(h['via'])} · "
            f"{h['effectiveStatus']}" + (f" (bị thay bởi {', '.join(h['supersededBy'])})" if h["supersededBy"] else "")
            + f" · {len(h['text'])} ký tự"
            for h in GraphContext.model_validate(view["graph_context"]).hits()
        ]
    return view


def _failed(state: ChatState) -> bool:
    return state.get("kind") == "error"


def _message_text(message: BaseMessage) -> str:
    return message.text if isinstance(message, HumanMessage) else str(message.content)


def _documents_in(params: dict | None, rows: list[dict] | None) -> tuple[str, ...]:
    """Phạm vi ưu tiên cho GraphRAG: văn bản câu hỏi nhắc tới (tham số
    normalizedNumber đã resolve) trước, rồi văn bản trong kết quả template
    (cột documentNumber, hoặc target ở template quan hệ); bỏ trùng, giữ thứ tự."""

    asked = [(params or {}).get("normalizedNumber")]
    in_rows = [r.get("documentNumber") or r.get("target") for r in rows or []]
    return tuple(dict.fromkeys(n for n in asked + in_rows if isinstance(n, str) and n))


class ChatNodes:
    def __init__(self, *, intent: IntentService, router: RouterService, templates: TemplateQueryService,
                 clarification: ClarificationService, answer: AnswerService, agent: AgentService,
                 retriever: ContextRetriever, max_clarify_rounds: int):
        self._intent = intent
        self._router = router
        self._templates = templates
        self._clarification = clarification
        self._answer = answer
        self._agent = agent
        self._retriever = retriever
        self._max_clarify_rounds = max_clarify_rounds

    # ------------------------------------------------------------ nodes

    @safe_node(INTENT)
    def intent(self, state: ChatState) -> dict:
        messages = state["messages"]
        rounds = state.get("clarify_rounds") or 0
        result = self._intent.classify(messages[:-1], _message_text(messages[-1]), awaiting_clarification=rounds > 0)
        return {
            "intent": result.intent,
            "question": result.standalone_question,
            "direct_reply": result.direct_reply,
            "clarify_rounds": rounds if result.continues_clarification else 0,
        }

    @safe_node(RESPOND_DIRECT)
    def respond_direct(self, state: ChatState) -> dict:
        intent = state.get("intent") or "out_of_scope"
        reply = (state.get("direct_reply") or "").strip() or FALLBACK_REPLIES.get(intent, FALLBACK_REPLIES["out_of_scope"])
        if intent in ("smalltalk", "out_of_scope"):
            reply = f"{reply}\n\n{SUGGESTIONS}"
        return self._finish(reply, kind="direct")

    @safe_node(ROUTE)
    def route(self, state: ChatState) -> dict:
        frame, decision = self._router.route(state["question"])
        return {
            "action": frame.action,
            "slots": frame.slots.filled(),
            "route_kind": decision.kind,
            "route_reason": decision.reason,
            "template": decision.template,
            "raw_params": decision.raw_params,
            "pending_missing": decision.missing,
        }

    @safe_node(RUN_TEMPLATE)
    def run_template(self, state: ChatState) -> dict:
        try:
            result = self._templates.run(state["template"], state.get("raw_params") or {})
        except ResolutionFailed as exc:
            return {"route_kind": _RESOLUTION, "route_reason": exc.reason,
                    "pending_missing": (exc.slot,) if exc.slot else (), "pending_candidates": exc.candidates}
        except TemplateParamError as exc:
            return {"route_kind": "agent", "route_reason": str(exc)}
        return {"cypher": result.cypher, "params": result.params, "rows": result.rows}

    @safe_node(ASK_CLARIFY)
    def ask_clarify(self, state: ChatState) -> dict:
        missing = tuple(state.get("pending_missing") or ())
        if state.get("route_kind") == _RESOLUTION:
            clar = self._clarification.for_resolution(
                missing[0] if missing else None, state.get("route_reason") or "",
                tuple(state.get("pending_candidates") or ()),
            )
        else:
            clar = self._clarification.for_missing(missing)
        rounds = (state.get("clarify_rounds") or 0) + 1
        log_event("clarify", missing=list(missing), candidates=list(clar.candidates), round=rounds)
        update = self._finish(clar.question, kind="clarification", clarify_rounds=rounds)
        update["clarification"] = {"question": clar.question, "candidates": list(clar.candidates)}
        return update

    @safe_node(RETRIEVE)
    def retrieve(self, state: ChatState) -> dict:
        # GraphRAG là bằng chứng phụ — lỗi ở đây không được làm hỏng kết quả Cypher đã có.
        try:
            context = self._retriever.retrieve(
                state["question"], scope_docs=_documents_in(state.get("params"), state.get("rows")),
                mode=retrieval_mode(state.get("action")), phrase=(state.get("slots") or {}).get("phrase"),
            )
        except Exception as exc:
            log_event("graph_rag", level=logging.WARNING, failed=True, error=str(exc)[:300])
            return {"graph_context": None, "retrieval_reason": f"Truy xuất ngữ cảnh thất bại: {exc}"}
        return {"graph_context": context.model_dump()}

    @safe_node(ANSWER)
    def answer(self, state: ChatState) -> dict:
        query = QueryResult(template=state.get("template"), cypher=state.get("cypher") or "",
                            params=state.get("params") or {}, rows=state.get("rows") or [], elapsed_ms=0.0)
        context = GraphContext.model_validate(state.get("graph_context") or {})
        text, sources, has_evidence = self._answer.compose(state["question"], query, context)
        update = self._finish(text, kind="answer" if has_evidence else "no_data")
        update["sources"] = sources
        return update

    @safe_node(AGENT)
    def agent(self, state: ChatState) -> dict:
        messages = state["messages"]
        outcome = self._agent.run(
            state["question"], history=messages[:-1], original=_message_text(messages[-1]),
            action=state.get("action"), slots=state.get("slots"), route_reason=state.get("route_reason"),
        )
        update = self._finish(outcome.answer, kind="agent_answer")
        update.update({
            "template": None, "cypher": outcome.cypher, "rows": outcome.rows,
            "graph_context": outcome.context.model_dump(),
            "sources": collect_sources(outcome.rows, outcome.context.hits()),
        })
        return update

    @staticmethod
    def _finish(answer: str, *, kind: str, clarify_rounds: int = 0) -> dict:
        """Kết thúc lượt: ghi câu trả lời vào state và vào lịch sử hội thoại."""

        answer = to_plain_text(answer)
        return {"answer": answer, "kind": kind, "messages": [AIMessage(answer)], "clarify_rounds": clarify_rounds}

    # ------------------------------------------------------------ định tuyến

    def _can_clarify(self, state: ChatState) -> bool:
        return (state.get("clarify_rounds") or 0) < self._max_clarify_rounds

    def after_intent(self, state: ChatState) -> str:
        if _failed(state):
            return END
        return ROUTE if state.get("intent") == "domain_query" else RESPOND_DIRECT

    def after_route(self, state: ChatState) -> str:
        if _failed(state):
            return END
        kind = state.get("route_kind")
        if kind == "template":
            return RUN_TEMPLATE
        if kind == "clarify":
            return ASK_CLARIFY if self._can_clarify(state) else AGENT
        return AGENT

    def after_run_template(self, state: ChatState) -> str:
        if _failed(state):
            return END
        kind = state.get("route_kind")
        if kind == _RESOLUTION:
            return ASK_CLARIFY if self._can_clarify(state) else AGENT
        if kind == "agent":
            return AGENT
        # Thống kê / đếm / xếp hạng: kết quả template đã đủ, không truy xuất Điều.
        return ANSWER if retrieval_mode(state.get("action")) == "none" else RETRIEVE
