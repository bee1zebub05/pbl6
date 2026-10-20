"""
Log theo PHIÊN hội thoại — một file văn bản cho mỗi thread_id, viết để người
đọc debug: mỗi lượt người dùng nhắn ghi lại từng bước (node) với đầu ra, mọi
lời gọi LLM kèm prompt và output, truy xuất GraphRAG, tool của agent, lỗi kèm
traceback, rồi kết quả cuối của lượt.

    logs/sessions/<YYYY-MM-DD>/<HHMMSS>_<thread_id>.log

Khác `logs/chat.log` (JSON mỗi dòng, gộp mọi phiên, cho máy lọc): file phiên
ghi đầy đủ nội dung nên lớn hơn nhiều; tắt bằng LKG_SESSION_LOG=false.

Cho gọn: prompt hệ thống (2–15 nghìn ký tự, giống nhau mọi lượt) chỉ in đầy đủ
ở lần đầu xuất hiện trong file, các lần sau ghi tham chiếu `#n`; tin nhắn đã in
trong cùng lượt (agent gửi lại cả hội thoại ở mỗi bước) chỉ in một lần.

Mọi hàm ở đây là no-op ngoài một lượt hỏi (CLI chạy template thủ công, backfill
embedding) và không bao giờ làm hỏng lượt hỏi: lỗi ghi file chỉ bị bỏ qua.
"""

from __future__ import annotations

import hashlib
import json
import threading
import traceback
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Sequence

from langchain_core.messages import AIMessage, BaseMessage
from pydantic import BaseModel

from .. import config

_ROLES = {"system": "SYSTEM", "human": "NGƯỜI DÙNG / PROMPT", "ai": "LLM", "tool": "KẾT QUẢ TOOL"}
_INDENT = "    "
_MAX_VALUE_CHARS = 1000  # cắt giá trị chuỗi rất dài trong dòng Cypher (toàn văn Điều)


@dataclass
class _Session:
    path: Path
    turns: int = 0
    system_prompts: dict[str, int] = field(default_factory=dict)  # hash -> số thứ tự #n


@dataclass
class _Turn:
    session: _Session
    printed: set[str] = field(default_factory=set)


_lock = threading.Lock()
_sessions: dict[str, _Session] = {}
_current: ContextVar[_Turn | None] = ContextVar("lkg_session_turn", default=None)


def _session_for(thread_id: str) -> _Session:
    with _lock:
        session = _sessions.get(thread_id)
        if session is None:
            now = datetime.now()
            path = config.SESSION_LOG_DIR / f"{now:%Y-%m-%d}" / f"{now:%H%M%S}_{thread_id}.log"
            session = _sessions[thread_id] = _Session(path)
        return session


def _write(session: _Session, text: str) -> None:
    try:
        with _lock:
            session.path.parent.mkdir(parents=True, exist_ok=True)
            with session.path.open("a", encoding="utf-8") as f:
                f.write(text.rstrip("\n") + "\n\n")
    except OSError:
        pass


def session_path(thread_id: str) -> Path | None:
    """File log của phiên (None nếu phiên chưa ghi gì trong tiến trình này)."""

    session = _sessions.get(thread_id)
    return session.path if session else None


# ------------------------------------------------------------ trình bày

def _indent(text: str, level: int = 1) -> str:
    pad = _INDENT * level
    return "\n".join(pad + line if line else line for line in text.splitlines())


