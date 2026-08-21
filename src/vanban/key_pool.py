"""
Bể API key Gemini, dùng chung cho nhiều luồng.

Free tier của Gemini/Gemma giới hạn theo **từng key** (mỗi phút và mỗi ngày),
nên có nhiều key thì cách nhanh nhất là trải request đều ra tất cả các key,
key nào bị 429 thì cho nghỉ và đẩy việc sang key còn khoẻ.

Ba trạng thái của một key:

    khoẻ    -> gọi được ngay
    nghỉ    -> vừa dính 429, tạm khoá đến `cool_until`
    chết    -> key sai / bị thu hồi / hết hạn, loại vĩnh viễn khỏi vòng xoay

`acquire()` luôn trả về key khoẻ đang rảnh nhất. Nếu mọi key đều đang nghỉ,
luồng gọi sẽ ngủ đúng đến lúc key sớm nhất tỉnh dậy chứ không quay vòng đốt CPU.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field

from . import config


class NoKeyAvailable(RuntimeError):
    """Mọi key đều đã chết — không còn gì để thử."""


_RETRY_DELAY = re.compile(r"'?retryDelay'?\s*[:=]\s*'?(\d+(?:\.\d+)?)s", re.I)

# Dấu hiệu key hỏng hẳn, thử lại bao nhiêu lần cũng vậy.
_DEAD_HINTS = (
    "api_key_invalid",
    "api key not valid",
    "api key expired",
    "invalid api key",
    "permission_denied",
    "unauthenticated",
    "consumer_suspended",
    "has been suspended",
    "billing",
)

# Dấu hiệu hết quota NGÀY (khác với chạm trần mỗi phút).
_DAILY_HINTS = ("perday", "per day", "daily limit", "requests per day")


def classify_error(exc: Exception) -> tuple[str, float | None]:
    """
    Phân loại lỗi thành ("rate" | "dead" | "transient" | "other", giây nghỉ).

    Chỉ nhìn mã HTTP thôi là chưa đủ: 400 vừa có thể là "key sai" vừa có thể là
    "model không nhận tham số này" — hai chuyện phải xử lý ngược nhau, nên ta
    đọc thêm nội dung thông báo.
    """

    code = getattr(exc, "code", None)
    text = f"{getattr(exc, 'status', '')} {getattr(exc, 'message', '')} {exc}".lower()

    if code == 429 or "resource_exhausted" in text or "rate limit" in text:
        match = _RETRY_DELAY.search(text)

        if match:
            delay = min(float(match.group(1)) + 1, config.GEMINI_KEY_COOLDOWN_MAX)
        elif any(hint in text for hint in _DAILY_HINTS):
            delay = config.GEMINI_KEY_COOLDOWN_DAILY
        else:
            delay = config.GEMINI_KEY_COOLDOWN

        return "rate", delay

    if code in (401, 403) or any(hint in text for hint in _DEAD_HINTS):
        return "dead", None

    if code is not None and 500 <= code < 600:
        return "transient", None

    if "deadline" in text or "timeout" in text or "unavailable" in text:
        return "transient", None

    return "other", None


@dataclass
class KeyState:
    label: str
    key: str

    inflight: int = 0
    last_used: float = 0.0
    calls: int = 0
    rate_hits: int = 0

    cool_until: float = 0.0
    dead: bool = False
    dead_reason: str = ""

    client: object | None = field(default=None, repr=False)

    def masked(self) -> str:
        return f"{self.key[:6]}…{self.key[-4:]}" if len(self.key) > 12 else "…"


class KeyPool:
    """Chọn key theo kiểu 'ai rảnh nhất thì đi' — trải đều tải lên mọi key."""

    def __init__(
        self,
        keys: list[tuple[str, str]] | None = None,
        *,
        quiet=False,
        max_inflight: int | None = None,
    ):
        keys = keys if keys is not None else config.GEMINI_API_KEYS

        if not keys:
            raise NoKeyAvailable(
                "Chưa có API key Gemini nào. Mở .env và điền GEMINI_API_KEY_0=..., "
                "GEMINI_API_KEY_1=... (xem .env.example)."
            )

        self.states = [KeyState(label=label, key=key) for label, key in keys]
        self.quiet = quiet
        self.max_inflight = max(1, max_inflight or config.GEMINI_MAX_INFLIGHT_PER_KEY)

        self._lock = threading.Lock()
        self._wake = threading.Condition(self._lock)

    # --------------------------------------------------------
    # Vòng đời
    # --------------------------------------------------------

    def __len__(self) -> int:
        return len(self.states)

    def _say(self, message: str) -> None:
        if not self.quiet:
            print(f"    [key] {message}", flush=True)

    def acquire(self, timeout: float | None = None) -> KeyState:
        """
        Mượn một key khoẻ. Chặn cho đến khi có key rảnh hoặc hết `timeout`.

        Ném NoKeyAvailable nếu mọi key đã chết (chờ thêm cũng vô ích).
        """

        deadline = None if timeout is None else time.time() + timeout

        with self._wake:
            while True:
                now = time.time()
                alive = [state for state in self.states if not state.dead]

                if not alive:
                    raise NoKeyAvailable(
                        "Tất cả API key đều hỏng: "
                        + "; ".join(
                            f"{s.label} ({s.dead_reason})" for s in self.states
                        )
                    )

                awake = [state for state in alive if state.cool_until <= now]
                ready = [s for s in awake if s.inflight < self.max_inflight]

                if ready:
                    # Ưu tiên key đang gánh ít request nhất, rồi đến key lâu
                    # chưa dùng — hai tiêu chí này cùng nhau giữ tải cân bằng
                    # dù số luồng nhiều hay ít hơn số key.
                    chosen = min(ready, key=lambda s: (s.inflight, s.last_used))
                    chosen.inflight += 1
                    chosen.last_used = now
                    chosen.calls += 1

                    return chosen

                if awake:
                    # Có key tỉnh nhưng đều đã chật chỗ -> chờ một lượt xong.
                    # release()/report_*() sẽ đánh thức; 1s chỉ là lưới an toàn.
                    wait = 1.0
                else:
                    # Mọi key đang nghỉ -> ngủ đúng đến lúc key sớm nhất tỉnh.
                    wait = max(min(s.cool_until for s in alive) - now, 0.05)

                if deadline is not None:
                    left = deadline - now

                    if left <= 0:
                        why = "đều chật chỗ" if awake else "đều đang nghỉ"
                        raise TimeoutError(f"Chờ {timeout:.0f}s mà mọi key {why}.")

                    wait = min(wait, left)

                self._wake.wait(wait)

    def release(self, state: KeyState) -> None:
        with self._wake:
            state.inflight = max(0, state.inflight - 1)
            self._wake.notify()

    # --------------------------------------------------------
    # Báo kết quả
    # --------------------------------------------------------

    def report_ok(self, state: KeyState) -> None:
        self.release(state)

    def report_rate_limit(self, state: KeyState, delay: float | None) -> None:
        delay = delay or config.GEMINI_KEY_COOLDOWN

        with self._wake:
            state.inflight = max(0, state.inflight - 1)
            state.rate_hits += 1
            state.cool_until = time.time() + delay
            alive = sum(
                1
                for s in self.states
                if not s.dead and s.cool_until <= time.time()
            )
            self._wake.notify_all()

        self._say(
            f"{state.label} chạm giới hạn -> nghỉ {delay:.0f}s "
            f"(còn {alive} key sẵn sàng)"
        )

    def report_dead(self, state: KeyState, reason: str) -> None:
        with self._wake:
            state.inflight = max(0, state.inflight - 1)

            # Nhiều luồng cùng dùng một key thì cùng ăn một lỗi — chỉ luồng đầu
            # tiên mới báo, không thì log lặp lại y hệt.
            first = not state.dead

            state.dead = True
            state.dead_reason = reason[:120]
            alive = sum(1 for s in self.states if not s.dead)
            self._wake.notify_all()

        if first:
            self._say(f"{state.label} ({state.masked()}) HỎNG: {reason[:100]}")
            self._say(f"còn {alive}/{len(self.states)} key dùng được")

    def report_transient(self, state: KeyState) -> None:
        """Lỗi phía server, không phải tại key — trả key về nguyên vẹn."""

        self.release(state)

    # --------------------------------------------------------
    # Báo cáo
    # --------------------------------------------------------

    def client_for(self, state: KeyState):
        """Client của genai gắn với một key, tạo một lần rồi dùng lại."""

        if state.client is None:
            from google import genai

            with self._lock:
                if state.client is None:
                    state.client = genai.Client(api_key=state.key)

        return state.client

    def alive(self) -> int:
        return sum(1 for state in self.states if not state.dead)

    def summary(self) -> str:
        now = time.time()
        parts = []

        for state in self.states:
            if state.dead:
                mark = "chết"
            elif state.cool_until > now:
                mark = f"nghỉ {state.cool_until - now:.0f}s"
            else:
                mark = "khoẻ"

            parts.append(f"{state.label}: {state.calls} lượt, {mark}")

        return " | ".join(parts)

    def capacity(self) -> int:
        """Số request tối đa có thể bay cùng lúc qua các key còn sống."""

        return self.alive() * self.max_inflight
