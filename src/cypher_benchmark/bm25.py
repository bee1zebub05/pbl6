"""
Baseline BM25 cho 20 kịch bản: đưa NGUYÊN câu hỏi tiếng Việt vào full-text
index của Neo4j (Lucene, xếp hạng BM25, analyzer `standard-no-stop-words`)
rồi lấy danh sách ID theo thứ hạng — không hiểu cấu trúc, không lọc theo
thuộc tính/quan hệ. Đây là đối chứng "tìm kiếm từ khoá thuần" cho Cypher.

Chọn index theo đơn vị đáp án của case (`Query.id_field`):

    documentNumber -> doc_text      (Document.title, summary)
    articleId      -> article_text  (Article.heading, text)
    contentId      -> content_text  (NormativeContent.title)

Đơn vị khác (orgId, tên tổ chức) không có full-text index -> BM25 không trả
lời được, trả về danh sách rỗng. Câu đếm/thống kê (không có `id_field`) cũng
vậy: BM25 chỉ trả văn bản, không tính ra con số.
"""

from __future__ import annotations

import re

from .query import Query

INDEX_BY_FIELD = {
    "documentNumber": ("doc_text", "documentNumber"),
    "articleId": ("article_text", "articleId"),
    "contentId": ("content_text", "contentId"),
}

# Ký tự đặc biệt của cú pháp Lucene — thay bằng khoảng trắng.
_LUCENE_SPECIAL = re.compile(r'[+\-&|!(){}\[\]^"~*?:\/]')


def lucene_query(question: str) -> str:
    """Câu hỏi -> các từ rời, OR mặc định. Viết thường để "và/hoặc" không bao
    giờ thành toán tử (Lucene chỉ nhận AND/OR/NOT viết hoa)."""

    return re.sub(r"\s+", " ", _LUCENE_SPECIAL.sub(" ", question)).strip().lower()


def search(session, query: Query, limit: int) -> list[str] | None:
    """Danh sách ID theo điểm BM25 giảm dần; None nếu BM25 không áp dụng."""

    target = INDEX_BY_FIELD.get(query.id_field or "")
    if target is None or not query.question:
        return None
    index, prop = target
    rows = session.run(
        "CALL db.index.fulltext.queryNodes($index, $q) YIELD node, score "
        f"RETURN node.{prop} AS id ORDER BY score DESC LIMIT $limit",
        index=index, q=lucene_query(query.question), limit=limit,
    )
    return [r["id"] for r in rows if r["id"] is not None]
