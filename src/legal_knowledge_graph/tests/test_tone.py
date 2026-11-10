"""Giọng văn: các câu cố định không lộ cách máy làm việc, không có văn mẫu dán thêm."""

import logging

import pytest

from core.chat import prompts
from core.chat.answering.clarification import SLOT_PHRASES, ClarificationService
from core.chat.container import build_chat_service
from core.chat.models import IntentResult, RouterOutput
from core.graph_query import entity_resolver
from core.observability import _ConsoleFormatter, _console_worthy
from fakes import FakeExecutor, FakeLLM, FakeResolver, FakeRetriever

_SERVICE = ClarificationService()

_FIXED_REPLIES = [
    prompts.NO_DATA_ANSWER, prompts.ERROR_ANSWER, prompts.AGENT_GAVE_UP_ANSWER, *prompts.FALLBACK_REPLIES.values(),
    *(_SERVICE.for_missing((slot,)).question for slot in SLOT_PHRASES),
    _SERVICE.for_missing(("org", "topic", "target_group")).question,
    _SERVICE.for_resolution("org", "không tìm thấy 'X'", ()).question,
    _SERVICE.for_resolution("org", "'X' mơ hồ", ("A", "B")).question,
]


@pytest.mark.parametrize("reply", _FIXED_REPLIES)
def test_fixed_replies_sound_human(reply):
    assert not [p for p in prompts.TONE_BANNED if p in reply.lower()]


def _intent(kind="domain_query", question="q", reply=""):
    return IntentResult(intent=kind, standalone_question=question, continues_clarification=False, direct_reply=reply)


def test_thanks_gets_a_plain_reply_without_suggestion_block():
    llm = FakeLLM({"intent": [_intent("smalltalk", "Cảm ơn", reply="Không có gì nhé!")]})
    service = build_chat_service(llm=llm, executor=FakeExecutor(), resolver=FakeResolver(), retriever=FakeRetriever())
    assert service.ask("Cảm ơn").answer == "Không có gì nhé!"


def test_template_name_never_reaches_the_user():
    class Missing(FakeResolver):
        def resolve(self, resolver_kind, raw):
            return entity_resolver.NotFound(suggestion="thử template TPL_DOCUMENT_FULLTEXT_SEARCH")

    llm = FakeLLM({"intent": [_intent()], "route": [RouterOutput(action="document_detail", doc_number="1/QĐ")]})
    service = build_chat_service(llm=llm, executor=FakeExecutor(), resolver=Missing(), retriever=FakeRetriever())
    r = service.ask("1/QĐ nói gì?")
    assert r.kind == "clarification" and "1/QĐ" in r.answer and "TPL_" not in r.answer


def _record(level, **fields):
    record = logging.LogRecord("lkg.chat", level, "", 0, "x", (), None)
    record.fields = fields
    return record


def test_console_shows_one_short_line_per_turn():
    line = _ConsoleFormatter().format(_record(logging.INFO, stage="turn.end", kind="answer", llm_calls=3, ms=8200.0,
                                              question="Học phí?"))
    assert line.endswith('answer 3 LLM 8.2s "Học phí?"') and "{" not in line


def test_console_hides_step_logs_but_keeps_problems():
    assert not _console_worthy(_record(logging.INFO, stage="cypher"))
    assert _console_worthy(_record(logging.INFO, stage="turn.end"))
    assert _console_worthy(_record(logging.ERROR, stage="error", node="answer"))
