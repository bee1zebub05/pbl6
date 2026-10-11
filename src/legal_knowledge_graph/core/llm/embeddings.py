"""
Embedding văn bản — chọn nhà cung cấp theo LKG_EMBED_PROVIDER, độc lập với LLM:

  gemini             gemini-embedding-001 qua bể key (gemini_key_pool.call_embed);
                     phân biệt câu hỏi / văn bản bằng task_type
  openai_compatible  endpoint /v1/embeddings chuẩn OpenAI — tự host (vLLM,
                     Ollama, TEI...) hoặc dịch vụ (OpenAI...)

Mọi vector được kiểm số chiều so với EMBED_DIMENSIONS: vector index trong
Neo4j có số chiều cố định, lệch thì truy vấn hỏng — báo lỗi rõ ngay ở đây.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from openai import OpenAI, OpenAIError

from .. import config
from . import gemini_key_pool

EmbedKind = Literal["query", "document"]

_GEMINI_TASK_TYPES = {"query": "RETRIEVAL_QUERY", "document": "RETRIEVAL_DOCUMENT"}


class EmbeddingError(Exception):
    pass


def embed_texts(texts: list[str], *, kind: EmbedKind) -> list[list[float]]:
    """Một request cho cả danh sách, trả đúng thứ tự. `kind`: 'query' cho câu
    hỏi người dùng, 'document' cho Điều khi backfill (embedding bất đối xứng)."""

    if config.EMBED_PROVIDER == "gemini":
        vectors = _embed_gemini(texts, kind)
    elif config.EMBED_PROVIDER == "openai_compatible":
        vectors = _embed_openai_compatible(texts)
    else:
        raise EmbeddingError(f"LKG_EMBED_PROVIDER='{config.EMBED_PROVIDER}' không hợp lệ — "
                             f"chọn một trong {config.LLM_PROVIDERS}")
    wrong = {len(v) for v in vectors} - {config.EMBED_DIMENSIONS}
    if wrong:
        raise EmbeddingError(
            f"Model embedding '{config.EMBED_MODEL}' trả vector {sorted(wrong)} chiều nhưng "
            f"LKG_EMBED_DIMENSIONS={config.EMBED_DIMENSIONS}. Đặt LKG_EMBED_DIMENSIONS đúng số chiều của "
            f"model rồi chạy `lkg embed-articles --reset` để dựng lại vector index."
        )
    return vectors


def _embed_gemini(texts: list[str], kind: EmbedKind) -> list[list[float]]:
    try:
        return gemini_key_pool.call_embed(texts, task_type=_GEMINI_TASK_TYPES[kind],
                                          output_dimensionality=config.EMBED_DIMENSIONS)
    except gemini_key_pool.GeminiCallError as exc:
        raise EmbeddingError(str(exc)) from exc


@lru_cache(maxsize=1)
def _openai_client() -> OpenAI:
    if not config.EMBED_MODEL:
        raise EmbeddingError("Chưa đặt LKG_EMBED_MODEL cho provider 'openai_compatible'")
    return OpenAI(base_url=config.EMBED_BASE_URL or None, api_key=config.EMBED_API_KEY or "not-needed",
                  timeout=config.LLM_TIMEOUT_SECONDS, max_retries=config.LLM_MAX_RETRIES)


def _embed_openai_compatible(texts: list[str]) -> list[list[float]]:
    try:
        response = _openai_client().embeddings.create(model=config.EMBED_MODEL, input=texts)
    except OpenAIError as exc:
        raise EmbeddingError(f"Gọi embedding thất bại: {exc}") from exc
    return [item.embedding for item in sorted(response.data, key=lambda d: d.index)]
