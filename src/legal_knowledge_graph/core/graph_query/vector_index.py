"""
Vector index trên Article.embedding — tạo, đọc số chiều, dựng lại.

Tạo ở bước build (rẻ, idempotent) nhưng ĐỔ embedding chỉ qua lệnh riêng
`lkg embed-articles` (tốn quota). Số chiều của index cố định lúc tạo — đổi
model / số chiều embedding phải dựng lại (`reset`), "IF NOT EXISTS" không tự
sửa số chiều cũ.
"""

from __future__ import annotations

from .. import config

_CREATE = """
CREATE VECTOR INDEX {index_name} IF NOT EXISTS
FOR (a:Article) ON (a.embedding)
OPTIONS {{indexConfig: {{
  `vector.dimensions`: {dimensions},
  `vector.similarity_function`: 'cosine'
}}}}
"""


def ensure(session_) -> None:
    session_.run(_CREATE.format(index_name=config.VECTOR_INDEX_NAME, dimensions=config.EMBED_DIMENSIONS))


def dimensions(session_) -> int | None:
    """Số chiều của index đang có trong Neo4j; None nếu chưa có index."""

    row = session_.run("SHOW INDEXES YIELD name, options WHERE name = $name RETURN options",
                       name=config.VECTOR_INDEX_NAME).single()
    if row is None:
        return None
    return int(row["options"]["indexConfig"]["vector.dimensions"])


def reset(session_) -> int:
    """Xoá index và MỌI embedding Article, rồi tạo lại index theo EMBED_DIMENSIONS.
    -> số Article đã xoá embedding."""

    session_.run(f"DROP INDEX {config.VECTOR_INDEX_NAME} IF EXISTS")
    removed = session_.run(
        "MATCH (a:Article) WHERE a.embedding IS NOT NULL "
        "CALL (a) { REMOVE a.embedding } IN TRANSACTIONS OF 1000 ROWS RETURN count(a) AS n"
    ).single()["n"]
    ensure(session_)
    return removed
