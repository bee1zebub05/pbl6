"""
Composition root — nơi DUY NHẤT ráp bản cài cụ thể (LLM, Neo4j) vào các
service. Kiểm thử truyền bản giả qua tham số, phần còn lại dùng mặc định.
"""

from __future__ import annotations

import threading

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

from .. import config
from ..db import Neo4jConnection
from ..observability import setup_logging
from .adapters.gemini_llm import GeminiPooledLLM
from .adapters.graph_retriever import Neo4jGraphRetriever
from .adapters.neo4j_adapters import Neo4jEntityResolver, Neo4jQueryExecutor
from .adapters.openai_compatible_llm import OpenAICompatibleLLM
from .agent import AgentService
from .answering.answer import AnswerService
from .answering.clarification import ClarificationService
from .chat_service import ChatService
from .ports import ContextRetriever, EntityResolver, LLMProvider, QueryExecutor
from .retrieval.graph_rag import GraphRagService
from .retrieval.template_query import TemplateQueryService
from .understanding.intent import IntentService
from .understanding.router import RouterService
from .understanding.template_selector import TemplateSelector
from .workflow.builder import ChatGraphBuilder
from .workflow.nodes import ChatNodes

_connection: Neo4jConnection | None = None
_lock = threading.RLock()


def _neo4j_connection() -> Neo4jConnection:
    global _connection
    with _lock:
        if _connection is None:
            _connection = Neo4jConnection()
        return _connection


_STRUCTURED_METHODS = ("json_schema", "function_calling", "json_mode")


def build_llm() -> LLMProvider:
    """Chọn LLM theo LKG_LLM_PROVIDER — chỗ DUY NHẤT biết đang dùng nhà cung cấp
    nào. Cấu hình sai báo lỗi ngay lúc khởi động, không đợi câu hỏi đầu tiên."""

    provider = config.LLM_PROVIDER
    if provider not in config.LLM_PROVIDERS:
        raise ValueError(f"LKG_LLM_PROVIDER='{provider}' không hợp lệ — chọn một trong {config.LLM_PROVIDERS}")
    if not config.LLM_MODEL:
        raise ValueError(f"Chưa đặt LKG_LLM_MODEL cho provider '{provider}'")
    if provider == "gemini":
        return GeminiPooledLLM(config.LLM_MODEL, config.LLM_TIMEOUT_SECONDS, config.LLM_FALLBACK_MODEL)
    if config.LLM_STRUCTURED_METHOD not in _STRUCTURED_METHODS:
        raise ValueError(f"LKG_LLM_STRUCTURED_METHOD='{config.LLM_STRUCTURED_METHOD}' không hợp lệ — "
                         f"chọn một trong {_STRUCTURED_METHODS}")
    return OpenAICompatibleLLM(
        model_name=config.LLM_MODEL, base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY,
        structured_method=config.LLM_STRUCTURED_METHOD, timeout_seconds=config.LLM_TIMEOUT_SECONDS,
        max_retries=config.LLM_MAX_RETRIES,
    )


def build_template_query_service(executor: QueryExecutor | None = None,
                                 resolver: EntityResolver | None = None) -> TemplateQueryService:
    return TemplateQueryService(
        executor or Neo4jQueryExecutor(_neo4j_connection()),
        resolver or Neo4jEntityResolver(_neo4j_connection()),
    )


def build_graph_retriever(*, enabled: bool = config.RETRIEVAL_ENABLED) -> Neo4jGraphRetriever:
    return Neo4jGraphRetriever(
        _neo4j_connection(),
        GraphRagService(top_k=config.RETRIEVAL_TOP_K, context_chars=config.GRAPH_RAG_CONTEXT_CHARS,
                        article_chars=config.GRAPH_RAG_ARTICLE_CHARS),
        enabled=enabled, seed_k=config.GRAPH_RAG_SEED_K, scope_docs=config.GRAPH_RAG_SCOPE_DOCS,
        scope_per_doc=config.GRAPH_RAG_SCOPE_PER_DOC, max_related=config.GRAPH_RAG_MAX_RELATED,
    )


def build_chat_service(*, llm: LLMProvider | None = None, executor: QueryExecutor | None = None,
                       resolver: EntityResolver | None = None, retriever: ContextRetriever | None = None,
                       checkpointer: BaseCheckpointSaver | None = None,
                       retrieval_enabled: bool = config.RETRIEVAL_ENABLED) -> ChatService:
    setup_logging()
    llm = llm or build_llm()
    executor = executor or Neo4jQueryExecutor(_neo4j_connection())
    retriever = retriever or build_graph_retriever(enabled=retrieval_enabled)

    templates = build_template_query_service(executor, resolver)
    nodes = ChatNodes(
        intent=IntentService(llm, config.CHAT_HISTORY_WINDOW),
        router=RouterService(llm, TemplateSelector()),
        templates=templates,
        clarification=ClarificationService(),
        answer=AnswerService(llm, config.ANSWER_MAX_ROWS),
        agent=AgentService(llm, templates, executor, retriever, config.AGENT_MAX_STEPS, config.ANSWER_MAX_ROWS,
                           config.CHAT_HISTORY_WINDOW),
        retriever=retriever,
        max_clarify_rounds=config.MAX_CLARIFY_ROUNDS,
    )
    graph = ChatGraphBuilder(nodes).build(checkpointer if checkpointer is not None else MemorySaver())
    return ChatService(graph, llm.model_name, config.CHAT_MAX_QUESTION_CHARS, config.TURN_DEADLINE_SECONDS)


_default_service: ChatService | None = None


def get_chat_service() -> ChatService:
    """Một ChatService dùng chung cho cả tiến trình (API) — MemorySaver của nó
    giữ lịch sử hội thoại theo thread_id cho tới khi tiến trình dừng."""

    global _default_service
    with _lock:
        if _default_service is None:
            _default_service = build_chat_service()
        return _default_service
