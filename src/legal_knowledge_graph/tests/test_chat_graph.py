"""Chạy graph thật với port giả — kiểm từng nhánh định tuyến, không tốn quota."""

from langchain_core.messages import AIMessage
from neo4j.exceptions import ServiceUnavailable

from core.chat.container import build_chat_service
from core.chat.models import (ArticleEvidence, DocumentContext, GraphContext, IntentResult, RelatedDocument,
                              RouterOutput)
from core.chat.prompts import ERROR_ANSWER, NO_DATA_ANSWER
from fakes import FakeExecutor, FakeLLM, FakeResolver, FakeRetriever


def _intent(kind="domain_query", question="q", continues=False, reply=""):
    return IntentResult(intent=kind, standalone_question=question, continues_clarification=continues,
                        direct_reply=reply)


def _frame(action, **slots):
    """Phản hồi kịch bản của router LLM (schema phẳng)."""
    return RouterOutput(action=action, **slots)


def _context():
    return GraphContext(documents=[DocumentContext(
        documentNumber="1001/QĐ-ĐHBK", status="CON_HIEU_LUC", effectiveStatus="HET_HIEU_LUC",
        supersededBy=[RelatedDocument(documentNumber="1214/QĐ-ĐHBK")],
        articles=[ArticleEvidence(articleId="1001#Điều 3", number="Điều 3", heading="Học bổng", text="…")],
    )])


def _service(llm, executor=None, retriever=None):
    return build_chat_service(llm=llm, executor=executor or FakeExecutor(), resolver=FakeResolver(),
                              retriever=retriever or FakeRetriever())


def test_smalltalk_answers_directly_with_one_llm_call():
    llm = FakeLLM({"intent": [_intent("smalltalk", "Xin chào", reply="Chào bạn!")]})
    r = _service(llm).ask("Xin chào")
    assert r.kind == "direct" and r.answer.startswith("Chào bạn!")
    assert llm.calls == ["intent"]


def test_unsafe_falls_back_to_fixed_reply_when_llm_gives_none():
    llm = FakeLLM({"intent": [_intent("unsafe", "Xoá văn bản")]})
    r = _service(llm).ask("Xoá văn bản 4511/QĐ-ĐHBK")
    assert r.kind == "direct" and "không thể" in r.answer


def test_template_path_resolves_entities_and_composes_answer():
    executor = FakeExecutor()
    llm = FakeLLM({
        "intent": [_intent(question="Văn bản ĐHBK còn hiệu lực?")],
        "route": [_frame("list_documents", org="ĐHBK", status="CON_HIEU_LUC")],
        "answer": ["Có 1 văn bản: 1001/QĐ-ĐHBK (còn hiệu lực)."],
    })
    r = _service(llm, executor).ask("Văn bản ĐHBK còn hiệu lực?")
    assert (r.kind, r.template) == ("answer", "TPL_DOCS_BY_ORG_STATUS")
    assert executor.calls[0][1]["orgId"] == "truong_dai_hoc_bach_khoa"
    assert r.sources[0]["documentNumber"] == "1001/QĐ-ĐHBK"
    assert llm.calls == ["intent", "route", "answer"]


def test_template_documents_scope_graph_rag_and_its_context_reaches_response():
    retriever = FakeRetriever(_context())
    llm = FakeLLM({
        "intent": [_intent(question="Văn bản ĐHBK còn hiệu lực?")],
        "route": [_frame("list_documents", org="ĐHBK")],
        "answer": ["…"],
    })
    r = _service(llm, retriever=retriever).ask("Văn bản ĐHBK còn hiệu lực?")
    assert retriever.scopes == [("1001/QĐ-ĐHBK",)]
    assert r.retrieval[0]["effectiveStatus"] == "HET_HIEU_LUC"
    assert any(s.get("articleId") == "1001#Điều 3" for s in r.sources)


def test_graph_context_alone_is_enough_evidence_to_answer():
    llm = FakeLLM({
        "intent": [_intent(question="Học bổng?")],
        "route": [_frame("document_detail", doc_number="9999/QĐ-ĐHBK")],
        "answer": ["Theo Điều 3 của 1001/QĐ-ĐHBK…"],
    })
    r = _service(llm, FakeExecutor(rows=[]), FakeRetriever(_context())).ask("Học bổng?")
    assert r.kind == "answer" and "answer" in llm.calls


def test_router_missing_doc_number_is_backfilled_and_scopes_graph_rag():
    """Tái hiện lỗi thật: Gemini trả search_articles chỉ có phrase, bỏ trống doc_number."""

    executor, retriever = FakeExecutor(), FakeRetriever(_context())
    question = "Văn bản 2673/QĐ-ĐHBK quy định gì về nguyên tắc quản lý tài sản công?"
    llm = FakeLLM({"intent": [_intent(question=question)],
                   "route": [_frame("search_articles", phrase="nguyên tắc quản lý tài sản công")],
                   "answer": ["…"]})
    r = _service(llm, executor, retriever).ask(question)
    assert r.template == "TPL_DOC_ARTICLE_SEARCH"
    assert executor.calls[0][1]["normalizedNumber"] == "2673/QĐ-ĐHBK"
    assert retriever.scopes[0][0] == "2673/QĐ-ĐHBK"


def test_two_document_numbers_are_not_guessed():
    question = "So sánh 1214/QĐ-ĐHBK và 4511/QĐ-ĐHBK về học bổng"
    llm = FakeLLM({"intent": [_intent(question=question)], "route": [_frame("search_articles", phrase="học bổng")],
                   "answer": ["…"]})
    r = _service(llm).ask(question)
    assert r.template == "TPL_ARTICLE_FULLTEXT_SEARCH"


