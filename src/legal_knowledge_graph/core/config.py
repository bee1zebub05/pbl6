"""
Cấu hình riêng cho legal_knowledge_graph — KHÔNG import src/vanban/config.py,
KHÔNG dùng chung biến môi trường với pipeline tự động (tiền tố LKG_ riêng).
File .env vật lý dùng CHUNG với repo (gộp theo yêu cầu merge hạ tầng — env/
requirements/docker/run — về một chỗ), nhưng namespace biến vẫn tách biệt
hoàn toàn, nên module này vẫn chạy độc lập được về mặt logic/kết nối.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# core/config.py -> parents: [0]=core [1]=legal_knowledge_graph [2]=src [3]=<goc repo>
ROOT = Path(__file__).resolve().parents[1]  # legal_knowledge_graph/
REPO_ROOT = Path(__file__).resolve().parents[3]

load_dotenv(REPO_ROOT / ".env")

SCHEMA_PATH = ROOT / "schema" / "document.schema.json"
REFERENCE_DIR = ROOT / "reference"
ORGANIZATIONS_SEED_PATH = REFERENCE_DIR / "organizations_seed.json"
TOPICS_SEED_PATH = REFERENCE_DIR / "topics_seed.json"
TARGET_GROUPS_SEED_PATH = REFERENCE_DIR / "target_groups_seed.json"
DEFAULT_DATA_DIR = ROOT / "samples"

# Trỏ vào container Neo4j THỨ HAI, tách biệt hoàn toàn khỏi instance của
# pipeline tự động (src/vanban). Không dùng chung port/biến môi trường.
NEO4J_URI = os.getenv("LKG_NEO4J_URI", "bolt://localhost:7688")
NEO4J_USER = os.getenv("LKG_NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("LKG_NEO4J_PASSWORD", "lkg12345678")
NEO4J_DATABASE = os.getenv("LKG_NEO4J_DATABASE", "neo4j")

BATCH_SIZE = 500

# ============================================================
# NLQ (core/nlq/) — Gemini key/model RIÊNG của module này, KHÔNG dùng
# chung với GEMINI_* ở .env gốc repo (đó chỉ phục vụ hiệu đính OCR trong
# src/vanban, không liên quan truy vấn đồ thị — giữ đúng quy tắc tách biệt).
# ============================================================
def nlq_gemini_keys() -> list[str]:
    """Bể key cho NLQ, theo thứ tự ưu tiên, bỏ trùng và giữ nguyên thứ tự.

      1. LKG_GEMINI_API_KEY_<n>  — đánh số tuỳ ý, không cần liên tục
      2. LKG_GEMINI_API_KEY      — cách cũ một key, vẫn chạy
      3. LKG_GEMINI_API_KEYS     — tất cả trên một dòng, ngăn bằng dấu phẩy
      4. GEMMA_API_KEY<...>      — DÙNG CHUNG bể của tools/gemini_api/

    Mục 4 là ngoại lệ có chủ đích với nguyên tắc tách namespace nêu ở đầu
    file, và chỉ chạm tới khi ba mục trên đều rỗng. Lý do: free tier chặn
    20 request/NGÀY/project/model, một key không đủ cho cả `nlq-eval`
    (19 câu) lẫn chat UI. Để key ở MỘT chỗ thì xoay key chỉ phải sửa một
    chỗ. Muốn tách hẳn thì cứ điền LKG_GEMINI_API_KEY_0 — nó thắng.
    """
    ra: list[str] = []

    def them(v: str) -> None:
        for k in v.split(","):
            k = k.strip().strip('"').strip("'")
            if k and k not in ra:
                ra.append(k)

    def theo_so(muc):
        return int(muc[0].rsplit("_", 1)[1])

    danh_so = [(t, v) for t, v in os.environ.items()
               if t.startswith("LKG_GEMINI_API_KEY_") and t[19:].isdigit()]
    for ten, gia_tri in sorted(danh_so, key=theo_so):
        them(gia_tri)
    them(os.getenv("LKG_GEMINI_API_KEY", ""))
    them(os.getenv("LKG_GEMINI_API_KEYS", ""))
    if ra:
        return ra

    them(os.getenv("GEMMA_API_KEY", ""))
    danh_so = [(t, v) for t, v in os.environ.items()
               if t.startswith("GEMMA_API_KEY_") and t[14:].isdigit()]
    for ten, gia_tri in sorted(danh_so, key=theo_so):
        them(gia_tri)
    them(os.getenv("GEMMA_API_KEYS", ""))
    return ra


# Giữ lại cho tương thích ngược: key đầu bể. Code mới dùng nlq_gemini_keys().
NLQ_GEMINI_API_KEY = (nlq_gemini_keys() or [""])[0]
NLQ_GEMINI_MODEL = os.getenv("LKG_GEMINI_MODEL", "gemini-3.6-flash")

# Stage A: độ tin cậy tối thiểu để chấp nhận 1 template match; dưới ngưỡng
# này thì rơi xuống Stage B (freeform).
NLQ_TEMPLATE_CONFIDENCE_MIN = float(os.getenv("LKG_NLQ_TEMPLATE_CONFIDENCE_MIN", "0.6"))

# Số dòng tối đa cho MỌI truy vấn NLQ (cả template lẫn freeform).
NLQ_ROW_CAP = int(os.getenv("LKG_NLQ_ROW_CAP", "200"))

# Timeout Cypher phía server (giây), áp dụng qua Session.begin_transaction()
# — xem core/nlq/execute.py để biết vì sao KHÔNG dùng session.run(timeout=).
NLQ_QUERY_TIMEOUT_SECONDS = float(os.getenv("LKG_NLQ_QUERY_TIMEOUT_SECONDS", "10"))
