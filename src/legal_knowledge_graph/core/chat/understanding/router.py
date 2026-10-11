"""Trích khung câu hỏi (action + slot) bằng LLM rồi để TemplateSelector quyết định."""

from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from ...normalize import find_document_numbers
from ...observability import debug_enabled, log_event
from ..models import QueryFrame, RouteDecision, RouterOutput, frame_from_router
from ..ports import LLMProvider
from ..prompts import ROUTER_SYSTEM
from .template_selector import TemplateSelector


def backfill_doc_number(question: str, frame: QueryFrame) -> QueryFrame:
    """LLM đôi khi bỏ trống doc_number khi số hiệu là chủ ngữ của câu ("Văn bản
    2673/QĐ-ĐHBK quy định gì về ...") — đã tái hiện được với gemini-3.6-flash.
    Câu có ĐÚNG MỘT số hiệu thì tự điền bằng regex; nhiều số hiệu (so sánh...)
    thì để nguyên, không đoán."""

    if frame.slots.doc_number:
        return frame
    numbers = find_document_numbers(question)
    if len(numbers) != 1:
        return frame
    log_event("route", backfilled_doc_number=numbers[0])
    return frame.model_copy(update={"slots": frame.slots.model_copy(update={"doc_number": numbers[0]})})


class RouterService:
    def __init__(self, llm: LLMProvider, selector: TemplateSelector):
        self._llm = llm
        self._selector = selector

    def route(self, question: str) -> tuple[QueryFrame, RouteDecision]:
        output = self._llm.structured(
            RouterOutput, [SystemMessage(ROUTER_SYSTEM), HumanMessage(f"CÂU HỎI: {question}")], node="route"
        )
        frame = frame_from_router(output)
        if debug_enabled():
            log_event("route", level=logging.DEBUG, frame=frame.model_dump())
        frame = backfill_doc_number(question, frame)
        return frame, self._selector.select(frame)
