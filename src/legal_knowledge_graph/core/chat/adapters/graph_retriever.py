"""
ContextRetriever cài bằng Neo4j + embedding (core/llm/embeddings.py) — điều phối
I/O cho GraphRAG: embed câu hỏi (1 lượt), chạy các Cypher ở
core/graph_query/graph_context.py, rồi giao phần gộp / đóng gói cho
GraphRagService. Hai bước `seed` và `expand` là span con riêng trên LangSmith.
"""

from __future__ import annotations

import logging
from typing import Sequence

from ...db import Neo4jConnection
from ...graph_query import graph_context
from ...llm import embeddings
from ...normalize import normalize_document_number
from ...observability import debug_enabled, log_event, traceable
from ..models import GraphContext
from ..ports import ContextRetriever
from ..retrieval.graph_rag import GraphRagService

def _seed_summary(seeds: list[dict]) -> dict:
    return {"seeds": [{"articleId": s["articleId"], "documentNumber": s.get("documentNumber"),
                       "score": round(s["score"], 5), "via": s["via"]} for s in seeds]}

def _expand_summary(result: tuple[list[dict], list[dict]]) -> dict:
    docs, neighbors = result
    return {"documents": [{"documentNumber": d["documentNumber"], "status": d.get("status"),
                           "replacedBy": [r["documentNumber"] for r in d.get("replacedBy") or []],
                           "repealedBy": [r["documentNumber"] for r in d.get("repealedBy") or []]}
                          for d in docs],
            "neighbors": len(neighbors)}

def _context_summary(ctx: GraphContext) -> dict:
    return {"documents": [{"documentNumber": d.documentNumber, "effectiveStatus": d.effectiveStatus,
                           "articles": [a.articleId for a in d.articles]} for d in ctx.documents]}

class Neo4jGraphRetriever(ContextRetriever):
    def __init__(self, connection: Neo4jConnection, service: GraphRagService, *, enabled: bool, seed_k: int,
                 scope_docs: int, scope_per_doc: int, max_related: int):
        self._conn = connection
        self._service = service
        self._enabled = enabled
        self._seed_k = seed_k
        self._scope_docs = scope_docs
        self._scope_per_doc = scope_per_doc
        self._max_related = max_related

    @traceable(name="graph_rag", run_type="retriever", process_outputs=_context_summary)
    def retrieve(self, question: str, *, scope_docs: Sequence[str] = ()) -> GraphContext:
        if not self._enabled:
            return GraphContext()
        scope = tuple(dict.fromkeys(normalize_document_number(n) for n in scope_docs))[: self._scope_docs]
        seeds = self._seed(question, scope)
        doc_rows, neighbor_rows = self._expand(seeds)
        ctx = self._service.build(seeds, doc_rows, neighbor_rows, priority_keys=scope)

        superseded = [d.documentNumber for d in ctx.documents if d.supersededBy]
        log_event("graph_rag", seeds=len(seeds), scope_docs=list(scope), documents=len(ctx.documents),
                  articles=sum(len(d.articles) for d in ctx.documents), superseded=superseded,
                  chars=sum(len(a.text) for d in ctx.documents for a in d.articles))
        if debug_enabled():
            log_event("graph_rag", level=logging.DEBUG, **_seed_summary(seeds))
        return ctx

    @traceable(name="graph_rag.seed", run_type="retriever", process_outputs=_seed_summary)
    def _seed(self, question: str, scope: tuple[str, ...]) -> list[dict]:
        query_vector = embeddings.embed_texts([question], kind="query")[0]
        with self._conn.session() as s:
            vector = graph_context.seed_vector(s, query_vector, self._seed_k)
            fulltext = graph_context.seed_fulltext(s, question, self._seed_k)
            scoped = graph_context.scoped_articles(s, query_vector, list(scope), self._scope_per_doc)
        log_event("graph_rag.seed", vector=len(vector), fulltext=len(fulltext), scoped=len(scoped),
                  overlap=len({r["articleId"] for r in vector} & {r["articleId"] for r in fulltext}))
        return self._service.select_seeds(vector, fulltext, scoped)

    @traceable(name="graph_rag.expand", run_type="retriever", process_outputs=_expand_summary)
    def _expand(self, seeds: list[dict]) -> tuple[list[dict], list[dict]]:
        doc_keys = list(dict.fromkeys(s["docKey"] for s in seeds if s.get("docKey")))
        with self._conn.session() as s:
            docs = graph_context.expand_documents(s, doc_keys, self._max_related)
            neighbors = graph_context.neighbor_articles(s, self._service.short_seed_ids(seeds))
        return docs, neighbors
