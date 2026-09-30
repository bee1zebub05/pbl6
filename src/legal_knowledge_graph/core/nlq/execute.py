"""
Thực thi Cypher có timeout THẬT — dùng chung cho cả nhánh template lẫn
freeform (guard.py gọi vào đây, và cả 2 nhánh phải đi qua cùng 1 hàm này,
không viết lặp lại logic timeout ở 2 nơi).

QUAN TRỌNG: driver cài thật là neo4j==6.3.1. `session.run(query,
timeout=N)` KHÔNG hoạt động như timeout — extra kwargs của `run()` bị coi
là Cypher parameter (`$timeout`) vô nghĩa, không phải option driver (đã
xác minh trực tiếp trong site-packages/neo4j/_sync/work/session.py). Timeout
thật sự phải qua `Session.begin_transaction(timeout=...)`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .. import neo4j_session

# Re-export: 1 session dùng chung cho cả bước resolve (tra cứu
# Organization/Document sống) lẫn bước execute cuối — tránh mở nhiều kết
# nối cho 1 lần hỏi. Định nghĩa thật nằm ở core/neo4j_session.py, dùng
# chung với graph_loader.py/query/runner.py — giữ tên `execute.session()`
# ở đây vì phần lớn code core/nlq/ đã gọi qua tên này.
session = neo4j_session.session


@dataclass(frozen=True)
class ExecutionResult:
    rows: list[dict]
    elapsed_ms: float


def run_in_session(session_, cypher: str, params: dict, timeout_seconds: float) -> ExecutionResult:
    start = time.perf_counter()
    tx = session_.begin_transaction(timeout=timeout_seconds)
    try:
        result = tx.run(cypher, **params)
        rows = [dict(r) for r in result]
        tx.commit()
    except Exception:
        tx.rollback()
        raise
    finally:
        tx.close()
    elapsed_ms = (time.perf_counter() - start) * 1000
    return ExecutionResult(rows=rows, elapsed_ms=elapsed_ms)


def run_cypher(cypher: str, params: dict, timeout_seconds: float) -> ExecutionResult:
    """Tiện ích mở session riêng rồi chạy — dùng khi không cần chia sẻ
    session với bước resolve (vd test độc lập 1 Cypher)."""

    with session() as s:
        return run_in_session(s, cypher, params, timeout_seconds)


def explain(cypher: str, params: dict, session_) -> None:
    """Chạy EXPLAIN <cypher> — parse/plan mà KHÔNG đụng data. Raise nếu cú
    pháp/plan sai; không raise không có nghĩa Cypher đúng NGỮ NGHĨA, chỉ là
    hợp lệ để chạy (xem guard.py bước property/label whitelist cho phần
    EXPLAIN không bắt được).

    Bắt buộc nhận session có sẵn (không tự mở session riêng) — caller
    (guard.py, qua pipeline._run_freeform) dùng LẠI đúng session sẽ chạy
    Cypher thật sau đó, tránh mở 2 kết nối Neo4j cho 1 lượt Stage B."""

    session_.run(f"EXPLAIN {cypher}", **params).consume()
