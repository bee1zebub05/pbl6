"""
Cấu hình riêng cho legal_knowledge_graph — KHÔNG đọc .env của repo gốc,
KHÔNG import src/vanban/config.py. Module này phải chạy được độc lập hoàn toàn.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]  # legal_knowledge_graph/

load_dotenv(ROOT / ".env")

SCHEMA_PATH = ROOT / "schema" / "document.schema.json"
REFERENCE_DIR = ROOT / "reference"
ORGANIZATIONS_SEED_PATH = REFERENCE_DIR / "organizations_seed.json"
TOPICS_SEED_PATH = REFERENCE_DIR / "topics_seed.json"
DEFAULT_DATA_DIR = ROOT / "samples"

# Trỏ vào container Neo4j THỨ HAI, tách biệt hoàn toàn khỏi instance của
# pipeline tự động (src/vanban). Không dùng chung port/biến môi trường.
NEO4J_URI = os.getenv("LKG_NEO4J_URI", "bolt://localhost:7688")
NEO4J_USER = os.getenv("LKG_NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("LKG_NEO4J_PASSWORD", "lkg12345678")
NEO4J_DATABASE = os.getenv("LKG_NEO4J_DATABASE", "neo4j")

BATCH_SIZE = 500
