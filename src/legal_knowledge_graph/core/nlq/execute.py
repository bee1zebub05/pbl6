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
from contextlib import contextmanager
from dataclasses import dataclass

from neo4j import GraphDatabase

from .. import config


@dataclass(frozen=True)
class ExecutionResult:
    rows: list[dict]
    elapsed_ms: float


@contextmanager
def session():
    """1 session dùng chung cho cả bước resolve (tra cứu Organization/
    Document sống) lẫn bước execute cuối — tránh mở nhiều kết nối cho 1
    lần hỏi."""

    driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
    try:
        with driver.session(database=config.NEO4J_DATABASE) as s:
            yield s
    finally:
        driver.close()


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


def explain(cypher: str, params: dict, session_=None) -> None:
    """Chạy EXPLAIN <cypher> — parse/plan mà KHÔNG đụng data. Raise nếu cú
    pháp/plan sai; không raise không có nghĩa Cypher đúng NGỮ NGHĨA, chỉ là
    hợp lệ để chạy (xem guard.py bước property/label whitelist cho phần
    EXPLAIN không bắt được)."""

    if session_ is not None:
        session_.run(f"EXPLAIN {cypher}", **params).consume()
        return
    with session() as s:
        s.run(f"EXPLAIN {cypher}", **params).consume()
