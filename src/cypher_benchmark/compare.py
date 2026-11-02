"""
So sánh các hệ truy hồi trên 20 kịch bản (catalogs/scenarios.py), cùng
ground truth `expected_ids`, cùng hàm chấm (scoring.py) — §6.4–6.5 của
rules/Ontology.md.

Hệ (xem retrievers.py, chatbot.py):

    cypher      câu Cypher viết tay của từng case — MỨC TRẦN của graph: người
                viết đã biết câu hỏi và schema
    chatbot     chatbot LangGraph đầu-cuối: câu tiếng Việt -> chatbot tự chọn
                template / tự viết Cypher — số đo của HỆ THỐNG THẬT
    bm25        từ khoá trên tiêu đề + tóm tắt (index theo đơn vị đáp án)
    bm25_full   từ khoá trên cả toàn văn các Điều
    vector      embedding ngữ nghĩa trên các Điều
    hybrid      bm25_full + vector (RRF)
    hybrid_kg   hybrid lọc 5 văn bản hạt giống + KG mở rộng một bước quan hệ

Số đo:
- P/R/F1: cypher, chatbot chấm trên toàn bộ kết quả trả về; các hệ xếp hạng
  không tự biết dừng nên cắt tại k = |gold| (có lợi cho chúng), lúc đó
  P = R = F1.
- P@10, nDCG@10, MRR: chất lượng xếp hạng.
- S12, S18 là câu đếm: cypher đúng khi số dòng khớp `expected_rows`, chatbot
  đúng khi câu trả lời chứa đủ các con số đã kiểm; các hệ tìm kiếm không có
  cơ chế đếm.

Chạy: `python run.py bench --compare-bm25 [--out FILE.md] [--rerun-chatbot] [--no-chatbot]`.
"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from . import chatbot, db
from .catalogs import scenarios
from .query import Query
from .retrievers import SYSTEMS
from .scoring import score_ids, score_ranked

LEVELS = ["Mức 1 — 1-hop", "Mức 2 — 1-hop nhiều quan hệ", "Mức 3 — multi-hop",
          "Mức 4 — fulltext/hybrid", "Mức 5 — tổng hợp, đa điều kiện"]
LABELS = {"cypher": "Cypher viết tay", "chatbot": "Chatbot", "bm25": "BM25 (tiêu đề)",
          "bm25_full": "BM25 toàn văn", "vector": "Vector", "hybrid": "Hybrid",
          "hybrid_kg": "Hybrid + KG"}
SET_SYSTEMS = ("cypher", "chatbot")  # trả một tập kết quả, chấm trên toàn bộ
# Câu phải đi theo quan hệ giữa các văn bản (căn cứ, sửa đổi, thay thế) —
# nhóm multi-hop của §6.3/§6.5: nơi KG phải thắng rõ.
RELATION_CASES = ("S08", "S09", "S10", "S11", "S16", "S20")
REVIEW_CASES = ("S13", "S14", "S15", "S16", "S17") + tuple(f"S{n}" for n in range(21, 32))
REPORTS = Path(__file__).resolve().parent / "reports"
DEFAULT_OUT = REPORTS / "bm25_vs_cypher.md"


def _level(case: str) -> int:
    # scenarios.py xếp 4 case mỗi mức cho S01..S20; S21–S31 (tìm theo nội dung
    # quy chế đào tạo, thêm sau) thuộc mức 4. Tính theo số case, không theo vị
    # trí, vì kho v4 bỏ bớt case.
    n = int(case[1:])
    return (n - 1) // 4 + 1 if n <= 20 else 4


def detect_corpus(session) -> str:
    """Graph dựng từ v4 có 103 văn bản thật, từ v2 có 403 — chọn gold theo đó."""
    real = session.run("MATCH (d:Document) WHERE d.isStub = false RETURN count(d) AS n").single()["n"]
    return "v4" if real <= 150 else "v2"


def evaluate_case(session, query: Query, chat_response: dict | None, universe) -> dict:
    gold = query.expected_ids
    limit = max(100, len(gold) if gold else 0)
    rows = list(session.run(query.cypher))
    result = {"name": query.name, "case": query.name[:3], "question": query.question, "kind": query.kind,
              "gold_size": len(gold) if gold else None, "count_question": gold is None, "systems": {}, "top": {}}

    if gold is None:  # câu đếm/thống kê
        result["systems"]["cypher"] = {"correct": query.expected_rows is not None and len(rows) == query.expected_rows}
        if chat_response is not None:
            result["systems"]["chatbot"] = {"correct": chatbot.count_answer_correct(query.name, chat_response)}
        for name in SYSTEMS:
            result["systems"][name] = {"correct": False, "applicable": False}
        return result

    ranked: dict[str, list[str] | None] = {"cypher": [r[query.id_field] for r in rows]}
    if chat_response is not None:
        ranked["chatbot"] = chatbot.extract_ids(chat_response, query.id_field, universe)
    for name, fn in SYSTEMS.items():
        ranked[name] = fn(session, query, limit)

    for name, ids in ranked.items():
        if ids is None:
            scores = {**score_ids([], gold), **score_ranked([], gold), "applicable": False}
        else:
            cut = ids if name in SET_SYSTEMS else ids[:len(gold)]
            scores = {**score_ids(cut, gold), **score_ranked(ids, gold), "applicable": True}
            result["top"][name] = ids[:10]
        result["systems"][name] = scores
    return result


def _fmt(v) -> str:
    return "–" if v is None else f"{v:.2f}"


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def render_markdown(results: list[dict], systems: list[str], chat_meta: dict[str, dict], corpus: str) -> str:
    scored = [r for r in results if not r["count_question"]]
    counts = [r for r in results if r["count_question"]]
    relation = [r for r in scored if r["case"] in RELATION_CASES]
    metrics = ["f1", "P@10", "nDCG@10", "MRR"]

    def mean_of(group, system, metric):
        return _mean([r["systems"][system][metric] for r in group])

    lines = [
        f"# Benchmark các hệ truy hồi — {len(results)} kịch bản",
        "",
        f"Chạy ngày {date.today():%d/%m/%Y} trên graph `legal_knowledge_graph` (Neo4j `LKG_NEO4J_*`), kho {corpus}"
        + (" — gold theo `catalogs/gold_v4.json`" if corpus == "v4" else "") + ". "
        "Sinh bởi `python run.py bench --compare-bm25`.",
        "",
        "| Hệ | Cách trả lời |",
        "|---|---|",
        "| Cypher viết tay | Câu Cypher người viết cho từng case. Mức trần của graph: người viết đã biết câu hỏi |",
        "| Chatbot | Chatbot LangGraph nhận câu tiếng Việt, tự chọn template hoặc tự viết Cypher. Số đo của hệ thống thật |",
        "| BM25 (tiêu đề) | Từ khoá trên tiêu đề + tóm tắt (full-text Neo4j) |",
        "| BM25 toàn văn | Từ khoá trên cả toàn văn các Điều, gộp lên văn bản |",
        "| Vector | Embedding ngữ nghĩa (Gemini) trên các Điều, gộp lên văn bản |",
        "| Hybrid | BM25 toàn văn + Vector, gộp thứ hạng (RRF) |",
        "| Hybrid + KG | Hybrid chọn 5 văn bản hạt giống, KG mở rộng một bước theo căn cứ / sửa đổi / thay thế / bãi bỏ |",
        "",
        "P/R/F1: Cypher và Chatbot chấm trên toàn bộ kết quả; các hệ tìm kiếm cắt tại k = số đáp án đúng "
        "(có lợi cho chúng). Ground truth S13–S17 và S21–S31 do Claude gán thay người — phiếu kiểm "
        "`reports/review_S13_S17.csv`; các case còn lại lấy từ graph đã kiểm.",
        "",
        "## Tổng hợp",
        "",
        f"Trung bình macro trên {len(scored)} case có danh sách đáp án, cộng {len(counts)} câu đếm:",
        "",
        "| Hệ | F1 | P@10 | nDCG@10 | MRR | Câu đếm đúng | Câu không trả lời được |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in systems:
        unanswerable = sum(1 for r in results if r["systems"][s].get("applicable") is False)
        n_count = sum(1 for r in counts if r["systems"][s].get("correct"))
        lines.append(f"| {LABELS[s]} | " + " | ".join(_fmt(mean_of(scored, s, m)) for m in metrics)
                     + f" | {n_count}/{len(counts)} | {unanswerable}/{len(results)} |")

    lines += ["", "## F1 theo mức độ", "", "| Mức | Số case | " + " | ".join(LABELS[s] for s in systems) + " |",
              "|---|---|" + "---|" * len(systems)]
    for lv in range(1, 6):
        group = [r for r in results if _level(r["case"]) == lv and not r["count_question"]]
        lines.append(f"| {LEVELS[lv - 1]} | {len(group)} | " + " | ".join(_fmt(mean_of(group, s, "f1")) for s in systems) + " |")

    lines += [
        "",
        "## Nhóm câu đi theo quan hệ (§6.5)",
        "",
        f"{', '.join(r['case'] for r in relation)}: câu trả lời nằm ở cạnh giữa các văn bản (căn cứ, sửa đổi, thay thế), "
        "không nằm trong chữ của văn bản. Đây là nhóm mà Ontology §6.5 yêu cầu KG phải thắng rõ.",
        "",
        "| Hệ | F1 | nDCG@10 |",
        "|---|---|---|",
    ]
    for s in systems:
        lines.append(f"| {LABELS[s]} | {_fmt(mean_of(relation, s, 'f1'))} | {_fmt(mean_of(relation, s, 'nDCG@10'))} |")

    lines += ["", "## F1 từng case", "", "| Case | Câu hỏi | Số đáp án | " + " | ".join(LABELS[s] for s in systems) + " |",
              "|---|---|---|" + "---|" * len(systems)]
    for r in results:
        if r["count_question"]:
            cells = ["đúng" if r["systems"][s].get("correct") else ("–" if r["systems"][s].get("applicable") is False else "sai")
                     for s in systems]
            lines.append(f"| {r['case']} | {r['question']} | (con số) | " + " | ".join(cells) + " |")
        else:
            cells = [_fmt(r["systems"][s]["f1"]) if r["systems"][s]["applicable"] else "–" for s in systems]
            lines.append(f"| {r['case']} | {r['question']} | {r['gold_size']} | " + " | ".join(cells) + " |")
    lines += ["", "`–`: hệ không có cách trả lời loại đáp án này (không có index cho tổ chức, không đếm được)."]

    if chat_meta:
        lines += ["", "## Chatbot từng câu", "",
                  "| Case | Loại trả lời | Template | Lượt LLM | Thời gian |", "|---|---|---|---|---|"]
        for r in results:
            m = chat_meta.get(r["name"])
            if m:
                lines.append(f"| {r['case']} | {m.get('kind')} | {m.get('template') or '–'} | {m.get('llm_calls')} | "
                             f"{(m.get('elapsed_ms') or 0) / 1000:.1f} s |")

    lines += ["", "## Top 5 từng hệ (để soi lỗi)", ""]
    for r in scored:
        lines.append(f"**{r['name']}** — {r['question']}")
        lines.append("")
        for s in systems:
            if s in r["top"]:
                lines.append(f"- {LABELS[s]}: {', '.join(r['top'][s][:5]) or '(rỗng)'}")
        lines.append("")
    return "\n".join(lines) + "\n"


def write_review_sheet(session, results: list[dict], queries: list[Query], path: Path) -> None:
    """Phiếu để NGƯỜI kiểm lại ground truth gán thay: mỗi dòng là một ứng viên
    — đáp án đang gán, cộng mọi kết quả top 10 của bất kỳ hệ nào (pooling
    kiểu TREC). Người kiểm điền cột `nguoi_kiem_lien_quan` (1/0)."""

    titles = {}
    for r in session.run("MATCH (d:Document) RETURN d.documentNumber AS k, d.title AS t "
                         "UNION ALL MATCH (a:Article) RETURN a.articleId AS k, a.heading AS t "
                         "UNION ALL MATCH (c:NormativeContent) RETURN c.contentId AS k, c.title AS t"):
        titles[r["k"]] = r["t"]
    by_name = {q.name: q for q in queries}
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["case", "cau_hoi", "id", "tieu_de", "dang_gan_la_dung", "he_tim_thay", "nguoi_kiem_lien_quan", "ghi_chu"])
        for r in results:
            if r["case"] not in REVIEW_CASES:
                continue
            gold = by_name[r["name"]].expected_ids or frozenset()
            found: dict[str, list[str]] = {}
            for s, ids in r["top"].items():
                for i in ids:
                    found.setdefault(i, []).append(LABELS[s])
            # S14 có 464 đáp án: chỉ đưa phần giao với kết quả các hệ + mẫu 40 đáp án đầu.
            gold_rows = sorted(gold) if len(gold) <= 50 else sorted(set(gold) & set(found)) + sorted(gold - set(found))[:40]
            for i in list(dict.fromkeys(gold_rows + sorted(found))):
                w.writerow([r["case"], r["question"], i, titles.get(i) or "", 1 if i in gold else 0,
                            "; ".join(found.get(i, [])), "", ""])


def write_dashboard_csv(results: list[dict], systems: list[str], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["case", "level", "question", "answer_type", "gold_size", "system", "system_label", "applicable",
                    "f1", "precision", "recall", "p10", "ndcg10", "mrr", "count_correct", "relation_case"])
        for r in results:
            for s in systems:
                v = r["systems"][s]
                if r["count_question"]:
                    w.writerow([r["case"], LEVELS[_level(r["case"]) - 1], r["question"], "count", "", s, LABELS[s],
                                str(v.get("applicable", True)).lower(), "", "", "", "", "", "",
                                str(v.get("correct")).lower(), "false"])
                else:
                    w.writerow([r["case"], LEVELS[_level(r["case"]) - 1], r["question"], "list", r["gold_size"], s, LABELS[s],
                                str(v["applicable"]).lower(), *(round(v[m], 4) for m in ("f1", "precision", "recall", "P@10", "nDCG@10", "MRR")),
                                "", str(r["case"] in RELATION_CASES).lower()])


def main(out: Path | None = None, with_chatbot: bool = True, rerun_chatbot: bool = False) -> int:
    with db.session() as session:
        corpus = detect_corpus(session)
    # Báo cáo v4 ghi riêng thư mục để không đè kết quả trên kho v2.
    out = out or (DEFAULT_OUT if corpus == "v2" else REPORTS / corpus / DEFAULT_OUT.name)
    queries = scenarios.for_corpus(corpus)
    print(f"Kho {corpus}: {len(queries)} kịch bản")
    responses = chatbot.ask_all(queries, rerun=rerun_chatbot) if with_chatbot else {}
    systems = ["cypher"] + (["chatbot"] if with_chatbot else []) + list(SYSTEMS)

    with db.session() as session:
        universe = chatbot.id_universe(session) if with_chatbot else {}
        results = [evaluate_case(session, q, responses.get(q.name) if with_chatbot else None, universe) for q in queries]
        out.parent.mkdir(parents=True, exist_ok=True)
        write_review_sheet(session, results, queries, out.parent / "review_S13_S17.csv")

    chat_meta = {k: {f: v.get(f) for f in ("kind", "template", "llm_calls", "elapsed_ms")} for k, v in responses.items()}
    report = render_markdown(results, systems, chat_meta, corpus)
    out.write_text(report, encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    write_dashboard_csv(results, systems, out.parent / "systems_by_case.csv")
    print(report)
    print(f"Đã ghi {out} (+ .json, systems_by_case.csv, review_S13_S17.csv)")
    return 0
