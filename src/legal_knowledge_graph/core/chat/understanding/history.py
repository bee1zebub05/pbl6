"""Cắt và trình bày lịch sử hội thoại cho prompt — một chỗ duy nhất."""

from __future__ import annotations

from typing import Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

_MAX_CHARS_PER_MESSAGE = 600


def recent_turns(history: Sequence[BaseMessage], window: int) -> list[BaseMessage]:
    """`window` tin nhắn người dùng/bot gần nhất (bỏ tin nhắn tool/system)."""

    turns = [m for m in history if isinstance(m, (HumanMessage, AIMessage))]
    return turns[-window:] if window > 0 else []


def format_history(history: Sequence[BaseMessage], window: int) -> str:
    lines = []
    for m in recent_turns(history, window):
        role = "Người dùng" if isinstance(m, HumanMessage) else "Bot"
        text = m.text.strip()
        if len(text) > _MAX_CHARS_PER_MESSAGE:
            text = text[:_MAX_CHARS_PER_MESSAGE] + "…"
        lines.append(f"{role}: {text}")
    return "\n".join(lines) if lines else "(chưa có)"
