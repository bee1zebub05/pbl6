"""
Gemini client cho core/nlq/ — một hàm gọi structured JSON output, đứng trên
một BỂ KEY xoay vòng.

Vì sao cần bể key (trước đây module này cố tình chỉ dùng 1 key): free tier
của `gemini-3.6-flash` chặn ở **20 request/NGÀY/project/model**
(`GenerateRequestsPerDayPerProjectPerModel-FreeTier`), đo thật ngày
22/09/2026 khi chạy `run.py lkg nlq-eval`. Bộ gold có 19 câu, mỗi câu 1-2
lần gọi -> cháy quota ngay giữa lượt chạy đầu tiên, 3 câu cuối FAIL vì 429
chứ không phải vì sai logic. Một key là không đủ cho cả eval lẫn chat UI.

Đây KHÔNG phải bản copy của `src/vanban/clean/key_pool.py` (bể đó đếm cả
RPM lẫn TPM cho OCR hàng loạt, hàng nghìn lượt gọi). NLQ gọi thưa nên chỉ
cần đúng ba việc: xoay vòng, cho key dính 429 nghỉ rồi nhảy sang key khác
NGAY thay vì ngồi sleep, và loại hẳn key đã chết.

Thread-safe: `core/api/app.py` khai báo handler bằng `def` thường nên
Starlette chạy nó trong threadpool — nhiều câu hỏi có thể vào bể cùng lúc.
"""

from __future__ import annotations

import json
import re
import threading
import time

from google import genai
from google.genai import types

from .. import config


class GeminiCallError(Exception):
    pass


# Lỗi tạm thời: đổi key rồi thử tiếp. Khác với lỗi chết hẳn bên dưới.
_TRANSIENT = ("429", "503", "500", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "INTERNAL")

# 401 = service account bị xoá, 403 = project bị từ chối: chết hẳn, loại
# key khỏi bể luôn. KHÔNG còn "PerDay"/"PerProjectPerDay" ở đây — xác nhận
# thật qua quan sát trực tiếp (không suy đoán, xem _retry_delay_giay()):
# lỗi 429 mang quotaId chứa "PerDay" (VD
# "EmbedContentRequestsPerDayPerUserPerProjectPerModel-FreeTier") vẫn kèm
# `retryDelay` chỉ vài chục giây — Google tự báo đây là giới hạn TẠM THỜI
# (burst) dù tên quota gây hiểu lầm là "cả ngày". Từng loại vĩnh viễn theo
# tên quota khiến cả bể bị loại oan chỉ sau ~1 đợt burst, phải kill/restart
# CLI thủ công nhiều lần khi backfill embedding. Giờ ưu tiên đọc
# `retryDelay` thật trong response trước, chỉ rơi xuống _CHET_HAN khi
# KHÔNG có retryDelay (VD lỗi auth/quyền truy cập thật sự không có cơ chế
# tự hồi phục).
_CHET_HAN = ("401", "403", "UNAUTHENTICATED", "PERMISSION_DENIED")

_NGHI_MAC_DINH = 45.0      # giây, cho key dính 429 theo phút (khi Google không kèm retryDelay)
# Ngân sách đếm LƯỢT GỌI API THẬT, không đếm lượt "cả bể đang nghỉ nên phải
# chờ" — trộn hai thứ này vào một biến thì với bể 17 key, 8 lượt chờ đã tiêu
# hết ngân sách trước khi kịp gọi lại key đầu tiên vừa hết hạn nghỉ.
_MAX_GOI = 10
_HAN_GIAY = 90.0           # trần thời gian cho MỘT lời gọi call_json()

_RETRY_DELAY_RE = re.compile(r"retryDelay['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)s")


def _retry_delay_giay(loi_text: str) -> float | None:
    """Đọc `retryDelay` (giây) Google trả kèm lỗi 429/RESOURCE_EXHAUSTED,
    nếu có — đây là con số THẬT từ phía Google, đáng tin hơn việc đoán
    "chết hẳn" qua tên quota (xem docstring _CHET_HAN)."""
    m = _RETRY_DELAY_RE.search(loi_text)
    return float(m.group(1)) if m else None


