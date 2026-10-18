"""Cho phép import `core.*` như khi chạy qua run.py (gốc module là legal_knowledge_graph/).

Kiểm thử không bao giờ gửi trace lên LangSmith (mỗi lượt pytest sinh hàng chục
trace, tiêu hạn mức tháng) và không ghi log phiên vào logs/sessions/ (test cần
thì tự bật vào thư mục tạm). Đặt TRƯỚC khi import `core` — load_dotenv không ghi
đè biến môi trường đã có, nên giá trị trong .env không bật lại được.
"""

import os
import sys
from pathlib import Path

os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LKG_SESSION_LOG"] = "false"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
