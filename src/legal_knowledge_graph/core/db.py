"""
Kết nối Neo4j của module — chỗ DUY NHẤT tạo driver và chạy Cypher.

  Neo4jConnection  một driver sống suốt tiến trình (chatbot, API)
  session()        mở rồi đóng driver mỗi lần (lệnh CLI chạy một lần: nạp, benchmark, backfill)
  run_in_session   chạy Cypher ĐỌC có timeout thật
  explain          kiểm cú pháp/plan bằng EXPLAIN, không đụng dữ liệu
  run_batched      chạy Cypher GHI theo lô

QUAN TRỌNG về timeout: driver cài thật là neo4j==6.3.1. `session.run(query,
timeout=N)` KHÔNG hoạt động như timeout — extra kwargs của `run()` bị coi là
Cypher parameter (`$timeout`) vô nghĩa (đã xác minh trong
site-packages/neo4j/_sync/work/session.py). Timeout thật phải qua
`Session.begin_transaction(timeout=...)`.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass

from neo4j import Driver, GraphDatabase

from . import config


def _new_driver() -> Driver:
    return GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))


class Neo4jConnection:
    """Giữ một Driver dùng chung (thread-safe theo thiết kế của neo4j driver), mở lười."""

    def __init__(self) -> None:
        self._driver: Driver | None = None
        self._lock = threading.Lock()

    @property
    def driver(self) -> Driver:
        with self._lock:
            if self._driver is None:
                self._driver = _new_driver()
            return self._driver

    def session(self):
        return self.driver.session(database=config.NEO4J_DATABASE)

    def close(self) -> None:
        with self._lock:
            if self._driver is not None:
                self._driver.close()
                self._driver = None


@contextmanager
def session():
    driver = _new_driver()
    try:
        with driver.session(database=config.NEO4J_DATABASE) as s:
            yield s
    finally:
        driver.close()


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
    return ExecutionResult(rows=rows, elapsed_ms=(time.perf_counter() - start) * 1000)


def explain(cypher: str, params: dict, session_) -> None:
    """Raise nếu cú pháp/plan sai. Không raise KHÔNG có nghĩa Cypher đúng ngữ
    nghĩa — graph_query/cypher_guard.py kiểm thêm whitelist label/property.
    Nhận session có sẵn để dùng lại đúng phiên sẽ chạy Cypher thật."""

    session_.run(f"EXPLAIN {cypher}", **params).consume()


def run_batched(session_, cypher: str, rows: list[dict]) -> dict[str, int]:
    """Chạy một Cypher ghi (`UNWIND $rows ...`) theo lô BATCH_SIZE dòng, cộng
    dồn bộ đếm. Dùng cho nạp graph (ingest/) và backfill embedding."""

    totals = {"nodes_created": 0, "relationships_created": 0, "properties_set": 0}
    for start in range(0, len(rows), config.BATCH_SIZE):
        chunk = rows[start:start + config.BATCH_SIZE]
        if not chunk:
            continue
        counters = session_.run(cypher, rows=chunk).consume().counters
        totals["nodes_created"] += counters.nodes_created
        totals["relationships_created"] += counters.relationships_created
        totals["properties_set"] += counters.properties_set
    return totals
