from core.chat.answering.evidence import collect_sources, rows_to_text, to_plain_text


def test_rows_hitting_query_limit_are_flagged_as_truncated():
    text = rows_to_text([{"documentNumber": str(i)} for i in range(50)], limit=30, query_limit=50)
    assert "ĐÃ CHẠM GIỚI HẠN 50" in text and "hiển thị 30/50" in text


def test_rows_below_query_limit_are_not_flagged():
    assert "GIỚI HẠN" not in rows_to_text([{"a": 1}] * 3, limit=30, query_limit=50)


def test_markdown_is_stripped():
    assert to_plain_text("Có **13 văn bản**\n## Danh sách\n- a") == "Có 13 văn bản\nDanh sách\n- a"


def test_sources_are_deduplicated_across_rows_and_hits():
    rows = [{"documentNumber": "1/QĐ", "title": "A"}, {"documentNumber": "1/QĐ", "title": "A"}]
    hits = [{"documentNumber": "1/QĐ", "articleId": "1/QD#Điều 2", "heading": "Phạm vi"}]
    sources = collect_sources(rows, hits)
    assert [s.get("articleId") for s in sources] == [None, "1/QD#Điều 2"]


def test_row_source_status_is_corrected_by_graph_context():
    rows = [{"documentNumber": "1/QĐ", "status": "CON_HIEU_LUC"}]
    hits = [{"documentNumber": "1/QĐ", "articleId": "1#Điều 2", "effectiveStatus": "HET_HIEU_LUC"}]
    assert collect_sources(rows, hits)[0]["status"] == "HET_HIEU_LUC"


def test_full_article_text_reaches_the_prompt():
    text = rows_to_text([{"articleId": "x", "text": "a" * 1200}], limit=30)
    assert text.count("a") >= 1200 and "đã cắt" not in text


def test_other_long_columns_are_still_shortened():
    assert rows_to_text([{"title": "a" * 1200}], limit=30).count("a") < 400


def test_text_over_budget_is_cut_and_says_so():
    text = rows_to_text([{"text": "a" * 50000}], limit=30)
    assert text.count("a") < 50000 and "đã cắt" in text


def test_current_version_of_latest_version_template_is_the_source():
    rows = [{"askedDocument": "1489/QĐ-ĐHĐN", "askedStatus": "HET_HIEU_LUC", "currentVersion": "1899/QĐ-ĐHĐN"}]
    assert [s["documentNumber"] for s in collect_sources(rows, [])] == ["1899/QĐ-ĐHĐN"]


def test_graph_rag_scope_includes_the_current_version():
    from core.chat.workflow.nodes import _documents_in

    rows = [{"askedDocument": "1489/QĐ-ĐHĐN", "currentVersion": "1899/QĐ-ĐHĐN"}]
    assert _documents_in({"normalizedNumber": "1489/QD-DHDN"}, rows) == ("1489/QD-DHDN", "1899/QĐ-ĐHĐN")
