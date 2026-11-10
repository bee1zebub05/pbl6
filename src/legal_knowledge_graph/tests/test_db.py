"""core/db.py: kết quả Neo4j phải là kiểu thuần để qua được checkpoint và API."""

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from neo4j.graph import Graph, Node
from neo4j.time import Date

from core.chat.models import ChatResponse
from core.db import run_in_session


class _Tx:
    def __init__(self, rows):
        self._rows = rows

    def run(self, cypher, **params):
        return self._rows

    def commit(self):
        pass

    def close(self):
        pass


class _Session:
    def __init__(self, rows):
        self._rows = rows

    def begin_transaction(self, timeout=None):
        return _Tx(self._rows)


def _node():
    return Node(Graph(), "4:x:1", 1, ["Article"], {"articleId": "a", "embedding": [0.1] * 768})


def test_nodes_become_plain_dicts_without_embedding():
    source = [{"a": _node(), "d": Date(2024, 1, 2), "m": {"embedding": [1.0], "x": 1}}]
    rows = run_in_session(_Session(source), "q", {}, 1).rows
    assert rows == [{"a": {"articleId": "a"}, "d": "2024-01-02", "m": {"x": 1}}]
    JsonPlusSerializer().dumps_typed(rows)
    ChatResponse(thread_id="t", turn_id="u", kind="agent_answer", answer="ok", elapsed_ms=1,
                 rows=rows).model_dump(mode="json")
