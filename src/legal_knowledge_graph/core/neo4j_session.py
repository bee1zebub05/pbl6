"""
Contextmanager mở 1 Neo4j session — dùng CHUNG cho graph_loader.py,
core/query/runner.py, core/nlq/execute.py. Trước đây mỗi nơi tự viết tay
`GraphDatabase.driver(...)` + `try/finally: driver.close()` (3 bản gần
như giống hệt nhau, một chỗ sửa thường quên sửa 2 chỗ còn lại).
"""

from __future__ import annotations

from contextlib import contextmanager

from neo4j import GraphDatabase

from . import config


@contextmanager
def session():
    driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
    try:
        with driver.session(database=config.NEO4J_DATABASE) as s:
            yield s
    finally:
        driver.close()
