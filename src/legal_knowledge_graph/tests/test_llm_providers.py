"""Đổi nhà cung cấp LLM / embedding bằng cấu hình. Provider OpenAI-compatible
được kiểm qua một server giả chạy cục bộ theo đúng chuẩn OpenAI API — đi trọn
đường thật (base_url, api_key, structured output, tool calling, embedding)
mà không cần mạng."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from core import config
from core.chat import container
from core.chat.adapters.gemini_llm import GeminiPooledLLM
from core.chat.adapters.openai_compatible_llm import OpenAICompatibleLLM
from core.chat.models import RouterOutput
from core.llm import embeddings


class _FakeOpenAI(BaseHTTPRequestHandler):
    requests: list[dict] = []
    embedding_dims = 4

    def log_message(self, *args):  # im lặng
        pass

    def _reply(self, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        req["_auth"] = self.headers.get("Authorization")
        req["_path"] = self.path
        _FakeOpenAI.requests.append(req)
        if self.path.endswith("/embeddings"):
            data = [{"object": "embedding", "index": i, "embedding": [0.1] * self.embedding_dims}
                    for i, _ in enumerate(req["input"])]
            return self._reply({"object": "list", "data": data, "model": req["model"],
                                "usage": {"prompt_tokens": 1, "total_tokens": 1}})
        message = {"role": "assistant", "content": "Xin chào"}
        if req.get("tools"):
            name = req["tools"][0]["function"]["name"]
            message = {"role": "assistant", "content": None, "tool_calls": [{
                "id": "call_1", "type": "function",
                "function": {"name": name, "arguments": json.dumps({"query": "học bổng"})}}]}
        elif req.get("response_format", {}).get("type") == "json_schema":
            message["content"] = json.dumps({"action": "search_articles", **{k: None for k in
                                             req["response_format"]["json_schema"]["schema"]["properties"]
                                             if k != "action"}, "phrase": "học bổng"})
        self._reply({"id": "x", "object": "chat.completion", "created": 0, "model": req["model"],
                     "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
                     "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})


@pytest.fixture(scope="module")
def server_url():
    httpd = HTTPServer(("127.0.0.1", 0), _FakeOpenAI)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}/v1"
    httpd.shutdown()


@pytest.fixture
def llm(server_url):
    _FakeOpenAI.requests.clear()
    return OpenAICompatibleLLM(model_name="qwen-test", base_url=server_url, api_key="sk-local",
                               structured_method="json_schema", timeout_seconds=5, max_retries=0)


def test_structured_output_goes_through_json_schema(llm):
    out = llm.structured(RouterOutput, [HumanMessage("Học bổng?")], node="route")
    assert (out.action, out.phrase, out.org) == ("search_articles", "học bổng", None)
    req = _FakeOpenAI.requests[-1]
    assert req["model"] == "qwen-test" and req["_auth"] == "Bearer sk-local"
    # Schema gửi đi vẫn bắt buộc đủ mọi key — quy tắc của RouterOutput giữ nguyên với provider này.
    schema = req["response_format"]["json_schema"]["schema"]
    assert set(schema["required"]) == set(schema["properties"])


def test_text_and_tool_calling(llm):
    assert llm.text([HumanMessage("Chào")], node="answer") == "Xin chào"

    @tool
    def search_articles(query: str) -> str:
        """Tìm Điều."""
        return query

    message = llm.invoke_with_tools([HumanMessage("Học bổng?")], [search_articles], node="agent")
    assert message.tool_calls[0]["name"] == "search_articles"
    assert message.tool_calls[0]["args"] == {"query": "học bổng"}


def test_llm_call_is_written_to_session_log_with_prompt_and_output(llm, monkeypatch, tmp_path):
    from core.chat import session_log

    monkeypatch.setattr(config, "SESSION_LOG_ENABLED", True)
    monkeypatch.setattr(config, "SESSION_LOG_DIR", tmp_path)
    with session_log.turn("t-provider", "turn1", "Học bổng?"):
        llm.structured(RouterOutput, [HumanMessage("CÂU HỎI: Học bổng?")], node="route")
    text = session_log.session_path("t-provider").read_text(encoding="utf-8")
    assert "[route] LLM qwen-test" in text and "CÂU HỎI: Học bổng?" in text and '"phrase": "học bổng"' in text


def test_build_llm_picks_provider_from_config(monkeypatch, server_url):
    monkeypatch.setattr(config, "LLM_PROVIDER", "openai_compatible")
    monkeypatch.setattr(config, "LLM_MODEL", "qwen-test")
    monkeypatch.setattr(config, "LLM_BASE_URL", server_url)
    assert isinstance(container.build_llm(), OpenAICompatibleLLM)

    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "LLM_MODEL", "gemini-3.6-flash")
    assert isinstance(container.build_llm(), GeminiPooledLLM)


@pytest.mark.parametrize("setting, value, message", [
    ("LLM_PROVIDER", "claude", "LKG_LLM_PROVIDER"),
    ("LLM_MODEL", "", "LKG_LLM_MODEL"),
    ("LLM_STRUCTURED_METHOD", "xml", "LKG_LLM_STRUCTURED_METHOD"),
])
def test_bad_llm_config_fails_fast_with_clear_message(monkeypatch, setting, value, message):
    monkeypatch.setattr(config, "LLM_PROVIDER", "openai_compatible")
    monkeypatch.setattr(config, "LLM_MODEL", "qwen-test")
    monkeypatch.setattr(config, setting, value)
    with pytest.raises(ValueError, match=message):
        container.build_llm()


@pytest.fixture
def openai_embeddings(monkeypatch, server_url):
    monkeypatch.setattr(config, "EMBED_PROVIDER", "openai_compatible")
    monkeypatch.setattr(config, "EMBED_MODEL", "bge-test")
    monkeypatch.setattr(config, "EMBED_BASE_URL", server_url)
    monkeypatch.setattr(config, "EMBED_API_KEY", "")
    embeddings._openai_client.cache_clear()
    yield
    embeddings._openai_client.cache_clear()


def test_openai_compatible_embeddings(monkeypatch, openai_embeddings):
    monkeypatch.setattr(config, "EMBED_DIMENSIONS", 4)
    vectors = embeddings.embed_texts(["a", "b"], kind="document")
    assert vectors == [[0.1] * 4, [0.1] * 4]
    assert _FakeOpenAI.requests[-1]["_path"].endswith("/embeddings")


def test_embedding_dimension_mismatch_explains_how_to_fix(monkeypatch, openai_embeddings):
    monkeypatch.setattr(config, "EMBED_DIMENSIONS", 768)
    with pytest.raises(embeddings.EmbeddingError, match="embed-articles --reset"):
        embeddings.embed_texts(["a"], kind="query")
