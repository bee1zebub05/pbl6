"""
Nền chung cho mọi LLMProvider chạy qua một chat model của LangChain. Lớp con
chỉ lo phần khác nhau giữa các nhà cung cấp — cách gọi model (`_call`):
Gemini đi qua bể key, OpenAI-compatible gọi thẳng một endpoint.
"""

from __future__ import annotations

import time
from abc import abstractmethod
from typing import Any, Callable, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from ...observability import log_event
from ..ports import M, LLMProvider

# Biến chat model thành runnable cần gọi (structured / bind_tools / nguyên bản).
Build = Callable[[BaseChatModel], Runnable]


class LangChainLLM(LLMProvider):
    provider: str = "unknown"

    def __init__(self, model_name: str, structured_method: str | None = None):
        self.model_name = model_name
        # None = để chat model dùng cách mặc định của nó.
        self._structured_kwargs = {"method": structured_method} if structured_method else {}

    @abstractmethod
    def _call(self, build: Build, messages: list[BaseMessage], info: dict[str, Any]) -> Any:
        """Gọi model. Ghi thông tin cho log (số lần thử, key...) vào `info` NGAY
        trong lúc gọi — để log vẫn đủ khi lời gọi thất bại."""

    def _invoke(self, node: str, build: Build, messages: Sequence[BaseMessage]) -> Any:
        started = time.perf_counter()
        ok, info = False, {}
        try:
            result = self._call(build, list(messages), info)
            ok = True
            return result
        finally:
            log_event("llm", node=node, provider=self.provider, model=self.model_name, ok=ok,
                      ms=round((time.perf_counter() - started) * 1000, 1), **info)

    def structured(self, schema: type[M], messages: Sequence[BaseMessage], *, node: str) -> M:
        return self._invoke(node, lambda m: m.with_structured_output(schema, **self._structured_kwargs), messages)

    def text(self, messages: Sequence[BaseMessage], *, node: str) -> str:
        message: AIMessage = self._invoke(node, lambda m: m, messages)
        return message.text.strip()

    def invoke_with_tools(self, messages: Sequence[BaseMessage], tools: Sequence[BaseTool], *,
                          node: str) -> AIMessage:
        return self._invoke(node, lambda m: m.bind_tools(list(tools)), messages)
