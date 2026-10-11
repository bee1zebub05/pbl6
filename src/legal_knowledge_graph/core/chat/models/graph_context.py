"""Ngữ cảnh GraphRAG (retrieval/graph_rag.py dựng, answering/evidence.py trình bày)."""

from __future__ import annotations

from pydantic import BaseModel

class RelatedDocument(BaseModel):
    """Văn bản nối với văn bản đang xét qua một quan hệ (thay thế, căn cứ...)."""

    documentNumber: str
    title: str | None = None
    status: str | None = None
    issueDate: str | None = None
    targetArticle: str | None = None  # chỉ có ở AMENDS


class ArticleEvidence(BaseModel):
    articleId: str
    number: str | None = None
    heading: str | None = None
    text: str = ""
    container: str | None = None       # tiêu đề nội dung kèm theo chứa Điều (nếu có)
    score: float = 0.0                 # điểm RRF sau khi gộp các nguồn
    via: list[str] = []                # vector | fulltext | scope
    neighbors: list["ArticleEvidence"] = []


class DocumentContext(BaseModel):
    documentNumber: str
    title: str | None = None
    documentType: str | None = None
    issueDate: str | None = None
    issuers: list[str] = []
    status: str | None = None          # nguyên giá trị trong graph
    effectiveStatus: str | None = None  # đã hiệu chỉnh theo quan hệ thay thế / bãi bỏ
    supersededBy: list[RelatedDocument] = []  # văn bản thay thế / bãi bỏ có hiệu lực thật
    amendedBy: list[RelatedDocument] = []
    basedOn: list[RelatedDocument] = []
    articles: list[ArticleEvidence] = []


class GraphContext(BaseModel):
    """Bằng chứng GraphRAG, gom theo văn bản. Lưu vào state bằng model_dump()."""

    documents: list[DocumentContext] = []

    def is_empty(self) -> bool:
        return not any(d.articles for d in self.documents)

    def hits(self) -> list[dict]:
        """Dạng phẳng mỗi Điều một dòng — trường `retrieval` của API và nguồn trích dẫn."""

        return [
            {"articleId": a.articleId, "heading": a.heading, "text": a.text, "score": a.score, "via": a.via,
             "documentNumber": d.documentNumber, "status": d.status, "effectiveStatus": d.effectiveStatus,
             "supersededBy": [s.documentNumber for s in d.supersededBy]}
            for d in self.documents for a in d.articles
        ]
