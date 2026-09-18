"""
Chạy bộ Cypher test (query_catalog.py) trên Neo4j riêng của
legal_knowledge_graph, đo thời gian thật + đọc PROFILE plan để biết có dùng
index/fulltext hay bị rơi về quét toàn bộ. In báo cáo dạng bảng, thoát mã
khác 0 nếu có câu assert sai số dòng.

Với 17 văn bản trong samples/, số đo elapsed_ms KHÔNG nói lên gì về hiệu
năng thật — giá trị ở bước này là chứng minh CƠ CHẾ (assertion + đọc plan)
chạy đúng, sẵn sàng có ý nghĩa khi nạp data thật lớn hơn.
"""

from __future__ import annotations

import argparse
import time

from neo4j import GraphDatabase

from . import config
from .query_catalog import QUERIES, Query


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
    if kind == "sanity":
        return None  # không áp dụng
    low = signature.lower()
    if kind in ("fulltext", "hybrid"):
        return "fulltext" in low
    if kind in ("lookup", "multihop"):
        return "indexseek" in low.replace(" ", "")
    return None


def run_one(session, query: Query) -> dict:
    start = time.perf_counter()
    rows = list(session.run(query.cypher))
    elapsed_ms = (time.perf_counter() - start) * 1000

    profile_summary = session.run(f"PROFILE {query.cypher}").consume()
    signature = _plan_signature(profile_summary.profile)
    index_used = _index_used(signature, query.kind)

    n = len(rows)
    if query.expected_rows is None:
        passed = n >= 1
    else:
        passed = n == query.expected_rows

    return {
        "name": query.name,
        "rows": n,
        "expected": query.expected_rows,
        "elapsed_ms": elapsed_ms,
        "index_used": index_used,
        "passed": passed,
        "sample": [dict(r) for r in rows[:3]],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chạy bộ Cypher test trên Neo4j riêng của legal_knowledge_graph")
    parser.add_argument("--verbose", action="store_true", help="In luôn vài dòng kết quả mẫu mỗi câu")
    args = parser.parse_args(argv)

    driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
    results = []
    try:
        with driver.session(database=config.NEO4J_DATABASE) as session:
            for query in QUERIES:
                results.append(run_one(session, query))
    finally:
        driver.close()

    header = f"{'query':<30} {'rows':>5} {'expected':>9} {'elapsed_ms':>11} {'index_used':>11}  assertion"
    print(header)
    print("-" * len(header))
    for r in results:
        expected_display = "-" if r["expected"] is None else str(r["expected"])
        index_display = "-" if r["index_used"] is None else ("Y" if r["index_used"] else "N (WARN)")
        status = "PASS" if r["passed"] else "FAIL"
        print(
            f"{r['name']:<30} {r['rows']:>5} {expected_display:>9} "
            f"{r['elapsed_ms']:>11.2f} {index_display:>11}  {status}"
        )
        if args.verbose and r["sample"]:
            for row in r["sample"]:
                print(f"      {row}")

    n_fail = sum(1 for r in results if not r["passed"])
    print(f"\n{len(results) - n_fail}/{len(results)} câu PASS.")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
