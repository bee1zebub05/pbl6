"""
Cấu hình tập trung cho toàn bộ pipeline.

Mọi đường dẫn đều tính từ ROOT (thư mục gốc của project) nên script chạy
được từ bất kỳ chỗ nào.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"

RAW_DIR = DATA_DIR / "raw"
PDF_DIR = RAW_DIR / "pdf"
METADATA_CSV = RAW_DIR / "metadata.csv"

INTERIM_DIR = DATA_DIR / "interim"
OCR_PDF_DIR = INTERIM_DIR / "ocr_pdf"

PROCESSED_DIR = DATA_DIR / "processed"
TEXT_RAW_DIR = PROCESSED_DIR / "text_raw"
# Tầng giữa: text OCR đã tiêm số hiệu/ngày từ metadata và chuẩn hoá trích dẫn.
# Tách riêng để text_raw luôn giữ nguyên hiện trạng OCR, phục vụ đối chiếu.
TEXT_NORM_DIR = PROCESSED_DIR / "text_norm"
TEXT_CLEAN_DIR = PROCESSED_DIR / "text_clean"

MANIFEST_PATH = DATA_DIR / "manifest.jsonl"

# Kho text đã hiệu đính dùng để xây knowledge graph.
#
# Không trỏ vào TEXT_CLEAN_DIR: bước hiệu đính cuối cùng chạy ngoài pipeline
# (Colab) rồi tải kết quả về đây, nên đường dẫn khác với chỗ pipeline tự ghi.
# Đổi được bằng KG_CORPUS_DIR trong .env hoặc `--corpus` khi chạy.
KG_CORPUS_DIR = Path(
    os.getenv("KG_CORPUS_DIR", "") or DATA_DIR / "clean" / "text_clean_gemma"
)

# Node / quan hệ đã trích xuất, dạng JSONL, sẵn sàng nạp vào Neo4j.
KG_DIR = DATA_DIR / "kg"

# Toàn bộ đầu ra của khối đánh giá §6: gold set, phiếu gán, số đo, báo cáo.
# Mọi thứ ở đây là FILE — chạy ở máy nào cũng chỉ cần copy thư mục này về.
EVAL_DIR = DATA_DIR / "eval"

SESSIONS_DIR = ROOT / "sessions"
LOGS_DIR = ROOT / "logs"


# ============================================================
# NEO4J
# ============================================================

# Mặc định khớp với lệnh docker trong docs: NEO4J_AUTH=neo4j/12345678.
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "12345678")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")


def ensure_dirs() -> None:
    """Tạo sẵn toàn bộ thư mục cần thiết."""

    for path in (
        RAW_DIR,
        PDF_DIR,
        INTERIM_DIR,
        PROCESSED_DIR,
        TEXT_RAW_DIR,
        TEXT_NORM_DIR,
        TEXT_CLEAN_DIR,
        KG_DIR,
        EVAL_DIR,
        SESSIONS_DIR,
        LOGS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


# ============================================================
# OCR API
# ============================================================

OCR_BASE_URL = os.getenv(
    "OCR_BASE_URL",
    "http://104.37.191.24:7600",
).rstrip("/")

OCR_ENDPOINT = f"{OCR_BASE_URL}/v1/ocr"

OCR_LANGUAGES = [
    lang.strip()
    for lang in os.getenv("OCR_LANGUAGES", "vie").split(",")
    if lang.strip()
]

# API upstream xoay vòng nhiều key, thỉnh thoảng trả 500/401 -> phải retry.
OCR_MAX_ATTEMPTS = int(os.getenv("OCR_MAX_ATTEMPTS", "5"))
OCR_UPLOAD_TIMEOUT = int(os.getenv("OCR_UPLOAD_TIMEOUT", "900"))
OCR_DOWNLOAD_TIMEOUT = int(os.getenv("OCR_DOWNLOAD_TIMEOUT", "600"))
OCR_BACKOFF_BASE = float(os.getenv("OCR_BACKOFF_BASE", "3"))
OCR_BACKOFF_MAX = float(os.getenv("OCR_BACKOFF_MAX", "60"))

OCR_WORKERS = int(os.getenv("OCR_WORKERS", "3"))

# Dừng OCR khi credit còn dưới mức này, chừa lại một ít để còn xoay xở.
# Session nhớ chỗ đang dở -> nạp thêm credit rồi chạy lại là đi tiếp.
OCR_MIN_CREDITS = int(os.getenv("OCR_MIN_CREDITS", "100"))


# ============================================================
# OCR NỘI BỘ (EasyOCR, chạy trên CPU)
# ============================================================

# "local" = EasyOCR chạy tại máy (miễn phí, không giới hạn, chính xác hơn API)
# "api"   = gọi API OCR (nhanh hơn nhưng tốn credit)
OCR_ENGINE = os.getenv("OCR_ENGINE", "local").strip().lower()

LOCAL_OCR_LANGS = [
    lang.strip()
    for lang in os.getenv("LOCAL_OCR_LANGS", "vi").split(",")
    if lang.strip()
]

# 150 DPI: đo thực tế 120->300 DPI độ chính xác gần như không đổi nhưng
# 300 DPI chậm hơn 2,3 lần.
LOCAL_OCR_DPI = int(os.getenv("LOCAL_OCR_DPI", "150"))

# 4 tiến trình x 3 luồng torch -> 431 trang/giờ, thêm nữa không nhanh hơn.
LOCAL_OCR_WORKERS = int(os.getenv("LOCAL_OCR_WORKERS", "4"))
LOCAL_OCR_THREADS = int(os.getenv("LOCAL_OCR_THREADS", "3"))

# Bật khi chạy trên máy có GPU (Colab, ...). Lúc đó ĐỂ WORKERS=1: nhiều tiến
# trình cùng nạp model lên một GPU chỉ tổ hết VRAM chứ không nhanh hơn.
LOCAL_OCR_GPU = os.getenv("LOCAL_OCR_GPU", "false").lower() in ("1", "true", "yes")

# Link download chỉ sống 300s -> tải ngay, không xếp hàng.
OCR_KEEP_PDF = os.getenv("OCR_KEEP_PDF", "false").lower() in ("1", "true", "yes")


# ============================================================
# GEMINI
# ============================================================

def _collect_gemini_keys() -> list[tuple[str, str]]:
    """
    Gom mọi API key Gemini trong .env, trả về [(nhãn, key), ...] đã khử trùng.

    Chấp nhận cả ba cách khai báo:
        GEMINI_API_KEY=...              (một key, cách cũ)
        GEMINI_API_KEY_0=...            (nhiều key, đánh số tuỳ ý)
        GEMINI_API_KEYS=key1,key2,...   (nhiều key trên một dòng)

    Key đánh số được sắp theo SỐ chứ không theo chuỗi, để _10 đứng sau _9.
    """

    found: list[tuple[tuple[int, str], str, str]] = []

    for name, value in os.environ.items():
        if not name.startswith("GEMINI_API_KEY"):
            continue

        suffix = name[len("GEMINI_API_KEY"):].lstrip("_")

        if name == "GEMINI_API_KEYS":
            for i, part in enumerate(value.split(",")):
                if part.strip():
                    found.append(((2, f"{i:04d}"), f"KEYS[{i}]", part.strip()))
            continue

        key = value.strip()

        if not key:
            continue

        if not suffix:
            found.append(((0, ""), "GEMINI_API_KEY", key))
        elif suffix.isdigit():
            found.append(((1, f"{int(suffix):04d}"), f"#{suffix}", key))
        else:
            found.append(((3, suffix), name, key))

    found.sort(key=lambda item: item[0])

    seen: set[str] = set()
    keys: list[tuple[str, str]] = []

    for _, label, key in found:
        if key in seen:
            continue

        seen.add(key)
        keys.append((label, key))

    return keys


# Danh sách [(nhãn, key)] — pipeline xoay vòng qua đây, key nào dính 429 thì
# cho nghỉ rồi dùng key khác (xem key_pool.py).
GEMINI_API_KEYS = _collect_gemini_keys()

# Giữ lại tên cũ cho các chỗ chỉ cần MỘT key (health, models).
GEMINI_API_KEY = GEMINI_API_KEYS[0][1] if GEMINI_API_KEYS else ""

# Dùng Gemma qua Gemini API. Xem model nào key của bạn gọi được:
#     python run.py models
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemma-4-31b-it")

# Số request được BAY CÙNG LÚC trên MỘT key. Free tier tính hạn mức theo phút
# trên từng key, nên chặn ở đây rẻ hơn nhiều so với để nó bắn 429 rồi mới lùi:
# vượt trần là mất luôn cả lượt gọi lẫn thời gian cooldown.
GEMINI_MAX_INFLIGHT_PER_KEY = int(os.getenv("GEMINI_MAX_INFLIGHT_PER_KEY", "2"))

# Không đặt GEMINI_WORKERS -> tự co giãn theo số key. Đặt bằng đúng sức chứa
# của bể (số key x hạn mức mỗi key) để không luồng nào phải nằm chờ vô ích.
GEMINI_WORKERS = int(
    os.getenv("GEMINI_WORKERS")
    or min(16, max(2, GEMINI_MAX_INFLIGHT_PER_KEY * len(GEMINI_API_KEYS)))
)
GEMINI_MAX_ATTEMPTS = int(os.getenv("GEMINI_MAX_ATTEMPTS", "4"))

# Key dính 429 thì nghỉ bao lâu (giây) trước khi được gọi lại. Nếu API có gửi
# kèm `retryDelay` thì dùng con số của API, hai mốc dưới đây là cận dưới/trên.
GEMINI_KEY_COOLDOWN = float(os.getenv("GEMINI_KEY_COOLDOWN", "45"))
GEMINI_KEY_COOLDOWN_MAX = float(os.getenv("GEMINI_KEY_COOLDOWN_MAX", "900"))

# Hết quota NGÀY thì nghỉ hẳn chừng này giây — thử lại sau vài phút chỉ tốn
# công, key đó coi như hết cho hôm nay.
GEMINI_KEY_COOLDOWN_DAILY = float(os.getenv("GEMINI_KEY_COOLDOWN_DAILY", "3600"))

# Cắt văn bản thành từng khối trước khi nhờ Gemini sửa, tránh vượt giới hạn
# output token với các văn bản dài (có file 155 trang).
GEMINI_CHUNK_CHARS = int(os.getenv("GEMINI_CHUNK_CHARS", "7000"))

# Gemma có hạn mức output nhỏ hơn Gemini -> tự hạ trần khi dùng model Gemma.
GEMMA_CHUNK_CHARS = int(os.getenv("GEMMA_CHUNK_CHARS", "4500"))

# Tắt reasoning — tác vụ sửa lỗi chính tả không cần, mà BẬT thì hỏng thật:
# Gemma 4 tiêu 32.765 token vào phần suy nghĩ, chạm trần output rồi trả về RỖNG.
#
# Hai model họ dùng hai tham số KHÁC NHAU (đã đo trên gemma-4-26b-a4b-it):
#   Gemma  : thinking_level="minimal"   (thinking_budget -> 400 not supported)
#   Gemini : thinking_budget=0          (thinking_level  -> 400 not supported)
GEMINI_THINKING_BUDGET = int(os.getenv("GEMINI_THINKING_BUDGET", "0"))
GEMMA_THINKING_LEVEL = os.getenv("GEMMA_THINKING_LEVEL", "minimal")

# Nới rộng để bản hiệu đính của khối dài không bị cắt cụt giữa chừng.
GEMINI_MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "16000"))


# ============================================================
# PIPELINE
# ============================================================

# Số ký tự trung bình / trang tối thiểu để coi PDF là "đã có lớp text".
NATIVE_TEXT_THRESHOLD = int(os.getenv("NATIVE_TEXT_THRESHOLD", "200"))

DEFAULT_SESSION = os.getenv("SESSION_NAME", "default")

# Danh sách lĩnh vực hợp lệ, dùng để phục hồi tên file bị hỏng trong folder "ID".
CATEGORIES = [
    "Công nghệ thông tin, CĐS",
    "Công tác sinh viên",
    "Cơ sở vật chất, xây dựng",
    "Học liệu, truyền thông",
    "Hợp tác quốc tế",
    "Khoa học Công nghệ",
    "Khảo thí",
    "Khác",
    "Pháp chế",
    "Sở hữu trí tuệ",
    "Thanh tra, kiểm tra",
    "Thi đua, khen thưởng",
    "Tuyển sinh",
    "Tài chính, kế toán",
    "Tổ chức, hành chính",
    "Văn thư, lưu trữ",
    "Đào tạo",
    "Đảm bảo chất lượng, KĐCL",
]
