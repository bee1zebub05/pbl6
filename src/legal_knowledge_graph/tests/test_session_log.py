"""Log theo phiên (core/chat/session_log.py): mỗi thread_id một file, mỗi lượt ghi từng bước."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core import config
from core.chat import session_log
from core.chat.container import build_chat_service
from core.chat.models import IntentResult, RouterOutput
from fakes import FakeExecutor, FakeLLM, FakeResolver, FakeRetriever


@pytest.fixture
def log_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "SESSION_LOG_ENABLED", True)
    monkeypatch.setattr(config, "SESSION_LOG_DIR", tmp_path)
    return tmp_path


def _intent(question):
    return IntentResult(intent="domain_query", standalone_question=question, continues_clarification=False,
                        direct_reply="")


def _service(llm):
    return build_chat_service(llm=llm, executor=FakeExecutor(), resolver=FakeResolver(), retriever=FakeRetriever())


def _read(thread_id):
    return session_log.session_path(thread_id).read_text(encoding="utf-8")


def test_each_turn_of_a_thread_goes_to_one_file_with_every_step(log_dir):
    llm = FakeLLM({
        "intent": [_intent("Văn bản ĐHBK còn hiệu lực?"), _intent("Văn bản ĐHBK?")],
        "route": [RouterOutput(action="list_documents", org="ĐHBK", status="CON_HIEU_LUC"),
                  RouterOutput(action="list_documents", org="ĐHBK")],
        "answer": ["Có 1 văn bản: 1001/QĐ-ĐHBK.", "Có 1 văn bản."],
    })
    service = _service(llm)
    service.ask("Văn bản ĐHBK còn hiệu lực?", thread_id="t-log")
    service.ask("còn văn bản nào nữa?", thread_id="t-log")

    files = list(log_dir.rglob("*.log"))
    assert len(files) == 1 and files[0].name.endswith("_t-log.log")
    text = _read("t-log")
    assert "LƯỢT 1" in text and "LƯỢT 2" in text and "Người dùng: còn văn bản nào nữa?" in text
    for node in ("intent", "route", "run_template", "retrieve", "answer"):
        assert f"[{node}] đầu ra node" in text
    # Đầu ra run_template: template, Cypher, tham số đã resolve, dòng kết quả.
    assert "TPL_DOCS_BY_ORG_STATUS" in text and "truong_dai_hoc_bach_khoa" in text and "1001/QĐ-ĐHBK" in text
    assert "KẾT QUẢ LƯỢT · answer" in text and "Có 1 văn bản: 1001/QĐ-ĐHBK." in text


def test_new_thread_gets_its_own_file(log_dir):
    llm = FakeLLM({"intent": [IntentResult(intent="smalltalk", standalone_question="Chào",
                                           continues_clarification=False, direct_reply="Chào bạn!")] * 2})
    service = _service(llm)
    service.ask("Chào", thread_id="t-a")
    service.ask("Chào", thread_id="t-b")
    assert len(list(log_dir.rglob("*.log"))) == 2


def test_agent_tool_results_are_logged_with_cypher(log_dir):
    tool_call = AIMessage(content="", tool_calls=[{
        "name": "run_cypher", "id": "c1", "args": {"cypher": "MATCH (d:Document) RETURN d.documentNumber AS documentNumber"},
    }])
    llm = FakeLLM({"intent": [_intent("câu khó")], "route": [RouterOutput(action="other")],
                   "agent": [tool_call, AIMessage(content="Xong.")]})
    _service(llm).ask("câu khó", thread_id="t-agent")
    text = _read("t-agent")
    assert "[agent.tool] run_cypher" in text and "LIMIT 200" in text and "[agent] đầu ra node" in text


def test_node_error_is_logged_with_traceback(log_dir):
    from neo4j.exceptions import ServiceUnavailable

    llm = FakeLLM({"intent": [_intent("Phân bố?")], "route": [RouterOutput(action="status_distribution")]})
    build_chat_service(llm=llm, executor=FakeExecutor(error=ServiceUnavailable("neo4j down")), resolver=FakeResolver(),
                       retriever=FakeRetriever()).ask("Phân bố?", thread_id="t-err")
    text = _read("t-err")
    assert "[run_template] LỖI" in text and "ServiceUnavailable: neo4j down" in text and "Traceback" in text


def test_llm_call_prints_system_prompt_once_and_skips_repeated_messages(log_dir):
    system, question = SystemMessage("PROMPT HỆ THỐNG DÀI"), HumanMessage("Học bổng?")
    step1 = AIMessage(content="", tool_calls=[{"name": "search_articles", "id": "s1", "args": {"query": "học bổng"}}])
    with session_log.turn("t-llm", "turn1", "Học bổng?"):
        session_log.llm_call("agent", model="m", ms=1, info={"attempts": 1}, messages=[system, question], output=step1)
        session_log.tool("search_articles", "Điều 3 ...")
        session_log.llm_call("agent", model="m", ms=1, info={}, messages=[system, question, step1],
                             output=AIMessage(content="Trả lời"))
    text = _read("t-llm")
    assert text.count("PROMPT HỆ THỐNG DÀI") == 1 and "giống prompt #1" in text
    assert text.count("Học bổng?\n") >= 1 and "(… 2 tin nhắn đã in ở trên trong lượt này)" in text
    assert '→ gọi tool search_articles({"query": "học bổng"})' in text and "Trả lời" in text


def test_disabled_session_log_writes_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "SESSION_LOG_ENABLED", False)
    monkeypatch.setattr(config, "SESSION_LOG_DIR", tmp_path)
    llm = FakeLLM({"intent": [IntentResult(intent="smalltalk", standalone_question="Chào",
                                           continues_clarification=False, direct_reply="Chào bạn!")]})
    _service(llm).ask("Chào", thread_id="t-off")
    assert list(tmp_path.rglob("*")) == []
