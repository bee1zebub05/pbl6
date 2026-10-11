"""Chấm điểm kết quả truy hồi theo tập ID — độc lập với nguồn kết quả."""

from __future__ import annotations


def score_ids(result_ids: list[str], expected_ids: frozenset[str] | None) -> dict:
    """Precision/Recall/F1 kiểu tập hợp (intersection/union) — nhận list ID
    THÔ, không quan tâm nguồn gốc (Cypher hôm nay, hay BM25/semantic
    retrieval sau này). Đây là điểm TÁI DÙNG khi cắm thêm 1 nguồn kết quả
    khác vào cùng bộ case: chỉ cần đưa list ID của nguồn đó + đúng
    `expected_ids` của case (xem catalogs/scenarios.py) vào đây, không cần
    viết lại evaluate."""

    if expected_ids is None:
        return {"precision": None, "recall": None, "f1": None}

    result_set = set(result_ids)
    tp = len(result_set & expected_ids)
    precision = tp / len(result_set) if result_set else 1.0
    recall = tp / len(expected_ids) if expected_ids else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}
