"""
Session có thể dừng / chạy tiếp.

Toàn bộ tiến độ nằm trong một file SQLite `sessions/<tên>/state.db`.
Mỗi PDF là một dòng, mỗi giai đoạn (ocr / fix) có status riêng nên có thể
Ctrl+C bất cứ lúc nào rồi chạy lại — những file đã xong sẽ bị bỏ qua.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import SESSIONS_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (
    key            TEXT PRIMARY KEY,   -- đường dẫn tương đối của PDF
    doc_id         TEXT,
    category       TEXT,
    so_hieu        TEXT,
    title          TEXT,
    stem           TEXT,
    broken_name    INTEGER DEFAULT 0,
    size_bytes     INTEGER,
    pages          INTEGER,
    native_chars   INTEGER,        -- ký tự / trang của lớp text sẵn có
    vi_score       REAL,           -- tỷ lệ dấu tiếng Việt; <0.15 = lớp text hỏng

    ocr_status     TEXT DEFAULT 'pending',  -- pending|done|fallback|failed
    ocr_engine     TEXT,                    -- local|api
    ocr_attempts   INTEGER DEFAULT 0,
    ocr_error      TEXT,
    ocr_seconds    REAL,
    raw_txt        TEXT,
    raw_chars      INTEGER,

    fix_status     TEXT DEFAULT 'pending',  -- pending|done|failed|skipped
    fix_attempts   INTEGER DEFAULT 0,
    fix_error      TEXT,
    fix_seconds    REAL,
    clean_md       TEXT,
    clean_chars    INTEGER,

    updated_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_ocr_status ON docs(ocr_status);
CREATE INDEX IF NOT EXISTS idx_fix_status ON docs(fix_status);

CREATE TABLE IF NOT EXISTS meta (
    k TEXT PRIMARY KEY,
    v TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    ts    TEXT,
    stage TEXT,
    key   TEXT,
    level TEXT,
    msg   TEXT
);
"""

