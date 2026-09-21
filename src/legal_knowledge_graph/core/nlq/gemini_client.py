"""
Gemini client MỎNG cho core/nlq/ — chỉ 1 hàm gọi structured JSON output.

Cố tình KHÔNG copy cơ chế key-pool/multi-variant-fallback phức tạp của
src/vanban/clean/gemini_fix.py (GeminiCorrector) — đó phục vụ OCR hàng
loạt, tần suất gọi rất cao, cần xoay nhiều key. NLQ gọi ít (1 câu hỏi = 1-2
lần gọi), không cần độ phức tạp đó. Key/model đọc từ config.NLQ_GEMINI_*
(nạp từ legal_knowledge_graph/.env, RIÊNG với GEMINI_* ở .env gốc).
"""

from __future__ import annotations

import json
import time

from google import genai
from google.genai import types

from .. import config


class GeminiCallError(Exception):
    pass


# Lỗi tạm thời (quá tải/vượt rate limit) — thử lại vài lần trước khi bỏ
# cuộc, thay vì để 1 lần 429/503 thoáng qua làm hỏng cả câu hỏi. Free-tier
# key có quota thấp (vd 5 request/phút) nên việc gặp 429 là bình thường,
# không phải lỗi code.
_RETRY_STATUS_MARKERS = ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE")
_MAX_RETRIES = 3
_BASE_DELAY_SECONDS = 5.0


_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not config.NLQ_GEMINI_API_KEY:
            raise GeminiCallError(
                "Chưa cấu hình LKG_GEMINI_API_KEY_0 trong legal_knowledge_graph/.env"
            )
        _client = genai.Client(api_key=config.NLQ_GEMINI_API_KEY)
    return _client


def call_json(prompt: str, response_schema: dict, temperature: float = 0.0) -> dict:
    """Gọi Gemini, ép output JSON đúng response_schema (dict dạng OpenAPI
    subset — xem google.genai.types.Schema). Raise GeminiCallError nếu lỗi
    gọi API hoặc output không parse được JSON."""

    client = _get_client()
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=config.NLQ_GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=response_schema,
                ),
            )
            break
        except Exception as exc:
            last_exc = exc
            transient = any(marker in str(exc) for marker in _RETRY_STATUS_MARKERS)
            if not transient or attempt == _MAX_RETRIES:
                raise GeminiCallError(f"Gọi Gemini thất bại: {exc}") from exc
            time.sleep(_BASE_DELAY_SECONDS * (2 ** attempt))
    else:
        raise GeminiCallError(f"Gọi Gemini thất bại sau {_MAX_RETRIES} lần thử lại: {last_exc}")

    text = response.text
    if not text:
        raise GeminiCallError("Gemini trả về rỗng (có thể bị chặn bởi safety filter)")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise GeminiCallError(f"Gemini trả JSON không hợp lệ: {exc}\nRaw: {text[:500]}") from exc
