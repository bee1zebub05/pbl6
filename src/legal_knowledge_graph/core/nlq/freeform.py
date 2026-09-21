"""
Stage B — fallback khi Stage A (match_template.py) không khớp template
nào. Gemini tự viết Cypher tự do, bị giới hạn nghiêm ngặt bởi
schema_context.py (chỉ label/relationship/property có thật). Đây là lớp
phòng vệ MỀM (dựa vào Gemini tự tuân thủ prompt) — lớp CỨNG bắt buộc là
guard.py ở bước sau (pipeline.py gọi), KHÔNG tin tưởng một mình prompt.

Gemini ở đây tự embed literal (tên tổ chức, cụm từ...) thẳng vào Cypher
text, không dùng $param — vì đây là Cypher hoàn toàn do LLM viết/kiểm soát
nội dung, không phải nơi truyền thẳng input người dùng chưa qua xử lý.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import gemini_client, schema_context

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "unsupported": {"type": "boolean"},
        "cypher": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["unsupported", "cypher", "reason"],
}

_PROMPT_TEMPLATE = """Bạn viết Cypher READ-ONLY cho Neo4j, trả lời câu hỏi về văn bản pháp quy quản trị đại học Việt Nam. Câu hỏi này KHÔNG khớp bất kỳ template có sẵn nào, nên bạn phải tự viết Cypher từ đầu — CHỈ được dùng đúng schema dưới đây, không được bịa label/property/relationship nào khác.

{schema}

QUY TẮC BẮT BUỘC:
- CHỈ dùng: MATCH, OPTIONAL MATCH, WHERE, WITH, UNWIND, RETURN, ORDER BY, CALL db.index.fulltext.queryNodes. TUYỆT ĐỐI CẤM: CREATE, MERGE, SET, DELETE, REMOVE, DETACH, DROP, LOAD CSV, FOREACH, CALL apoc.*, CALL dbms.*, CALL gds.*.
- KHÔNG tự thêm LIMIT ở cuối — hệ thống sẽ tự ép giới hạn số dòng.
- CHỈ 1 statement Cypher duy nhất (không dùng dấu ';' để nối nhiều câu).
- Nếu câu hỏi không thể trả lời bằng đúng schema này (không có node/relationship/property nào phù hợp, hoặc yêu cầu ghi/sửa/xoá dữ liệu) -> unsupported=true, cypher="", giải thích ngắn gọn ở 'reason'. Đừng cố viết Cypher gượng ép cho vừa.
- Nếu viết được -> unsupported=false, điền Cypher hoàn chỉnh vào 'cypher'.

CÂU HỎI: "{question}"

Trả JSON đúng schema đã cho, không thêm chữ nào khác ngoài JSON."""


@dataclass(frozen=True)
class StageBResult:
    unsupported: bool
    cypher: str | None
    reason: str


def generate_freeform(question: str) -> StageBResult:
    prompt = _PROMPT_TEMPLATE.format(schema=schema_context.render_prompt_context(), question=question)
    data = gemini_client.call_json(prompt, _RESPONSE_SCHEMA)

    unsupported = bool(data.get("unsupported"))
    cypher = (data.get("cypher") or "").strip()
    reason = data.get("reason", "")

    if not unsupported and not cypher:
        unsupported = True
        reason = reason or "Gemini không sinh được Cypher (rỗng)"

    return StageBResult(unsupported=unsupported, cypher=cypher or None, reason=reason)
