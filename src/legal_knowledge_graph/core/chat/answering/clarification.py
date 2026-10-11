"""Soạn câu hỏi lại khi thiếu slot hoặc thực thể mơ hồ / không tìm thấy."""

from __future__ import annotations

from ..models import Clarification

SLOT_PHRASES: dict[str, str] = {
    "org": "cơ quan / đơn vị ban hành",
    "topic": "lĩnh vực",
    "target_group": "nhóm đối tượng áp dụng",
    "doc_number": "số hiệu văn bản (ví dụ 4511/QĐ-ĐHBK)",
    "person": "họ tên người ký",
    "position": "chức danh người ký (ví dụ Hiệu trưởng)",
    "doc_type": "loại văn bản (Luật, Nghị định, Thông tư, Quyết định...)",
    "year": "năm ban hành",
    "since_year": "mốc năm bắt đầu",
    "article_number": "số Điều (ví dụ Điều 5)",
    "status": "tình trạng hiệu lực (còn / hết hiệu lực)",
    "content_type": "loại nội dung (Quy định, Quy chế, Nội quy...)",
    "phrase": "cụm từ hoặc chủ đề cần tìm",
    "limit": "số lượng kết quả",
}


class ClarificationService:
    @staticmethod
    def _phrase(slot: str | None) -> str:
        return SLOT_PHRASES.get(slot or "", "thông tin cần tra cứu")

    _MAX_OPTIONS = 3  # hỏi lại quá nhiều phương án thì người dùng khó trả lời

    def for_missing(self, slots: tuple[str, ...]) -> Clarification:
        options = [self._phrase(s) for s in slots[: self._MAX_OPTIONS]] or [self._phrase(None)]
        if len(options) == 1:
            return Clarification(f"Bạn cho mình biết thêm {options[0]} nhé?")
        return Clarification(f"Bạn muốn lọc theo {', '.join(options[:-1])} hay {options[-1]}?")

    def for_resolution(self, slot: str | None, reason: str, candidates: tuple[str, ...]) -> Clarification:
        if candidates:
            return Clarification(
                f"Mình thấy có vài {self._phrase(slot)} gần giống, bạn muốn nói tới cái nào?", candidates
            )
        return Clarification(f"Mình {reason}. Bạn kiểm tra lại {self._phrase(slot)} giúp mình nhé?")
