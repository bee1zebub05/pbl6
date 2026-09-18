"""
Hiệu đính text OCR bằng Gemini.

OCR tiếng Việt hay sai theo vài kiểu rất đặc trưng, ví dụ trong một văn bản
thật đã chạy thử:

    "16 chức"      -> "tổ chức"
    "Gido dục"     -> "Giáo dục"
    "ngdn sách"    -> "ngân sách"
    "vé việc"      -> "về việc"
    "QUYET ĐỊNH"   -> "QUYẾT ĐỊNH"
    "Quyết dmh"    -> "Quyết định"
    "Đà MỄng"      -> "Đà Nẵng"

Đây là lỗi mất/sai dấu và nhận nhầm mặt chữ — mô hình ngôn ngữ sửa rất tốt
nhờ ngữ cảnh, miễn là ta ràng buộc chặt: chỉ sửa, không viết lại, không tóm tắt.
"""

from __future__ import annotations

import random
import re
import threading
import time

from ..core import config
from .key_pool import KeyPool, NoKeyAvailable, classify_error
from .pdf_text import PAGE_MARKER

_PAGE_SPLIT = re.compile(r"\n*-{5} \[Trang (\d+)\] -{5}\n*")
_FENCE = re.compile(r"^```[a-zA-Z]*\n(.*)\n```$", re.S)

SYSTEM_PROMPT = """\
Bạn là biên tập viên hiệu đính văn bản quy phạm pháp luật Việt Nam.

Đầu vào là text được trích từ OCR một văn bản pháp quy (nghị định, thông tư,
quyết định, quy chế...). OCR thường mắc các lỗi sau:
- Mất dấu hoặc sai dấu tiếng Việt: "vé việc" -> "về việc", "ngdn sách" -> "ngân sách".
- Nhận nhầm mặt chữ giống nhau: "16 chức" -> "tổ chức", "Gido dục" -> "Giáo dục",
  "dmh" -> "định", "0P" -> "QĐ", "NO-HĐĐH" -> "NQ-HĐĐH", "l" / "1" / "I" lẫn lộn.
- Dính chữ, tách chữ sai, thiếu khoảng trắng.
- Chữ trong con dấu / chữ ký chèn ngang vào giữa câu.

NHIỆM VỤ: sửa các lỗi OCR đó và trả về văn bản đã sửa.

QUY TẮC BẮT BUỘC:
1. CHỈ sửa lỗi OCR. TUYỆT ĐỐI không tóm tắt, không diễn giải, không rút gọn,
   không thêm nội dung mới, không dịch.
2. Giữ nguyên toàn bộ cấu trúc: thứ tự dòng, xuống dòng, Điều/Khoản/Điểm,
   đánh số, tiêu đề, bảng biểu.
3. Giữ nguyên các dòng đánh dấu trang dạng `----- [Trang N] -----`.
4. Số hiệu văn bản, ngày tháng, số tiền, tên riêng: chỉ sửa khi chắc chắn là
   lỗi OCR dựa vào ngữ cảnh. Nếu không chắc thì GIỮ NGUYÊN.
4b. Dòng "Số: ... /QĐ-..." và "ngày ... tháng ... năm ..." ở ĐẦU văn bản đã
   được đối chiếu với dữ liệu gốc trước khi đưa vào đây — chúng ĐÚNG. Chép
   lại y nguyên, tuyệt đối không "sửa" cho khớp với phần còn lại.
5. Đoạn nào là rác OCR không thể hiểu (chữ trong con dấu, watermark) thì giữ
   nguyên, đừng bịa ra nội dung.
6. Đầu ra chỉ chứa văn bản đã hiệu đính. Không lời dẫn, không giải thích,
   không bọc trong ``` .
"""

USER_TEMPLATE = """\
Văn bản: {title}
Số hiệu: {so_hieu}
Lĩnh vực: {category}

Hiệu đính phần text OCR dưới đây (đây là phần {part}/{total} của văn bản):

<<<OCR
{text}
OCR>>>
"""


class GeminiError(RuntimeError):
    pass


