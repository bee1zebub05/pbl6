"""
Stage A — chọn 1 template (hoặc miss) từ câu hỏi tự nhiên, bằng Gemini với
output ép theo JSON schema cố định.

QUAN TRỌNG: Gemini ở đây KHÔNG tự viết Cypher, chỉ chọn tên template có
sẵn (templates.py) và trích tham số THÔ dạng chuỗi (tên tổ chức, số hiệu
văn bản...) — không tự suy ra orgId/normalizedNumber, việc đó thuộc về
resolve.py ở bước sau. Chỉ chấp nhận matched=true khi đủ điều kiện
(confidence, tên template hợp lệ) — không đủ thì coi là miss, để
pipeline.ask() rơi xuống Stage B.
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import config
from ..validate import load_seed_entries
from . import gemini_client
from .templates import TEMPLATES, catalog_text

_TOPIC_VALUES = tuple(e["name"] for e in load_seed_entries(config.TOPICS_SEED_PATH))
_TARGET_GROUP_VALUES = tuple(e["name"] for e in load_seed_entries(config.TARGET_GROUPS_SEED_PATH))

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "matched": {"type": "boolean"},
        "template": {"type": "string"},
        "confidence": {"type": "number"},
        # Gemini Developer API KHÔNG hỗ trợ object tự do (additionalProperties
        # chỉ dùng được ở Vertex/Enterprise) — dùng mảng {key, value} thay vì
        # object, rồi tự ghép lại thành dict sau khi parse (xem match_template()).
        "params": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                },
                "required": ["key", "value"],
            },
        },
        "reason": {"type": "string"},
    },
    "required": ["matched", "template", "confidence", "params", "reason"],
}

_PROMPT_TEMPLATE = """Bạn là bộ định tuyến câu hỏi cho một Cypher/Neo4j knowledge graph về văn bản pháp quy quản trị đại học Việt Nam (Đại học Đà Nẵng, Trường Đại học Bách khoa và các văn bản pháp luật cấp trên liên quan).

Nhiệm vụ: đọc CÂU HỎI của người dùng, quyết định câu hỏi có khớp với MỘT trong các template Cypher đã liệt kê dưới đây không.

QUY TẮC BẮT BUỘC:
- Chỉ chọn template nếu câu hỏi THỰC SỰ khớp ý nghĩa nghiệp vụ của template đó. Không chắc thì để matched=false, đừng đoán liều.
- Với tham số kiểu tên tổ chức (orgId) / số hiệu văn bản (normalizedNumber) / cụm từ tìm kiếm (luceneQuery): trích CHUỖI THÔ đúng như người dùng viết (đừng tự chuẩn hoá, đừng tự suy ra ID — có bước riêng xử lý việc đó, vì tên tổ chức có hàng trăm giá trị bạn không biết hết).
- Với tham số 'topicId': đây là từ vựng ĐÓNG, chỉ có đúng {n_topics} giá trị sau — PHẢI map câu hỏi sang ĐÚNG NGUYÊN VĂN 1 trong các giá trị này (kể cả khi người dùng dùng từ đồng nghĩa/viết khác đi), không trích chuỗi thô: {topics}
- Với tham số 'targetGroupId': cũng là từ vựng ĐÓNG, chỉ có đúng {n_groups} giá trị sau — PHẢI map sang ĐÚNG NGUYÊN VĂN 1 trong các giá trị này (vd người dùng hỏi "sinh viên"/"học sinh"/"người học" đều map thành "Người học"): {target_groups}
- Với tham số 'status': map sang đúng 1 trong CON_HIEU_LUC (còn hiệu lực) / HET_HIEU_LUC (hết hiệu lực) / CHUA_HIEU_LUC (chưa có hiệu lực). Không chắc/không nhắc tới thì đừng điền tham số này.
- Với tham số 'contentType': map sang đúng 1 trong: Quy định, Quy chế, Điều lệ, Quy trình, Nội quy, Đề án, Kế hoạch, Hướng dẫn, Chương trình.
- Với tham số 'limit'/'seedLimit': chỉ điền nếu người dùng nêu số cụ thể (vd "top 5"), không thì bỏ qua.
- Không khớp template nào (hoặc câu hỏi mơ hồ/ngoài phạm vi) -> matched=false, template="", confidence=0, params=[], giải thích ngắn ở 'reason'.
- 'confidence' là số 0.0-1.0, phản ánh thật độ chắc chắn — đừng luôn trả 1.0.
- 'params' là MẢNG các object {{"key": tên_tham_số, "value": giá_trị_thô}}, mỗi tham số bắt buộc/tuỳ chọn đã trích được là 1 phần tử — không phải object phẳng.

DANH SÁCH TEMPLATE:
{catalog}

CÂU HỎI: "{question}"

Trả JSON đúng schema đã cho, không thêm chữ nào khác ngoài JSON."""


@dataclass(frozen=True)
class StageAResult:
    matched: bool
    template: str | None
    confidence: float
    params: dict[str, str]
    reason: str


def match_template(question: str) -> StageAResult:
    prompt = _PROMPT_TEMPLATE.format(
        catalog=catalog_text(),
        question=question,
        n_topics=len(_TOPIC_VALUES),
        topics=", ".join(_TOPIC_VALUES),
        n_groups=len(_TARGET_GROUP_VALUES),
        target_groups=", ".join(_TARGET_GROUP_VALUES),
    )
    data = gemini_client.call_json(prompt, _RESPONSE_SCHEMA)

    matched = bool(data.get("matched"))
    template = data.get("template") or None
    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    # params trả về dạng mảng [{"key":..,"value":..}] (xem _RESPONSE_SCHEMA) -> ghép lại thành dict.
    params = {
        item["key"]: item["value"]
        for item in (data.get("params") or [])
        if isinstance(item, dict) and "key" in item and "value" in item
    }
    reason = data.get("reason", "")

    if matched and (template not in TEMPLATES or confidence < config.NLQ_TEMPLATE_CONFIDENCE_MIN):
        # Không đủ điều kiện (tên template lạ, hoặc dưới ngưỡng tin cậy) ->
        # coi là miss, KHÔNG chạy Cypher với 1 lựa chọn không chắc chắn.
        matched = False

    return StageAResult(
        matched=matched, template=template, confidence=confidence, params=params, reason=reason
    )
