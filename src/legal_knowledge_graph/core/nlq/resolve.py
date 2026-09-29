"""
Resolve thực thể THÔ (chuỗi LLM trích ra hoặc người dùng gõ tay ở CLI
--template thủ công) -> giá trị thật trong graph. KHÔNG dùng LLM ở file
này — thuần Python xác định, để test được độc lập với Gemini (Phase 1).

Nguyên tắc: KHÔNG BAO GIỜ tự đoán khi mơ hồ — trả `Ambiguous`/`NotFound`
thay vì chọn đại 1 candidate. Xem plan (abundant-sleeping-moth.md) mục
"Kết quả trả về: 4 loại rõ ràng" — resolve thất bại phải lộ ra thành
`resolution_failed`, không được âm thầm chạy Cypher với tham số sai.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from .. import config, normalize
from ..validate import load_seed_entries
from . import aliases as aliases_module
from . import schema_context

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
    value: str


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
# Organization — 778 node THẬT trong graph, seed chỉ có 21 (fast-path).
# Resolve phải đối chiếu trực tiếp Organization.name sống trong graph,
# không thể chỉ dựa vào seed (xem plan, mục "Facts đã xác minh").
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
    return _fuzzy_pick(mention, _load_org_cache(session), aliases_module.load_org_aliases())


# ============================================================
# Topic (18 giá trị, reference/topics_seed.json) và TargetGroup (8 giá
# trị, reference/target_groups_seed.json) — cùng 1 khuôn: load seed 1
# lần, cache trong closure, fuzzy-match qua alias rồi _fuzzy_pick. Gộp
# thành factory thay vì lặp cache+hàm cho từng loại (trước đây 2 khối
# gần như copy-paste).
# ============================================================

def _make_seed_resolver(seed_path, alias_loader):
    """Trả về 1 hàm resolve_<x>(mention) -> Resolution, seed load 1 lần
    qua aliases_module.lazy_cache() (org không dùng factory này — nguồn
    là Neo4j sống qua session, không phải seed tĩnh, xem _load_org_cache)."""

    load_cache = aliases_module.lazy_cache(
        lambda: {normalize.slug(e["name"]): e["name"] for e in load_seed_entries(seed_path)}
    )

    def resolve(mention: str) -> Resolution:
        return _fuzzy_pick(mention, load_cache(), alias_loader())

    return resolve


resolve_topic = _make_seed_resolver(config.TOPICS_SEED_PATH, aliases_module.load_topic_aliases)
resolve_target_group = _make_seed_resolver(config.TARGET_GROUPS_SEED_PATH, aliases_module.load_target_group_aliases)


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
# Enum phòng vệ — Stage A (Gemini) đã map trực tiếp sang các giá trị này,
# đây chỉ là lớp validate chặn giá trị sai lọt qua trước khi vào Cypher.
# Giá trị lấy THẲNG từ schema_context.ENUMS — 1 nguồn sự thật duy nhất,
# tránh 2 danh sách enum lệch nhau khi có loại văn bản/status mới.
# ============================================================

STATUS_VALUES = schema_context.ENUMS["Document.status"]
CONTENT_TYPE_VALUES = schema_context.ENUMS["NormativeContent.contentType"]


def _resolve_enum(mention: str, values: tuple[str, ...], field_name: str) -> Resolution:
    if mention in values:
        return Resolved(mention)
    return NotFound(suggestion=f"{field_name} phải là 1 trong: {', '.join(values)}")


def resolve_status(mention: str) -> Resolution:
    return _resolve_enum(mention, STATUS_VALUES, "status")


def resolve_content_type(mention: str) -> Resolution:
    return _resolve_enum(mention, CONTENT_TYPE_VALUES, "contentType")


# ============================================================
# Fulltext phrase — luôn thành công, chỉ escape ký tự đặc biệt Lucene rồi
# bọc ngoặc kép để tìm cụm chính xác. Tự viết lại (không import từ
# src/vanban/rag/engines.py, chỉ giống Ý TƯỞNG — xem plan, quy tắc decoupling).
# ============================================================

_LUCENE_SPECIAL = re.compile(r'[+\-!(){}\[\]^"~*?:\\/&|]')


def resolve_fulltext_phrase(raw: str) -> str:
    cleaned = _LUCENE_SPECIAL.sub(" ", raw).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return f'"{cleaned}"'


# ============================================================
# Int limit — luôn thành công, parse + clamp
# ============================================================

def resolve_int_limit(raw: str, default: int, cap: int = 200) -> int:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, min(n, cap))
