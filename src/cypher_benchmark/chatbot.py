"""
Chạy chatbot của legal_knowledge_graph đầu-cuối trên 20 câu hỏi: câu tiếng
Việt -> chatbot tự hiểu, tự chọn template / tự viết Cypher -> các dòng kết
quả nó lấy ra. Khác 20 câu Cypher viết tay (mức trần của graph), đây là số
đo của HỆ THỐNG THẬT.

Chatbot chạy trong một tiến trình con để bộ đo không import mã của
legal_knowledge_graph (hai bên chỉ chung dữ liệu). Tốn quota Gemini (vài
lượt LLM mỗi câu) nên kết quả được lưu ở reports/chatbot_responses.jsonl và
dùng lại; `--rerun-chatbot` để hỏi lại.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from .query import Query

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(__file__).resolve().parent / "reports" / "chatbot_responses.jsonl"

_CHILD = r"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path('src/legal_knowledge_graph').resolve()))
sys.stdout.reconfigure(encoding='utf-8')
from core.chat.container import build_chat_service
service = build_chat_service()
for line in sys.stdin:
    item = json.loads(line)
    r = service.ask(item['question'])
    print(json.dumps({'name': item['name'], **r.model_dump()}, ensure_ascii=False, default=str), flush=True)
"""


def ask_all(queries: list[Query], rerun: bool = False) -> dict[str, dict]:
    cached: dict[str, dict] = {}
    if CACHE.exists() and not rerun:
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                cached[r["name"]] = r
    todo = [q for q in queries if q.question and (q.name not in cached or cached[q.name].get("kind") == "error")]
    if todo:
        payload = "".join(json.dumps({"name": q.name, "question": q.question}, ensure_ascii=False) + "\n" for q in todo)
        proc = subprocess.run([sys.executable, "-c", _CHILD], input=payload, cwd=ROOT, capture_output=True,
                              text=True, encoding="utf-8", timeout=3600)
        for line in proc.stdout.splitlines():
            if line.startswith("{"):
                r = json.loads(line)
                cached[r["name"]] = r
        if proc.returncode != 0 and not proc.stdout.strip():
            raise RuntimeError(f"Chatbot không chạy được:\n{proc.stderr[-2000:]}")
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text("".join(json.dumps(cached[q.name], ensure_ascii=False) + "\n"
                                 for q in queries if q.name in cached), encoding="utf-8")
    return cached


def id_universe(session) -> dict[str, dict[str, str]]:
    """Mọi cách viết một ID có thể xuất hiện trong dòng kết quả -> ID chuẩn
    của từng đơn vị đáp án (vd số hiệu đã chuẩn hoá -> số hiệu gốc)."""

    docs: dict[str, str] = {}
    for r in session.run("MATCH (d:Document) RETURN d.documentNumber AS dn, d.normalizedNumber AS nn"):
        if r["dn"]:
            docs[r["dn"]] = r["dn"]
            if r["nn"]:
                docs[r["nn"]] = r["dn"]
    orgs_by_id: dict[str, str] = {}
    orgs_by_name: dict[str, str] = {}
    for r in session.run("MATCH (o:Organization) RETURN o.orgId AS id, o.name AS name"):
        orgs_by_id[r["id"]] = r["id"]
        orgs_by_id[r["name"]] = r["id"]
        orgs_by_name[r["name"]] = r["name"]
        orgs_by_name[r["id"]] = r["name"]
    arts = {r["id"]: r["id"] for r in session.run("MATCH (a:Article) RETURN a.articleId AS id")}
    conts = {r["id"]: r["id"] for r in session.run("MATCH (c:NormativeContent) RETURN c.contentId AS id")}
    return {"documentNumber": docs, "articleId": arts, "contentId": conts,
            "orgId": orgs_by_id, "organization": orgs_by_name}


def extract_ids(response: dict, id_field: str, universe: dict[str, dict[str, str]]) -> list[str]:
    """ID chatbot trả về: mọi giá trị trong các dòng kết quả (rows) khớp một
    ID của đơn vị đáp án, theo thứ tự xuất hiện. Không có rows (câu trả lời
    của agent) thì dùng nguồn trích dẫn (sources)."""

    lookup = universe.get(id_field, {})
    out: list[str] = []
    records = response.get("rows") or response.get("sources") or []

    # Có cột mang đúng đơn vị đáp án thì chỉ đọc cột đó — cột phụ (vd danh
    # sách văn bản sửa đổi) không phải là câu trả lời.
    for col in _ID_COLUMNS.get(id_field, ()):
        hits = [lookup[r[col]] for r in records if isinstance(r, dict) and isinstance(r.get(col), str) and r[col] in lookup]
        if hits:
            return list(dict.fromkeys(hits))

    def visit(value) -> None:
        if isinstance(value, str):
            hit = lookup.get(value)
            if hit and hit not in out:
                out.append(hit)
        elif isinstance(value, dict):
            for v in value.values():
                visit(v)
        elif isinstance(value, list):
            for v in value:
                visit(v)

    visit(records)
    return out


_ID_COLUMNS = {
    "documentNumber": ("documentNumber", "normalizedNumber", "docKey"),
    "articleId": ("articleId",),
    "contentId": ("contentId",),
    "orgId": ("orgId", "organization", "name"),
    "organization": ("organization", "name", "orgName", "orgId"),
}


# Câu đếm: đáp án là các con số đã kiểm trong `note` của case.
COUNT_ANSWERS = {
    "S12_chain_depth_distribution": ["250", "44", "7", "2"],
    "S18_status_distribution": ["381", "21", "1"],
}


def count_answer_correct(name: str, response: dict) -> bool:
    text = response.get("answer") or ""
    rows_text = json.dumps(response.get("rows") or [], ensure_ascii=False)
    return all(re.search(rf"(?<![\d.,]){n}(?![\d.,])", text + " " + rows_text) for n in COUNT_ANSWERS.get(name, ["@"]))
