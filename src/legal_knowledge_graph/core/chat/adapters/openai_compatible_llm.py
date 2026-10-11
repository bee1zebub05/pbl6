"""
LLMProvider cho mọi server theo chuẩn OpenAI Chat Completions — tự host trên
cloud (vLLM, Ollama, TGI, LM Studio...) hoặc dịch vụ (OpenAI, OpenRouter,
Together, Groq, DeepSeek...). Chỉ cần `base_url`, `api_key`, `model`.

Server tự host cần bật hai khả năng chatbot dùng:
- output có cấu trúc (node intent, route): JSON Schema qua `response_format`,
  hoặc đặt LKG_LLM_STRUCTURED_METHOD=function_calling nếu server chưa hỗ trợ;
- tool calling (agent): ví dụ vLLM chạy với `--enable-auto-tool-choice
  --tool-call-parser <parser của model>`.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

from ...observability import count_llm_call
from .langchain_llm import Build, LangChainLLM

# langchain-openai bắt buộc có api_key; server tự host không kiểm key thì giá trị nào cũng được.
_NO_KEY = "not-needed"


class OpenAICompatibleLLM(LangChainLLM):
    provider = "openai_compatible"

    def __init__(self, *, model_name: str, base_url: str, api_key: str, structured_method: str,
                 timeout_seconds: float, max_retries: int):
        super().__init__(model_name, structured_method)
        self._model = ChatOpenAI(
            model=model_name, base_url=base_url or None, api_key=api_key or _NO_KEY,
            timeout=timeout_seconds, max_retries=max_retries,
        )
        self._base_url = base_url or "https://api.openai.com/v1"

    def _call(self, build: Build, messages: list[BaseMessage], info: dict[str, Any]) -> Any:
        info["base_url"] = self._base_url
        count_llm_call()
        return build(self._model).invoke(messages)
