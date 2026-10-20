"""
Quan sát chatbot: log cục bộ có cấu trúc + LangSmith tracing.

- Log: logger `lkg.chat`, mỗi dòng một JSON, ra console và `logs/chat.log`
  (xoay vòng 5 MB x 3). Mọi nơi chỉ gọi `log_event(stage, **fields)` — hàm
  này tự gắn `thread_id`/`turn_id` của lượt hỏi đang chạy (contextvars), nên
  grep một `turn_id` là ra trọn chuỗi intent -> route -> cypher -> answer.
- LangSmith: bật khi `.env` có `LANGSMITH_API_KEY` (và `LANGSMITH_TRACING`
  không phải "false"). Node LangGraph, lời gọi LLM, tool tự lên trace qua
  callback của LangChain; phần thuần Python (Cypher, resolve, chọn template,
  retrieval) bọc `traceable` ở đây để vẫn hiện thành run con.

Không bao giờ log/trace API key — chỉ ghi vị trí key trong bể (`#2`).
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from typing import Any, Iterator

from langsmith import traceable as _ls_traceable
from langsmith.run_helpers import get_current_run_tree

from . import config

LOGGER_NAME = "lkg.chat"

_thread_id: ContextVar[str | None] = ContextVar("lkg_thread_id", default=None)
_turn_id: ContextVar[str | None] = ContextVar("lkg_turn_id", default=None)
_llm_calls: ContextVar[list[int] | None] = ContextVar("lkg_llm_calls", default=None)
_turn_deadline: ContextVar[float | None] = ContextVar("lkg_turn_deadline", default=None)

_configured = False


def _ensure_tracing_env() -> None:
    """Có key mà chưa khai LANGSMITH_TRACING thì bật mặc định; không có key
    thì tắt hẳn để SDK không cố gửi trace rồi báo lỗi."""

    if os.getenv("LANGSMITH_API_KEY"):
        os.environ.setdefault("LANGSMITH_TRACING", "true")
        os.environ.setdefault("LANGSMITH_PROJECT", "pbl6-legal-chatbot")
    else:
        os.environ["LANGSMITH_TRACING"] = "false"


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            **getattr(record, "fields", {"msg": record.getMessage()}),
        }
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging() -> logging.Logger:
    """Idempotent — gọi lại nhiều lần (API, CLI, test) chỉ cấu hình một lần."""

    global _configured
    logger = logging.getLogger(LOGGER_NAME)
    if _configured:
        return logger

    _ensure_tracing_env()
    # SDK google-genai log INFO mỗi lần gọi; riêng `google_genai.models` còn
    # cảnh báo "AFC not recommended" một lần mỗi tiến trình khi LangChain
    # truyền tool — vô hại (LangChain tự xử lý tool call, không dùng AFC).
    logging.getLogger("google_genai").setLevel(logging.WARNING)
    logging.getLogger("google_genai.models").setLevel(logging.ERROR)
    logger.setLevel(config.LOG_LEVEL)
    logger.propagate = False
    formatter = _JsonFormatter()

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        config.LOG_DIR / "chat.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    _configured = True
    return logger


def log_event(stage: str, level: int = logging.INFO, **fields: Any) -> None:
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.isEnabledFor(level):
        return
    record_fields = {"stage": stage, "thread_id": _thread_id.get(), "turn_id": _turn_id.get(), **fields}
    logger.log(level, stage, extra={"fields": record_fields})


def debug_enabled() -> bool:
    return logging.getLogger(LOGGER_NAME).isEnabledFor(logging.DEBUG)


@contextmanager
def turn_context(thread_id: str, deadline_seconds: float | None = None) -> Iterator[str]:
    """Gắn thread_id/turn_id, bộ đếm lượt gọi LLM và hạn chót của một lượt hỏi
    (`deadline_seconds` kể từ lúc vào; None = không giới hạn)."""

    turn_id = uuid.uuid4().hex[:12]
    deadline = time.time() + deadline_seconds if deadline_seconds else None
    tokens = (_thread_id.set(thread_id), _turn_id.set(turn_id), _llm_calls.set([0]), _turn_deadline.set(deadline))
    try:
        yield turn_id
    finally:
        _thread_id.reset(tokens[0])
        _turn_id.reset(tokens[1])
        _llm_calls.reset(tokens[2])
        _turn_deadline.reset(tokens[3])


def turn_deadline() -> float | None:
    """Thời điểm (epoch giây) lượt hỏi hiện tại phải xong; None khi ngoài lượt hỏi
    (backfill embedding, CLI template thủ công) hoặc không giới hạn."""

    return _turn_deadline.get()


def count_llm_call() -> None:
    counter = _llm_calls.get()
    if counter is not None:
        counter[0] += 1


def llm_calls_in_turn() -> int:
    counter = _llm_calls.get()
    return counter[0] if counter is not None else 0


def _drop_self(inputs: dict) -> dict:
    """Method được bọc traceable có `self` trong inputs — bỏ đi, chỉ giữ tham số thật."""

    return {k: v for k, v in inputs.items() if k != "self"}


def traceable(*, name: str, run_type: str = "chain", process_outputs=None):
    """Bọc hàm thuần Python thành run con trên LangSmith; tracing tắt thì
    langsmith tự bỏ qua (không gửi gì, chi phí gần như bằng 0).
    `process_outputs` rút gọn output trước khi gửi (vd chỉ 20 dòng đầu)."""

    kwargs = {"name": name, "run_type": run_type, "process_inputs": _drop_self}
    if process_outputs is not None:
        kwargs["process_outputs"] = process_outputs
    return _ls_traceable(**kwargs)


def current_trace_id() -> str | None:
    run = get_current_run_tree()
    return str(run.trace_id) if run is not None else None


def annotate_current_trace(*, tags: list[str] | None = None, metadata: dict | None = None) -> None:
    run = get_current_run_tree()
    if run is None:
        return
    if tags:
        run.add_tags([t for t in tags if t])
    if metadata:
        run.add_metadata(metadata)


def preview_rows(rows: list[dict], n: int) -> list[dict]:
    """Rút gọn dòng kết quả cho log/trace — cắt chuỗi dài (toàn văn Điều)."""

    def short(v: Any) -> Any:
        return v[:200] + "…" if isinstance(v, str) and len(v) > 200 else v

    return [{k: short(v) for k, v in r.items()} for r in rows[:n]]
