"""
FastAPI mỏng cho chat UI (frontend/) — nhận câu hỏi, gọi ChatService
(core/chat/), trả JSON. Không có logic nghiệp vụ ở đây.

Lỗi trong graph đã được node tự bọc thành kind="error"; handler dưới đây và
exception_handler toàn cục chỉ là lưới an toàn cuối cho lỗi ngoài graph,
luôn trả JSON {"error": "..."} và không để lộ traceback ra response.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .. import config
from ..chat.container import get_chat_service
from ..chat.models import ChatResponse

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Dựng chatbot ngay khi server khởi động: cấu hình LLM / embedding sai thì
    # server không lên và báo lỗi rõ, thay vì lỗi 500 ở câu hỏi đầu tiên.
    get_chat_service()
    yield


app = FastAPI(title="legal_knowledge_graph chat API", lifespan=lifespan)

# Origin lấy từ LKG_CORS_ORIGINS (mặc định chỉ Vite dev server chạy local).
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error_response(context: str) -> JSONResponse:
    """Log đầy đủ phía server, trả message chung chung cho client."""

    logger.exception(context)
    return JSONResponse(status_code=500, content={"error": context})


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=config.CHAT_MAX_QUESTION_CHARS,
                          description="Câu hỏi tiếng Việt tự nhiên")
    thread_id: str | None = Field(default=None, max_length=64,
                                  description="Mã hội thoại; bỏ trống để bắt đầu hội thoại mới")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return _error_response("Lỗi nội bộ")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    # def thường (không async): Starlette chạy trong threadpool, không block
    # event loop — ask() là I/O đồng bộ (Gemini + Neo4j).
    try:
        return get_chat_service().ask(req.question, thread_id=req.thread_id)
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"error": str(exc)})
    except Exception:
        return _error_response("Lỗi khi xử lý câu hỏi")
