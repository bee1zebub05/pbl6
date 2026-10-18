"""
Kho template Cypher đã kiểm duyệt cho chatbot — sắp theo nhóm nghiệp vụ, trong
mỗi nhóm từ đơn giản tới phức tạp (level 1 → 5), từ câu hay được sinh viên /
phụ huynh / giảng viên hỏi tới câu chủ yếu phục vụ quản lý, quản trị dữ liệu.

    documents        tra cứu danh sách văn bản
    single_document  hỏi về một văn bản cụ thể
    relations        quan hệ căn cứ / thay thế / sửa đổi / bãi bỏ
    content          tìm theo nội dung quy định
    people_orgs      người ký, cơ quan
    statistics       thống kê, phân tích toàn kho

LLM không viết Cypher ở nhánh template: router trích khung action + slot,
`core/chat/understanding/template_selector.py` chọn template từ `action` và slot
suy ra từ `params` của chính template; entity_resolver.py biến giá trị thô thành
khoá thật trước khi điền vào $param.
"""

from __future__ import annotations

from typing import Collection

from . import content, documents, people_orgs, relations, single_document, statistics
from .actions import (ACTION_DESCRIPTIONS, AGENT_ACTION, RETRIEVAL_FULL, RETRIEVAL_NONE, RetrievalMode,
                      retrieval_mode)
from .base import (INT_SLOTS, INTERNAL_PARAMS, PARAM_TO_SLOT, RESOLVER_KINDS, SLOT_TO_PARAM, ParamSpec, Template)

_GROUPS = (documents, single_document, relations, content, people_orgs, statistics)

TEMPLATES: dict[str, Template] = {t.name: t for group in _GROUPS for t in group.TEMPLATES}

# Template luôn có trong danh mục agent dù câu hỏi đã có action: lọc kết hợp
# nhiều điều kiện và tìm theo nội dung — hai đường agent hay cần nhất.
AGENT_BASE_ACTIONS = frozenset({"list_documents", "search_articles"})

__all__ = [
    "ACTION_DESCRIPTIONS", "AGENT_ACTION", "AGENT_BASE_ACTIONS", "INT_SLOTS", "INTERNAL_PARAMS", "PARAM_TO_SLOT",
    "RESOLVER_KINDS", "RETRIEVAL_FULL", "RETRIEVAL_NONE", "RetrievalMode", "SLOT_TO_PARAM", "ParamSpec", "Template",
    "TEMPLATES", "action_description", "actions_in_order", "catalog_markdown", "catalog_text", "retrieval_mode",
    "template_slots",
]


def template_slots(tpl: Template) -> tuple[frozenset[str], frozenset[str]]:
    """(slot bắt buộc, slot nhận được) suy từ tham số của template."""

    required = frozenset(PARAM_TO_SLOT[p.name] for p in tpl.params
                         if p.required and p.default is None)
    accepted = frozenset(PARAM_TO_SLOT[p.name] for p in tpl.params if p.name not in INTERNAL_PARAMS)
    return required, accepted


def actions_in_order() -> list[str]:
    """Các action theo thứ tự xuất hiện trong kho (nhóm hay hỏi trước), `other` cuối cùng."""

    return [*dict.fromkeys(t.action for t in TEMPLATES.values()), AGENT_ACTION]


def action_description(action: str) -> str:
    if action in ACTION_DESCRIPTIONS:
        return ACTION_DESCRIPTIONS[action]
    return next(t.description for t in TEMPLATES.values() if t.action == action)


def catalog_text(actions: Collection[str] | None = None) -> str:
    """Danh mục template cho prompt agent (tool run_template). `actions`: chỉ
    liệt kê template của các action này (None = toàn bộ kho)."""

    lines: list[str] = []
    for tpl in TEMPLATES.values():
        if actions is not None and tpl.action not in actions:
            continue
        required = [p.name for p in tpl.params if p.required and p.default is None]
        optional = [p.name for p in tpl.params if p.name not in required and p.name not in INTERNAL_PARAMS]
        params = ", ".join([*required, *(f"{p}?" for p in optional)]) or "không"
        lines.append(f"- {tpl.name}({params}): {tpl.description}")
    return "\n".join(lines)


