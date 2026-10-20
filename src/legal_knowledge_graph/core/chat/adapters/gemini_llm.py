"""
LLMProvider cho Gemini Developer API (`langchain-google-genai`), đi qua bể key
xoay vòng của core/llm/gemini_key_pool.py. Giữ một ChatGoogleGenerativeAI cho
mỗi (model, key); `max_retries=1` (= không tự retry, quy ước của SDK Google —
`0` lại có nghĩa là "dùng mặc định") để bể key tự xoay sang key khác thay vì SDK ngồi chờ.

Model dự phòng (LKG_LLM_FALLBACK_MODEL): model chính báo 503 quá tải thì gọi
lại ngay bằng model dự phòng thay vì cho từng key nghỉ rồi chờ — quá tải tính
theo model, đổi key không giúp được. Sau đó model chính bị bỏ qua trong
`_OVERLOAD_SECONDS` để không tốn một lượt 503 mỗi lời gọi.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from ...llm import gemini_key_pool
from ...observability import count_llm_call, log_event
from .langchain_llm import Build, LangChainLLM

_OVERLOAD_SECONDS = 60.0


class GeminiPooledLLM(LangChainLLM):
    provider = "gemini"

    def __init__(self, model_name: str, timeout_seconds: float, fallback_model: str = ""):
        # Không truyền temperature: gemini-3.x dùng sampling cố định và bỏ qua
        # tham số này (langchain-google-genai cảnh báo mỗi lần gọi). Structured
        # output dùng cách mặc định của ChatGoogleGenerativeAI (JSON Schema).
        super().__init__(model_name)
        self._timeout = timeout_seconds
        self._fallback = fallback_model if fallback_model != model_name else ""
        self._models: dict[tuple[str, str], ChatGoogleGenerativeAI] = {}
        self._primary_overloaded_until = 0.0
        self._lock = threading.Lock()

    def _model_for(self, model: str, key: str) -> ChatGoogleGenerativeAI:
        with self._lock:
            if (model, key) not in self._models:
                self._models[(model, key)] = ChatGoogleGenerativeAI(
                    model=model, google_api_key=key, max_retries=1, timeout=self._timeout,
                )
            return self._models[(model, key)]

    def _call(self, build: Build, messages: list[BaseMessage], info: dict[str, Any]) -> Any:
        info["attempts"] = 0
        if not self._fallback:
            return self._call_model(self.model_name, build, messages, info)
        if time.time() < self._primary_overloaded_until:
            return self._call_model(self._fallback, build, messages, info)
        try:
            return self._call_model(self.model_name, build, messages, info, fail_fast_on_overload=True)
        except gemini_key_pool.ModelOverloaded as exc:
            with self._lock:
                self._primary_overloaded_until = time.time() + _OVERLOAD_SECONDS
            log_event("llm.fallback", model=self.model_name, fallback=self._fallback,
                      skip_seconds=_OVERLOAD_SECONDS, reason=str(exc)[:200])
            return self._call_model(self._fallback, build, messages, info)

    def _call_model(self, model: str, build: Build, messages: list[BaseMessage], info: dict[str, Any], *,
                    fail_fast_on_overload: bool = False) -> Any:
        # Bể riêng theo model: quota và quá tải tính theo model, key đang nghỉ
        # ở model chính vẫn gọi được model dự phòng.
        pool = gemini_key_pool.get_pool(f"generate:{model}")
        info["model"] = model

        def call(key: str, _client) -> Any:
            info["attempts"] += 1
            info["key"] = pool.label(key)  # nhãn vị trí trong bể, không bao giờ là key thật
            count_llm_call()
            return build(self._model_for(model, key)).invoke(messages)

        return gemini_key_pool.call_with_pool(pool, call, f"Gọi Gemini {model}",
                                              fail_fast_on_overload=fail_fast_on_overload)