PENDING_OCR = ("pending", "failed")
PENDING_FIX = ("pending", "failed")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Session:
    """Kho trạng thái của một lần chạy pipeline."""

    def __init__(self, name: str):
        self.name = name
        self.dir = SESSIONS_DIR / name
        self.dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.dir / "state.db"

        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(SCHEMA)
        self._migrate()
        self._conn.commit()

        self.set_meta("last_opened", _now())

        if not self.get_meta("created_at"):
            self.set_meta("created_at", _now())

    def _migrate(self) -> None:
        """Thêm cột mới cho session tạo từ phiên bản cũ."""

        existing = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(docs)").fetchall()
        }

        for column, ddl in (("vi_score", "REAL"), ("ocr_engine", "TEXT")):
            if column not in existing:
                self._conn.execute(f"ALTER TABLE docs ADD COLUMN {column} {ddl}")

    # --------------------------------------------------------
    # META
    # --------------------------------------------------------

    def set_meta(self, key: str, value: Any) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO meta(k, v) VALUES(?, ?) "
                "ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                (key, json.dumps(value, ensure_ascii=False)),
            )
            self._conn.commit()

    def get_meta(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._conn.execute(
                "SELECT v FROM meta WHERE k = ?", (key,)
            ).fetchone()

        return json.loads(row["v"]) if row else default

    # --------------------------------------------------------
    # DOCS
    # --------------------------------------------------------

    def register(self, records: Iterable[dict]) -> int:
        """
        Thêm PDF mới vào session. File đã có thì giữ nguyên tiến độ, chỉ cập
        nhật `vi_score` (chỉ số này được thêm về sau nên cần backfill).
        """

        with self._lock:
            before = self._conn.execute(
                "SELECT COUNT(*) AS n FROM docs"
            ).fetchone()["n"]

            for record in records:
                self._conn.execute(
                    """
                    INSERT INTO docs (
                        key, doc_id, category, so_hieu, title, stem,
                        broken_name, size_bytes, pages, native_chars, vi_score,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        vi_score = excluded.vi_score
                    """,
                    (
                        record["key"],
                        record.get("doc_id", ""),
                        record.get("category", ""),
                        record.get("so_hieu", ""),
                        record.get("title", ""),
                        record.get("stem", ""),
                        int(record.get("broken_name", False)),
                        record.get("size_bytes"),
                        record.get("pages"),
                        record.get("native_chars"),
                        record.get("vi_score"),
                        _now(),
                    ),
                )

            after = self._conn.execute(
                "SELECT COUNT(*) AS n FROM docs"
            ).fetchone()["n"]

            self._conn.commit()

        return after - before

    def update(self, key: str, **fields: Any) -> None:
        if not fields:
            return

        fields["updated_at"] = _now()

        assignments = ", ".join(f"{name} = ?" for name in fields)
        values = list(fields.values()) + [key]

        with self._lock:
            self._conn.execute(
                f"UPDATE docs SET {assignments} WHERE key = ?", values
            )
            self._conn.commit()

    def bump_attempt(self, key: str, stage: str) -> None:
        column = "ocr_attempts" if stage == "ocr" else "fix_attempts"

        with self._lock:
            self._conn.execute(
                f"UPDATE docs SET {column} = {column} + 1, updated_at = ? "
                "WHERE key = ?",
                (_now(), key),
            )
            self._conn.commit()

    def get(self, key: str) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM docs WHERE key = ?", (key,)
            ).fetchone()

    def all_docs(self) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM docs ORDER BY category, doc_id"
            ).fetchall()

    def todo_ocr(self, limit: int | None = None, retry_failed: bool = True):
        statuses = PENDING_OCR if retry_failed else ("pending",)
        placeholders = ", ".join("?" * len(statuses))

        query = (
            f"SELECT * FROM docs WHERE ocr_status IN ({placeholders}) "
            "ORDER BY size_bytes ASC"
        )
        params: list[Any] = list(statuses)

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        with self._lock:
            return self._conn.execute(query, params).fetchall()

    def todo_fix(self, limit: int | None = None, retry_failed: bool = True):
        """Chỉ hiệu đính các file đã có text (ocr done hoặc fallback)."""

        statuses = PENDING_FIX if retry_failed else ("pending",)
        placeholders = ", ".join("?" * len(statuses))

        query = (
            f"SELECT * FROM docs WHERE fix_status IN ({placeholders}) "
            "AND ocr_status IN ('done', 'fallback') "
            "AND raw_chars > 0 "
            "ORDER BY raw_chars ASC"
        )
        params: list[Any] = list(statuses)

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        with self._lock:
            return self._conn.execute(query, params).fetchall()

    # --------------------------------------------------------
    # EVENTS / STATS
    # --------------------------------------------------------

    def log(self, stage: str, key: str, level: str, msg: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO events(ts, stage, key, level, msg) "
                "VALUES(?, ?, ?, ?, ?)",
                (_now(), stage, key, level, msg[:2000]),
            )
            self._conn.commit()

    def counts(self, column: str) -> dict[str, int]:
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {column} AS status, COUNT(*) AS n "
                f"FROM docs GROUP BY {column}"
            ).fetchall()

        return {row["status"]: row["n"] for row in rows}

    def total(self) -> int:
        with self._lock:
            return self._conn.execute(
                "SELECT COUNT(*) AS n FROM docs"
            ).fetchone()["n"]

    def recent_errors(self, limit: int = 15):
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM events WHERE level = 'error' "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()

    def reset(self, stage: str, only_failed: bool = True) -> int:
        """Đặt lại một giai đoạn về `pending` để chạy lại."""

        prefix = "ocr" if stage == "ocr" else "fix"
        condition = f"WHERE {prefix}_status = 'failed'" if only_failed else ""

        with self._lock:
            cursor = self._conn.execute(
                f"UPDATE docs SET {prefix}_status = 'pending', "
                f"{prefix}_error = NULL, updated_at = '{_now()}' {condition}"
            )
            self._conn.commit()

        return cursor.rowcount

    def close(self) -> None:
        with self._lock:
            self._conn.commit()
            self._conn.close()


def list_sessions() -> list[Path]:
    if not SESSIONS_DIR.exists():
        return []

    return sorted(
        path for path in SESSIONS_DIR.iterdir() if (path / "state.db").exists()
    )
