"""
Cấu hình riêng cho legal_knowledge_graph — KHÔNG import src/vanban/config.py,
KHÔNG dùng chung biến môi trường với pipeline tự động (tiền tố LKG_ riêng).
File .env vật lý dùng CHUNG với repo (gộp theo yêu cầu merge hạ tầng — env/
requirements/docker/run — về một chỗ), nhưng namespace biến vẫn tách biệt
hoàn toàn, nên module này vẫn chạy độc lập được về mặt logic/kết nối.

Ngoại lệ có chủ đích: key Gemini cho NLQ (nlq_gemini_keys()) dùng CHUNG bể
với GEMINI_API_KEY_*/GEMMA_API_KEY_* của các module khác trong repo — xem
docstring hàm đó.
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
ALIASES_SEED_PATH = REFERENCE_DIR / "aliases_seed.json"
DEFAULT_DATA_DIR = ROOT / "samples"

# Trỏ vào container Neo4j THỨ HAI, tách biệt hoàn toàn khỏi instance của
# pipeline tự động (src/vanban). Không dùng chung port/biến môi trường.
NEO4J_URI = os.getenv("LKG_NEO4J_URI", "bolt://localhost:7688")
NEO4J_USER = os.getenv("LKG_NEO4J_USER", "neo4j")
# Mật khẩu mặc định KHỚP NEO4J_AUTH trong docker-compose.yml — chỉ dùng cho
# container local dev đi kèm repo, không phải secret thật. Deploy nơi khác
# PHẢI set LKG_NEO4J_PASSWORD qua .env, không dựa vào default này.
NEO4J_PASSWORD = os.getenv("LKG_NEO4J_PASSWORD", "lkg12345678")
NEO4J_DATABASE = os.getenv("LKG_NEO4J_DATABASE", "neo4j")

BATCH_SIZE = 500

# ============================================================
# NLQ (core/nlq/) — Gemini key/model RIÊNG của module này, KHÔNG dùng
# chung với GEMINI_* ở .env gốc repo (đó chỉ phục vụ hiệu đính OCR trong
# src/vanban, không liên quan truy vấn đồ thị — giữ đúng quy tắc tách biệt).
# ============================================================
def nlq_gemini_keys() -> list[str]:
    """Bể key CHUNG cho NLQ — gộp cả ba nguồn key Gemini có trong .env,
    bỏ trùng (theo giá trị key) và giữ nguyên thứ tự xuất hiện đầu tiên:

      1. LKG_GEMINI_API_KEY_<n> / LKG_GEMINI_API_KEY / LKG_GEMINI_API_KEYS
      2. GEMINI_API_KEY_<n> / GEMINI_API_KEY / GEMINI_API_KEYS   — bể của src/vanban (hiệu đính OCR)
      3. GEMMA_API_KEY_<n> / GEMMA_API_KEY / GEMMA_API_KEYS       — bể của tools/gemini_api/

    Trước đây 3 nguồn này đọc theo THỨ TỰ ƯU TIÊN (nguồn sau chỉ được đọc
    khi nguồn trước rỗng hoàn toàn) — đổi thành GỘP CHUNG một bể theo yêu
    cầu người dùng: quota Gemini tính theo KEY (PerProjectPerDayPerModel),
    không theo module gọi, nên càng nhiều key trong bể, NLQ (backfill
    embedding, chat UI, nlq-eval) càng ít phải chờ cooldown. Đánh số tuỳ
    ý, không cần liên tục.
    """
    ra: list[str] = []

    def them(v: str) -> None:
        for k in v.split(","):
            k = k.strip().strip('"').strip("'")
            if k and k not in ra:
                ra.append(k)

    def theo_so(ten: str) -> int:
        return int(ten.rsplit("_", 1)[1])

    for tien_to in ("LKG_GEMINI_API_KEY_", "GEMINI_API_KEY_", "GEMMA_API_KEY_"):
        danh_so = [t for t in os.environ
                   if t.startswith(tien_to) and t[len(tien_to):].isdigit()]
        for ten in sorted(danh_so, key=theo_so):
            them(os.environ[ten])

    for ten_don in ("LKG_GEMINI_API_KEY", "GEMINI_API_KEY", "GEMMA_API_KEY"):
        them(os.getenv(ten_don, ""))

    for ten_list in ("LKG_GEMINI_API_KEYS", "GEMINI_API_KEYS", "GEMMA_API_KEYS"):
        them(os.getenv(ten_list, ""))

    return ra


NLQ_GEMINI_MODEL = os.getenv("LKG_GEMINI_MODEL", "gemini-3.6-flash")

# Stage A: độ tin cậy tối thiểu để chấp nhận 1 template match; dưới ngưỡng
# này thì rơi xuống Stage B (freeform).
NLQ_TEMPLATE_CONFIDENCE_MIN = float(os.getenv("LKG_NLQ_TEMPLATE_CONFIDENCE_MIN", "0.6"))

# Số dòng tối đa cho MỌI truy vấn NLQ (cả template lẫn freeform).
NLQ_ROW_CAP = int(os.getenv("LKG_NLQ_ROW_CAP", "200"))

# Timeout Cypher phía server (giây), áp dụng qua Session.begin_transaction()
# — xem core/nlq/execute.py để biết vì sao KHÔNG dùng session.run(timeout=).
NLQ_QUERY_TIMEOUT_SECONDS = float(os.getenv("LKG_NLQ_QUERY_TIMEOUT_SECONDS", "10"))

# Số lượt tối đa hệ thống chủ động hỏi lại 1 tham số còn thiếu/mơ hồ trước
# khi bỏ cuộc hẳn (unsupported) — xem core/nlq/pipeline.py::_run_template().
NLQ_MAX_CLARIFY_ROUNDS = int(os.getenv("LKG_NLQ_MAX_CLARIFY_ROUNDS", "2"))

# Số lần tối đa Stage B (freeform) được tự sửa Cypher sau khi bị guard.py
# chặn, trước khi bỏ cuộc hẳn — xem core/nlq/pipeline.py::_run_freeform().
NLQ_FREEFORM_MAX_ATTEMPTS = int(os.getenv("LKG_NLQ_FREEFORM_MAX_ATTEMPTS", "2"))

# ============================================================
# Retrieval ngữ nghĩa (embedding) trên Article — chạy song song Cypher,
# xem core/nlq/retrieval.py, core/nlq/embed_articles.py.
# ============================================================

# Đã xác nhận bằng lệnh gọi thật (không suy đoán): model tồn tại trên bể
# key đang dùng, output_dimensionality=768 hoạt động đúng.
NLQ_EMBED_MODEL = os.getenv("LKG_EMBED_MODEL", "gemini-embedding-001")
NLQ_EMBED_DIMENSIONS = int(os.getenv("LKG_EMBED_DIMENSIONS", "768"))

# Số Article đọc mỗi lượt round-trip Neo4j (embed_articles.py).
NLQ_EMBED_READ_BATCH_SIZE = int(os.getenv("LKG_EMBED_READ_BATCH_SIZE", "200"))
# Số text gộp vào 1 lần gọi embed_content() — giảm số request thật gửi đi.
NLQ_EMBED_API_BATCH_SIZE = int(os.getenv("LKG_EMBED_API_BATCH_SIZE", "32"))

NLQ_RETRIEVAL_TOP_K = int(os.getenv("LKG_RETRIEVAL_TOP_K", "5"))
NLQ_VECTOR_INDEX_NAME = os.getenv("LKG_VECTOR_INDEX_NAME", "article_embedding")

# Tắt được để nlq-eval/test thường ngày không tốn gấp đôi quota Gemini —
# chat UI thật vẫn mặc định bật (đúng quyết định "chạy cho mọi câu hỏi").
NLQ_RETRIEVAL_ENABLED = os.getenv("LKG_RETRIEVAL_ENABLED", "true").lower() == "true"
