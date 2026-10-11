"""Chạy THẬT từng template với `example_params` (giá trị lấy từ graph) trên
Neo4j của module. Tự bỏ qua nếu Neo4j không chạy — bộ offline vẫn đủ."""

import pytest
from neo4j.exceptions import ServiceUnavailable

from core.chat.container import build_template_query_service
from core.graph_query.templates import TEMPLATES

# Template mà dữ liệu hiện tại có thể trả 0 dòng hợp lệ (không coi là lỗi).
MAY_BE_EMPTY: set[str] = set()


@pytest.fixture(scope="module")
def service():
    svc = build_template_query_service()
    try:
        svc.run("TPL_DOC_DISTRIBUTION_BY_STATUS", {})
    except ServiceUnavailable:
        pytest.skip("Neo4j (LKG) không chạy")
    return svc


@pytest.mark.parametrize("name", list(TEMPLATES))
def test_template_runs_on_real_graph(service, name):
    tpl = TEMPLATES[name]
    result = service.run(name, dict(tpl.example_params))
    if name not in MAY_BE_EMPTY:
        assert result.rows, f"{name} trả 0 dòng với example_params={tpl.example_params}"
