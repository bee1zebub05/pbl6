"""
Resolve thực thể THÔ (chuỗi LLM trích ra hoặc người dùng gõ tay ở CLI
--template thủ công) -> giá trị thật trong graph. KHÔNG dùng LLM ở file
này — thuần Python xác định, test được độc lập với LLM.

Nguyên tắc: KHÔNG BAO GIỜ tự đoán khi mơ hồ — trả `Ambiguous`/`NotFound`
thay vì chọn đại 1 candidate. Chatbot đổi hai kết quả này thành câu hỏi lại
(ResolutionFailed), không âm thầm chạy Cypher với tham số sai.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass

from .. import config, normalize
from ..reference import load_seed_entries
from . import entity_aliases, schema

_MIN_SCORE = 0.5
_AMBIGUITY_MARGIN = 0.08  # 2 candidate cách nhau dưới mức này -> coi là mơ hồ

# Tiền tố chung của hầu hết tên tổ chức tiếng Việt ("Trường Đại học X",
# "Đại học Y"...) — so khớp trên TOÀN chuỗi (kể cả qua SequenceMatcher) bị
# tiền tố này đánh lừa: 2 tên HOÀN TOÀN khác nhau (vd "Trường Đại học
# Không Tồn Tại" vs "Trường Đại học Thương mại") vẫn ra ratio cao > 0.8
# chỉ vì chung "truong_dai_hoc_". Phải bỏ tiền tố rồi so phần CÒN LẠI
# (token phân biệt thật sự) mới đúng.
_GENERIC_PREFIXES = ("truong_dai_hoc_", "dai_hoc_", "truong_")


@dataclass(frozen=True)
class Resolved:
    value: str | int  # int với resolver số (năm, giới hạn dòng) — Neo4j cần Integer


@dataclass(frozen=True)
class Ambiguous:
    candidates: tuple[str, ...]


@dataclass(frozen=True)
class NotFound:
    suggestion: str | None = None


Resolution = Resolved | Ambiguous | NotFound


def _strip_generic_prefix(slug: str) -> str:
    for prefix in _GENERIC_PREFIXES:
        if slug.startswith(prefix):
            return slug[len(prefix):]
    return slug


def _similarity(query_slug: str, candidate_slug: str) -> float:
    """Jaccard trên TOKEN PHÂN BIỆT (sau khi bỏ tiền tố chung) — không
    dùng SequenceMatcher trên toàn chuỗi vì tiền tố chung ("truong_dai_
    hoc_"...) làm 2 tên khác hẳn nhau vẫn ra điểm cao giả tạo."""

    q_tokens = set(_strip_generic_prefix(query_slug).split("_")) - {""}
    c_tokens = set(_strip_generic_prefix(candidate_slug).split("_")) - {""}
    if not q_tokens or not c_tokens:
        return difflib.SequenceMatcher(None, query_slug, candidate_slug).ratio()
    return len(q_tokens & c_tokens) / len(q_tokens | c_tokens)


def _fuzzy_pick(query: str, options: dict[str, str], aliases: dict[str, str] | None = None) -> Resolution:
    """options: slug -> tên hiển thị gốc. Trả Resolved(slug) khi khớp rõ
    ràng (đúng slug hoặc 1 candidate vượt trội theo token phân biệt),
    Ambiguous(tên hiển thị của 2-3 candidate gần nhau) khi không phân biệt
    được, NotFound() khi không có candidate nào đủ gần (điểm dưới
    _MIN_SCORE — chặn trường hợp tên hoàn toàn khác nhau nhưng chung tiền
    tố "Trường Đại học..." vẫn bị coi là gần).

    aliases (nếu có): slug(alias) -> slug(canonical), tra TRƯỚC exact-slug-
    match — bắt các viết tắt (VD "ĐHBK") mà fuzzy match theo token không
    bắt được (không chia sẻ token nào với "truong_dai_hoc_bach_khoa"). Nếu
    canonical đã lưu không còn khớp options sống (org đổi tên/xoá) thì rơi
    tiếp xuống các bước match bên dưới, không hard-fail."""

    query_slug = normalize.slug(query)
    if aliases and query_slug in aliases:
        canonical_slug = aliases[query_slug]
        if canonical_slug in options:
            return Resolved(canonical_slug)
    if query_slug in options:
        return Resolved(query_slug)

    scored = [(slug, _similarity(query_slug, slug)) for slug in options]
    scored = [(slug, score) for slug, score in scored if score >= _MIN_SCORE]
    if not scored:
        return NotFound()

    scored.sort(key=lambda pair: pair[1], reverse=True)
    if len(scored) == 1 or scored[0][1] - scored[1][1] >= _AMBIGUITY_MARGIN:
        return Resolved(scored[0][0])
    return Ambiguous(tuple(options[slug] for slug, _ in scored[:3]))


# ============================================================
# Organization — graph có hàng trăm cơ quan (phần lớn phát sinh từ dữ liệu),
# reference/organizations_seed.json chỉ có vài chục. Resolve phải đối chiếu
# trực tiếp Organization.name trong graph, không thể chỉ dựa vào seed.
# ============================================================

_org_cache: dict[str, str] | None = None  # slug(name) -> name, cache trong tiến trình


def _load_org_cache(session) -> dict[str, str]:
    global _org_cache
    if _org_cache is None:
        rows = session.run("MATCH (o:Organization) RETURN o.name AS name")
        _org_cache = {normalize.slug(r["name"]): r["name"] for r in rows if r["name"]}
    return _org_cache


def resolve_organization(mention: str, session) -> Resolution:
    # orgId = slug(name) (core/normalize.py::org_id), nên slug khớp trong
    # _fuzzy_pick CHÍNH LÀ orgId cần điền vào $param, không cần map thêm.
    return _fuzzy_pick(mention, _load_org_cache(session), entity_aliases.load_org_aliases())


# ============================================================
# Person — 60 người ký trong graph. Người dùng hay gọi kèm danh xưng ("thầy
# Đoàn Quang Vinh", "PGS.TS ...") hoặc chỉ tên gọi ("thầy Vinh"): bỏ danh
# xưng, so khớp mờ như org; không đủ gần thì thử "mọi token của câu hỏi đều có
# trong tên" (duy nhất -> nhận, nhiều -> mơ hồ, đưa ứng viên cho người dùng chọn).
# ============================================================

_person_cache: dict[str, str] | None = None  # personId -> fullName
_HONORIFICS = re.compile(
    r"^\s*((thầy|cô|ông|bà|anh|chị|đồng chí|gs|pgs|ts|ths|ths\.|gs\.|pgs\.|ts\.)[\s.]*)+", re.IGNORECASE
)


def _load_person_cache(session) -> dict[str, str]:
    global _person_cache
    if _person_cache is None:
        rows = session.run("MATCH (p:Person) RETURN p.personId AS id, p.fullName AS name")
        _person_cache = {r["id"]: r["name"] for r in rows if r["id"] and r["name"]}
    return _person_cache


def resolve_person(mention: str, session) -> Resolution:
    options = _load_person_cache(session)
    name = _HONORIFICS.sub("", str(mention)).strip()
    result = _fuzzy_pick(name, options)
    if not isinstance(result, NotFound):
        return result
    tokens = set(normalize.slug(name).split("_")) - {""}
    hits = [pid for pid in options if tokens and tokens <= set(pid.split("_"))]
    if len(hits) == 1:
        return Resolved(hits[0])
    if hits:
        return Ambiguous(tuple(options[pid] for pid in hits[:5]))
    return NotFound()


# ============================================================
# Topic (18 giá trị, reference/topics_seed.json) và TargetGroup (8 giá
# trị, reference/target_groups_seed.json) — cùng 1 khuôn: load seed 1
# lần, cache trong closure, fuzzy-match qua alias rồi _fuzzy_pick — một
# factory chung cho cả hai.
# ============================================================

def _make_seed_resolver(seed_path, alias_loader):
    """Trả về 1 hàm resolve_<x>(mention) -> Resolution, seed load 1 lần
    qua entity_aliases.lazy_cache() (org không dùng factory này — nguồn
    là Neo4j sống qua session, không phải seed tĩnh, xem _load_org_cache)."""

    load_cache = entity_aliases.lazy_cache(
        lambda: {normalize.slug(e["name"]): e["name"] for e in load_seed_entries(seed_path)}
    )

    def resolve(mention: str) -> Resolution:
        return _fuzzy_pick(mention, load_cache(), alias_loader())

    return resolve


resolve_topic = _make_seed_resolver(config.TOPICS_SEED_PATH, entity_aliases.load_topic_aliases)
resolve_target_group = _make_seed_resolver(config.TARGET_GROUPS_SEED_PATH, entity_aliases.load_target_group_aliases)


# ============================================================
# Document number — kể cả stub cũng hợp lệ (catalog gốc vận hành trên stub)
# ============================================================

def resolve_document_number(mention: str, session) -> Resolution:
    key = normalize.normalize_document_number(mention)
    row = session.run(
        "MATCH (d:Document {normalizedNumber: $key}) RETURN d.normalizedNumber AS key",
        key=key,
    ).single()
    if row:
        return Resolved(key)
    return NotFound(
        suggestion="Không tìm thấy đúng số hiệu này — thử template tìm theo từ khoá "
        "(TPL_DOCUMENT_FULLTEXT_SEARCH) thay vì số hiệu chính xác."
    )


# ============================================================
# Enum phòng vệ — router (Gemini) đã map trực tiếp sang các giá trị này,
# đây chỉ là lớp validate chặn giá trị sai lọt qua trước khi vào Cypher.
# Giá trị lấy THẲNG từ schema.ENUMS — 1 nguồn sự thật duy nhất,
# tránh 2 danh sách enum lệch nhau khi có loại văn bản/status mới.
# ============================================================

STATUS_VALUES = schema.ENUMS["Document.status"]
CONTENT_TYPE_VALUES = schema.ENUMS["NormativeContent.contentType"]
DOC_TYPE_VALUES = schema.ENUMS["Document.documentType"]


def _resolve_enum(mention: str, values: tuple[str, ...], field_name: str) -> Resolution:
    """Khớp không phân biệt hoa/thường và dấu ("quy che" = "Quy chế")."""

    by_slug = {normalize.slug(v): v for v in values}
    hit = by_slug.get(normalize.slug(str(mention)))
    if hit is not None:
        return Resolved(hit)
    return NotFound(suggestion=f"{field_name} phải là 1 trong: {', '.join(values)}")


def resolve_status(mention: str) -> Resolution:
    return _resolve_enum(mention, STATUS_VALUES, "status")


def resolve_content_type(mention: str) -> Resolution:
    return _resolve_enum(mention, CONTENT_TYPE_VALUES, "contentType")


def resolve_doc_type(mention: str) -> Resolution:
    return _resolve_enum(mention, DOC_TYPE_VALUES, "loại văn bản")


# ============================================================
# Năm, số Điều, chuỗi tự do
# ============================================================

_YEAR = re.compile(r"(19|20)\d{2}")
_ARTICLE_NUMBER = re.compile(r"(\d+[a-zA-Z]?)")


def resolve_year(raw) -> Resolution:
    match = _YEAR.search(str(raw))
    if match:
        return Resolved(int(match.group(0)))
    return NotFound(suggestion="năm phải có dạng 4 chữ số, ví dụ 2024")


def resolve_article_number(raw) -> Resolution:
    """'điều 5' / '5' / 'Điều 5a' -> 'Điều 5' (đúng dạng Article.number)."""

    match = _ARTICLE_NUMBER.search(str(raw))
    if match:
        return Resolved(f"Điều {match.group(1)}")
    return NotFound(suggestion="cần số Điều, ví dụ Điều 5")


def resolve_text(raw) -> Resolution:
    text = re.sub(r"\s+", " ", str(raw)).strip()
    return Resolved(text) if text else NotFound()


# ============================================================
# Fulltext phrase — luôn thành công: escape ký tự đặc biệt Lucene, ưu tiên
# cụm chính xác. Viết riêng, không import từ src/vanban/ — module này độc
# lập với pipeline tự động.
# ============================================================

_MIN_SYLLABLES_FOR_AND = 3
_LUCENE_SPECIAL = re.compile(r'[+\-!(){}\[\]^"~*?:\\/&|]')


def _lucene_clean(raw: str) -> str:
    return re.sub(r"\s+", " ", _LUCENE_SPECIAL.sub(" ", raw)).strip()


def resolve_fulltext_phrase(raw: str) -> str:
    """Cụm chính xác được ưu tiên (boost ^2); cụm từ 3 âm tiết trở lên còn
    khớp Điều chứa ĐỦ các âm tiết dù không liền nhau — "nguyên tắc quản lý
    tài sản công" phải tìm được "Nguyên tắc và yêu cầu trong việc quản lý ...
    tài sản công". Cụm 1–2 âm tiết thường là MỘT từ tiếng Việt ("học vụ",
    "học phí"): tách âm tiết ra AND sẽ khớp nhầm hàng nghìn Điều, nên giữ
    nguyên cụm. Viết thường để từ trong câu không thành toán tử AND/OR/NOT."""

    cleaned = _lucene_clean(raw)
    syllables = cleaned.lower().split()
    if len(syllables) < _MIN_SYLLABLES_FOR_AND:
        return f'"{cleaned}"'
    return f'"{cleaned}"^2 OR ({" AND ".join(syllables)})'


# Từ dừng của CÂU HỎI (không phải của văn bản): có mặt ở gần như mọi Điều
# hoặc chỉ là từ để hỏi, đưa vào BM25 chỉ làm nhiễu xếp hạng. Cụm nhiều âm
# tiết bỏ trước; âm tiết đơn chỉ gồm những âm tiết hiếm khi nằm trong từ ghép
# mang nội dung (không có "điều" — "điều kiện").
_QUESTION_STOP_PHRASES = (
    "trường đại học bách khoa", "đại học bách khoa", "đại học đà nẵng", "như thế nào", "còn hiệu lực",
    "hết hiệu lực", "văn bản", "quy định", "thế nào", "ra sao", "bao nhiêu", "là gì", "những gì", "hiện hành",
    "hiện nay", "hiện tại", "hiệu lực", "cho biết", "hay không", "có phải", "đhbk", "đhđn",
)
_QUESTION_STOP_PHRASE_RE = re.compile(
    r"(?<!\S)(?:" + "|".join(re.escape(p) for p in sorted(_QUESTION_STOP_PHRASES, key=len, reverse=True)) + r")(?!\S)"
)
_QUESTION_STOP_SYLLABLES = frozenset({
    "nào", "gì", "là", "của", "các", "những", "về", "theo", "và", "có", "không", "được", "cho", "tôi", "em",
    "mình", "ai", "hãy", "với", "thì", "mà", "này", "đó", "ạ", "nhé", "vậy", "sao", "bị", "đã", "đang", "sẽ",
    "nêu", "hỏi", "muốn",
})
_SPAN_BREAK = "|"


def keyword_query(question: str) -> str:
    """Câu hỏi tự do -> truy vấn Lucene cho seed BM25 của GraphRAG. Bỏ số hiệu
    văn bản (đã đi theo phạm vi văn bản) và từ dừng của câu hỏi; mỗi đoạn liên
    tục còn lại phát các cặp hai âm tiết làm cụm chính xác `"a b"^2` (từ tiếng
    Việt phần lớn là hai âm tiết) cùng các âm tiết đơn. Không còn gì -> "" (chỉ
    dùng vector). Viết thường để AND/OR/NOT trong câu không thành toán tử."""

    text = unicodedata.normalize("NFC", question)
    for number in normalize.find_document_numbers(text):
        text = text.replace(number, " ")
    text = re.sub(r"[^\w\s]|_", " ", text).lower()
    text = _QUESTION_STOP_PHRASE_RE.sub(f" {_SPAN_BREAK} ", text)

    spans: list[list[str]] = [[]]
    for syllable in text.split():
        if syllable == _SPAN_BREAK or syllable in _QUESTION_STOP_SYLLABLES:
            spans.append([])
        else:
            spans[-1].append(syllable)

    terms: list[str] = []
    for span in spans:
        terms += [f'"{a} {b}"^2' for a, b in zip(span, span[1:])]
        terms += [s for s in span if not s.isdigit()]
    return " OR ".join(dict.fromkeys(terms))


# ============================================================
# Int limit — luôn thành công, parse + clamp
# ============================================================

def resolve_int_limit(raw: str, default: int, cap: int = 200) -> int:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, min(n, cap))
