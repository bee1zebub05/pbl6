"""
FastAPI mỏng cho chat UI (frontend/) — chỉ 1 việc: nhận câu hỏi, gọi thật
core/nlq/pipeline.ask(), trả JSON. KHÔNG tự thêm logic nghiệp vụ ở đây.

Lớp bắt lỗi quan trọng nhất ở module này: pipeline.ask() chỉ tự bọc 3 loại
lỗi thành NlqResult (GeminiCallError, ResolutionFailed, TemplateParamError)
— một lỗi hạ tầng (Neo4j mất kết nối, timeout mạng...) sẽ ném thẳng ra
ngoài ask(), chưa được bắt ở đâu cả. Handler /api/chat và exception_handler
toàn cục dưới đây là nơi chặn lỗi đó lại, luôn trả JSON {"error": "..."},
không bao giờ để lộ traceback thô ra response.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..nlq import pipeline

app = FastAPI(title="legal_knowledge_graph chat API")

# Chỉ mở cho Vite dev server chạy local — demo/prototype, không phải service
# public. Mở rộng origin ở đây nếu sau này deploy nơi khác.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, description="Câu hỏi tiếng Việt tự nhiên")


class ChatResponse(BaseModel):
    kind: str
    template: str | None = None
    cypher: str | None = None
    params: dict | None = None
    rows: list[dict] | None = None
    elapsed_ms: float | None = None
    reason: str | None = None
    confidence: float | None = None


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Lưới an toàn cuối cùng — bất kỳ lỗi nào lọt qua handler bên dưới
    # (kể cả lỗi framework) vẫn trả JSON nhất quán, không trắng trang/HTML.
    return JSONResponse(status_code=500, content={"error": f"Lỗi nội bộ: {exc}"})


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    # def thường (không async): Starlette tự chạy trong threadpool nên
    # không block event loop — ask() là I/O đồng bộ (gọi Gemini + Neo4j).
    try:
        result = pipeline.ask(req.question)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Lỗi khi xử lý câu hỏi: {exc}"})
    return ChatResponse(**result.__dict__)