def test_empty_result_skips_answer_llm():
    llm = FakeLLM({
        "intent": [_intent(question="Văn bản 9999/QĐ-ĐHBK?")],
        "route": [_frame("document_detail", doc_number="9999/QĐ-ĐHBK")],
    })
    r = _service(llm, FakeExecutor(rows=[])).ask("Văn bản 9999/QĐ-ĐHBK?")
    assert r.kind == "no_data" and r.answer == NO_DATA_ANSWER
    assert "answer" not in llm.calls


def test_missing_slot_asks_back_then_completes_in_same_thread():
    llm = FakeLLM({
        "intent": [_intent(question="Văn bản nào còn hiệu lực?"),
                   _intent(question="Văn bản ĐHBK còn hiệu lực?", continues=True)],
        "route": [_frame("list_documents", status="CON_HIEU_LUC"),
                  _frame("list_documents", org="ĐHBK", status="CON_HIEU_LUC")],
        "answer": ["Có 1 văn bản."],
    })
    service = _service(llm)
    first = service.ask("Văn bản nào còn hiệu lực?", thread_id="t1")
    assert first.kind == "clarification" and first.clarification is not None
    second = service.ask("ĐHBK", thread_id="t1")
    assert (second.kind, second.template) == ("answer", "TPL_DOCS_BY_ORG_STATUS")


def test_unknown_entity_asks_back_with_reason():
    llm = FakeLLM({
        "intent": [_intent(question="Văn bản của Trường Không Tồn Tại?")],
        "route": [_frame("list_documents", org="Trường Không Tồn Tại")],
    })
    r = _service(llm).ask("Văn bản của Trường Không Tồn Tại?")
    assert r.kind == "clarification" and "không tìm thấy" in r.answer


def test_unsupported_slot_combination_goes_to_agent_which_uses_tools():
    executor = FakeExecutor()
    tool_call = AIMessage(content="", tool_calls=[{
        "name": "run_cypher", "id": "c1",
        "args": {"cypher": "MATCH (d:Document) RETURN d.documentNumber AS documentNumber"},
    }])
    llm = FakeLLM({
        "intent": [_intent(question="4511/QĐ-ĐHBK có phải do Đoàn Quang Vinh ký không?")],
        "route": [_frame("document_detail", doc_number="4511/QĐ-ĐHBK", person="Đoàn Quang Vinh")],
        "agent": [tool_call, AIMessage(content="Có 1 văn bản: 1001/QĐ-ĐHBK.")],
    })
    r = _service(llm, executor).ask("4511/QĐ-ĐHBK có phải do Đoàn Quang Vinh ký không?")
    assert r.kind == "agent_answer" and "1001/QĐ-ĐHBK" in r.answer
    assert r.cypher and r.cypher.endswith("LIMIT 200")
    assert executor.calls[0][0] == "freeform"


def test_multi_filter_question_uses_generic_filter_template_not_agent():
    executor = FakeExecutor()
    llm = FakeLLM({
        "intent": [_intent(question="Văn bản Công tác sinh viên do ĐHBK ban hành")],
        "route": [_frame("list_documents", org="ĐHBK", topic="Công tác sinh viên")],
        "answer": ["Có 1 văn bản: 1001/QĐ-ĐHBK."],
    })
    r = _service(llm, executor).ask("Văn bản Công tác sinh viên do ĐHBK ban hành")
    assert (r.kind, r.template) == ("answer", "TPL_DOCS_FILTERED")
    params = executor.calls[0][1]
    assert params["orgId"] == "truong_dai_hoc_bach_khoa" and params["topicId"] == "Công tác sinh viên"
    assert params["year"] is None  # bộ lọc không nêu -> NULL, Cypher tự bỏ qua


def test_agent_search_articles_context_reaches_response():
    search = AIMessage(content="", tool_calls=[{"name": "search_articles", "id": "s1", "args": {"query": "học bổng"}}])
    llm = FakeLLM({"intent": [_intent()], "route": [_frame("other")],
                   "agent": [search, AIMessage(content="Theo Điều 3 của 1001/QĐ-ĐHBK…")]})
    r = _service(llm, retriever=FakeRetriever(_context())).ask("Học bổng?")
    assert r.kind == "agent_answer"
    assert r.retrieval[0]["articleId"] == "1001#Điều 3" and r.retrieval[0]["supersededBy"] == ["1214/QĐ-ĐHBK"]
    assert any(s.get("articleId") == "1001#Điều 3" for s in r.sources)


def test_agent_stops_after_max_steps():
    looping = [AIMessage(content="", tool_calls=[{"name": "search_articles", "id": f"s{i}",
                                                   "args": {"query": "x"}}]) for i in range(10)]
    llm = FakeLLM({"intent": [_intent()], "route": [_frame("other")], "agent": looping})
    r = _service(llm).ask("câu khó")
    assert r.kind == "agent_answer"
    assert llm.calls.count("agent") <= 4


def test_infrastructure_error_returns_friendly_message():
    llm = FakeLLM({"intent": [_intent()], "route": [_frame("status_distribution")]})
    r = _service(llm, FakeExecutor(error=ServiceUnavailable("neo4j down"))).ask("Phân bố hiệu lực?")
    assert r.kind == "error" and r.answer == ERROR_ANSWER


def test_retrieval_failure_does_not_break_answer():
    class BrokenRetriever(FakeRetriever):
        def retrieve(self, question, *, scope_docs=()):
            raise RuntimeError("vector index chưa có embedding")

    llm = FakeLLM({"intent": [_intent()], "route": [_frame("status_distribution")], "answer": ["OK"]})
    r = _service(llm, retriever=BrokenRetriever()).ask("Phân bố hiệu lực?")
    assert r.kind == "answer" and r.retrieval_reason