class _BeKey:
    """Xoay vòng key, cho key lỗi nghỉ, loại hẳn key chết."""

    def __init__(self, keys: list[str]):
        self._keys = list(keys)
        self._goc = list(keys)
        self._nghi_toi: dict[str, float] = {}
        self._client: dict[str, genai.Client] = {}
        self._i = 0
        self._khoa = threading.Lock()

    def __len__(self) -> int:
        with self._khoa:
            return len(self._keys)

    @property
    def tong(self) -> int:
        return len(self._goc)

    def lay(self) -> tuple[str, genai.Client] | None:
        """Key còn suất gần nhất. None = mọi key đang nghỉ hoặc bể rỗng."""
        with self._khoa:
            if not self._keys:
                return None
            gio = time.time()
            for _ in range(len(self._keys)):
                k = self._keys[self._i % len(self._keys)]
                self._i += 1
                if self._nghi_toi.get(k, 0.0) > gio:
                    continue
                if k not in self._client:
                    self._client[k] = genai.Client(api_key=k)
                return k, self._client[k]
            return None

    def cho_nghi(self, key: str, giay: float = _NGHI_MAC_DINH) -> None:
        with self._khoa:
            self._nghi_toi[key] = time.time() + giay

    def loai(self, key: str) -> int:
        """Bỏ hẳn key khỏi bể. -> số key còn lại."""
        with self._khoa:
            if key in self._keys:
                self._keys.remove(key)
                self._client.pop(key, None)
            return len(self._keys)

    def cho_bao_lau(self) -> float:
        """Còn bao lâu nữa thì có key rảnh. 0 nếu bể rỗng hẳn."""
        with self._khoa:
            if not self._keys:
                return 0.0
            gio = time.time()
            return max(0.0, min(self._nghi_toi.get(k, 0.0) for k in self._keys) - gio)


_be: _BeKey | None = None
_be_embed: _BeKey | None = None
_khoa_be = threading.Lock()


def _load_keys() -> list[str]:
    keys = config.nlq_gemini_keys()
    if not keys:
        raise GeminiCallError(
            "Chưa cấu hình key cho NLQ. Điền LKG_GEMINI_API_KEY_0 (hoặc "
            "GEMINI_API_KEY_0 / GEMMA_API_KEY_0 — dùng chung bể, xem "
            "config.nlq_gemini_keys()) trong .env ở gốc repo."
        )
    return keys


def _get_be() -> _BeKey:
    global _be
    with _khoa_be:
        if _be is None:
            _be = _BeKey(_load_keys())
        return _be


def _get_be_embed() -> _BeKey:
    """Bể key RIÊNG cho embed_content() — KHÔNG dùng chung _get_be() dù
    cùng đọc từ cùng danh sách key. Lý do: quota Gemini tính theo
    PerProjectPerDayPerModel — generate_content (gemini-3.6-flash) và
    embed_content (model khác, VD gemini-embedding-001) nhiều khả năng có
    quota tách biệt theo model dù chung project/key. Nếu dùng chung 1
    _BeKey, 1 key bị loại vì hết quota generate_content sẽ kéo theo bị
    loại luôn ở embed_content — dù embed_content có thể còn nguyên quota.
    Xác nhận thật (không suy đoán): quan sát trực tiếp phiên làm việc —
    Stage A hết quota loại cả 4 key khỏi bể chung, khiến retrieval báo lỗi
    'hết quota' NGAY LẬP TỨC mà chưa từng thật sự gọi embed_content — tách
    bể để loại trừ khả năng chặn nhầm này."""

    global _be_embed
    with _khoa_be:
        if _be_embed is None:
            _be_embed = _BeKey(_load_keys())
        return _be_embed


def so_key() -> tuple[int, int]:
    """-> (số key còn sống, tổng số key nạp ban đầu). Cho CLI in ra."""
    be = _get_be()
    return len(be), be.tong


def call_json(prompt: str, response_schema: dict, temperature: float = 0.0) -> dict:
    """Gọi Gemini, ép output JSON đúng response_schema (dict dạng OpenAPI
    subset — xem google.genai.types.Schema). Raise GeminiCallError nếu hết
    key, lỗi gọi API, hoặc output không parse được JSON."""

    be = _get_be()
    cau_hinh = types.GenerateContentConfig(
        temperature=temperature,
        response_mime_type="application/json",
        response_schema=response_schema,
    )

    loi_cuoi = ""
    n_goi = 0
    han = time.time() + _HAN_GIAY
    while n_goi < _MAX_GOI and time.time() < han:
        lay = be.lay()
        if lay is None:
            if len(be) == 0:
                raise GeminiCallError(
                    f"Cả {be.tong} key đều đã hết hạn mức ngày hoặc bị từ chối. "
                    f"Lỗi cuối: {loi_cuoi}"
                )
            # Còn key nhưng đang nghỉ hết -> chờ tới lúc key đầu tiên rảnh.
            # KHÔNG tính vào n_goi: đây là chờ, chưa tốn lượt gọi nào.
            time.sleep(max(0.5, min(be.cho_bao_lau() + 0.5, han - time.time())))
            continue

        key, client = lay
        n_goi += 1
        try:
            response = client.models.generate_content(
                model=config.NLQ_GEMINI_MODEL, contents=prompt, config=cau_hinh
            )
        except Exception as exc:
            loi_cuoi = str(exc)
            retry_giay = _retry_delay_giay(loi_cuoi)
            if retry_giay is not None:
                # Google tự báo đây là giới hạn TẠM THỜI (kèm retryDelay
                # thật) — dù thông điệp có thể chứa tên quota gây hiểu lầm
                # "PerDay", KHÔNG loại vĩnh viễn, chỉ cho nghỉ đúng số giây
                # Google yêu cầu (xem docstring _CHET_HAN).
                be.cho_nghi(key, max(retry_giay, 1.0))
                continue
            if any(m in loi_cuoi for m in _CHET_HAN):
                con = be.loai(key)
                if con == 0:
                    raise GeminiCallError(
                        f"Cả {be.tong} key đều đã hết hạn mức ngày hoặc bị từ "
                        f"chối. Lỗi cuối: {loi_cuoi}"
                    ) from exc
                continue
            if any(m in loi_cuoi for m in _TRANSIENT):
                be.cho_nghi(key)
                continue
            raise GeminiCallError(f"Gọi Gemini thất bại: {exc}") from exc

        text = response.text
        if not text:
            raise GeminiCallError("Gemini trả về rỗng (có thể bị chặn bởi safety filter)")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise GeminiCallError(
                f"Gemini trả JSON không hợp lệ: {exc}\nRaw: {text[:500]}"
            ) from exc

    raise GeminiCallError(
        f"Gọi Gemini thất bại sau {n_goi} lượt gọi trên bể {len(be)}/{be.tong} key "
        f"(trần {_MAX_GOI} lượt / {_HAN_GIAY:.0f}s). Lỗi cuối: {loi_cuoi}"
    )


