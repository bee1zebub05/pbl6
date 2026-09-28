"""
Bảng alias cho entity linking (reference/aliases_seed.json) — người tự tay
bảo trì, KHÔNG sinh tự động. Bù cho _fuzzy_pick() trong resolve.py: fuzzy
match theo Jaccard token chỉ bắt được biến thể diễn đạt GẦN GIỐNG cấu trúc
tên gốc, không bắt được viết tắt (VD "ĐHBK" không chia sẻ token nào với
"truong_dai_hoc_bach_khoa" nên fuzzy match bỏ sót hoàn toàn).

Mỗi loại trả dict[slug(alias) -> slug(canonical)] — resolve.py tự kiểm tra
canonical còn sống trong options hiện tại hay không trước khi dùng, để
alias trỏ tới 1 org đã đổi tên/xoá không làm hard-fail cả resolver.
"""

from __future__ import annotations

import json

from .. import config, normalize

_org_aliases: dict[str, str] | None = None
_topic_aliases: dict[str, str] | None = None
_target_group_aliases: dict[str, str] | None = None


def _load_raw() -> dict:
    with open(config.ALIASES_SEED_PATH, encoding="utf-8") as f:
        return json.load(f)


def _to_slug_map(entries: list[dict]) -> dict[str, str]:
    return {normalize.slug(e["alias"]): normalize.slug(e["canonical"]) for e in entries}


def load_org_aliases() -> dict[str, str]:
    global _org_aliases
    if _org_aliases is None:
        _org_aliases = _to_slug_map(_load_raw().get("organizations") or [])
    return _org_aliases


def load_topic_aliases() -> dict[str, str]:
    global _topic_aliases
    if _topic_aliases is None:
        _topic_aliases = _to_slug_map(_load_raw().get("topics") or [])
    return _topic_aliases


def load_target_group_aliases() -> dict[str, str]:
    global _target_group_aliases
    if _target_group_aliases is None:
        _target_group_aliases = _to_slug_map(_load_raw().get("target_groups") or [])
    return _target_group_aliases