def _short(value: Any) -> Any:
    if isinstance(value, str) and len(value) > _MAX_VALUE_CHARS:
        return value[:_MAX_VALUE_CHARS] + f"… (+{len(value) - _MAX_VALUE_CHARS} ký tự)"
    if isinstance(value, dict):
        return {k: _short(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_short(v) for v in value]
    return value


def render(value: Any) -> str:
    if isinstance(value, BaseMessage):
        return _message_body(value)
    if isinstance(value, BaseModel):
        value = value.model_dump()
    if isinstance(value, str):
        return value
    return json.dumps(_short(value), ensure_ascii=False, indent=2, default=str)


def _message_body(message: BaseMessage) -> str:
    body = message.text if isinstance(message.content, (str, list)) else str(message.content)
    if isinstance(message, AIMessage) and message.tool_calls:
        calls = "\n".join(f"→ gọi tool {c['name']}({json.dumps(c['args'], ensure_ascii=False)})"
                          for c in message.tool_calls)
        body = f"{body}\n{calls}" if body.strip() else calls
    return body.strip()


def _key(message_type: str, body: str) -> str:
    return f"{message_type}:{body}"


def _render_messages(turn: _Turn, messages: Sequence[BaseMessage]) -> str:
    parts: list[str] = []
    repeated = 0
    for m in messages:
        body = _message_body(m)
        if m.type == "system":
            digest = hashlib.sha1(body.encode("utf-8")).hexdigest()
            number = turn.session.system_prompts.get(digest)
            if number is not None:
                parts.append(f"[SYSTEM #{number}] (giống prompt #{number} đã in ở trên, {len(body)} ký tự)")
                continue
            number = turn.session.system_prompts[digest] = len(turn.session.system_prompts) + 1
            parts.append(f"[SYSTEM #{number}] ({len(body)} ký tự)\n{body}")
            continue
        key = _key(m.type, body)
        if key in turn.printed:
            repeated += 1
            continue
        turn.printed.add(key)
        parts.append(f"[{_ROLES.get(m.type, m.type.upper())}]\n{body}")
    if repeated:
        parts.insert(1 if parts and parts[0].startswith("[SYSTEM") else 0,
                     f"(… {repeated} tin nhắn đã in ở trên trong lượt này)")
    return "\n\n".join(parts)


def _empty(value: Any) -> bool:
    return value is None or value == "" or (isinstance(value, (list, tuple, dict, set)) and not value)


def _block(title: str, sections: dict[str, Any]) -> str:
    lines = [f"── {title}"]
    for name, value in sections.items():
        if _empty(value):
            continue
        if isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value):
            lines.append(f"{_INDENT}▸ {name}:")
            lines.append(_indent("\n".join(value), 2))
            continue
        text = render(value)
        if "\n" in text or len(text) > 100:
            lines.append(f"{_INDENT}▸ {name}:")
            lines.append(_indent(text, 2))
        else:
            lines.append(f"{_INDENT}▸ {name}: {text}")
    return "\n".join(lines)


# ------------------------------------------------------------ API

@contextmanager
def turn(thread_id: str, turn_id: str, question: str) -> Iterator[None]:
    """Mở một lượt trong file của phiên; mọi `step`/`llm_call`/`tool` trong khối ghi vào lượt này."""

    if not config.SESSION_LOG_ENABLED:
        yield
        return
    session = _session_for(thread_id)
    with _lock:
        session.turns += 1
        number = session.turns
    if number == 1:
        _write(session, f"PHIÊN {thread_id} — bắt đầu {datetime.now():%Y-%m-%d %H:%M:%S}\n"
                        f"Model: {config.LLM_PROVIDER}/{config.LLM_MODEL}"
                        + (f" (dự phòng {config.LLM_FALLBACK_MODEL})" if config.LLM_FALLBACK_MODEL else ""))
    _write(session, f"{'═' * 100}\nLƯỢT {number} · {datetime.now():%H:%M:%S} · turn {turn_id}\n"
                    f"Người dùng: {question}\n{'═' * 100}")
    token = _current.set(_Turn(session))
    try:
        yield
    finally:
        _current.reset(token)


def step(title: str, **sections: Any) -> None:
    """Một khối: tiêu đề + các mục `tên: giá trị` (giá trị có cấu trúc in JSON thụt dòng)."""

    t = _current.get()
    if t is not None:
        _write(t.session, _block(title, sections))


def llm_call(node: str, *, model: str, ms: float, info: dict[str, Any], messages: Sequence[BaseMessage],
             output: Any = None, error: BaseException | None = None) -> None:
    t = _current.get()
    if t is None:
        return
    head = [f"[{node}] LLM {model}", f"{ms:.0f} ms"]
    if info.get("attempts") is not None:
        head.append(f"{info['attempts']} lần thử")
    if info.get("key"):
        head.append(f"key {info['key']}")
    if isinstance(output, AIMessage):
        t.printed.add(_key("ai", _message_body(output)))
    _write(t.session, _block(" · ".join(head), {
        "Đầu vào": _render_messages(t, messages),
        "Đầu ra": output if error is None else None,
        "LỖI": f"{type(error).__name__}: {error}" if error is not None else None,
    }))


def tool(name: str, content: str, **artifact: Any) -> None:
    """Kết quả một tool của agent — đúng nội dung LLM sẽ đọc ở bước sau (in một lần)."""

    t = _current.get()
    if t is None:
        return
    t.printed.add(_key("tool", content.strip()))
    _write(t.session, _block(f"[agent.tool] {name}", {"Cypher": artifact.get("cypher"), "Kết quả": content}))


def error(node: str, exc: BaseException) -> None:
    step(f"[{node}] LỖI", lỗi=f"{type(exc).__name__}: {exc}",
         traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