def call_embed(texts: list[str], task_type: str, output_dimensionality: int) -> list[list[float]]:
    """Gọi Gemini embed_content() cho retrieval ngữ nghĩa (core/nlq/retrieval.py,
    core/nlq/embed_articles.py) — dùng BỂ KEY RIÊNG (_get_be_embed(), KHÔNG
    dùng chung _get_be() của call_json()) vì quota Gemini tính theo model,
    key hết quota generate_content không có nghĩa hết quota embed_content
    (xem docstring _get_be_embed()). Cùng cơ chế phân loại lỗi transient/
    chết hẳn, chỉ khác điểm gọi API và cách đọc response. `contents` nhận
    cả danh sách -> 1 lần gọi embed nhiều text, trả về đúng thứ tự (giảm
    số request thật gửi đi).

    task_type: 'RETRIEVAL_DOCUMENT' lúc backfill Article, 'RETRIEVAL_QUERY'
    lúc embed câu hỏi người dùng — embedding bất đối xứng, Gemini khuyến nghị
    dùng đúng loại cho từng phía để tăng độ chính xác retrieval."""

    be = _get_be_embed()
    cau_hinh = types.EmbedContentConfig(
        task_type=task_type,
        output_dimensionality=output_dimensionality,
    )

    loi_cuoi = ""
    n_goi = 0
    han = time.time() + _HAN_GIAY
    while n_goi < _MAX_GOI and time.time() < han:
        lay = be.lay()
        if lay is None:
            if len(be) == 0:
                raise GeminiCallError(
                    f"Cả {be.tong} key đều đã hết hạn mức ngày hoặc bị từ chối. "
                    f"Lỗi cuối: {loi_cuoi}"
                )
            time.sleep(max(0.5, min(be.cho_bao_lau() + 0.5, han - time.time())))
            continue

        key, client = lay
        n_goi += 1
        try:
            response = client.models.embed_content(
                model=config.NLQ_EMBED_MODEL, contents=texts, config=cau_hinh
            )
        except Exception as exc:
            loi_cuoi = str(exc)
            retry_giay = _retry_delay_giay(loi_cuoi)
            if retry_giay is not None:
                be.cho_nghi(key, max(retry_giay, 1.0))
                continue
            if any(m in loi_cuoi for m in _CHET_HAN):
                con = be.loai(key)
                if con == 0:
                    raise GeminiCallError(
                        f"Cả {be.tong} key đều đã hết hạn mức ngày hoặc bị từ "
                        f"chối. Lỗi cuối: {loi_cuoi}"
                    ) from exc
                continue
            if any(m in loi_cuoi for m in _TRANSIENT):
                be.cho_nghi(key)
                continue
            raise GeminiCallError(f"Gọi Gemini embed thất bại: {exc}") from exc

        if not response.embeddings:
            raise GeminiCallError("Gemini embed trả về rỗng (có thể bị chặn bởi safety filter)")
        return [e.values for e in response.embeddings]

    raise GeminiCallError(
        f"Gọi Gemini embed thất bại sau {n_goi} lượt gọi trên bể {len(be)}/{be.tong} key "
        f"(trần {_MAX_GOI} lượt / {_HAN_GIAY:.0f}s). Lỗi cuối: {loi_cuoi}"
    )
