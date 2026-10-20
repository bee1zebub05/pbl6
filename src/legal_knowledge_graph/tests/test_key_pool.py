import time

import pytest

from core.chat.adapters.gemini_llm import GeminiPooledLLM
from core.llm.gemini_key_pool import GeminiCallError, KeyPool, ModelOverloaded, call_with_pool
from core.observability import turn_context


@pytest.mark.parametrize("error", [
    "429 RESOURCE_EXHAUSTED",
    "503 UNAVAILABLE. This model is currently experiencing high demand",
    "504 DEADLINE_EXCEEDED. Deadline expired before operation could complete.",
])
def test_transient_error_moves_to_next_key(error):
    pool = KeyPool("test", ["k1", "k2"])
    used = []

    def call(key, _client):
        used.append(key)
        if key == "k1":
            raise RuntimeError(error)
        return "ok"

    assert call_with_pool(pool, call, "test") == "ok"
    assert used == ["k1", "k2"]


def test_dead_key_is_removed_and_last_one_raises():
    pool = KeyPool("test", ["k1"])

    def call(key, _client):
        raise RuntimeError("403 PERMISSION_DENIED")

    with pytest.raises(GeminiCallError):
        call_with_pool(pool, call, "test")
    assert len(pool) == 0


def test_overload_fails_fast_without_cooling_the_key():
    pool = KeyPool("test", ["k1", "k2"])
    used = []

    def call(key, _client):
        used.append(key)
        raise RuntimeError("503 UNAVAILABLE. This model is currently experiencing high demand")

    with pytest.raises(ModelOverloaded):
        call_with_pool(pool, call, "test", fail_fast_on_overload=True)
    assert used == ["k1"] and pool.seconds_until_available() == 0


def test_turn_deadline_stops_the_pool_before_calling():
    pool = KeyPool("test", ["k1"])
    used = []
    with turn_context("t", deadline_seconds=0.001):
        time.sleep(0.01)
        with pytest.raises(GeminiCallError, match="hết thời gian của lượt hỏi"):
            call_with_pool(pool, lambda key, _c: used.append(key), "test")
    assert used == []


def test_gemini_switches_to_fallback_model_on_overload_and_skips_primary_for_a_while():
    llm = GeminiPooledLLM("main", 30, fallback_model="lite")
    calls = []

    def fake_call_model(model, build, messages, info, *, fail_fast_on_overload=False):
        calls.append((model, fail_fast_on_overload))
        if model == "main":
            raise ModelOverloaded("503")
        return "ok"

    llm._call_model = fake_call_model
    assert llm._call(None, [], {}) == "ok"
    assert llm._call(None, [], {}) == "ok"
    assert calls == [("main", True), ("lite", False), ("lite", False)]


def test_gemini_without_fallback_keeps_pool_retry_behaviour():
    llm = GeminiPooledLLM("main", 30)
    calls = []
    llm._call_model = lambda model, build, messages, info, **kw: calls.append((model, kw)) or "ok"
    assert llm._call(None, [], {}) == "ok"
    assert calls == [("main", {})]


def test_unknown_error_is_not_retried():
    pool = KeyPool("test", ["k1", "k2"])
    used = []

    def call(key, _client):
        used.append(key)
        raise ValueError("schema không hợp lệ")

    with pytest.raises(GeminiCallError):
        call_with_pool(pool, call, "test")
    assert used == ["k1"]
