"""Phân loại intent + viết lại câu hỏi nối tiếp thành câu độc lập (1 lượt LLM)."""

from __future__ import annotations

import logging
from typing import Sequence

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from ...observability import debug_enabled, log_event
from ..models import IntentResult
from ..ports import LLMProvider
from ..prompts import INTENT_SYSTEM
from .history import format_history


class IntentService:
    def __init__(self, llm: LLMProvider, history_window: int):
        self._llm = llm
        self._window = history_window

    def classify(self, history: Sequence[BaseMessage], message: str, awaiting_clarification: bool) -> IntentResult:
        history_text = format_history(history, self._window)
        prompt = (
            f"LỊCH SỬ (cũ -> mới):\n{history_text}\n\n"
            f"Bot vừa hỏi lại để xin thêm thông tin ở lượt trước: {'có' if awaiting_clarification else 'không'}\n\n"
            f"TIN NHẮN MỚI: {message}"
        )
        if debug_enabled():
            log_event("intent", level=logging.DEBUG, history=history_text)

        result = self._llm.structured(
            IntentResult, [SystemMessage(INTENT_SYSTEM), HumanMessage(prompt)], node="intent"
        )
        if not result.standalone_question.strip():
            result = result.model_copy(update={"standalone_question": message})
        log_event("intent", intent=result.intent, question=result.standalone_question,
                  continues_clarification=result.continues_clarification)
        return result
