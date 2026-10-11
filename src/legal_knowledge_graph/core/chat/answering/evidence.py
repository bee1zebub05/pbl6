"""Trình bày bằng chứng (dòng Cypher, ngữ cảnh GraphRAG) cho prompt và rút
nguồn trích dẫn — dùng chung cho AnswerService và AgentService."""

from __future__ import annotations

import json
import re
from typing import Any

from ..models import ArticleEvidence, GraphContext, RelatedDocument

_MAX_VALUE_CHARS = 300


def _short(value: Any, limit: int = _MAX_VALUE_CHARS) -> Any:
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + "…"
    return value


def rows_to_text(rows: list[dict], limit: int, query_limit: int | None = None) -> str:
    """JSON gọn của tối đa `limit` dòng, kèm tổng số dòng. `query_limit` là
    LIMIT của chính truy vấn: số dòng chạm đúng mức đó nghĩa là kết quả đã bị
    cắt, tổng thật có thể lớn hơn — phải nói rõ để LLM không báo sai tổng."""

    shown = [{k: _short(v) for k, v in r.items()} for r in rows[:limit]]
    body = json.dumps(shown, ensure_ascii=False, default=str)
    notes = []
    if len(rows) > limit:
        notes.append(f"hiển thị {len(shown)}/{len(rows)} dòng")
    if query_limit is not None and len(rows) >= query_limit:
        notes.append(f"ĐÃ CHẠM GIỚI HẠN {query_limit} DÒNG của truy vấn — tổng thật có thể nhiều hơn, "
                     f"hãy nói 'ít nhất {len(rows)}'")
    note = f" ({'; '.join(notes)})" if notes else ""
    return f"{len(rows)} dòng{note}:\n{body}"


_MARKDOWN_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__", re.S)
_MARKDOWN_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+", re.M)


def to_plain_text(text: str) -> str:
    """Bỏ định dạng markdown (đậm, tiêu đề) mà LLM đôi khi vẫn dùng dù prompt
    cấm — giao diện hiển thị văn bản thuần."""

    text = _MARKDOWN_BOLD.sub(lambda m: m.group(1) or m.group(2), text)
    return _MARKDOWN_HEADING.sub("", text).strip()


def _ref(doc: RelatedDocument) -> str:
    extra = ", ".join(x for x in (doc.issueDate, doc.status) if x)
    title = f" — {_short(doc.title, 120)}" if doc.title else " (chưa có toàn văn trong kho)"
    return f"{doc.documentNumber}{title}{f' ({extra})' if extra else ''}"


def _article_text(a: ArticleEvidence, indent: str = "  ") -> str:
    # Toàn văn Điều thường đã mở đầu bằng "Điều N. <tiêu đề>" — không lặp lại.
    head = ". ".join(x for x in (a.number, a.heading) if x) or a.articleId
    body = a.text if a.number and a.text.startswith(a.number) else f"{head}\n{a.text}"
    inside = f"[thuộc: {_short(a.container, 120)}] " if a.container else ""
    return f"{indent}{inside}{body}"


def context_to_text(ctx: GraphContext) -> str:
    """Ngữ cảnh GraphRAG gom theo văn bản: hiệu lực ĐÃ HIỆU CHỈNH theo quan hệ,
    văn bản thay thế / sửa đổi / căn cứ, rồi các Điều liên quan."""

    blocks = []
    for d in ctx.documents:
        meta = " | ".join(x for x in (d.documentType, d.issueDate and f"ban hành {d.issueDate}",
                                      ", ".join(d.issuers) or None) if x)
        lines = [f"[{d.documentNumber}] {_short(d.title or '', 200)}" + (f" | {meta}" if meta else "")]
        if d.supersededBy:
            lines.append(f"Hiệu lực: HET_HIEU_LUC — đã bị thay thế hoặc bãi bỏ bởi "
                         f"{'; '.join(_ref(s) for s in d.supersededBy)}"
                         + (f" (thuộc tính trong kho vẫn ghi {d.status})" if d.status != d.effectiveStatus else ""))
        else:
            lines.append(f"Hiệu lực: {d.effectiveStatus or 'không rõ'}")
        if d.amendedBy:
            lines.append("Đã bị sửa đổi một phần bởi: " + "; ".join(
                _ref(a) + (f" [sửa {a.targetArticle}]" if a.targetArticle else "") for a in d.amendedBy))
        if d.basedOn:
            lines.append("Căn cứ: " + "; ".join(_ref(b) for b in d.basedOn))
        for a in d.articles:
            lines.append(_article_text(a))
            lines += ["  (Điều liền kề) " + _article_text(n).lstrip() for n in a.neighbors]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def collect_sources(rows: list[dict] | None, hits: list[dict] | None, limit: int = 20) -> list[dict]:
    """Danh sách văn bản / Điều làm nguồn, bỏ trùng, giữ thứ tự xuất hiện."""

    sources: list[dict] = []
    seen: set[tuple] = set()

    def add(item: dict) -> None:
        key = (item.get("documentNumber"), item.get("articleId"), item.get("contentId"))
        if key != (None, None, None) and key not in seen and len(sources) < limit:
            seen.add(key)
            sources.append({k: v for k, v in item.items() if v is not None})

    # Hiệu lực đã hiệu chỉnh theo quan hệ (GraphRAG) thắng cột status thô của dòng Cypher.
    corrected = {h["documentNumber"]: h["effectiveStatus"] for h in hits or []
                 if h.get("documentNumber") and h.get("effectiveStatus")}
    for r in rows or []:
        number = r.get("documentNumber") or r.get("target")
        add({"documentNumber": number, "title": r.get("title"), "status": corrected.get(number, r.get("status")),
             "articleId": r.get("articleId"), "contentId": r.get("contentId")})
    for h in hits or []:
        add({"documentNumber": h.get("documentNumber"), "articleId": h.get("articleId"),
             "title": h.get("heading"), "status": h.get("effectiveStatus") or h.get("status")})
    return sources
