"""
Session cho các bước xây knowledge graph — dừng / chạy tiếp được.

Vì sao KHÔNG dùng chung `sessions/<tên>/state.db` của pipeline OCR: bảng `docs`
ở đó khoá theo **đường dẫn PDF**, mà `data/raw/pdf/` giờ không còn trên máy nữa
(đã xoá sau khi OCR xong). Bước xây graph khoá theo **số hiệu** — một khoá
hoàn toàn khác, lại còn phải gộp các văn bản trùng số hiệu (55 nhóm trong kho).
Nhét chung một bảng thì hai khoá chính đá nhau.

Nên KG có DB riêng `sessions/<tên>/kg.db`, cùng thư mục session nên vẫn dùng
chung một cái tên session với pipeline cũ. Mỗi giai đoạn (§8 Ontology) là một
cột `*_status` riêng, thêm giai đoạn mới không phải đụng vào giai đoạn cũ:

    doc_status      Bước 0 — chốt bảng Document
    seg_status      Bước 1 — cắt vùng header / căn cứ / thân / thi hành
    cite_status     Bước 2 — trích + resolve số hiệu
    rel_status      Bước 3 — phân loại quan hệ hiệu lực
    art_status      Bước 4 — NormativeContent + Article
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..config import SESSIONS_DIR

# Các giai đoạn theo lộ trình §8 Ontology, theo đúng thứ tự phụ thuộc.
STAGES = ("doc", "seg", "cite", "rel", "art")

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (
    doc_key         TEXT PRIMARY KEY,   -- so_hieu_key: khoá chính sau khi gộp trùng
    so_hieu         TEXT,               -- dạng chuẩn để hiển thị
    so_hieu_raw     TEXT,               -- nguyên văn metadata, giữ để đối chiếu
    doc_ids         TEXT,               -- doc_id crawler đã gộp, JSON list
    title           TEXT,
    doc_type        TEXT,
    normative_type  TEXT,               -- vế sau của "Quyết định, Quy định" (§2.6)
    org_name        TEXT,
    org_id          TEXT,
    authority_level INTEGER,
    level_note      TEXT,               -- bậc tra từ ontology hay suy rộng
    status          TEXT,               -- CON_HIEU_LUC | HET_HIEU_LUC | CHUA_HIEU_LUC
    issue_date      TEXT,               -- ISO
    effective_date  TEXT,
    expiry_date     TEXT,
    topics          TEXT,               -- JSON list (n->m: có văn bản 2 lĩnh vực)
    file_url        TEXT,
    pages           INTEGER,
    clean_path      TEXT,               -- đường dẫn text đã hiệu đính
    clean_chars     INTEGER,
    meta_source     TEXT,               -- manifest | ten-file
    header_check    TEXT,               -- khop | lech | khong-thay | khong-co-file

    doc_status      TEXT DEFAULT 'pending',
    doc_note        TEXT,
    seg_status      TEXT DEFAULT 'pending',
    cite_status     TEXT DEFAULT 'pending',
    rel_status      TEXT DEFAULT 'pending',
    art_status      TEXT DEFAULT 'pending',

    updated_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_doc_status ON docs(doc_status);
CREATE INDEX IF NOT EXISTS idx_seg_status ON docs(seg_status);

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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class KGSession:
    """Trạng thái xây graph của một lần chạy."""

    def __init__(self, name: str):
        self.name = name
        self.dir = SESSIONS_DIR / name
        self.dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.dir / "kg.db"

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
        self._conn.commit()

        self.set_meta("last_opened", _now())

        if not self.get_meta("created_at"):
            self.set_meta("created_at", _now())

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

    def register(self, records: Iterable[dict]) -> tuple[int, int]:
        """
        Nạp danh sách văn bản vào session. Trả về (thêm mới, cập nhật).

        Chỉ ghi đè phần **đầu vào** (metadata, đường dẫn file). Mọi cột kết quả
        và cột `*_status` giữ nguyên — nhờ vậy chạy lại `kg docs` sau khi bổ
        sung metadata không xoá mất tiến độ của các bước sau.
        """

        added = updated = 0

        with self._lock:
            for record in records:
                cursor = self._conn.execute(
                    """
                    INSERT INTO docs (
                        doc_key, so_hieu, so_hieu_raw, doc_ids, title,
                        topics, file_url, pages, clean_path, meta_source,
                        doc_type, normative_type, org_name,
                        issue_date, effective_date, expiry_date, status,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(doc_key) DO UPDATE SET
                        so_hieu        = excluded.so_hieu,
                        so_hieu_raw    = excluded.so_hieu_raw,
                        doc_ids        = excluded.doc_ids,
                        title          = excluded.title,
                        topics         = excluded.topics,
                        file_url       = excluded.file_url,
                        pages          = excluded.pages,
                        clean_path     = excluded.clean_path,
                        meta_source    = excluded.meta_source,
                        updated_at     = excluded.updated_at
                    """,
                    (
                        record["doc_key"],
                        record.get("so_hieu", ""),
                        record.get("so_hieu_raw", ""),
                        json.dumps(record.get("doc_ids", []), ensure_ascii=False),
                        record.get("title", ""),
                        json.dumps(record.get("topics", []), ensure_ascii=False),
                        record.get("file_url"),
                        record.get("pages"),
                        record.get("clean_path"),
                        record.get("meta_source"),
                        record.get("doc_type"),
                        record.get("normative_type"),
                        record.get("org_name"),
                        record.get("issue_date"),
                        record.get("effective_date"),
                        record.get("expiry_date"),
                        record.get("status"),
                        _now(),
                    ),
                )

                if cursor.rowcount == 1:
                    added += 1
                else:
                    updated += 1

            self._conn.commit()

        return added, updated

    def update(self, doc_key: str, **fields: Any) -> None:
        if not fields:
            return

        fields["updated_at"] = _now()

        assignments = ", ".join(f"{name} = ?" for name in fields)
        values = list(fields.values()) + [doc_key]

        with self._lock:
            self._conn.execute(
                f"UPDATE docs SET {assignments} WHERE doc_key = ?", values
            )
            self._conn.commit()

    def todo(self, stage: str, limit: int | None = None) -> list[sqlite3.Row]:
        """Các văn bản chưa xong ở giai đoạn `stage`."""

        if stage not in STAGES:
            raise ValueError(f"Giai đoạn không hợp lệ: {stage}")

        query = (
            f"SELECT * FROM docs WHERE {stage}_status != 'done' "
            "ORDER BY doc_key"
        )
        params: list[Any] = []

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        with self._lock:
            return self._conn.execute(query, params).fetchall()

    def all_docs(self) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM docs ORDER BY authority_level DESC, doc_key"
            ).fetchall()

    def total(self) -> int:
        with self._lock:
            return self._conn.execute(
                "SELECT COUNT(*) AS n FROM docs"
            ).fetchone()["n"]

    def counts(self, column: str) -> dict[str, int]:
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {column} AS v, COUNT(*) AS n FROM docs GROUP BY {column}"
            ).fetchall()

        return {row["v"]: row["n"] for row in rows}

    def flagged(self) -> list[sqlite3.Row]:
        """Văn bản có ghi chú cần soi tay."""

        with self._lock:
            return self._conn.execute(
                "SELECT doc_key, so_hieu, doc_note FROM docs "
                "WHERE doc_note IS NOT NULL AND doc_note != '' ORDER BY doc_key"
            ).fetchall()

    def reset(self, stage: str, only_failed: bool = True) -> int:
        if stage not in STAGES:
            raise ValueError(f"Giai đoạn không hợp lệ: {stage}")

        condition = f"WHERE {stage}_status = 'failed'" if only_failed else ""

        with self._lock:
            cursor = self._conn.execute(
                f"UPDATE docs SET {stage}_status = 'pending', updated_at = ? "
                f"{condition}",
                (_now(),),
            )
            self._conn.commit()

        return cursor.rowcount

    def clear(self) -> int:
        """Xoá sạch bảng docs — dùng khi muốn dựng lại từ đầu."""

        with self._lock:
            cursor = self._conn.execute("DELETE FROM docs")
            self._conn.commit()

        return cursor.rowcount

    # --------------------------------------------------------
    # EVENTS
    # --------------------------------------------------------

    def log(self, stage: str, key: str, level: str, msg: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO events(ts, stage, key, level, msg) "
                "VALUES(?, ?, ?, ?, ?)",
                (_now(), stage, key, level, msg[:2000]),
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.commit()
            self._conn.close()


def list_kg_sessions() -> list[Path]:
    if not SESSIONS_DIR.exists():
        return []

    return sorted(
        path for path in SESSIONS_DIR.iterdir() if (path / "kg.db").exists()
    )
