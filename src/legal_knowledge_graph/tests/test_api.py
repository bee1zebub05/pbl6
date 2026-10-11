"""Chat API: dựng chatbot lúc khởi động (cấu hình sai thì không lên) và CORS theo cấu hình.
Không gọi LLM: chỉ dựng đối tượng, Neo4j và Gemini đều kết nối lười."""

import pytest
from fastapi.testclient import TestClient

from core import config
from core.api.app import app
from core.chat import container


@pytest.fixture
def fresh_service(monkeypatch):
    monkeypatch.setattr(container, "_default_service", None)


def test_startup_builds_chat_service(fresh_service):
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        assert container._default_service is not None


def test_bad_llm_config_stops_server_at_startup(fresh_service, monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "claude")
    with pytest.raises(ValueError, match="LKG_LLM_PROVIDER"):
        with TestClient(app):
            pass


@pytest.mark.parametrize("origin, allowed", [("http://localhost:5173", True), ("https://evil.example", False)])
def test_cors_follows_configured_origins(origin, allowed):
    client = TestClient(app)  # không vào context -> không chạy lifespan
    response = client.options("/api/chat", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
    assert (response.headers.get("access-control-allow-origin") == origin) is allowed
