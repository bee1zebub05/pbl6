import pytest

from core.llm.gemini_key_pool import GeminiCallError, KeyPool, call_with_pool


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


def test_unknown_error_is_not_retried():
    pool = KeyPool("test", ["k1", "k2"])
    used = []

    def call(key, _client):
        used.append(key)
        raise ValueError("schema không hợp lệ")

    with pytest.raises(GeminiCallError):
        call_with_pool(pool, call, "test")
    assert used == ["k1"]
