"""Tổng hợp câu trả lời văn xuôi từ kết quả template + ngữ cảnh GraphRAG (1 lượt LLM)."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from ...graph_query.templates import TEMPLATES
from ...observability import log_event
from ..models import GraphContext, QueryResult
from ..ports import LLMProvider
from ..prompts import ANSWER_SYSTEM, NO_DATA_ANSWER
from .evidence import collect_sources, context_to_text, rows_to_text


class AnswerService:
    def __init__(self, llm: LLMProvider, max_rows: int):
        self._llm = llm
        self._max_rows = max_rows

    def compose(self, question: str, query: QueryResult | None,
                context: GraphContext) -> tuple[str, list[dict], bool]:
        """-> (câu trả lời, nguồn, có_bằng_chứng). Không có bằng chứng thì trả
        câu cố định, không tốn lượt gọi LLM."""

        rows = query.rows if query else []
        sources = collect_sources(rows, context.hits())
        if not rows and context.is_empty():
            log_event("answer", has_evidence=False)
            return NO_DATA_ANSWER, sources, False

        parts = [f"CÂU HỎI: {question}", "BẰNG CHỨNG:"]
        if query is not None:
            description = TEMPLATES[query.template].description if query.template in TEMPLATES else ""
            query_limit = query.params.get("limit") if isinstance(query.params.get("limit"), int) else None
            parts.append(f"[Kết quả truy vấn đồ thị — {description}]\n"
                         f"{rows_to_text(rows, self._max_rows, query_limit)}")
        if not context.is_empty():
            parts.append("[Ngữ cảnh từ đồ thị: các Điều liên quan nhất, gom theo văn bản, kèm hiệu lực thực tế "
                         "và quan hệ — có thể có Điều không liên quan, hãy tự chọn lọc]\n"
                         f"{context_to_text(context)}")

        answer = self._llm.text([SystemMessage(ANSWER_SYSTEM), HumanMessage("\n\n".join(parts))], node="answer")
        log_event("answer", has_evidence=True, chars=len(answer), sources=len(sources))
        return answer, sources, True
