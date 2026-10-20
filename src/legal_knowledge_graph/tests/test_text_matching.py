"""Nhận diện số hiệu trong câu tự do và dựng truy vấn Lucene — thuần Python."""

import pytest

from core.graph_query.entity_resolver import keyword_query, resolve_fulltext_phrase
from core.normalize import find_document_numbers


@pytest.mark.parametrize("text, expected", [
    ("Văn bản 2673/QĐ-ĐHBK quy định gì?", ["2673/QĐ-ĐHBK"]),
    ("Thông tư 08/2021/TT-BGDĐT, mục 3", ["08/2021/TT-BGDĐT"]),
    ("(4511/qđ-đhbk).", ["4511/qđ-đhbk"]),
    ("Nghị quyết 57-NQ/TW nói gì", ["57-NQ/TW"]),
    ("30a/2008/NQ-CP và 16/2006/TTLT/BLĐTBXH-BGDĐT-BTC", ["30a/2008/NQ-CP", "16/2006/TTLT/BLĐTBXH-BGDĐT-BTC"]),
    ("so sánh 1214/QĐ-ĐHBK với 1214/QĐ-ĐHBK", ["1214/QĐ-ĐHBK"]),
])
def test_document_numbers_are_found(text, expected):
    assert find_document_numbers(text) == expected


@pytest.mark.parametrize("text", [
    "Ngày 12/3/2024 có văn bản nào?", "Năm học 2024/2025", "tỷ lệ 3/4 sinh viên", "Học kỳ 1/2024-2025",
    "Lớp 21TCLC/DT1", "COVID-19/SARS", "Học phí 1.200.000 đồng/tín chỉ", "Điều 5 quy định gì?",
])
def test_dates_fractions_and_codes_are_not_document_numbers(text):
    assert find_document_numbers(text) == []


def test_short_phrase_stays_exact():
    # "học vụ" là MỘT từ hai âm tiết — tách ra AND sẽ khớp nhầm hàng nghìn Điều.
    assert resolve_fulltext_phrase("học vụ") == '"học vụ"'


def test_long_phrase_also_matches_all_syllables_out_of_order():
    assert resolve_fulltext_phrase("Nguyên tắc quản lý tài sản") == \
        '"Nguyên tắc quản lý tài sản"^2 OR (nguyên AND tắc AND quản AND lý AND tài AND sản)'


def test_keyword_query_drops_document_numbers_and_question_stopwords():
    query = keyword_query("Văn bản 2673/QĐ-ĐHBK quy định gì về tài sản công?")
    assert query == '"tài sản"^2 OR "sản công"^2 OR tài OR sản OR công'


def test_keyword_query_pairs_syllables_within_each_span_only():
    # "là"/"gì" cắt đoạn: không sinh cặp vắt qua từ dừng.
    query = keyword_query("Học bổng là gì")
    assert query == '"học bổng"^2 OR học OR bổng'


def test_keyword_query_keeps_dieu_kien_and_drops_bare_numbers():
    assert keyword_query("Điều kiện tốt nghiệp").startswith('"điều kiện"^2')
    assert keyword_query("Điều 5 quy định gì?") == '"điều 5"^2 OR điều'


def test_keyword_query_of_only_stopwords_is_empty():
    assert keyword_query("Văn bản nào còn hiệu lực?") == ""


def test_phrase_escapes_lucene_operators():
    assert resolve_fulltext_phrase('học phí "AND" (miễn)') == '"học phí AND miễn"^2 OR (học AND phí AND and AND miễn)'
