"""
Xếp hạng lại (rerank) các Điều ứng viên theo mức liên quan tới câu hỏi — chọn
nhà cung cấp theo LKG_RERANK_PROVIDER:

  none           tắt (mặc định): giữ nguyên thứ tự RRF của vector + fulltext
  gemini         một lời gọi LLM chấm điểm 0–10 cho cả danh sách, qua bể key
                 riêng "rerank:<model>" (không làm cạn bể của chatbot)
  cross_encoder  cross-encoder chạy tại máy qua sentence-transformers, mặc định
                 BAAI/bge-reranker-v2-m3 (đa ngôn ngữ, có tiếng Việt). Cần
                 `pip install sentence-transformers` — tải model ~2 GB lần đầu.

Vì sao có bước này: RRF chỉ gộp THỨ HẠNG của hai nguồn, không đọc lại câu hỏi
và Điều cùng lúc. Reranker đọc từng cặp (câu hỏi, Điều) nên tách được Điều chỉ
trùng từ khoá với Điều trả lời đúng câu hỏi. Trên ViDoRe V3 (4/2026), thêm
rerank nâng nDCG@10 của truy hồi văn bản từ 50,4 lên 63,6 — xem
reports/Pipeline chuẩn OCR scan sang embedding.md. Chưa đo trên kho của nhóm:
chạy `python run.py bench --compare-bm25` với hệ `hybrid_rerank`.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Callable

from .. import config

Scorer = Callable[[str, list[str]], list[float]]


class RerankError(Exception):
    pass


_PROMPT = """Bạn chấm mức liên quan giữa một câu hỏi và từng đoạn văn bản pháp quy.
Với MỖI đoạn, cho một số nguyên từ 0 đến 10:
10 = đoạn trả lời trực tiếp câu hỏi; 5 = cùng chủ đề nhưng không trả lời; 0 = không liên quan.
Chỉ dựa vào nội dung đoạn. Trả về đúng một mảng JSON gồm {n} số nguyên, theo thứ tự đoạn.

Câu hỏi: {question}

{passages}"""


def _score_gemini(question: str, passages: list[str]) -> list[float]:
    from google.genai import types

    from . import gemini_key_pool

    body = "\n\n".join(f"[Đoạn {i}]\n{p}" for i, p in enumerate(passages, 1))
    prompt = _PROMPT.format(n=len(passages), question=question, passages=body)
    cfg = types.GenerateContentConfig(temperature=0, response_mime_type="application/json",
                                      response_schema=list[int])

    def call(_key: str, client) -> list[float]:
        resp = client.models.generate_content(model=config.RERANK_MODEL, contents=prompt, config=cfg)
        scores = json.loads(resp.text or "[]")
        if not isinstance(scores, list) or len(scores) != len(passages):
            raise RerankError(f"reranker trả {len(scores) if isinstance(scores, list) else '?'} điểm "
                              f"cho {len(passages)} đoạn")
        return [float(s) for s in scores]

    try:
        return gemini_key_pool.call_with_pool(gemini_key_pool.get_pool(f"rerank:{config.RERANK_MODEL}"),
                                              call, "Gọi Gemini rerank")
    except gemini_key_pool.GeminiCallError as exc:
        raise RerankError(str(exc)) from exc


@lru_cache(maxsize=1)
def _cross_encoder():
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as exc:
        raise RerankError("LKG_RERANK_PROVIDER=cross_encoder cần `pip install sentence-transformers`") from exc
    return CrossEncoder(config.RERANK_MODEL, max_length=512)


def _score_cross_encoder(question: str, passages: list[str]) -> list[float]:
    return [float(s) for s in _cross_encoder().predict([(question, p) for p in passages])]


def build_scorer(provider: str | None = None) -> Scorer | None:
    """Hàm chấm điểm theo cấu hình, hoặc None khi tắt rerank."""

    provider = (provider or config.RERANK_PROVIDER).strip().lower()
    if provider in ("", "none"):
        return None
    if provider == "gemini":
        return _score_gemini
    if provider == "cross_encoder":
        return _score_cross_encoder
    raise RerankError(f"LKG_RERANK_PROVIDER='{provider}' không hợp lệ — chọn none, gemini hoặc cross_encoder")


def passage(row: dict, limit: int | None = None) -> str:
    """Đoạn đưa vào reranker: số hiệu văn bản + tiêu đề Điều + đầu nội dung Điều."""

    limit = limit or config.RERANK_PASSAGE_CHARS
    head = " — ".join(x for x in (row.get("documentNumber"), row.get("heading")) if x)
    text = (row.get("text") or "").strip()
    return f"{head}\n{text[:limit]}" if head else text[:limit]
