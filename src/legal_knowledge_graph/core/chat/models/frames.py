"""Khung câu hỏi: output có cấu trúc của LLM (intent, router) và quyết định chọn template."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

Intent = Literal["domain_query", "smalltalk", "out_of_scope", "unsafe"]


class IntentResult(BaseModel):
    intent: Intent = Field(description="Loại câu hỏi")
    standalone_question: str = Field(
        description="Câu hỏi viết lại thành câu ĐỘC LẬP, đầy đủ ý (thay đại từ bằng thực thể trong lịch sử, "
                    "ghép câu trả lời cho lượt hỏi lại vào câu hỏi gốc). Giữ nguyên nếu đã độc lập."
    )
    continues_clarification: bool = Field(
        description="true nếu tin nhắn này là câu trả lời cho câu bot vừa hỏi lại ở lượt trước"
    )
    direct_reply: str = Field(
        description="Câu trả lời ngắn cho smalltalk/out_of_scope/unsafe; để rỗng với domain_query"
    )


class Slots(BaseModel):
    """Tên trường PHẢI trùng khoá của core/graph_query/templates/base.py::SLOT_TO_PARAM và
    answering/clarification.py::SLOT_PHRASES (tests/test_template_selector.py kiểm)."""

    org: str | None = Field(default=None, description="Tên cơ quan/đơn vị, chép nguyên văn người dùng viết")
    topic: str | None = Field(default=None, description="Lĩnh vực — đúng nguyên văn 1 giá trị trong danh sách đóng")
    target_group: str | None = Field(default=None, description="Nhóm đối tượng — đúng nguyên văn 1 giá trị trong danh sách đóng")
    doc_number: str | None = Field(default=None, description="Số hiệu văn bản, chép nguyên văn (vd 4511/QĐ-ĐHBK)")
    person: str | None = Field(default=None, description="Họ tên người ký, chép nguyên văn")
    position: str | None = Field(default=None, description="Chức danh người ký (Hiệu trưởng, Bộ trưởng...)")
    status: Literal["CON_HIEU_LUC", "HET_HIEU_LUC", "CHUA_HIEU_LUC"] | None = Field(
        default=None, description="Chỉ điền khi câu hỏi nói rõ về tình trạng hiệu lực"
    )
    doc_type: str | None = Field(default=None, description="Loại văn bản — 1 giá trị trong danh sách đóng")
    content_type: str | None = Field(default=None, description="Loại nội dung kèm theo (Quy định, Quy chế...)")
    year: int | None = Field(default=None, description="Năm ban hành cụ thể (vd 2024)")
    since_year: int | None = Field(default=None, description="Từ năm ... trở lại đây (vd 'từ 2023 đến nay' -> 2023)")
    article_number: str | None = Field(default=None, description="Số Điều (vd 'Điều 5')")
    phrase: str | None = Field(default=None, description="Cụm từ / chủ đề nội dung cần tìm (vd học bổng, thôi học)")
    limit: int | None = Field(default=None, description="Chỉ điền khi người dùng nêu số lượng cụ thể (vd top 5)")

    def filled(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if v not in (None, "")}


_ACTION_FIELD = Field(description="Hành động người dùng muốn — đúng 1 giá trị trong danh sách action")


class QueryFrame(BaseModel):
    """Khung câu hỏi dùng NỘI BỘ (TemplateSelector, state). LLM không thấy model này."""

    action: str = _ACTION_FIELD
    slots: Slots


def _require_every_key(schema: dict) -> None:
    """Mọi key BẮT BUỘC có mặt (giá trị vẫn được null). Key tuỳ chọn thì
    Gemini (constrained decoding) hay bỏ hẳn, nhảy từ "action" sang vài key
    cuối — slot cần thiết không bao giờ được ghi (đã thấy trong output thô)."""

    schema["required"] = list(schema["properties"])


# Output của router LLM: action + các slot ở CÙNG MỘT CẤP, mọi key bắt buộc.
# Schema lồng (`slots` là object con qua $ref) hay trả slot rỗng. Sinh từ
# Slots để thêm slot chỉ phải sửa một chỗ; giá trị mặc định None giữ lại cho
# phía Python (test dựng RouterOutput với vài slot).
RouterOutput: type[BaseModel] = create_model(
    "RouterOutput",
    __doc__="Khung câu hỏi: hành động người dùng muốn và mọi thực thể / điều kiện họ nêu.",
    __config__=ConfigDict(json_schema_extra=_require_every_key),
    action=(str, _ACTION_FIELD),
    **{name: (f.annotation, Field(default=None, description=f.description)) for name, f in Slots.model_fields.items()},
)


def frame_from_router(output: BaseModel) -> QueryFrame:
    return QueryFrame(action=output.action, slots=Slots(**{name: getattr(output, name) for name in Slots.model_fields}))


@dataclass(frozen=True)
class RouteDecision:
    kind: Literal["template", "clarify", "agent"]
    template: str | None = None
    raw_params: dict[str, Any] = field(default_factory=dict)  # tên $param -> giá trị thô
    missing: tuple[str, ...] = ()  # slot thiếu (các phương án thay thế nhau)
    extra: tuple[str, ...] = ()    # slot người dùng nêu nhưng template không nhận
    reason: str = ""
