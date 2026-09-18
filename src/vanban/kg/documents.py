"""
Bước 0 — chốt bảng `Document` (§2.1 Ontology).

Đây là bảng gốc của toàn bộ knowledge graph: mọi quan hệ ở Bước 2–4 đều nối
vào khoá chính sinh ra ở đây. Làm sai một lần là hỏng cả graph, nên bước này
làm ba việc và chỉ ba việc:

**1. Neo vào kho text CÓ THẬT trên đĩa.**
`data/manifest.jsonl` được xuất ngày 17/8, ghi `fix_status: pending` cho
498/501 văn bản và `text_clean: null` — trong khi thực tế 460 văn bản đã hiệu
đính xong, nằm ở `data/clean/text_final/` (đường dẫn khác hẳn cái
`data/processed/text_clean/` mà pipeline ghi trong session). Tin manifest là
dựng graph trên nền rỗng. Nên nguồn chuẩn về **text** là thư mục trên đĩa,
manifest chỉ còn là nguồn chuẩn về **metadata** (ngày ban hành, cơ quan, tình
trạng hiệu lực — những trường này chỉ có trong đó, vì `data/raw/metadata.csv`
đã bị xoá cùng thư mục PDF).

**2. Gộp trùng theo số hiệu.**
501 dòng manifest chỉ ứng với 445 số hiệu phân biệt: 55 nhóm trùng, trong đó
11 nhóm được crawler cấp hai `doc_id` khác nhau cho cùng một văn bản
(`1980/QĐ-ĐHBK` = 0044 + 0213). §2.1 lấy `so_hieu_norm` làm khoá chính, không
gộp thì `MERGE` trong Neo4j sẽ vỡ. Bốn nhóm nằm ở **hai lĩnh vực khác nhau** —
đó không phải xung đột mà đúng bản chất `HAS_TOPIC` n→m (§4), nên gộp bằng
cách hợp nhất danh sách topic chứ không phải chọn một bỏ một.

**3. Suy các thuộc tính ontology mà metadata thô chưa có.**
`authority_level` (§3), `status`/`expiryDate` tách từ chuỗi `tinh_trang`,
`documentType` tách khỏi `"Quyết định, Quy định"` (§2.6), `orgId`/`orgType`
(§2.2). Xem `norm.py`.

Kèm theo là một phép **đối chiếu header**: mở text đã hiệu đính, đọc vùng đầu
trang 1, xem số hiệu in trong đó có khớp với metadata không. Bước `normalize`
trước đây đã tiêm số hiệu vào chỗ này, nên tỷ lệ khớp chính là thước đo văn
bản nào có header đáng tin — Bước 1 (cắt vùng) và Bước 2 (trích dẫn) dựa hết
vào đó.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path

from ..core import config
from ..core.text import _header_span, deaccent
from ..core.console import STOP, say
from . import norm
from .session import KGSession


# ============================================================
# NGUỒN METADATA
# ============================================================

def _load_manifest() -> dict[str, dict]:
    """Đọc `data/manifest.jsonl`, đánh khoá theo doc_id."""

    path = config.MANIFEST_PATH

    if not path.exists():
        return {}

    result: dict[str, dict] = {}

    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()

            if not line:
                continue

            row = json.loads(line)
            doc_id = (row.get("doc_id") or "").strip()

            if doc_id:
                # Dòng trùng doc_id trong manifest là bản sao y hệt nhau
                # (đã kiểm: cùng số hiệu, cùng lĩnh vực) -> ghi đè vô hại.
                result[doc_id] = row

    return result


# Tên file kho sạch: `0151_09_2020_TT-BGDĐT_Thông tư 09_2020...`
#
# Không dùng `naming.parse_pdf_name` được: hàm đó cắt `stem.split("_", 2)` nên
# với số hiệu ba phần nó trả về `so_hieu = "09"`. Chỗ đó vô hại trong pipeline
# OCR vì metadata.csv ghi đè lên, nhưng ở đây tên file là nguồn duy nhất cho 5
# văn bản không có trong manifest.
_STEM = re.compile(
    r"^(?P<doc_id>\d{4})"
    r"_(?P<so_hieu>\d{1,4}(?:_\d{4})?_[A-ZĐÐa-z0-9]{1,8}(?:-[A-ZĐÐa-z0-9]{1,12})*)"
    r"_(?P<title>.+)$"
)


def _from_stem(path: Path) -> dict | None:
    """Moi doc_id / số hiệu / tiêu đề từ tên file. None nếu tên không đúng dạng."""

    stem = unicodedata.normalize("NFC", path.stem)
    match = _STEM.match(stem)

    if not match:
        return None

    # Dấu `/` trong số hiệu bị đổi thành `_` lúc đặt tên file -> đổi ngược lại.
    so_hieu = match.group("so_hieu").replace("_", "/")

    return {
        "doc_id": match.group("doc_id"),
        "so_hieu": so_hieu,
        "ten_van_ban": match.group("title"),
    }


def _scan_corpus(corpus_dir: Path) -> list[dict]:
    """Quét kho text đã hiệu đính. Lĩnh vực lấy từ tên thư mục cha."""

    if not corpus_dir.exists():
        raise FileNotFoundError(
            f"Không tìm thấy kho text đã hiệu đính: {corpus_dir}\n"
            "    Đặt lại bằng KG_CORPUS_DIR trong .env hoặc --corpus khi chạy."
        )

    files = sorted(
        path
        for path in corpus_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in (".txt", ".md")
    )

    items = []

    for path in files:
        relative = path.relative_to(corpus_dir)
        topic = relative.parts[0] if len(relative.parts) > 1 else "Khác"

        items.append(
            {
                "path": path,
                "topic": topic,
                "doc_id": path.stem[:4] if path.stem[:4].isdigit() else "",
                "stem_meta": _from_stem(path),
            }
        )

    return items


# ============================================================
# GOM NHÓM THEO SỐ HIỆU
# ============================================================

def collect(session: KGSession, corpus_dir: Path) -> dict[str, int]:
    """
    Dựng danh sách văn bản phân biệt rồi nạp vào session.

    Nguồn 1 — kho text trên đĩa (có nội dung, chắc chắn dùng được).
    Nguồn 2 — manifest (metadata đầy đủ, kể cả văn bản chưa kịp hiệu đính).

    Cả hai đổ chung vào một rổ theo `so_hieu_key`; văn bản nào có mặt ở cả hai
    thì lấy metadata của manifest và đường dẫn của đĩa.
    """

    manifest = _load_manifest()
    corpus = _scan_corpus(corpus_dir)

    say(f"  Kho text: {len(corpus)} file tại {corpus_dir}")
    say(f"  Manifest: {len(manifest)} bản ghi metadata")

    # doc_id -> các file text (bình thường 1, nhưng không cấm nhiều hơn)
    files_by_id: dict[str, list[dict]] = defaultdict(list)
    orphans: list[dict] = []

    for item in corpus:
        if item["doc_id"] and item["doc_id"] in manifest:
            files_by_id[item["doc_id"]].append(item)
        else:
            orphans.append(item)

    if orphans:
        say(
            f"  {len(orphans)} file không có trong manifest -> lấy metadata từ "
            "tên file"
        )

    groups: dict[str, dict] = {}

    def merge(so_hieu_raw: str, meta: dict, item: dict | None, source: str) -> None:
        key = norm.so_hieu_key(so_hieu_raw)

        if not key:
            session.log("doc", so_hieu_raw or "?", "error", "Không có số hiệu")
            return

        group = groups.setdefault(
            key,
            {
                "doc_key": key,
                "so_hieu": norm.so_hieu_norm(so_hieu_raw),
                "so_hieu_raw": so_hieu_raw,
                "doc_ids": [],
                "titles": [],
                "topics": [],
                "files": [],
                "metas": [],
                "sources": set(),
            },
        )

        doc_id = (meta.get("doc_id") or "").strip()

        if doc_id and doc_id not in group["doc_ids"]:
            group["doc_ids"].append(doc_id)

        title = (meta.get("ten_van_ban") or "").strip()

        if title and title not in group["titles"]:
            group["titles"].append(title)

        # Lĩnh vực: manifest và thư mục cha có thể khác nhau -> giữ cả hai,
        # HAS_TOPIC vốn là n->m (§4).
        for topic in ((meta.get("linh_vuc") or "").strip(), item["topic"] if item else ""):
            if topic and topic not in group["topics"]:
                group["topics"].append(topic)

        if item:
            group["files"].append(item["path"])

        group["metas"].append(meta)
        group["sources"].add(source)

    for doc_id, meta in manifest.items():
        so_hieu = (meta.get("so_hieu") or "").strip()

        if not so_hieu:
            session.log("doc", doc_id, "error", "Manifest thiếu số hiệu")
            continue

        for item in files_by_id.get(doc_id, [None]):
            merge(so_hieu, meta, item, "manifest")

    for item in orphans:
        meta = item["stem_meta"]

        if not meta:
            session.log(
                "doc", item["path"].name, "error", "Tên file không đọc được số hiệu"
            )
            continue

        merge(meta["so_hieu"], meta, item, "ten-file")

    records = [_to_record(group) for group in groups.values()]
    added, updated = session.register(records)

    session.set_meta("corpus_dir", str(corpus_dir))
    session.set_meta("collected_at", date.today().isoformat())

    return {
        "nhom": len(groups),
        "them_moi": added,
        "cap_nhat": updated,
        "khong_co_text": sum(1 for g in groups.values() if not g["files"]),
        "gop_trung": sum(1 for g in groups.values() if len(g["doc_ids"]) > 1),
    }


def _column(row, name: str):
    """Đọc một cột có thể chưa tồn tại (session tạo từ bước trước)."""

    try:
        return row[name]
    except (IndexError, KeyError):
        return None


def _relative(path: Path) -> str:
    """Đường dẫn tương đối so với gốc project — để JSONL còn mang đi máy khác."""

    try:
        return path.resolve().relative_to(config.ROOT).as_posix()
    except ValueError:
        # Kho text nằm ngoài project (KG_CORPUS_DIR trỏ đi chỗ khác).
        return path.as_posix()


def _to_record(group: dict) -> dict:
    """Một nhóm số hiệu -> một bản ghi để nạp vào session."""

    metas = group["metas"]

    def first(field: str) -> str:
        for meta in metas:
            value = (meta.get(field) or "").strip()

            if value:
                return value

        return ""

    # File dài nhất là bản đầy đủ nhất — bản sao trùng số hiệu đôi khi là bản
    # scan thiếu trang.
    files = sorted(group["files"], key=lambda p: p.stat().st_size, reverse=True)

    # Tiêu đề dài nhất giữ được nhiều thông tin nhất (bản ngắn thường bị
    # crawler cắt cụt ở 90 ký tự).
    title = max(group["titles"], key=len) if group["titles"] else ""

    doc_type, normative_type = norm.split_loai(first("loai_van_ban"))

    # Thiếu nhãn, hoặc nhãn chỉ là tên nhóm ("Luật, Pháp lệnh") -> hỏi số hiệu.
    if not doc_type or doc_type in norm.GROUP_LABELS:
        doc_type = norm.doc_type_from_so_hieu(group["so_hieu"]) or doc_type

    org_name = first("co_quan_ban_hanh")

    if not org_name:
        guess = norm.org_from_so_hieu(group["so_hieu"])
        org_name = guess[0] if guess else ""

    issue_date = norm.parse_date(first("ngay_ban_hanh"))
    effective_date = norm.parse_date(first("ngay_hieu_luc"))
    status, expiry_date, _ = norm.parse_status(first("tinh_trang"), effective_date)

    pages = max(
        (meta.get("so_trang") or 0 for meta in metas),
        default=0,
    )

    return {
        "doc_key": group["doc_key"],
        "so_hieu": group["so_hieu"],
        "so_hieu_raw": group["so_hieu_raw"],
        "doc_ids": sorted(group["doc_ids"]),
        "title": title,
        "topics": group["topics"],
        "file_url": first("pdf_url") or None,
        "pages": pages or None,
        "clean_path": _relative(files[0]) if files else None,
        "meta_source": "manifest" if "manifest" in group["sources"] else "ten-file",
        "doc_type": doc_type,
        "normative_type": normative_type,
        "org_name": org_name or None,
        "issue_date": issue_date,
        "effective_date": effective_date,
        "expiry_date": expiry_date,
        "status": status,
    }


# ============================================================
# ĐỐI CHIẾU HEADER
# ============================================================

# Số hiệu trong text đã hiệu đính. Rộng hơn regex của `normalize` vì ở đây
# text đã sạch, không cần chừa chỗ cho ký tự OCR nhầm.
#
# `\d{0,2}` sau cụm chữ cái là bắt buộc: số hiệu Luật kết thúc bằng khoá Quốc
# hội dính liền (`100/2015/QH13`). Thiếu nó thì header đọc ra `100/2015/QH`,
# lệch với metadata `100/2015/QH13` -> báo động giả cho toàn bộ 56 văn bản luật.
_SO_HIEU_IN_TEXT = re.compile(
    r"\b\d{1,4}\s*/\s*(?:\d{4}\s*/\s*)?[A-ZĐÐ]{1,8}\d{0,2}(?:-[A-ZĐÐa-z0-9]{1,15})*"
)


def _cut_short(expected: str, found: str) -> bool:
    """
    Hai số hiệu chỉ khác nhau ở chỗ một cái bị cắt cụt đuôi?

    Đuôi số hiệu hay bị xuống dòng ngay giữa chừng trong bản scan, nhất là loại
    dài: `9/2016/TTLT-BGDĐT-BTC-BLĐTBXH` in ra thành hai dòng, regex chỉ vớt
    được `9/2016/TTLT-BGDĐT-BTC`. Số và năm vẫn khớp thì đó là cùng một văn
    bản, không phải văn bản khác.
    """

    exp, got = expected.split("/"), found.split("/")

    if exp[0] != got[0]:
        return False

    # Cả hai đều dạng ba phần thì năm phải khớp — `17/2021/...` với
    # `17/2019/...` là hai văn bản khác nhau thật.
    if len(exp) >= 3 and len(got) >= 3 and exp[1] != got[1]:
        return False

    tail_exp, tail_got = "/".join(exp[1:]), "/".join(got[1:])

    return tail_exp.startswith(tail_got) or tail_got.startswith(tail_exp)


def check_header(text: str, doc_key: str) -> tuple[str, list[str]]:
    """
    Số hiệu in ở đầu trang 1 có khớp metadata không?

    Trả về (kết luận, các số hiệu tìm thấy). Kết luận:
        khop        header có đúng số hiệu này -> Bước 1/2 tin được
        gan-khop    khớp số và năm, đuôi bị cắt cụt -> vẫn tin được
        lech        header có số hiệu KHÁC hẳn -> metadata hoặc file bị lệch
        khong-thay  header không có số hiệu nào đọc ra được
    """

    start, end = _header_span(text)
    header = text[start:end]

    found = []

    for match in _SO_HIEU_IN_TEXT.finditer(header):
        candidate = norm.so_hieu_key(match.group(0))

        if candidate and candidate not in found:
            found.append(candidate)

    if not found:
        return "khong-thay", []

    if doc_key in found:
        return "khop", found

    if any(_cut_short(doc_key, candidate) for candidate in found):
        return "gan-khop", found

    return "lech", found


# ============================================================
# CHẠY BƯỚC 0
# ============================================================

def build(session: KGSession, limit: int | None = None) -> dict[str, int]:
    """
    Hoàn thiện từng văn bản: suy `authority_level`, đọc text, đối chiếu header.

    Ghi trạng thái sau mỗi văn bản nên Ctrl+C lúc nào cũng được — chạy lại
    lệnh cũ thì những văn bản `doc_status = done` bị bỏ qua.
    """

    rows = session.todo("doc", limit=limit)

    if not rows:
        return {}

    tally: dict[str, int] = defaultdict(int)
    today = date.today()

    for index, row in enumerate(rows, start=1):
        if STOP.is_set():
            say(f"\n  Dừng theo yêu cầu — còn {len(rows) - index + 1} văn bản.")
            break

        doc_key = row["doc_key"]
        notes: list[str] = []

        level, level_note = norm.authority_level(row["doc_type"], row["org_name"])

        if level is None:
            notes.append(f"khong-suy-duoc-bac: loai={row['doc_type']!r}")
        elif level_note != "onto":
            notes.append(f"bac-{level}: {level_note}")

        if not row["org_name"]:
            notes.append("thieu-co-quan-ban-hanh")

        if not row["issue_date"]:
            notes.append("thieu-ngay-ban-hanh")

        if not row["status"]:
            notes.append("thieu-tinh-trang-hieu-luc")

        # `CHUA_HIEU_LUC` phải tính lại ở đây chứ không ở `collect`: nó phụ
        # thuộc ngày hôm nay, mà session có thể được nạp từ hôm trước.
        status = row["status"]

        if (
            status == norm.STATUS_CON
            and row["effective_date"]
            and row["effective_date"] > today.isoformat()
        ):
            status = norm.STATUS_CHUA
            notes.append("chua-den-ngay-hieu-luc")

        # --- text đã hiệu đính ---
        clean_chars = None
        header_check = "khong-co-file"

        if row["clean_path"]:
            path = Path(row["clean_path"])

            if not path.is_absolute():
                path = config.ROOT / path

            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
                clean_chars = len(text)
                header_check, found = check_header(text, doc_key)

                if header_check == "lech":
                    notes.append(f"header-lech: {', '.join(found[:3])}")
                elif header_check == "khong-thay":
                    notes.append("header-khong-co-so-hieu")
                elif header_check == "gan-khop":
                    notes.append(f"header-cut-duoi: {found[0]}")

                if clean_chars < 500:
                    notes.append(f"text-qua-ngan: {clean_chars} ky-tu")
            except OSError as exc:
                notes.append(f"khong-doc-duoc-file: {exc}")
                session.log("doc", doc_key, "error", str(exc))
        else:
            notes.append("chua-co-text-da-hieu-dinh")

        session.update(
            doc_key,
            authority_level=level,
            level_note=level_note,
            status=status,
            clean_chars=clean_chars,
            header_check=header_check,
            org_id=norm.org_id(row["org_name"]) if row["org_name"] else None,
            doc_note="; ".join(notes),
            doc_status="done",
        )

        tally["done"] += 1
        tally[f"header:{header_check}"] += 1

        if notes:
            tally["co-ghi-chu"] += 1

        if index % 100 == 0:
            say(f"    ... {index}/{len(rows)}")

    return dict(tally)


# ============================================================
# XUẤT NODE
# ============================================================

def export(session: KGSession, out_dir: Path | None = None) -> dict[str, Path]:
    """
    Xuất `Document`, `Organization`, `Topic` ra JSONL cho bước nạp Neo4j.

    JSONL chứ không phải CSV: thuộc tính `topics` và `doc_ids` là danh sách,
    nhét vào CSV phải mã hoá lại một lần nữa.
    """

    out_dir = out_dir or config.KG_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = session.all_docs()
    docs_path = out_dir / "documents.jsonl"
    orgs_path = out_dir / "organizations.jsonl"
    topics_path = out_dir / "topics.jsonl"

    org_names: set[str] = set()
    topic_names: set[str] = set()

    with docs_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            topics = json.loads(row["topics"] or "[]")
            topic_names.update(topics)

            if row["org_name"]:
                org_names.add(row["org_name"])

            record = {
                "so_hieu_norm": row["doc_key"],
                "so_hieu": row["so_hieu"],
                "title": row["title"],
                "documentType": row["doc_type"],
                "normativeType": row["normative_type"],
                "authority_level": row["authority_level"],
                "status": row["status"],
                "issueDate": row["issue_date"],
                "effectiveDate": row["effective_date"],
                "expiryDate": row["expiry_date"],
                "fileUrl": row["file_url"],
                # Bước 2 nhét thêm node stub vào chính bảng này (§1: văn bản bị
                # viện dẫn mà chưa crawl vẫn là `Document`), nên cờ phải đọc từ
                # DB chứ không hằng số.
                "is_stub": bool(_column(row, "is_stub")),
                "stub_hits": _column(row, "stub_hits"),
                "orgId": row["org_id"],
                "topics": topics,
                "doc_ids": json.loads(row["doc_ids"] or "[]"),
                "pages": row["pages"],
                "clean_path": row["clean_path"],
                "clean_chars": row["clean_chars"],
                "header_check": row["header_check"],
                "level_note": row["level_note"],
                "note": row["doc_note"] or "",
            }

            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    # Cơ quan cấp trên có thể chưa từng ban hành văn bản nào trong kho (Bộ
    # GD&ĐT là cha của ĐHĐN nhưng nếu kho không có văn bản nào của Bộ thì nó
    # vẫn phải tồn tại để cạnh PART_OF không trỏ vào hư không).
    queue = list(org_names)

    while queue:
        parent = norm.org_parent(queue.pop())

        if parent and parent not in org_names:
            org_names.add(parent)
            queue.append(parent)

    # Hai cách viết cùng một cơ quan ("Thanh tra chính phủ" / "Thanh tra Chính
    # phủ") cho ra cùng một `orgId`. Gộp ở đây để số dòng xuất ra khớp đúng số
    # node Neo4j sẽ tạo — không thì báo cáo lệch mà chẳng hiểu vì sao.
    by_id: dict[str, str] = {}

    for name in sorted(org_names):
        by_id.setdefault(norm.org_id(name), name)

    with orgs_path.open("w", encoding="utf-8") as handle:
        for name in by_id.values():
            parent = norm.org_parent(name)

            handle.write(
                json.dumps(
                    {
                        "orgId": norm.org_id(name),
                        "name": name,
                        "orgType": norm.org_type(name),
                        "parentOrg": norm.org_id(parent) if parent else None,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    with topics_path.open("w", encoding="utf-8") as handle:
        for name in sorted(topic_names):
            handle.write(
                json.dumps(
                    {"topicId": norm.org_id(name), "name": name, "description": ""},
                    ensure_ascii=False,
                )
                + "\n"
            )

    say(f"  {len(rows):>4} Document      -> {docs_path}")
    say(f"  {len(by_id):>4} Organization  -> {orgs_path}")
    say(f"  {len(topic_names):>4} Topic         -> {topics_path}")

    return {"documents": docs_path, "organizations": orgs_path, "topics": topics_path}


# ============================================================
# BÁO CÁO
# ============================================================

def _counts(session: KGSession, column: str, real_only: bool = True) -> dict:
    """Đếm theo cột, mặc định chỉ tính văn bản thật (bỏ stub của Bước 2)."""

    where = "WHERE COALESCE(is_stub, 0) = 0" if real_only else ""

    with session._lock:  # noqa: SLF001
        rows = session._conn.execute(  # noqa: SLF001
            f"SELECT {column} AS v, COUNT(*) AS n FROM docs {where} GROUP BY {column}"
        ).fetchall()

    return {row["v"]: row["n"] for row in rows}


def report(session: KGSession) -> str:
    total = session.total()

    if not total:
        return "\nSession KG rỗng — chạy `python run.py kg docs` trước.\n"

    stubs = _counts(session, "is_stub", real_only=False).get(1, 0)
    real = total - stubs

    # Từ Bước 2 trở đi bảng này có thêm node stub (§1). Trộn chung vào thống kê
    # thì mọi con số của Bước 0 đổi nghĩa, nên tách hẳn ra.
    lines = [
        "",
        "=" * 62,
        f"KG SESSION: {session.name}   ({real} Document thật"
        + (f" + {stubs} stub" if stubs else "")
        + ")",
        "=" * 62,
    ]

    done = _counts(session, "doc_status")
    lines += ["", "  Bước 0 — bảng Document (không tính stub):"]

    for status in ("done", "pending", "failed"):
        if done.get(status):
            lines.append(f"    {status:<20} {done[status]:>5}")

    lines += ["", "  Bậc thẩm quyền (§3):"]

    levels = _counts(session, "authority_level")
    names = {
        6: "Hiến pháp",
        5: "Luật / Pháp lệnh",
        4: "Nghị định",
        3: "Thông tư / Thủ tướng / bộ ngành",
        2: "Đại học Đà Nẵng",
        1: "Trường ĐHBK",
    }

    for level in (6, 5, 4, 3, 2, 1):
        if levels.get(level):
            lines.append(f"    {level}  {names[level]:<34} {levels[level]:>5}")

    if levels.get(None):
        lines.append(f"    ?  {'chưa suy được':<34} {levels[None]:>5}")

    lines += ["", "  Hiệu lực (§2.1):"]

    for status, count in sorted(_counts(session, "status").items(), key=lambda x: -x[1]):
        lines.append(f"    {str(status):<24} {count:>5}")

    lines += ["", "  Đối chiếu số hiệu ở header:"]

    labels = {
        "khop": "khớp metadata",
        "gan-khop": "khớp, đuôi bị cắt",
        "lech": "lệch — cần soi tay",
        "khong-thay": "header không có số hiệu",
        "khong-co-file": "chưa có text hiệu đính",
    }

    for kind, count in sorted(
        _counts(session, "header_check").items(), key=lambda x: -x[1]
    ):
        if kind:
            lines.append(f"    {labels.get(kind, kind):<24} {count:>5}")

    flagged = session.flagged()

    if flagged:
        lines += [
            "",
            f"  {len(flagged)} văn bản có ghi chú — xem: python run.py kg review",
        ]

    lines.append("")

    return "\n".join(lines)
