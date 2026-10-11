"""
Thuật toán GraphRAG thuần Python (không I/O — adapter adapters/graph_retriever.py
lo embed và Cypher): gộp hạng các nguồn hạt giống, hiệu chỉnh hiệu lực theo
quan hệ, đóng gói ngữ cảnh theo ngân sách ký tự.
"""

from __future__ import annotations

from collections import defaultdict

from ..models import ArticleEvidence, DocumentContext, GraphContext, RelatedDocument

HET_HIEU_LUC = "HET_HIEU_LUC"


def fuse_rrf(ranked: dict[str, list[dict]], rrf_k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion: điểm = Σ 1/(rrf_k + hạng) qua các nguồn. Chỉ
    dùng THỨ HẠNG nên không cần chuẩn hoá điểm cosine với điểm BM25.
    -> danh sách Điều (bản sao dòng đầu tiên gặp) kèm `score` và `via`."""

    merged: dict[str, dict] = {}
    for source, rows in ranked.items():
        for rank, row in enumerate(rows, start=1):
            item = merged.setdefault(row["articleId"], {**row, "score": 0.0, "via": []})
            item["score"] += 1.0 / (rrf_k + rank)
            item["via"].append(source)
    return sorted(merged.values(), key=lambda r: r["score"], reverse=True)


def superseding(doc_row: dict) -> list[RelatedDocument]:
    """Văn bản thay thế / bãi bỏ văn bản này. Bỏ cạnh ngược thời gian (văn bản
    'thay thế' ban hành TRƯỚC văn bản bị thay thế — lỗi trích xuất, đã gặp
    trên dữ liệu thật); thiếu ngày thì tin cạnh."""

    issued = doc_row.get("issueDate")
    return [RelatedDocument(**r) for r in (doc_row.get("replacedBy") or []) + (doc_row.get("repealedBy") or [])
            if not (issued and r.get("issueDate") and r["issueDate"] < issued)]


def effective_status(status: str | None, superseded_by: list[RelatedDocument]) -> str | None:
    """Quan hệ thắng thuộc tính: đã có văn bản thay thế / bãi bỏ thì coi là hết
    hiệu lực dù `status` trong graph chưa cập nhật."""

    return HET_HIEU_LUC if superseded_by else status


def _clip(text: str | None, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + "…"


class GraphRagService:
    def __init__(self, *, top_k: int, context_chars: int, article_chars: int, short_article_chars: int = 400):
        self._top_k = top_k
        self._context_chars = context_chars
        self._article_chars = article_chars
        self._short_article_chars = short_article_chars

    def select_seeds(self, vector: list[dict], fulltext: list[dict], scoped: list[dict]) -> list[dict]:
        """top_k Điều sau khi gộp vector + fulltext, rồi thêm Điều trong văn
        bản template vừa trả về (người dùng đang hỏi đúng các văn bản đó)."""

        seeds = fuse_rrf({"vector": vector, "fulltext": fulltext})[: self._top_k]
        seen = {s["articleId"] for s in seeds}
        for item in fuse_rrf({"scope": scoped}):
            if item["articleId"] in seen:
                next(s for s in seeds if s["articleId"] == item["articleId"])["via"].append("scope")
            else:
                seeds.append(item)
                seen.add(item["articleId"])
        return seeds

    def short_seed_ids(self, seeds: list[dict]) -> list[str]:
        """Điều quá ngắn để tự đứng (vd chỉ một câu dẫn) -> cần Điều liền kề."""

        return [s["articleId"] for s in seeds if len(s.get("text") or "") < self._short_article_chars]

    def build(self, seeds: list[dict], doc_rows: list[dict], neighbor_rows: list[dict],
              priority_keys: tuple[str, ...] = ()) -> GraphContext:
        """Gom Điều theo văn bản, gắn quan hệ, xếp ưu tiên rồi cắt theo ngân sách.
        Văn bản trong `priority_keys` (khoá normalizedNumber) đứng trước, còn lại theo
        điểm Điều cao nhất."""

        docs_by_key = {r["docKey"]: r for r in doc_rows}
        neighbors: dict[str, list[dict]] = defaultdict(list)
        for n in neighbor_rows:
            neighbors[n["articleId"]].append(n)

        grouped: dict[str, list[dict]] = defaultdict(list)
        for s in seeds:
            if s.get("docKey") in docs_by_key:
                grouped[s["docKey"]].append(s)

        def priority(key: str) -> tuple:
            rank = priority_keys.index(key) if key in priority_keys else len(priority_keys)
            return rank, -max(s["score"] for s in grouped[key])

        budget = self._context_chars
        documents: list[DocumentContext] = []
        for key in sorted(grouped, key=priority):
            articles: list[ArticleEvidence] = []
            for s in sorted(grouped[key], key=lambda x: x["score"], reverse=True):
                if budget <= 0:
                    break
                article = self._article(s, neighbors.get(s["articleId"], []))
                budget -= len(article.text) + sum(len(n.text) for n in article.neighbors)
                articles.append(article)
            if articles:
                documents.append(self._document(docs_by_key[key], articles))
        return GraphContext(documents=documents)

    def _article(self, seed: dict, neighbor_rows: list[dict]) -> ArticleEvidence:
        return ArticleEvidence(
            articleId=seed["articleId"], number=seed.get("number"), heading=seed.get("heading"),
            text=_clip(seed.get("text"), self._article_chars), container=seed.get("container"),
            score=round(seed["score"], 5), via=list(seed["via"]),
            neighbors=[ArticleEvidence(articleId=n["neighborId"], number=n.get("number"), heading=n.get("heading"),
                                       text=_clip(n.get("text"), self._article_chars // 2))
                       for n in neighbor_rows],
        )

    @staticmethod
    def _document(row: dict, articles: list[ArticleEvidence]) -> DocumentContext:
        superseded_by = superseding(row)
        return DocumentContext(
            documentNumber=row["documentNumber"], title=row.get("title"), documentType=row.get("documentType"),
            issueDate=row.get("issueDate"), issuers=row.get("issuers") or [], status=row.get("status"),
            effectiveStatus=effective_status(row.get("status"), superseded_by), supersededBy=superseded_by,
            amendedBy=[RelatedDocument(**r) for r in row.get("amendedBy") or []],
            basedOn=[RelatedDocument(**r) for r in row.get("basedOn") or []],
            articles=articles,
        )