_GROUP_TITLES = {
    documents: "Tra cứu danh sách văn bản",
    single_document: "Hỏi về một văn bản cụ thể",
    relations: "Quan hệ giữa các văn bản",
    content: "Tìm theo nội dung quy định",
    people_orgs: "Người ký và cơ quan",
    statistics: "Thống kê và phân tích toàn kho",
}

_LEVEL_LABELS = {1: "1 — tra cứu 1 bước", 2: "2 — nhiều quan hệ / nhiều điều kiện", 3: "3 — nhiều bước, full-text có lọc",
                 4: "4 — chuỗi nhiều tầng, kết hợp", 5: "5 — tổng hợp toàn graph"}


def catalog_markdown() -> str:
    """Danh mục template dạng Markdown (docs/TEMPLATES.md) — sinh từ chính kho để
    tài liệu không lệch mã: `python run.py lkg templates`."""

    from collections import Counter

    levels = Counter(t.level for t in TEMPLATES.values())
    lines = [
        "# Kho template Cypher của chatbot",
        "",
        "Tệp này được sinh tự động bằng `python run.py lkg templates` từ `core/graph_query/templates/` — không sửa tay.",
        "",
        f"**{len(TEMPLATES)} template**, {len(actions_in_order()) - 1} action (cộng `other` -> agent).",
        "",
        "| Mức | Ý nghĩa | Số template |",
        "|---|---|---|",
        *(f"| {lv} | {_LEVEL_LABELS[lv].split(' — ')[1]} | {levels[lv]} |" for lv in sorted(levels)),
        "",
        "Mỗi nhóm sắp từ đơn giản tới phức tạp; cột *Người hay hỏi* cho biết câu hỏi phổ biến với ai.",
        "Slot in đậm là bắt buộc. Ví dụ tham số lấy từ dữ liệu thật và được kiểm bằng "
        "`tests/test_templates_live.py`.",
    ]
    number = 0
    for group in _GROUPS:
        lines += ["", f"## {_GROUP_TITLES[group]}", "",
                  "| # | Template | Mức | Action | Slot | Người hay hỏi | Ví dụ câu hỏi |",
                  "|---|---|---|---|---|---|---|"]
        for tpl in group.TEMPLATES:
            number += 1
            required, accepted = template_slots(tpl)
            slots = ", ".join([*(f"**{s}**" for s in sorted(required)), *sorted(accepted - required)]) or "—"
            lines.append(f"| {number} | `{tpl.name}` | {tpl.level} | `{tpl.action}` | {slots} | "
                         f"{', '.join(tpl.audience)} | {tpl.nl_examples[0]} |")
    return "\n".join(lines) + "\n"


def _check() -> None:
    names = [t.name for group in _GROUPS for t in group.TEMPLATES]
    duplicates = {n for n in names if names.count(n) > 1}
    assert not duplicates, f"Trùng tên template: {duplicates}"
    actions = {t.action for t in TEMPLATES.values()}
    for declared in (RETRIEVAL_FULL, RETRIEVAL_NONE, AGENT_BASE_ACTIONS):
        assert declared <= actions, f"Action không có trong kho template: {sorted(declared - actions)}"
    assert not RETRIEVAL_FULL & RETRIEVAL_NONE, f"Action vừa full vừa none: {sorted(RETRIEVAL_FULL & RETRIEVAL_NONE)}"
    for tpl in TEMPLATES.values():
        unknown = {p.name for p in tpl.params} - set(PARAM_TO_SLOT) - INTERNAL_PARAMS
        assert not unknown, f"{tpl.name}: tham số {unknown} chưa có slot trong SLOT_TO_PARAM"
        missing_examples = {p.name for p in tpl.params if p.required and p.default is None} - set(tpl.example_params)
        assert not missing_examples, f"{tpl.name}: thiếu example_params cho {missing_examples}"
        assert 1 <= tpl.level <= 5, f"{tpl.name}: level phải 1-5"
        for p in tpl.params:
            assert f"${p.name}" in tpl.cypher, f"{tpl.name}: tham số {p.name} không dùng trong Cypher"
            assert p.resolver in RESOLVER_KINDS, f"{tpl.name}: resolver '{p.resolver}' không hợp lệ"


_check()
