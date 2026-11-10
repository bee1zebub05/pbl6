"""Resolver thuần Python: số Điều / mục, danh xưng người ký, enum khớp JSON schema."""

import json

import pytest

from core import config
from core.graph_query import entity_resolver as er, schema


@pytest.mark.parametrize("raw, expected", [
    ("Điều 5", "Điều 5"), ("điều 5a", "Điều 5a"), ("5", "Điều 5"), ("Khoản 2 Điều 7", "Điều 7"),
    ("2.1", "2.1"), ("Mục 3", "3"), ("mục 2.1.", "2.1"), ("IV", "IV"), ("Phần II", "II"),
])
def test_article_number_keeps_the_numbering_of_the_document(raw, expected):
    assert er.resolve_article_number(raw) == er.Resolved(expected)


def test_article_number_without_a_number_is_not_found():
    assert isinstance(er.resolve_article_number("cuối cùng"), er.NotFound)


@pytest.mark.parametrize("raw, expected", [
    ("thầy Đoàn Quang Vinh", "Đoàn Quang Vinh"), ("PGS.TS Nguyễn Văn A", "Nguyễn Văn A"),
    ("TS. Lê B", "Lê B"), ("Công Minh", "Công Minh"), ("Bàng Thị A", "Bàng Thị A"),
])
def test_honorifics_only_strip_whole_words(raw, expected):
    assert er._HONORIFICS.sub("", raw).strip() == expected


def test_enums_match_the_json_schema():
    defs = json.loads(config.SCHEMA_PATH.read_text(encoding="utf-8"))["$defs"]
    assert set(schema.ENUMS["NormativeContent.contentType"]) == set(
        defs["normativeContent"]["properties"]["contentType"]["enum"])
    assert set(schema.ENUMS["Document.documentType"]) == set(defs["document"]["properties"]["documentType"]["enum"])
