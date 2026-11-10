"""
Kết nối Neo4j của module — chỗ DUY NHẤT tạo driver và chạy Cypher.

  Neo4jConnection  một driver sống suốt tiến trình (chatbot, API)
  session()        mở rồi đóng driver mỗi lần (lệnh CLI chạy một lần: nạp, backfill embedding)
  run_in_session   chạy Cypher ĐỌC có timeout thật, trả về kiểu Python thuần
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
from typing import Any

from neo4j import READ_ACCESS, Driver, GraphDatabase
from neo4j.graph import Node, Path, Relationship

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

    def session(self, *, read_only: bool = False):
        """`read_only`: Neo4j từ chối mọi lệnh ghi trong phiên này, kể cả khi lọt qua cypher_guard."""

        if read_only:
            return self.driver.session(database=config.NEO4J_DATABASE, default_access_mode=READ_ACCESS)
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


def _plain(value: Any) -> Any:
    """Đổi kết quả driver thành kiểu thuần: Node/Relationship/ngày giờ không qua được
    checkpoint LangGraph lẫn JSON của API. Bỏ `embedding`: vô nghĩa với LLM và rất dài."""

    if isinstance(value, (Node, Relationship, dict)):
        return {k: _plain(v) for k, v in value.items() if k != "embedding"}
    if isinstance(value, Path):
        return [_plain(n) for n in value.nodes]
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value.iso_format() if hasattr(value, "iso_format") else value


def run_in_session(session_, cypher: str, params: dict, timeout_seconds: float) -> ExecutionResult:
    start = time.perf_counter()
    tx = session_.begin_transaction(timeout=timeout_seconds)
    try:
        result = tx.run(cypher, **params)
        rows = [_plain(dict(r)) for r in result]
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
