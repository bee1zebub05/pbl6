"""
Chạy một bộ Cypher (catalog.py/benchmark_catalog.py/scenario_catalog.py)
trên Neo4j riêng của legal_knowledge_graph, đo thời gian thật + đọc PROFILE
plan để biết có dùng index/fulltext hay bị rơi về quét toàn bộ. In báo cáo
dạng bảng.

`--source samples` (mặc định): bộ catalog.py, assert đúng số dòng, thoát mã
khác 0 nếu có câu FAIL — dùng làm regression test cho cơ chế.
`--source benchmark`: bộ benchmark_catalog.py, không assert số dòng cố định
(mọi câu expected_rows=None) — luôn thoát mã 0 nếu không lỗi, mục đích là ĐỌC
số đo chứ không PASS/FAIL.
`--source scenarios`: bộ scenario_catalog.py (20 case, data thật, dễ->khó) —
CHẤM ĐIỂM precision/recall/F1 khi câu có `expected_ids` (xem `_score_ids()`),
ngoài ra vẫn giữ assert số dòng như 2 nguồn kia.
"""

from __future__ import annotations

import argparse
import time

from .. import neo4j_session
from . import benchmark_catalog, catalog, scenario_catalog
from .catalog import Query

SOURCES = {
    "samples": catalog.QUERIES,
    "benchmark": benchmark_catalog.QUERIES,
    "scenarios": scenario_catalog.QUERIES,
}


def _plan_signature(plan) -> str:
    """Gộp operatorType + arguments của toàn bộ plan thành một chuỗi để dò
    'có dùng index/fulltext không' bằng cách tìm từ khoá — đơn giản, đủ dùng
    cho mục đích cảnh báo, không cần parse plan chính xác tuyệt đối."""

    parts: list[str] = []

    def walk(node) -> None:
        if not node:
            return
        parts.append(str(node.get("operatorType", "")))
        parts.append(str(node.get("args", "")))
        for child in node.get("children", None) or []:
            walk(child)

    walk(plan)
    return " ".join(parts)


def _index_used(signature: str, kind: str) -> bool | None:
    if kind in ("sanity", "distribution", "ranking", "anomaly"):
        return None  # không áp dụng — GROUP BY/ranking/full-scan-có-điều-kiện không có "đúng/sai" về index
    low = signature.lower()
    if kind in ("fulltext", "hybrid"):
        return "fulltext" in low
    if kind in ("lookup", "multihop"):
        return "indexseek" in low.replace(" ", "")
    return None


def _score_ids(result_ids: list[str], expected_ids: frozenset[str] | None) -> dict:
    """Precision/Recall/F1 kiểu tập hợp (intersection/union) — nhận list ID
    THÔ, không quan tâm nguồn gốc (Cypher hôm nay, hay BM25/semantic
    retrieval sau này). Đây là điểm TÁI DÙNG khi cắm thêm 1 nguồn kết quả
    khác vào cùng bộ case: chỉ cần đưa list ID của nguồn đó + đúng
    `expected_ids` của case (xem scenario_catalog.py) vào đây, không cần
    viết lại evaluate."""

    if expected_ids is None:
        return {"precision": None, "recall": None, "f1": None}

    result_set = set(result_ids)
    tp = len(result_set & expected_ids)
    precision = tp / len(result_set) if result_set else 1.0
    recall = tp / len(expected_ids) if expected_ids else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def run_one(session, query: Query) -> dict:
    start = time.perf_counter()
    rows = list(session.run(query.cypher))
    elapsed_ms = (time.perf_counter() - start) * 1000

    profile_summary = session.run(f"PROFILE {query.cypher}").consume()
    signature = _plan_signature(profile_summary.profile)
    index_used = _index_used(signature, query.kind)

    n = len(rows)
    if query.expected_rows is None:
        # Không có số dòng kỳ vọng cố định -> không có "đúng/sai" để assert
        # (0 dòng có thể chính là kết quả đúng, vd câu kiểu "đếm bất thường").
        passed = True
    else:
        passed = n == query.expected_rows

    if query.expected_ids is not None:
        result_ids = [r[query.id_field] for r in rows]
        score = _score_ids(result_ids, query.expected_ids)
    else:
        score = {"precision": None, "recall": None, "f1": None}

    return {
        "name": query.name,
        "rows": n,
        "expected": query.expected_rows,
        "elapsed_ms": elapsed_ms,
        "index_used": index_used,
        "passed": passed,
        "sample": [dict(r) for r in rows[:3]],
        **score,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chạy bộ Cypher trên Neo4j riêng của legal_knowledge_graph")
    parser.add_argument("--source", choices=sorted(SOURCES), default="samples",
                         help="samples = regression 17 mẫu (assert số dòng); benchmark = minh hoạ trên data thật "
                              "(chỉ đo); scenarios = 20 case dễ->khó trên data thật (assert số dòng + P/R/F1 khi có ground-truth)")
    parser.add_argument("--verbose", action="store_true", help="In luôn vài dòng kết quả mẫu mỗi câu")
    args = parser.parse_args(argv)

    queries = SOURCES[args.source]

    results = []
    with neo4j_session.session() as session:
        for query in queries:
            results.append(run_one(session, query))

    header = (f"{'query':<38} {'rows':>5} {'expected':>9} {'elapsed_ms':>11} {'index_used':>11} "
              f"{'prec':>6} {'recall':>6} {'f1':>6}  assertion")
    print(header)
    print("-" * len(header))
    for r in results:
        expected_display = "-" if r["expected"] is None else str(r["expected"])
        index_display = "-" if r["index_used"] is None else ("Y" if r["index_used"] else "N (WARN)")
        status = "PASS" if r["passed"] else "FAIL"

        def _pct(v: float | None) -> str:
            return "-" if v is None else f"{v:.2f}"

        print(
            f"{r['name']:<38} {r['rows']:>5} {expected_display:>9} "
            f"{r['elapsed_ms']:>11.2f} {index_display:>11} "
            f"{_pct(r['precision']):>6} {_pct(r['recall']):>6} {_pct(r['f1']):>6}  {status}"
        )
        if args.verbose and r["sample"]:
            for row in r["sample"]:
                print(f"      {row}")

    n_fail = sum(1 for r in results if not r["passed"])
    print(f"\n{len(results) - n_fail}/{len(results)} câu PASS.")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
