import pytest

from core.chat.models import QueryFrame, RouterOutput, Slots
from core.chat.answering.clarification import SLOT_PHRASES
from core.chat.understanding.template_selector import RULES, TemplateSelector
from core.chat.adapters.neo4j_adapters import Neo4jEntityResolver
from core.db import Neo4jConnection
from core.graph_query.templates import INT_SLOTS, RESOLVER_KINDS, SLOT_TO_PARAM, TEMPLATES, actions_in_order


def _decide(action: str, **slots):
    return TemplateSelector().select(QueryFrame(action=action, slots=Slots(**slots)))


def test_every_template_is_reachable_by_its_own_action():
    covered = {r.template for rules in RULES.values() for r in rules}
    assert covered == set(TEMPLATES)
    assert len(TEMPLATES) >= 60


def test_every_template_is_selected_by_its_example_slots():
    """Khung câu hỏi dựng từ example_params của template phải chọn đúng template đó."""

    from core.graph_query.templates import PARAM_TO_SLOT

    for name, tpl in TEMPLATES.items():
        slots = {PARAM_TO_SLOT[p]: v for p, v in tpl.example_params.items()}
        decision = _decide(tpl.action, **slots)
        assert (decision.kind, decision.template) == ("template", name), f"{name}: {decision}"


@pytest.mark.parametrize("action, slots, template", [
    ("list_documents", {"org": "ĐHBK", "status": "CON_HIEU_LUC"}, "TPL_DOCS_BY_ORG_STATUS"),
    ("list_documents", {"topic": "Đào tạo"}, "TPL_DOCS_BY_TOPIC"),
    ("list_documents", {"doc_type": "Luật"}, "TPL_DOCS_BY_TYPE"),
    ("list_documents", {"year": 2024}, "TPL_DOCS_BY_YEAR"),
    ("list_documents", {"org": "ĐHBK", "topic": "Công tác sinh viên"}, "TPL_DOCS_FILTERED"),
    ("list_documents", {"topic": "Đào tạo", "target_group": "Người học", "doc_type": "Thông tư"}, "TPL_DOCS_FILTERED"),
    ("list_documents", {"since_year": 2023, "org": "ĐHBK"}, "TPL_DOCS_SINCE_YEAR"),
    ("search_articles", {"phrase": "học bổng"}, "TPL_ARTICLE_FULLTEXT_SEARCH"),
    ("search_articles", {"phrase": "học phí", "status": "CON_HIEU_LUC"}, "TPL_ARTICLE_SEARCH_ACTIVE"),
    ("search_articles", {"phrase": "khen thưởng", "doc_number": "1001/QĐ-ĐHBK"}, "TPL_DOC_ARTICLE_SEARCH"),
    ("documents_signed_by", {"person": "Đoàn Quang Vinh"}, "TPL_DOCS_BY_SIGNER"),
    ("documents_signed_by", {"position": "Hiệu trưởng"}, "TPL_DOCS_SIGNED_BY_POSITION"),
    ("count_documents", {}, "TPL_COUNT_DOCS"),
    ("rank_orgs", {"limit": 5}, "TPL_TOP_ORGS_BY_DOC_COUNT"),
])
def test_match(action, slots, template):
    d = _decide(action, **slots)
    assert (d.kind, d.template) == ("template", template)


def test_slot_values_are_mapped_to_cypher_params():
    d = _decide("article_text", doc_number="1001/QĐ-ĐHBK", article_number="Điều 5")
    assert d.raw_params == {"normalizedNumber": "1001/QĐ-ĐHBK", "articleNumber": "Điều 5"}


def test_single_filter_does_not_fall_into_generic_filter_template():
    assert _decide("list_documents", org="ĐHBK").template == "TPL_DOCS_BY_ORG_STATUS"


def test_status_only_asks_back_with_alternatives():
    d = _decide("list_documents", status="CON_HIEU_LUC")
    assert d.kind == "clarify" and {"org", "topic"} <= set(d.missing)


def test_missing_required_slot_asks_back():
    d = _decide("document_detail")
    assert d.kind == "clarify" and d.missing == ("doc_number",)


def test_unsupported_combination_goes_to_agent():
    d = _decide("document_detail", doc_number="4511/QĐ-ĐHBK", person="Đoàn Quang Vinh")
    assert d.kind == "agent"


@pytest.mark.parametrize("action", ["other", "khong_ton_tai"])
def test_unknown_action_goes_to_agent(action):
    assert _decide(action).kind == "agent"


def test_action_order_starts_with_common_questions():
    assert actions_in_order()[0] == "list_documents" and actions_in_order()[-1] == "other"


def test_slot_lists_stay_in_sync():
    """Một slot phải có mặt ở cả ba nơi: model router trích (Slots), bảng
    slot -> $param của kho template, và câu hỏi lại khi thiếu slot."""

    slots = set(Slots.model_fields)
    assert slots == set(SLOT_TO_PARAM) == set(SLOT_PHRASES)
    assert INT_SLOTS <= slots


def test_entity_resolver_dispatch_covers_every_resolver_kind():
    # Neo4jConnection mở driver lười — dựng resolver không cần Neo4j chạy.
    assert set(Neo4jEntityResolver(Neo4jConnection()).table) == RESOLVER_KINDS


def test_router_output_is_flat_and_requires_every_key():
    """Key tuỳ chọn thì Gemini hay bỏ hẳn slot cần thiết — xem models.RouterOutput."""

    schema = RouterOutput.model_json_schema()
    assert "$defs" not in schema
    assert set(schema["required"]) == set(schema["properties"]) == {"action", *Slots.model_fields}
