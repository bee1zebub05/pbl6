"""GraphRAG phần thuần Python: gộp hạng, hiệu chỉnh hiệu lực, đóng gói, trình bày."""

from core.chat.models import RelatedDocument
from core.chat.answering.evidence import context_to_text
from core.chat.retrieval.graph_rag import GraphRagService, effective_status, fuse_rrf, superseding


def _seed(article_id, doc="1/QĐ", text="nội dung đủ dài " * 40, **extra):
    return {"articleId": article_id, "number": article_id.split("#")[-1], "heading": "Tiêu đề", "text": text,
            "docKey": doc, "documentNumber": doc, "container": None, **extra}


def _doc(number, status="CON_HIEU_LUC", issue="2020-01-01", **rel):
    return {"docKey": number, "documentNumber": number, "title": f"Văn bản {number}", "documentType": "Quyết định",
            "issueDate": issue, "status": status, "issuers": ["Trường Đại học Bách khoa"],
            "replacedBy": rel.get("replacedBy", []), "repealedBy": rel.get("repealedBy", []),
            "amendedBy": rel.get("amendedBy", []), "basedOn": rel.get("basedOn", [])}


def _service(**kw):
    return GraphRagService(**{"top_k": 3, "context_chars": 10_000, "article_chars": 500, **kw})


def test_rrf_puts_article_found_by_both_sources_first():
    fused = fuse_rrf({"vector": [_seed("a"), _seed("b")], "fulltext": [_seed("c"), _seed("b")]})
    assert fused[0]["articleId"] == "b" and fused[0]["via"] == ["vector", "fulltext"]


def test_scope_articles_are_added_after_top_k_and_marked_when_overlapping():
    seeds = _service(top_k=2).select_seeds([_seed("a"), _seed("b"), _seed("x")], [], [_seed("b"), _seed("s")])
    assert [s["articleId"] for s in seeds] == ["a", "b", "s"]
    assert seeds[1]["via"] == ["vector", "scope"]


def test_replaced_document_is_effectively_expired_despite_status():
    row = _doc("1/QĐ", replacedBy=[{"documentNumber": "2/QĐ", "issueDate": "2024-01-01"}])
    superseded = superseding(row)
    assert [s.documentNumber for s in superseded] == ["2/QĐ"]
    assert effective_status("CON_HIEU_LUC", superseded) == "HET_HIEU_LUC"


def test_replacement_issued_before_target_is_ignored_as_extraction_error():
    row = _doc("1/QĐ", issue="2026-01-16", replacedBy=[{"documentNumber": "0/QĐ", "issueDate": "2025-05-27"}])
    assert superseding(row) == []


def test_amendment_keeps_status():
    assert effective_status("CON_HIEU_LUC", []) == "CON_HIEU_LUC"


def test_build_groups_by_document_and_prioritises_scope_docs():
    seeds = fuse_rrf({"vector": [_seed("A#Điều 1", doc="A"), _seed("B#Điều 2", doc="B")]})
    ctx = _service().build(seeds, [_doc("A"), _doc("B")], [], priority_keys=("B",))
    assert [d.documentNumber for d in ctx.documents] == ["B", "A"]
    assert ctx.hits()[0]["articleId"] == "B#Điều 2"


def _total_chars(ctx):
    return sum(len(a.text) + sum(len(n.text) for n in a.neighbors) for d in ctx.documents for a in d.articles)


def test_build_never_exceeds_budget_and_clips_long_articles():
    seeds = fuse_rrf({"vector": [_seed(f"A#Điều {i}", doc="A", text="x" * 2000) for i in range(5)]})
    ctx = _service(context_chars=1200, article_chars=500).build(seeds, [_doc("A")], [])
    articles = ctx.documents[0].articles
    # 2 Điều (501 ký tự mỗi Điều) — phần còn lại 198 ký tự quá ít để cắt thêm một Điều.
    assert len(articles) == 2 and all(len(a.text) <= 501 for a in articles)
    assert _total_chars(ctx) <= 1200


def test_last_article_is_clipped_to_fit_remaining_budget():
    seeds = fuse_rrf({"vector": [_seed(f"A#Điều {i}", doc="A", text="x" * 2000) for i in range(5)]})
    ctx = _service(context_chars=1400, article_chars=500).build(seeds, [_doc("A")], [])
    articles = ctx.documents[0].articles
    assert len(articles) == 3 and len(articles[2].text) == 1400 - 2 * 501
    assert _total_chars(ctx) == 1400


def test_short_seed_gets_neighbors_attached():
    service = _service()
    seeds = fuse_rrf({"vector": [_seed("A#Điều 3", doc="A", text="Ngắn.")]})
    assert service.short_seed_ids(seeds) == ["A#Điều 3"]
    neighbor = {"articleId": "A#Điều 3", "neighborId": "A#Điều 4", "number": "Điều 4", "heading": "Kế",
                "text": "Nội dung Điều 4"}
    ctx = service.build(seeds, [_doc("A")], [neighbor])
    assert ctx.documents[0].articles[0].neighbors[0].articleId == "A#Điều 4"


def test_seed_without_expanded_document_is_dropped():
    ctx = _service().build(fuse_rrf({"vector": [_seed("Z#Điều 1", doc="Z")]}), [], [])
    assert ctx.is_empty()


def test_context_text_shows_corrected_status_replacement_and_amendment():
    row = _doc("1/QĐ", replacedBy=[{"documentNumber": "2/QĐ", "title": "Quy chế mới", "issueDate": "2024-01-01"}],
               amendedBy=[{"documentNumber": "3/QĐ", "targetArticle": "Điều 5"}],
               basedOn=[{"documentNumber": "08/2021/TT-BGDĐT"}])
    ctx = _service().build(fuse_rrf({"vector": [_seed("1#Điều 12", doc="1/QĐ")]}), [row], [])
    text = context_to_text(ctx)
    assert "Hiệu lực: HET_HIEU_LUC" in text and "2/QĐ — Quy chế mới" in text
    assert "vẫn ghi CON_HIEU_LUC" in text
    assert "[sửa Điều 5]" in text
    assert "08/2021/TT-BGDĐT (chưa có toàn văn trong kho)" in text
    hit = ctx.hits()[0]
    assert hit["effectiveStatus"] == "HET_HIEU_LUC" and hit["supersededBy"] == ["2/QĐ"]


def test_related_document_model_accepts_graph_maps():
    assert RelatedDocument(documentNumber="1/QĐ", title=None, status=None, issueDate=None).title is None
