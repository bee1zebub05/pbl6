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
from typing import Callable, TypeVar

from .. import config, normalize

T = TypeVar("T")


def lazy_cache(loader: Callable[[], T]) -> Callable[[], T]:
    """Bọc 1 hàm load-1-lần thành hàm cache-trong-closure — gọi lại bao
    nhiêu lần cũng chỉ load thật 1 lần trong tiến trình. Dùng chung cho
    MỌI cache "load 1 lần rồi giữ nguyên" ở core/nlq/ (3 hàm alias dưới
    đây + resolve.py::_make_seed_resolver() — trước đây mỗi cache tự viết
    tay 1 biến global + check `is None`, lặp lại 6 lần giữa 2 file)."""

    cache: T | None = None

    def get() -> T:
        nonlocal cache
        if cache is None:
            cache = loader()
        return cache

    return get


def _load_raw() -> dict:
    with open(config.ALIASES_SEED_PATH, encoding="utf-8") as f:
        return json.load(f)


def _to_slug_map(entries: list[dict]) -> dict[str, str]:
    return {normalize.slug(e["alias"]): normalize.slug(e["canonical"]) for e in entries}


load_org_aliases = lazy_cache(lambda: _to_slug_map(_load_raw().get("organizations") or []))
load_topic_aliases = lazy_cache(lambda: _to_slug_map(_load_raw().get("topics") or []))
load_target_group_aliases = lazy_cache(lambda: _to_slug_map(_load_raw().get("target_groups") or []))
