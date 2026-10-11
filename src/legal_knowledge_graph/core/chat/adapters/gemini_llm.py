"""
LLMProvider cho Gemini Developer API (`langchain-google-genai`), đi qua bể key
xoay vòng của core/llm/gemini_key_pool.py. Giữ một ChatGoogleGenerativeAI cho
mỗi key; `max_retries=1` (= không tự retry, quy ước của SDK Google — `0` lại
có nghĩa là "dùng mặc định") để bể key tự xoay sang key khác thay vì SDK ngồi chờ.
"""

from __future__ import annotations

import threading
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from ...llm import gemini_key_pool
from ...observability import count_llm_call
from .langchain_llm import Build, LangChainLLM


class GeminiPooledLLM(LangChainLLM):
    provider = "gemini"

    def __init__(self, model_name: str, timeout_seconds: float):
        # Không truyền temperature: gemini-3.x dùng sampling cố định và bỏ qua
        # tham số này (langchain-google-genai cảnh báo mỗi lần gọi). Structured
        # output dùng cách mặc định của ChatGoogleGenerativeAI (JSON Schema).
        super().__init__(model_name)
        self._timeout = timeout_seconds
        self._models: dict[str, ChatGoogleGenerativeAI] = {}
        self._lock = threading.Lock()

    def _model_for(self, key: str) -> ChatGoogleGenerativeAI:
        with self._lock:
            if key not in self._models:
                self._models[key] = ChatGoogleGenerativeAI(
                    model=self.model_name, google_api_key=key, max_retries=1, timeout=self._timeout,
                )
            return self._models[key]

    def _call(self, build: Build, messages: list[BaseMessage], info: dict[str, Any]) -> Any:
        pool = gemini_key_pool.get_pool("generate")
        info["attempts"] = 0

        def call(key: str, _client) -> Any:
            info["attempts"] += 1
            info["key"] = pool.label(key)  # nhãn vị trí trong bể, không bao giờ là key thật
            count_llm_call()
            return build(self._model_for(key)).invoke(messages)

        return gemini_key_pool.call_with_pool(pool, call, "Gọi Gemini")