class RecitationError(GeminiError):
    """Model CHẶN đầu ra vì nhận ra nội dung trùng dữ liệu huấn luyện.

    Đây không phải lỗi tạm thời, cũng không phải lỗi cấu hình. Văn bản quy phạm
    pháp luật công khai rất dễ trùng, nên gặp thường xuyên trên kho này.

    Phân biệt với các kiểu rỗng khác là việc bắt buộc, vì cách chữa NGƯỢC nhau:

        rỗng do thinking tiêu hết token -> hạ cấu hình (tắt thinking)
        rỗng do RECITATION             -> hạ cấu hình VÔ ÍCH, phải CHIA NHỎ

    Gộp chung hai cái này gây hai thiệt hại cùng lúc: khối văn bản bị bỏ qua
    không sửa, và `_variant` (biến dùng chung cho mọi khối về sau) bị hạ oan
    xuống mức thấp hơn trong khi cấu hình vốn không có lỗi gì.
    """


# `finish_reason` của SDK là enum; so khớp trên chuỗi để không phụ thuộc phiên bản.
def _la_recitation(response) -> bool:
    try:
        return any(
            "RECITATION" in str(c.finish_reason).upper()
            for c in (response.candidates or [])
        )
    except Exception:
        return False


def is_gemma(model: str) -> bool:
    return model.lower().lstrip("models/").startswith("gemma")


# Lỗi báo hiệu model không nhận tham số nào đó -> hạ cấu hình rồi thử lại.
_UNSUPPORTED_HINTS = (
    "developer instruction",
    "system instruction",
    "system_instruction",
    "not supported",
    "not enabled",
    "unsupported",
    "invalid_argument",
    "thinking",
    "safety",
)


def _describe_empty(response) -> str:
    """Vì sao response rỗng — để log nói được điều gì có ích."""

    try:
        usage = response.usage_metadata
        thoughts = getattr(usage, "thoughts_token_count", None) or 0
        finish = [str(c.finish_reason) for c in (response.candidates or [])]

        if thoughts:
            return f"tiêu {thoughts} token vào thinking, finish={finish}"

        return f"finish={finish}"
    except Exception:
        return "không rõ"


def _looks_unsupported(error: str) -> bool:
    lowered = error.lower()

    return any(hint in lowered for hint in _UNSUPPORTED_HINTS)


def _strip_fence(text: str) -> str:
    match = _FENCE.match(text.strip())

    return match.group(1) if match else text


def split_chunks(text: str, max_chars: int | None = None) -> list[str]:
    """
    Cắt văn bản thành khối theo ranh giới trang.

    Cắt theo trang giữ được ngữ cảnh và tránh chẻ đôi một câu; trang nào tự
    nó đã dài hơn `max_chars` thì cắt tiếp theo đoạn văn.
    """

    max_chars = max_chars or config.GEMINI_CHUNK_CHARS

    parts = _PAGE_SPLIT.split(text)

    # split() trả về [đầu, số trang, nội dung, số trang, nội dung, ...]
    units: list[str] = []

    if parts[0].strip():
        units.append(parts[0].strip())

    for i in range(1, len(parts) - 1, 2):
        marker = PAGE_MARKER.format(n=parts[i]).strip("\n")
        body = parts[i + 1].strip()
        units.append(f"{marker}\n\n{body}" if body else marker)

    if not units:
        units = [text]

    # Trang quá dài -> chẻ nhỏ theo đoạn văn.
    sized: list[str] = []

    for unit in units:
        if len(unit) <= max_chars:
            sized.append(unit)
            continue

        buffer = ""

        for para in unit.split("\n\n"):
            if buffer and len(buffer) + len(para) + 2 > max_chars:
                sized.append(buffer)
                buffer = para
            else:
                buffer = f"{buffer}\n\n{para}" if buffer else para

        if buffer:
            sized.append(buffer)

    # Gộp các trang nhỏ lại cho đỡ tốn request.
    chunks: list[str] = []
    buffer = ""

    for unit in sized:
        if buffer and len(buffer) + len(unit) + 2 > max_chars:
            chunks.append(buffer)
            buffer = unit
        else:
            buffer = f"{buffer}\n\n{unit}" if buffer else unit

    if buffer:
        chunks.append(buffer)

    return chunks


