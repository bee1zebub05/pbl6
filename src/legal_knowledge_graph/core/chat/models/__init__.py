"""
Kiểu dữ liệu dùng chung của chatbot, chia theo nhóm:

    frames.py         output LLM (intent, router) + quyết định chọn template
    results.py        kết quả trung gian giữa các bước, lỗi nghiệp vụ
    graph_context.py  ngữ cảnh GraphRAG
    state.py          state của LangGraph
    response.py       response trả ra API/CLI

Không chứa logic. Import qua package này: `from ..models import GraphContext`.
"""

from .frames import (Intent, IntentResult, QueryFrame, RouteDecision, RouterOutput, Slots,
                     frame_from_router)
from .graph_context import ArticleEvidence, DocumentContext, GraphContext, RelatedDocument
from .response import ChatResponse, ClarificationOut
from .results import AgentOutcome, Clarification, QueryResult, ResolutionFailed, TemplateParamError
from .state import TURN_RESET, ChatState

__all__ = [
    "AgentOutcome",
    "ArticleEvidence",
    "ChatResponse",
    "ChatState",
    "Clarification",
    "ClarificationOut",
    "DocumentContext",
    "GraphContext",
    "Intent",
    "IntentResult",
    "QueryFrame",
    "QueryResult",
    "RelatedDocument",
    "ResolutionFailed",
    "RouteDecision",
    "RouterOutput",
    "Slots",
    "TURN_RESET",
    "TemplateParamError",
    "frame_from_router",
]
