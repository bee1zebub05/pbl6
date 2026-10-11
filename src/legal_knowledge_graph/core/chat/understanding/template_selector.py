"""
Chọn template từ khung câu hỏi (action + slot) — thuần Python, không LLM.

LLM ở RouterService chỉ làm phần hiểu ngôn ngữ (người dùng muốn LÀM GÌ, nói
tới THỰC THỂ nào). Luật chọn template dựng tự động từ chính kho template
(`core/graph_query/templates/`): mỗi template khai `action`, slot bắt buộc / nhận được
suy từ tham số của nó. Không có bảng ánh xạ riêng phải giữ đồng bộ.

- khớp     : mọi slot đã điền đều được template nhận, đủ slot bắt buộc và đủ
             `min_slots`. Nhiều template cùng khớp -> chọn template có nhiều
             slot bắt buộc nhất (cụ thể nhất), rồi theo thứ tự trong kho.
- thiếu    : không thừa slot nhưng thiếu slot bắt buộc -> hỏi lại.
- thừa     : có slot không template nào của action nhận -> agent, KHÔNG âm
             thầm bỏ bớt điều kiện người dùng nêu.
- không rõ : action "other" / lạ -> agent.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...graph_query.templates import (AGENT_ACTION, SLOT_TO_PARAM, TEMPLATES, action_description, actions_in_order,
                              template_slots)
from ...observability import log_event, traceable
from ..models import QueryFrame, RouteDecision


@dataclass(frozen=True)
class ActionRule:
    template: str
    required: frozenset[str]
    accepted: frozenset[str]
    min_slots: int
    order: int

    def matches(self, names: frozenset[str]) -> bool:
        counted = len(names - {"limit"})
        return self.required <= names <= self.accepted and counted >= self.min_slots


def _build_rules() -> dict[str, list[ActionRule]]:
    rules: dict[str, list[ActionRule]] = {}
    for order, tpl in enumerate(TEMPLATES.values()):
        required, accepted = template_slots(tpl)
        rules.setdefault(tpl.action, []).append(ActionRule(tpl.name, required, accepted, tpl.min_slots, order))
    return rules


RULES: dict[str, list[ActionRule]] = _build_rules()


class TemplateSelector:
    @traceable(name="select_template")
    def select(self, frame: QueryFrame) -> RouteDecision:
        decision = self._decide(frame)
        log_event("route", action=frame.action, slots=frame.slots.filled(), decision=decision.kind,
                  template=decision.template, missing=list(decision.missing), extra=list(decision.extra))
        return decision

    def _decide(self, frame: QueryFrame) -> RouteDecision:
        rules = RULES.get(frame.action)
        if not rules:
            return RouteDecision("agent", reason=f"action '{frame.action}' không có template")

        filled = frame.slots.filled()
        names = frozenset(filled)

        matching = [r for r in rules if r.matches(names)]
        if matching:
            best = min(matching, key=lambda r: (-len(r.required), r.order))
            params = {SLOT_TO_PARAM[s]: v for s, v in filled.items()}
            return RouteDecision("template", template=best.template, raw_params=params)

        # Không thừa slot so với ít nhất một template -> chỉ thiếu slot bắt buộc.
        fitting = [r for r in rules if names <= r.accepted and r.required - names]
        if fitting:
            missing = tuple(dict.fromkeys(s for r in sorted(fitting, key=lambda r: r.order)
                                          for s in sorted(r.required - names)))
            return RouteDecision("clarify", missing=missing, reason="thiếu slot bắt buộc")

        accepted_any = frozenset().union(*(r.accepted for r in rules))
        extra = tuple(sorted(names - accepted_any)) or tuple(sorted(names))
        return RouteDecision("agent", extra=extra, reason="câu hỏi có nhiều điều kiện hơn template hỗ trợ")


def actions_prompt() -> str:
    """Danh sách action cho prompt router — sinh từ kho template."""

    lines = []
    for action in actions_in_order():
        slots = sorted({s for r in RULES.get(action, []) for s in r.accepted})
        slot_note = f" [slot: {', '.join(slots)}]" if slots else ""
        lines.append(f"- {action}: {action_description(action)}{slot_note}")
    return "\n".join(lines)


__all__ = ["AGENT_ACTION", "RULES", "TemplateSelector", "actions_prompt"]