class GeminiCorrector:
    """
    Hiệu đính text OCR, tự xoay tua qua nhiều API key.

    Mỗi lượt gọi mượn một key từ `KeyPool`; key nào dính 429 thì bị cho nghỉ và
    lượt đó được thử LẠI NGAY trên key khác thay vì ngồi chờ hết cooldown.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        pool: KeyPool | None = None,
    ):
        from google.genai import types

        self._types = types
        self.model = model or config.GEMINI_MODEL

        # api_key truyền tay -> bể một key (giữ tương thích lời gọi cũ).
        if pool is None:
            keys = [("thủ công", api_key)] if api_key else None

            try:
                pool = KeyPool(keys)
            except NoKeyAvailable as exc:
                raise GeminiError(str(exc)) from exc

        self.pool = pool
        self.is_gemma = is_gemma(self.model)

        # Gemma chỉ có 2 vai "user" và "model" — không có system role. Truyền
        # system_instruction vào là API trả lỗi, nên với Gemma ta ghép luôn
        # phần hướng dẫn vào đầu lượt user (cách Google khuyến nghị).
        self._variants = self._build_variants()
        self._variant = 0
        self._variant_lock = threading.Lock()

        # Gemma có hạn mức output nhỏ hơn Gemini nhiều (~8k token). Tiếng Việt
        # có dấu tốn token, nên cắt khối nhỏ lại cho khỏi cụt giữa chừng.
        self.chunk_chars = config.GEMINI_CHUNK_CHARS

        if self.is_gemma:
            self.chunk_chars = min(self.chunk_chars, config.GEMMA_CHUNK_CHARS)

    def _build_variants(self) -> list[tuple[str, object, bool]]:
        """
        Danh sách cấu hình theo thứ tự ưu tiên: (tên, config, có ghép system).

        Nếu model từ chối cấu hình đầy đủ, client tự hạ xuống cấu hình đơn giản
        hơn và ghi nhớ, không thử lại cái đã hỏng nữa.
        """

        types = self._types

        safety = [
            types.SafetySetting(category=category, threshold="BLOCK_NONE")
            for category in (
                "HARM_CATEGORY_HARASSMENT",
                "HARM_CATEGORY_HATE_SPEECH",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "HARM_CATEGORY_DANGEROUS_CONTENT",
            )
        ]

        variants: list[tuple[str, object, bool]] = []

        if not self.is_gemma:
            variants.append(
                (
                    "đầy đủ",
                    types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.0,
                        max_output_tokens=config.GEMINI_MAX_OUTPUT_TOKENS,
                        thinking_config=types.ThinkingConfig(
                            thinking_budget=config.GEMINI_THINKING_BUDGET
                        ),
                        safety_settings=safety,
                    ),
                    False,
                )
            )

        # Gemma 4 CŨNG là model có thinking, và không tắt thì hỏng hẳn: đo được
        # nó tiêu 32.765 token vào phần suy nghĩ, chạm MAX_TOKENS rồi trả về
        # RỖNG (0 token đầu ra). Tắt đi thì cùng prompt chạy 2 giây, đúng hết.
        #
        # Gemma KHÔNG nhận thinking_budget (400 "not supported") mà nhận
        # thinking_level — ngược hẳn với Gemini. Cần google-genai >= 2.0.
        variants.append(
            (
                "ghép system vào prompt, tắt thinking",
                types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=config.GEMINI_MAX_OUTPUT_TOKENS,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=config.GEMMA_THINKING_LEVEL
                    ),
                    safety_settings=safety,
                ),
                True,
            )
        )

        variants.append(
            (
                "ghép system vào prompt",
                types.GenerateContentConfig(temperature=0.0, safety_settings=safety),
                True,
            )
        )

        # Chốt cuối: cấu hình trần, model nào cũng nuốt được.
        variants.append(
            ("tối giản", types.GenerateContentConfig(temperature=0.0), True)
        )

        return variants

    def _downgrade(self, index: int, why: str) -> bool:
        """Hạ xuống cấu hình đơn giản hơn. Trả về False nếu đã ở mức thấp nhất."""

        if index + 1 >= len(self._variants):
            return False

        with self._variant_lock:
            if self._variant == index:
                self._variant = index + 1
                print(
                    f"    [config] {self.model} {why} -> chuyển sang "
                    f"'{self._variants[index + 1][0]}'",
                    flush=True,
                )

        return True

    def _call(self, prompt: str) -> str:
        """
        Gọi model một lần, tự xoay qua các key cho đến khi có kết quả.

        Ngân sách `tries` tính theo số key: key nào dính 429 thì bị cho nghỉ và
        lượt đó được thử LẠI NGAY trên key khác, không ngồi chờ hết cooldown.
        Hết ngân sách thì ném lỗi lên `fix_chunk` — nơi đã có backoff riêng.
        """

        tries = max(4, 2 * len(self.pool))
        last_error = "không rõ"

        for _ in range(tries):
            with self._variant_lock:
                index = self._variant

            name, gen_config, fold_system = self._variants[index]
            contents = f"{SYSTEM_PROMPT}\n\n---\n\n{prompt}" if fold_system else prompt

            state = self.pool.acquire()

            try:
                response = self.pool.client_for(state).models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=gen_config,
                )
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                last_error = message
                kind, delay = classify_error(exc)

                if kind == "rate":
                    self.pool.report_rate_limit(state, delay)
                    continue

                if kind == "dead":
                    self.pool.report_dead(state, message)
                    continue

                self.pool.report_transient(state)

                # Model không nhận tham số -> hạ cấu hình rồi thử lại ngay.
                # Xét SAU phần phân loại key: 400 "invalid_argument" vì cấu hình
                # khác hẳn 400 "API key not valid" vì key hỏng.
                if _looks_unsupported(message) and self._downgrade(
                    index, f"không nhận cấu hình '{name}'"
                ):
                    continue

                raise
            else:
                self.pool.report_ok(state)

            text = (response.text or "").strip()

            if text:
                return _strip_fence(text)

            detail = _describe_empty(response)
            last_error = f"Model trả về rỗng ({detail})"

            # RECITATION phải tách ra TRƯỚC nhánh hạ cấu hình: hạ cấu hình không
            # gỡ được lệnh chặn, mà `_variant` lại dùng chung cho mọi khối sau
            # nên hạ một lần là hỏng luôn cả phần còn lại của kho.
            if _la_recitation(response):
                raise RecitationError(last_error)

            # Rỗng thường KHÔNG phải lỗi tạm thời mà là model đã tiêu hết hạn
            # mức output vào phần suy nghĩ. Thử lại y hệt chỉ tốn thời gian —
            # phải hạ cấu hình.
            if self._downgrade(index, f"trả về rỗng ({detail})"):
                continue

            raise GeminiError(last_error)

        raise GeminiError(
            f"Đã thử {tries} lượt trên {len(self.pool)} key mà vẫn hỏng. "
            f"Lỗi cuối: {last_error}"
        )

    # Dưới ngưỡng này thì chia tiếp cũng vô nghĩa: đoạn quá ngắn khiến model mất
    # ngữ cảnh để hiệu đính, mà vẫn có thể bị chặn.
    NGUONG_CHIA = 400

    def _chia_nho_khi_bi_chan(
        self,
        text: str,
        meta: dict,
        part: int,
        total: int,
        on_retry=None,
    ) -> str | None:
        """Bị RECITATION thì cắt đôi rồi sửa từng nửa. None nếu vẫn không thoát.

        Cắt ở ranh giới đoạn gần giữa nhất, không cắt giữa câu — cắt ẩu thì mỗi
        nửa mất đầu hoặc mất đuôi câu, model hiệu đính sẽ "chữa" thành câu khác.

        Chỉ cần MỘT nửa qua được là đã hơn hẳn cách cũ (bỏ nguyên khối), nên nửa
        nào vẫn bị chặn thì giữ bản gốc của riêng nửa đó.
        """

        if len(text) < self.NGUONG_CHIA:
            return None

        giua = text.find("\n\n", len(text) // 3)

        if giua == -1 or giua > len(text) * 2 // 3:
            giua = text.rfind("\n", len(text) // 3, len(text) * 2 // 3)

        if giua == -1:
            return None

        if on_retry:
            on_retry(0, f"bị chặn recitation -> cắt đôi khối {part}/{total}")

        trai, phai = text[:giua].strip(), text[giua:].strip()
        a, ok_a = self.fix_chunk(trai, meta, part, total, on_retry=on_retry)
        b, ok_b = self.fix_chunk(phai, meta, part, total, on_retry=on_retry)

        return f"{a}\n\n{b}" if (ok_a or ok_b) else None

    def fix_chunk(
        self,
        text: str,
        meta: dict,
        part: int,
        total: int,
        on_retry=None,
    ) -> tuple[str, bool]:
        """
        Sửa một khối text. Trả về (text đã sửa, có thực sự sửa được không).

        Nếu Gemini hỏng hoặc trả về nội dung quá ngắn so với đầu vào (dấu hiệu
        nó đã tóm tắt thay vì hiệu đính) thì giữ nguyên text gốc.
        """

        prompt = USER_TEMPLATE.format(
            title=meta.get("title") or "(không rõ)",
            so_hieu=meta.get("so_hieu") or "(không rõ)",
            category=meta.get("category") or "(không rõ)",
            part=part,
            total=total,
            text=text,
        )

        last_error = ""

        for attempt in range(1, config.GEMINI_MAX_ATTEMPTS + 1):
            try:
                fixed = self._call(prompt)

                # Chốt chặn chống tóm tắt: bản sửa không được ngắn hơn 60%
                # bản gốc (sửa lỗi chính tả gần như không đổi độ dài).
                if len(fixed) < len(text) * 0.6:
                    raise GeminiError(
                        f"Đầu ra ngắn bất thường ({len(fixed)} vs {len(text)} ký tự) "
                        "— nghi model đã tóm tắt"
                    )

                return fixed, True

            except RecitationError as exc:
                # Thử lại y hệt là vô ích — lần nào cũng bị chặn đúng như nhau
                # (đo trên 0124 và 0328: ba lượt đều trả về đúng 52 ký tự).
                # Cách thoát duy nhất đo được là CHIA NHỎ: một đoạn ngắn ít
                # giống "văn bản model đã thuộc" hơn cả khối lớn.
                nho = self._chia_nho_khi_bi_chan(text, meta, part, total, on_retry)

                if nho is not None:
                    return nho, True

                if on_retry:
                    on_retry(attempt, f"BỎ QUA khối (bị chặn recitation): {exc}")

                return text, False

            except NoKeyAvailable:
                # Mọi key đã chết — chờ thêm cũng vô ích, để run_fix dừng hẳn.
                raise

            except Exception as exc:  # SDK ném nhiều loại lỗi khác nhau
                last_error = f"{type(exc).__name__}: {exc}"

                if attempt >= config.GEMINI_MAX_ATTEMPTS:
                    break

                if on_retry:
                    on_retry(attempt, last_error)

                time.sleep(min(2 ** attempt, 30) * (0.6 + random.random() * 0.8))

        if on_retry:
            on_retry(config.GEMINI_MAX_ATTEMPTS, f"BỎ QUA khối: {last_error}")

        return text, False

    def fix_document(self, text: str, meta: dict, on_retry=None) -> tuple[str, int, int]:
        """Sửa cả văn bản. Trả về (text đã sửa, số khối OK, tổng số khối)."""

        chunks = split_chunks(text, self.chunk_chars)
        results = []
        ok = 0

        for index, chunk in enumerate(chunks, start=1):
            fixed, success = self.fix_chunk(
                chunk, meta, index, len(chunks), on_retry=on_retry
            )
            results.append(fixed)
            ok += int(success)

        return "\n\n".join(results).strip(), ok, len(chunks)
