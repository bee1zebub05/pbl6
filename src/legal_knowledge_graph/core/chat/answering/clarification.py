"""Soạn câu hỏi lại khi thiếu slot hoặc thực thể mơ hồ / không tìm thấy."""

from __future__ import annotations

from ..models import Clarification

SLOT_PHRASES: dict[str, str] = {
    "org": "đơn vị nào",
    "topic": "lĩnh vực nào",
    "target_group": "đối tượng nào",
    "doc_number": "văn bản số mấy (ví dụ 4511/QĐ-ĐHBK)",
    "person": "người ký nào",
    "position": "chức danh nào (ví dụ Hiệu trưởng)",
    "doc_type": "loại văn bản nào (Luật, Thông tư, Quyết định...)",
    "year": "năm nào",
    "since_year": "từ năm nào",
    "article_number": "Điều mấy",
    "status": "văn bản còn hay đã hết hiệu lực",
    "content_type": "loại nào (Quy chế, Quy định, Nội quy...)",
    "phrase": "nội dung gì",
    "limit": "mấy kết quả",
}


class ClarificationService:
    @staticmethod
    def _phrase(slot: str | None) -> str:
        return SLOT_PHRASES.get(slot or "", "nội dung gì")

    _MAX_OPTIONS = 3  # hỏi lại quá nhiều phương án thì người dùng khó trả lời

    def for_missing(self, slots: tuple[str, ...]) -> Clarification:
        options = [self._phrase(s) for s in slots[: self._MAX_OPTIONS]] or [self._phrase(None)]
        if len(options) == 1:
            return Clarification(f"Bạn đang quan tâm {options[0]}?")
        return Clarification(f"Câu này hơi rộng, bạn đang quan tâm {', '.join(options[:-1])} hay {options[-1]}?")

    def for_resolution(self, slot: str | None, reason: str, candidates: tuple[str, ...]) -> Clarification:
        if candidates:
            return Clarification("Mình thấy có vài kết quả gần giống, ý bạn là cái nào?", candidates)
        return Clarification(f"Mình {reason}. Bạn kiểm tra lại giúp mình, hoặc nói rõ hơn một chút nhé?")
