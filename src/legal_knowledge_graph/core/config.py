"""
Cấu hình riêng cho legal_knowledge_graph — KHÔNG import src/vanban/config.py,
KHÔNG dùng chung biến môi trường với pipeline tự động (tiền tố LKG_ riêng).
File .env vật lý dùng CHUNG với repo (env/requirements/docker/run để một
chỗ), nhưng namespace biến tách biệt hoàn toàn, nên module này vẫn chạy độc
lập được về mặt logic/kết nối.

Ngoại lệ có chủ đích: key Gemini của chatbot (gemini_keys()) dùng CHUNG bể
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
# LLM của chatbot — đổi nhà cung cấp chỉ bằng biến môi trường:
#   gemini             Gemini Developer API, bể nhiều key xoay vòng (gemini_keys())
#   openai_compatible  mọi server theo chuẩn OpenAI Chat Completions: tự host
#                      (vLLM, Ollama, TGI, LM Studio...) hoặc dịch vụ (OpenAI,
#                      OpenRouter, Together, Groq, DeepSeek...)
# Adapter: core/chat/adapters/; chọn adapter: core/chat/container.py::build_llm.
# Tên biến LKG_NLQ_* bên dưới là tên cũ, giữ để .env hiện có không phải sửa.
# ============================================================
LLM_PROVIDERS = ("gemini", "openai_compatible")
LLM_PROVIDER = os.getenv("LKG_LLM_PROVIDER", "gemini").strip().lower()
# LKG_GEMINI_MODEL là tên cũ, vẫn được đọc khi chưa đặt LKG_LLM_MODEL.
LLM_MODEL = os.getenv("LKG_LLM_MODEL") or os.getenv("LKG_GEMINI_MODEL") or (
    "gemini-3.6-flash" if LLM_PROVIDER == "gemini" else "")
# Chỉ dùng cho openai_compatible. Server tự host không cần key thì để trống.
LLM_BASE_URL = os.getenv("LKG_LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("LKG_LLM_API_KEY", "")
# Cách ép output có cấu trúc (intent, router) với openai_compatible:
#   json_schema       response_format JSON Schema (OpenAI, vLLM, Ollama mới) — mặc định
#   function_calling  qua tool call — cho server chưa hỗ trợ json_schema
#   json_mode         chỉ ép JSON hợp lệ, schema nằm trong prompt — phương án cuối
LLM_STRUCTURED_METHOD = os.getenv("LKG_LLM_STRUCTURED_METHOD", "json_schema")
LLM_TIMEOUT_SECONDS = float(os.getenv("LKG_LLM_TIMEOUT_SECONDS", "60"))
# Số lần SDK tự thử lại (openai_compatible). Gemini không dùng — bể key tự xoay.
LLM_MAX_RETRIES = int(os.getenv("LKG_LLM_MAX_RETRIES", "2"))


def gemini_keys() -> list[str]:
    """Bể key CHUNG cho chatbot — gộp cả ba nguồn key Gemini có trong .env,
    bỏ trùng (theo giá trị key) và giữ nguyên thứ tự xuất hiện đầu tiên:

      1. LKG_GEMINI_API_KEY_<n> / LKG_GEMINI_API_KEY / LKG_GEMINI_API_KEYS
      2. GEMINI_API_KEY_<n> / GEMINI_API_KEY / GEMINI_API_KEYS   — bể của src/vanban (hiệu đính OCR)
      3. GEMMA_API_KEY_<n> / GEMMA_API_KEY / GEMMA_API_KEYS       — bể của tools/gemini_api/

    Gộp chung một bể vì quota Gemini tính theo KEY (PerProjectPerDayPerModel),
    không theo module gọi: càng nhiều key, chatbot (backfill embedding, chat
    UI, chat-eval) càng ít phải chờ cooldown. Đánh số tuỳ ý, không cần liên tục.
    """
    keys: list[str] = []

    def add(value: str) -> None:
        for k in value.split(","):
            k = k.strip().strip('"').strip("'")
            if k and k not in keys:
                keys.append(k)

    def index_of(var: str) -> int:
        return int(var.rsplit("_", 1)[1])

    for prefix in ("LKG_GEMINI_API_KEY_", "GEMINI_API_KEY_", "GEMMA_API_KEY_"):
        numbered = [v for v in os.environ if v.startswith(prefix) and v[len(prefix):].isdigit()]
        for var in sorted(numbered, key=index_of):
            add(os.environ[var])

    for single in ("LKG_GEMINI_API_KEY", "GEMINI_API_KEY", "GEMMA_API_KEY"):
        add(os.getenv(single, ""))

    for listed in ("LKG_GEMINI_API_KEYS", "GEMINI_API_KEYS", "GEMMA_API_KEYS"):
        add(os.getenv(listed, ""))

    return keys


# Số dòng tối đa cho MỌI truy vấn Cypher của chatbot (template lẫn Cypher
# do agent tự viết).
CYPHER_ROW_CAP = int(os.getenv("LKG_NLQ_ROW_CAP", "200"))

# Timeout Cypher phía server (giây), áp dụng qua Session.begin_transaction()
# — xem core/db.py để biết vì sao KHÔNG dùng session.run(timeout=).
CYPHER_TIMEOUT_SECONDS = float(os.getenv("LKG_NLQ_QUERY_TIMEOUT_SECONDS", "10"))

# Số lượt tối đa chatbot hỏi lại một tham số thiếu/mơ hồ trước khi chuyển
# sang agent — xem core/chat/workflow/nodes.py.
MAX_CLARIFY_ROUNDS = int(os.getenv("LKG_NLQ_MAX_CLARIFY_ROUNDS", "2"))

# ============================================================
# Chatbot LangGraph (core/chat/)
# ============================================================

# Số tin nhắn gần nhất đưa vào node intent để viết lại câu hỏi nối tiếp.
CHAT_HISTORY_WINDOW = int(os.getenv("LKG_CHAT_HISTORY_WINDOW", "6"))
# Số vòng LLM -> tool tối đa của agent trước khi dừng.
AGENT_MAX_STEPS = int(os.getenv("LKG_AGENT_MAX_STEPS", "4"))
# Số dòng kết quả Cypher tối đa đưa vào prompt tổng hợp câu trả lời.
ANSWER_MAX_ROWS = int(os.getenv("LKG_ANSWER_MAX_ROWS", "30"))
# Độ dài tối đa câu hỏi nhận từ API/CLI.
CHAT_MAX_QUESTION_CHARS = int(os.getenv("LKG_CHAT_MAX_QUESTION_CHARS", "1000"))
# Origin được gọi API (core/api/app.py), phân tách bằng dấu phẩy. Mặc định chỉ
# Vite dev server chạy local; deploy giao diện ở domain khác thì thêm domain đó.
CORS_ORIGINS = [o.strip() for o in os.getenv(
    "LKG_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]

# Log cục bộ có cấu trúc (core/observability.py).
LOG_LEVEL = os.getenv("LKG_LOG_LEVEL", "INFO").upper()
LOG_DIR = REPO_ROOT / "logs"

# ============================================================
# Embedding Article và GraphRAG — bằng chứng bổ sung cho kết quả Cypher,
# xem core/graph_query/graph_context.py, core/graph_query/article_embeddings.py.
# ============================================================

# Provider embedding chọn độc lập với LLM (core/llm/embeddings.py), cùng hai
# giá trị gemini | openai_compatible. ĐỔI MODEL HOẶC SỐ CHIỀU embedding thì
# vector cũ vô nghĩa với model mới: chạy `lkg embed-articles --reset` để xoá
# embedding cũ, dựng lại vector index theo EMBED_DIMENSIONS rồi embed lại.
EMBED_PROVIDER = os.getenv("LKG_EMBED_PROVIDER", "gemini").strip().lower()
EMBED_MODEL = os.getenv("LKG_EMBED_MODEL", "gemini-embedding-001" if EMBED_PROVIDER == "gemini" else "")
# Phải bằng số chiều model thật sự trả về (embeddings.py kiểm, lệch là báo lỗi).
# gemini-embedding-001 nhận output_dimensionality nên chọn được 768.
EMBED_DIMENSIONS = int(os.getenv("LKG_EMBED_DIMENSIONS", "768"))
# Chỉ dùng cho openai_compatible; để trống thì dùng chung LKG_LLM_BASE_URL / LKG_LLM_API_KEY.
EMBED_BASE_URL = os.getenv("LKG_EMBED_BASE_URL", "") or LLM_BASE_URL
EMBED_API_KEY = os.getenv("LKG_EMBED_API_KEY", "") or LLM_API_KEY

# Số Article đọc mỗi lượt round-trip Neo4j (article_embeddings.py).
EMBED_READ_BATCH_SIZE = int(os.getenv("LKG_EMBED_READ_BATCH_SIZE", "200"))
# Số text gộp vào 1 lần gọi API embedding — giảm số request thật gửi đi.
EMBED_API_BATCH_SIZE = int(os.getenv("LKG_EMBED_API_BATCH_SIZE", "32"))

VECTOR_INDEX_NAME = os.getenv("LKG_VECTOR_INDEX_NAME", "article_embedding")

# GraphRAG (core/graph_query/graph_context.py, core/chat/retrieval/graph_rag.py).
# Số Điều hạt giống giữ lại sau khi gộp vector + fulltext bằng RRF.
RETRIEVAL_TOP_K = int(os.getenv("LKG_RETRIEVAL_TOP_K", "5"))
# Số ứng viên lấy từ MỖI nguồn (vector, fulltext) trước khi gộp.
GRAPH_RAG_SEED_K = int(os.getenv("LKG_GRAPH_RAG_SEED_K", "8"))
# Số văn bản (từ kết quả template) được lấy thêm Điều gần nghĩa bên trong, và số Điều mỗi văn bản.
GRAPH_RAG_SCOPE_DOCS = int(os.getenv("LKG_GRAPH_RAG_SCOPE_DOCS", "5"))
GRAPH_RAG_SCOPE_PER_DOC = int(os.getenv("LKG_GRAPH_RAG_SCOPE_PER_DOC", "2"))
# Số văn bản liên quan tối đa mỗi loại quan hệ (thay thế, bãi bỏ, sửa đổi, căn cứ).
GRAPH_RAG_MAX_RELATED = int(os.getenv("LKG_GRAPH_RAG_MAX_RELATED", "3"))
# Ngân sách ký tự toàn văn Điều đưa vào prompt, và mức cắt mỗi Điều.
GRAPH_RAG_CONTEXT_CHARS = int(os.getenv("LKG_GRAPH_RAG_CONTEXT_CHARS", "12000"))
GRAPH_RAG_ARTICLE_CHARS = int(os.getenv("LKG_GRAPH_RAG_ARTICLE_CHARS", "1500"))

# Tắt được để chat-eval/test thường ngày không tốn thêm quota embedding —
# chat UI thật vẫn mặc định bật (đúng quyết định "chạy cho mọi câu hỏi").
RETRIEVAL_ENABLED = os.getenv("LKG_RETRIEVAL_ENABLED", "true").lower() == "true"
