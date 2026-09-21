"""
Chuẩn hoá khoá cho legal_knowledge_graph — viết mới từ đầu, KHÔNG import
src/vanban/kg/norm.py (module này phải độc lập hoàn toàn với code cũ).

Nguyên tắc: người map chỉ gõ giá trị THÔ (như in trên văn bản); mọi khoá
dùng để MERGE trong Neo4j (normalizedNumber, orgId, contentId, articleId,
personId) đều do các hàm dưới đây suy ra, không bao giờ do người map tự gõ
(trừ khi dùng idOverride) — tránh lặp lại lỗi lệch khoá của pipeline tự động.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

_DASH_VARIANTS = re.compile(r"[‐‑‒–—−]")
_SO_PREFIX = re.compile(r"^\s*S[ôố]\s*:?\s*", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_LEADING_ZERO = re.compile(r"^0+(\d)")
_VN_DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")


def deaccent(text: str) -> str:
    """Bỏ dấu tiếng Việt. NFD không tách được nét gạch của Đ/đ nên xử lý riêng."""

    text = text.replace("Đ", "D").replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def _clean_document_number(raw: str) -> str:
    text = unicodedata.normalize("NFC", raw)
    text = _SO_PREFIX.sub("", text)
    text = _DASH_VARIANTS.sub("-", text)
    text = _WHITESPACE.sub(" ", text).strip()
    text = text.strip("/-")
    # Bỏ số 0 thừa ở đầu số hiệu (segment trước dấu "/" đầu tiên), giữ nguyên phần còn lại.
    if "/" in text:
        head, rest = text.split("/", 1)
        head = _LEADING_ZERO.sub(r"\1", head.strip())
        text = f"{head}/{rest}"
    else:
        text = _LEADING_ZERO.sub(r"\1", text)
    return text


def normalize_document_number(raw: str) -> str:
    """Khoá MERGE của Document (property Neo4j: normalizedNumber) — deaccent +
    uppercase, giữ nguyên dấu '/' và '-'.

    Cùng hình dạng với so_hieu_norm thật trong data/kg/documents.jsonl (vd
    "10/2016/TT-BGDDT", pipeline src/vanban/kg/ — tên property ở đó vẫn giữ
    tiếng Việt, không đụng tới), để hai bên dễ đối chiếu nếu cần ghép dữ liệu
    sau này.
    """

    cleaned = _clean_document_number(raw)
    return deaccent(cleaned).upper()


def slug(text: str) -> str:
    """orgId / personId / topicId — deaccent, lowercase, non-alnum -> '_'."""

    lowered = deaccent(text).lower()
    slugged = _NON_ALNUM.sub("_", lowered).strip("_")
    return re.sub(r"_+", "_", slugged)


def org_id(name: str) -> str:
    return slug(name)


def person_id(full_name: str) -> str:
    return slug(full_name)


def topic_id(name: str) -> str:
    return slug(name)


def target_group_id(name: str) -> str:
    return slug(name)


def content_id(doc_key: str, index: int) -> str:
    """index là vị trí 1-based của normativeContent trong mảng normativeContents[]."""

    return f"{doc_key}#nd{index}"


def article_id(parent_key: str, number: str) -> str:
    return f"{parent_key}#{number}"


def vn_date_to_iso(raw: str | None) -> str | None:
    if not raw:
        return None
    match = _VN_DATE.match(raw.strip())
    if not match:
        return None
    day, month, year = (int(x) for x in match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


# ============================================================
# authorityLevel (§3 Ontology) — hai bảng y hệt norm.py thật, viết lại độc
# lập. org-type ưu tiên hơn doc-type: 252/501 văn bản thật dùng chung nhãn
# "Quyết định" nhưng trải khắp mọi bậc, xét theo loại là vô nghĩa.
# ============================================================

LEVEL_BY_ORG_TYPE: dict[str, int] = {
    "quoc_hoi": 5,
    "chinh_phu": 4,
    "thu_tuong": 3,
    "bo_nganh": 3,
    "dai_hoc_vung": 2,
    "truong_thanh_vien": 1,
}

LEVEL_BY_DOC_TYPE: dict[str, int] = {
    "Hiến pháp": 6,
    "Luật": 5,
    "Pháp lệnh": 5,
    "Nghị định": 4,
    "Thông tư": 3,
    "Thông tư liên tịch": 3,
}


def authority_level(document_type: str, org_type: str | None) -> tuple[int | None, str]:
    """Trả về (level, ghi-chú-nguồn-gốc). None khi không suy được — để graph_model.py
    thử tiếp bằng cách mượn bậc của parentOrg (đơn vị trực thuộc/phòng ban)."""

    if document_type == "Hiến pháp":
        return 6, "onto"
    if org_type and org_type in LEVEL_BY_ORG_TYPE:
        return LEVEL_BY_ORG_TYPE[org_type], "onto"
    if document_type in LEVEL_BY_DOC_TYPE:
        return LEVEL_BY_DOC_TYPE[document_type], "onto: theo-loai"
    return None, "khong-suy-duoc"
