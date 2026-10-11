"""
Bể key Gemini dùng chung cho chatbot (core/chat/adapters/gemini_llm.py) và
embedding (call_embed — GraphRAG và backfill graph_query/article_embeddings.py).

Vì sao cần bể key: free tier của `gemini-3.6-flash` chặn ở **20 request/
NGÀY/project/model** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`),
đo thật ngày 22/09/2026 khi chạy bộ eval chatbot. Một key không đủ cho cả
eval lẫn chat UI.

Đây KHÔNG phải bản copy của `src/vanban/clean/key_pool.py` (bể đó đếm cả
RPM lẫn TPM cho OCR hàng loạt). Chatbot gọi thưa nên chỉ cần ba việc: xoay
vòng, cho key dính 429 nghỉ rồi nhảy sang key khác NGAY thay vì ngồi sleep,
và loại hẳn key đã chết. Toàn bộ vòng lặp đó nằm ở MỘT hàm `call_with_pool()`;
mọi điểm gọi API chỉ truyền vào việc cần làm với một key.

Thread-safe: `core/api/app.py` khai báo handler bằng `def` thường nên
Starlette chạy nó trong threadpool — nhiều câu hỏi có thể vào bể cùng lúc.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Callable, TypeVar

from google import genai
from google.genai import types

from .. import config
from ..observability import log_event

T = TypeVar("T")


class GeminiCallError(Exception):
    pass


# Lỗi tạm thời: đổi key rồi thử tiếp. Khác với lỗi chết hẳn bên dưới.
_TRANSIENT = ("429", "500", "503", "504", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "INTERNAL",
              "DEADLINE_EXCEEDED")

# 401 = service account bị xoá, 403 = project bị từ chối: chết hẳn, loại
# key khỏi bể luôn. Lỗi 429 mang quotaId chứa "PerDay" vẫn kèm `retryDelay`
# chỉ vài chục giây — Google tự báo đây là giới hạn TẠM THỜI dù tên quota
# gây hiểu lầm. Loại vĩnh viễn theo tên quota sẽ khiến cả bể bị loại oan
# sau một đợt burst. Vì vậy ưu tiên đọc `retryDelay` thật trước, chỉ rơi
# xuống _FATAL khi KHÔNG có retryDelay.
_FATAL = ("401", "403", "UNAUTHENTICATED", "PERMISSION_DENIED")

_DEFAULT_COOLDOWN_SECONDS = 45.0  # cho key dính 429 theo phút khi Google không kèm retryDelay
# Ngân sách đếm LƯỢT GỌI API THẬT, không đếm lượt "cả bể đang nghỉ nên phải
# chờ" — trộn hai thứ này thì với bể 17 key, 8 lượt chờ đã tiêu hết ngân
# sách trước khi kịp gọi lại key đầu tiên vừa hết hạn nghỉ.
_MAX_CALLS = 10
_DEADLINE_SECONDS = 90.0  # trần thời gian cho MỘT lời gọi qua bể

_RETRY_DELAY_RE = re.compile(r"retryDelay['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)s")


def _retry_delay_seconds(error_text: str) -> float | None:
    m = _RETRY_DELAY_RE.search(error_text)
    return float(m.group(1)) if m else None


def _error_text(exc: BaseException) -> str:
    """Gộp thông điệp của exception và các nguyên nhân bên trong — LangChain
    bọc lỗi SDK gốc (`raise ... from e`), retryDelay có thể chỉ nằm ở lỗi gốc."""

    parts: list[str] = []
    current: BaseException | None = exc
    while current is not None and len(parts) < 4:
        parts.append(str(current))
        current = current.__cause__
    return " | ".join(parts)


class KeyPool:
    """Xoay vòng key, cho key lỗi nghỉ, loại hẳn key chết."""

    def __init__(self, name: str, keys: list[str]):
        self.name = name
        self._keys = list(keys)
        self._original = list(keys)
        self._cooldown_until: dict[str, float] = {}
        self._clients: dict[str, genai.Client] = {}
        self._next = 0
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._keys)

    @property
    def total(self) -> int:
        return len(self._original)

    def label(self, key: str) -> str:
        """Nhãn che key cho log: vị trí trong bể, không bao giờ là key thật."""
        return f"#{self._original.index(key)}" if key in self._original else "#?"

    def acquire(self) -> tuple[str, genai.Client] | None:
        """Key còn suất kế tiếp. None = mọi key đang nghỉ hoặc bể rỗng."""
        with self._lock:
            if not self._keys:
                return None
            now = time.time()
            for _ in range(len(self._keys)):
                key = self._keys[self._next % len(self._keys)]
                self._next += 1
                if self._cooldown_until.get(key, 0.0) > now:
                    continue
                if key not in self._clients:
                    self._clients[key] = genai.Client(api_key=key)
                return key, self._clients[key]
            return None

    def cooldown(self, key: str, seconds: float, reason: str) -> None:
        with self._lock:
            self._cooldown_until[key] = time.time() + seconds
        log_event("keypool", pool=self.name, key=self.label(key), action="cooldown", seconds=round(seconds, 1),
                  reason=reason[:200])

    def remove(self, key: str, reason: str) -> int:
        """Bỏ hẳn key khỏi bể. -> số key còn lại."""
        with self._lock:
            if key in self._keys:
                self._keys.remove(key)
                self._clients.pop(key, None)
            remaining = len(self._keys)
        log_event("keypool", pool=self.name, key=self.label(key), action="removed", remaining=remaining,
                  reason=reason[:200])
        return remaining

    def seconds_until_available(self) -> float:
        """Còn bao lâu nữa thì có key rảnh. 0 nếu bể rỗng hẳn."""
        with self._lock:
            if not self._keys:
                return 0.0
            now = time.time()
            return max(0.0, min(self._cooldown_until.get(k, 0.0) for k in self._keys) - now)


def call_with_pool(pool: KeyPool, fn: Callable[[str, genai.Client], T], description: str) -> T:
    """Chạy `fn(key, client)` trên một key còn suất; lỗi tạm thời thì cho
    key nghỉ và thử ngay key khác, lỗi chết hẳn thì loại key. Hết ngân sách
    lượt gọi/thời gian hoặc hết key -> GeminiCallError.

    `fn` có thể dùng client của SDK (embedding) hoặc chỉ dùng key (adapter
    LangChain tự giữ một ChatGoogleGenerativeAI cho mỗi key)."""

    last_error = ""
    calls = 0
    deadline = time.time() + _DEADLINE_SECONDS
    while calls < _MAX_CALLS and time.time() < deadline:
        acquired = pool.acquire()
        if acquired is None:
            if len(pool) == 0:
                raise GeminiCallError(
                    f"Cả {pool.total} key đều đã hết hạn mức hoặc bị từ chối. Lỗi cuối: {last_error}"
                )
            # Còn key nhưng đang nghỉ hết -> chờ tới lúc key đầu tiên rảnh.
            # KHÔNG tính vào `calls`: đây là chờ, chưa tốn lượt gọi nào.
            time.sleep(max(0.5, min(pool.seconds_until_available() + 0.5, deadline - time.time())))
            continue

        key, client = acquired
        calls += 1
        try:
            return fn(key, client)
        except GeminiCallError:
            raise
        except Exception as exc:
            last_error = _error_text(exc)
            retry_seconds = _retry_delay_seconds(last_error)
            if retry_seconds is not None:
                pool.cooldown(key, max(retry_seconds, 1.0), last_error)
                continue
            if any(m in last_error for m in _FATAL):
                if pool.remove(key, last_error) == 0:
                    raise GeminiCallError(
                        f"Cả {pool.total} key đều đã hết hạn mức hoặc bị từ chối. Lỗi cuối: {last_error}"
                    ) from exc
                continue
            if any(m in last_error for m in _TRANSIENT):
                pool.cooldown(key, _DEFAULT_COOLDOWN_SECONDS, last_error)
                continue
            raise GeminiCallError(f"{description} thất bại: {last_error}") from exc

    raise GeminiCallError(
        f"{description} thất bại sau {calls} lượt gọi trên bể {len(pool)}/{pool.total} key "
        f"(trần {_MAX_CALLS} lượt / {_DEADLINE_SECONDS:.0f}s). Lỗi cuối: {last_error}"
    )


def _load_keys() -> list[str]:
    keys = config.gemini_keys()
    if not keys:
        raise GeminiCallError(
            "Chưa cấu hình key cho chatbot. Điền LKG_GEMINI_API_KEY_0 (hoặc "
            "GEMINI_API_KEY_0 / GEMMA_API_KEY_0 — dùng chung bể, xem "
            "config.gemini_keys()) trong .env ở gốc repo."
        )
    return keys


_pools: dict[str, KeyPool] = {}
_pools_lock = threading.Lock()


def get_pool(name: str) -> KeyPool:
    """Một bể riêng cho mỗi loại lời gọi ("generate", "embed") dù cùng danh
    sách key: quota Gemini tính theo model, key hết quota generate_content
    chưa chắc hết quota embed_content. Dùng chung một bể thì key bị loại vì
    generate sẽ kéo theo bị loại oan ở embed (đã gặp trên thực tế)."""

    with _pools_lock:
        if name not in _pools:
            _pools[name] = KeyPool(name, _load_keys())
        return _pools[name]


def call_embed(texts: list[str], task_type: str, output_dimensionality: int) -> list[list[float]]:
    """Embed một danh sách text qua bể "embed" — một request cho cả danh sách,
    trả về đúng thứ tự.

    task_type: 'RETRIEVAL_DOCUMENT' lúc backfill Article, 'RETRIEVAL_QUERY'
    lúc embed câu hỏi người dùng (embedding bất đối xứng)."""

    embed_config = types.EmbedContentConfig(task_type=task_type, output_dimensionality=output_dimensionality)

    def embed(_key: str, client: genai.Client) -> list[list[float]]:
        response = client.models.embed_content(model=config.EMBED_MODEL, contents=texts, config=embed_config)
        if not response.embeddings:
            raise GeminiCallError("Gemini embed trả về rỗng (có thể bị chặn bởi safety filter)")
        return [e.values for e in response.embeddings]

    return call_with_pool(get_pool("embed"), embed, "Gọi Gemini embed")
