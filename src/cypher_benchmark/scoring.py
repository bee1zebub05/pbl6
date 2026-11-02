"""Chấm điểm kết quả truy hồi theo tập ID — độc lập với nguồn kết quả."""

from __future__ import annotations

import math


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


def score_ranked(ranked_ids: list[str], expected_ids: frozenset[str] | None, k: int = 10) -> dict:
    """P@k, R@k, nDCG@k (nhị phân, ideal = min(k, |gold|) kết quả đúng đứng
    đầu), MRR và R-Precision (precision tại cutoff = |gold| — với tập gold
    lớn như S01 62 văn bản, P@10 không nói hết). Danh sách có thứ hạng; ID
    trùng chỉ tính lần đầu."""

    if expected_ids is None:
        return {f"P@{k}": None, f"R@{k}": None, f"nDCG@{k}": None, "MRR": None, "R-Prec": None}

    seen: set[str] = set()
    ranked = [i for i in ranked_ids if not (i in seen or seen.add(i))]
    rel = [1 if i in expected_ids else 0 for i in ranked]
    n_gold = len(expected_ids)

    def dcg(bits: list[int]) -> float:
        return sum(b / math.log2(pos + 2) for pos, b in enumerate(bits))

    ideal = dcg([1] * min(k, n_gold))
    first_hit = next((pos + 1 for pos, b in enumerate(rel) if b), 0)
    return {
        f"P@{k}": sum(rel[:k]) / k,
        f"R@{k}": sum(rel[:k]) / n_gold if n_gold else 0.0,
        f"nDCG@{k}": dcg(rel[:k]) / ideal if ideal else 0.0,
        "MRR": 1 / first_hit if first_hit else 0.0,
        "R-Prec": sum(rel[:n_gold]) / n_gold if n_gold else 0.0,
    }
