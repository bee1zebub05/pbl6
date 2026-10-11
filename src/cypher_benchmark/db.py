"""
Kết nối Neo4j cho bộ đo. Đo trên graph của legal_knowledge_graph nên đọc
CÙNG biến môi trường `LKG_NEO4J_*` (mặc định khớp docker-compose.yml), nhưng
không import mã của module đó — hai bên chỉ chung dữ liệu, không chung code.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

NEO4J_URI = os.getenv("LKG_NEO4J_URI", "bolt://localhost:7688")
NEO4J_USER = os.getenv("LKG_NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("LKG_NEO4J_PASSWORD", "lkg12345678")
NEO4J_DATABASE = os.getenv("LKG_NEO4J_DATABASE", "neo4j")


@contextmanager
def session():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session(database=NEO4J_DATABASE) as s:
            yield s
    finally:
        driver.close()
