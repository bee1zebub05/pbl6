"""
Đọc danh mục đóng trong reference/*_seed.json (Topic, TargetGroup,
Organization) — dùng chung cho bước nạp (ingest/), resolve thực thể
(graph_query/) và prompt chatbot (chat/).
"""

from __future__ import annotations

import json
from pathlib import Path


def load_seed_entries(path: Path) -> list[dict]:
    """Danh sách entry (dict, giữ tên hiển thị gốc) của một file seed."""

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("topics") or raw.get("organizations") or raw.get("target_groups") or []
