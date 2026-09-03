"""
Bước 4 — dựng node `NormativeContent` (§2.6) và `Article` (§2.7).

Bước 1 đã cắt sẵn phần và danh mục Điều; bước này chỉ việc biến chúng thành
node và lấy phần text tương ứng.

## Vì sao `NormativeContent` là một node riêng

Câu hỏi thật của người tra cứu là *"quy chế nào đang có hiệu lực về học vụ"* —
hỏi vào **nội dung**, không hỏi vào cái quyết định bọc ngoài. Nhưng thứ mang số
hiệu, ngày ban hành, tình trạng hiệu lực lại là cái quyết định. Tách hai node
rồi nối bằng `PROMULGATES` thì hỏi kiểu nào cũng trả lời được.

Trong kho: 178/448 văn bản có phần kèm theo như vậy.

## `Article` treo vào đâu

§2.7 nói `Article` thuộc `NormativeContent` qua `HAS_ARTICLE`. Nhưng phần lớn
văn bản trong kho **không** có nội dung kèm theo — một `Luật`, một `Nghị định`
có Điều ngay trong thân nó. Ép mọi Điều phải đi qua một `NormativeContent` giả
thì đồ thị có thêm 270 node rỗng chẳng để làm gì.

Nên `HAS_ARTICLE` ở đây nhận **cả `Document` lẫn `NormativeContent`** làm
domain. Đây là chỗ nới so với §2.7, ghi rõ ra để §4 của paper nói lại cho đúng.

Phụ lục bị bỏ qua hoàn toàn (§9: "nơi nhận/phụ lục — giá trị thấp").
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from .. import config
from ..normalize import deaccent
from ..pipeline import STOP, say
from . import norm, segment
from .session import KGSession

SCHEMA = """
CREATE TABLE IF NOT EXISTS normative (
    content_id   TEXT PRIMARY KEY,
    doc_key      TEXT,
    part_index   INTEGER,
    content_type TEXT,
    title        TEXT,
    status       TEXT,
    n_articles   INTEGER,
    marker       TEXT
);

CREATE INDEX IF NOT EXISTS idx_norm_doc ON normative(doc_key);
"""

# Dòng rác trong khối tiêu đề của phần kèm theo: quốc hiệu, tên cơ quan, mốc
# phân trang, dòng `(Kèm theo ...)`. Bỏ hết thì còn lại đúng cái tên.
_NOISE = re.compile(
    r"^\s*(?:-{3,}|CONG\s*HO|DOC\s*LAP|BO\s|DAI\s*HOC|TRUONG\s|UBND|UY\s*BAN"
    r"|\(|QUY\s|DIEU\s*LE|DE\s*AN|KE\s*HOACH|NOI\s*QUY|HUONG\s*DAN"
    r"|CHUONG\s*TRINH|PHU\s*LUC|DANH\s*MUC|NAM\s*\d{4}|\d+\s*$)",
    re.IGNORECASE,
)

_TITLE_KEYWORD = {
    "QUY DINH": "Quy định",
    "QUY CHE": "Quy chế",
    "DIEU LE": "Điều lệ",
    "QUY TRINH": "Quy trình",
    "NOI QUY": "Nội quy",
    "DE AN": "Đề án",
    "KE HOACH": "Kế hoạch",
    "HUONG DAN": "Hướng dẫn",
    "CHUONG TRINH": "Chương trình",
}


def ensure_schema(session: KGSession) -> None:
    with session._lock:  # noqa: SLF001
        session._conn.executescript(SCHEMA)  # noqa: SLF001
        session._conn.commit()  # noqa: SLF001

    session.add_columns((("art_note", "TEXT"),))


def content_title(text: str, part: segment.Part) -> str:
    """
    Tên của nội dung kèm theo, moi từ khối tiêu đề của nó.

    Khối đó trông như thế này, và chỉ dòng thứ ba là cái ta cần:

        BỘ GIÁO DỤC VÀ ĐÀO TẠO   CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM
        QUY CHẾ
        Công tác sinh viên đối với chương trình đào tạo đại học hệ chính quy
        (Ban hành kèm theo Thông tư số 10/2016/TT-BGDĐT ...)
    """

    start, end = part.zones.get("header", (part.start, min(part.end, part.start + 900)))
    lines = []

    for line in text[start:end].splitlines():
        stripped = line.strip()

        if not stripped or _NOISE.match(deaccent(stripped)):
            continue

        lines.append(stripped)

        if len(lines) >= 3:
            break

    return " ".join(lines)[:300]


# Dòng tiêu đề IN HOA ở bất kỳ đâu trong khối đầu phần — khác với regex dùng ở
# Bước 1 (chỉ khớp dòng SẠCH, không có gì khác trên dòng). Ở đây nới ra vì bản
# scan hay dính chữ thừa vào cùng dòng: `QUY CHẾ TUYỂN SINH`, `QUY ĐỊNH 2`.
_TYPE_IN_HEADER = re.compile(
    r"^[ \t]*(" + "|".join(_TITLE_KEYWORD) + r")\b",
    re.M | re.IGNORECASE,
)


def content_type(text: str, part: segment.Part, meta_type: str | None) -> str:
    """
    Loại nội dung: `Quy chế`, `Quy định`, ...

    Ưu tiên chữ IN HOA đọc được trong chính text — đó là cái in trên trang.

    Metadata là nguồn tệ cho việc này: nhãn `loai_van_ban` của crawler ghi
    `"Quyết định, Quy định"` cho **cả 224** văn bản có nội dung kèm theo, kể cả
    những cái mà trang bìa in rõ chữ `QUY CHẾ`. Tin nhãn đó thì 165/178 nội
    dung bị gán nhầm thành "Quy định".
    """

    if part.title in _TITLE_KEYWORD:
        return _TITLE_KEYWORD[part.title]

    start, end = part.zones.get(
        "header", (part.start, min(part.end, part.start + 900))
    )
    match = _TYPE_IN_HEADER.search(deaccent(text[start:end]))

    if match:
        return _TITLE_KEYWORD[match.group(1).upper()]

    return meta_type or "Quy định"


# ============================================================
# CHẠY BƯỚC 4
# ============================================================

def run(session: KGSession, limit: int | None = None) -> dict[str, int]:
    from .citations import _load_parts

    ensure_schema(session)

    rows = [row for row in session.todo("art", limit=limit) if row["clean_path"]]
    tally: dict[str, int] = defaultdict(int)

    for index, row in enumerate(rows, start=1):
        if STOP.is_set():
            say(f"\n  Dừng theo yêu cầu — còn {len(rows) - index + 1} văn bản.")
            break

        doc_key = row["doc_key"]
        path = Path(row["clean_path"])

        if not path.is_absolute():
            path = config.ROOT / path

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            session.log("art", doc_key, "error", str(exc))
            session.update(doc_key, art_status="failed")
            tally["failed"] += 1
            continue

        parts = _load_parts(session, doc_key)

        with session._lock:  # noqa: SLF001
            session._conn.execute(  # noqa: SLF001
                "DELETE FROM normative WHERE doc_key = ?", (doc_key,)
            )

            for part in parts:
                if part.kind != segment.PART_NOI_DUNG:
                    continue

                content_id = f"{doc_key}#nd{part.index}"

                session._conn.execute(  # noqa: SLF001
                    "INSERT INTO normative VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        content_id,
                        doc_key,
                        part.index,
                        content_type(text, part, row["normative_type"]),
                        content_title(text, part),
                        # Nội dung kèm theo sống chết theo văn bản ban hành nó:
                        # quyết định hết hiệu lực thì quy chế kèm theo cũng vậy.
                        row["status"],
                        len(part.articles),
                        part.marker,
                    ),
                )

                tally["normative"] += 1

            session._conn.commit()  # noqa: SLF001

        n_art = sum(
            len(part.articles)
            for part in parts
            if part.kind != segment.PART_PHU_LUC
        )

        session.update(
            doc_key,
            art_status="done",
            art_note="" if n_art else "khong-co-dieu-nao",
        )

        tally["done"] += 1
        tally["dieu"] += n_art

        if index % 100 == 0:
            say(f"    ... {index}/{len(rows)}")

    return dict(tally)


# ============================================================
# XUẤT
# ============================================================

def export(session: KGSession, out_dir: Path | None = None) -> dict[str, Path]:
    """
    Xuất `NormativeContent`, `Article` và hai quan hệ chứa chúng.

    `Article` mang theo **toàn văn** phần text của nó — đó là điểm của §2.7:
    retrieval ở cấp điều khoản chứ không phải cấp văn bản (§6.3).
    """

    from .citations import _load_parts

    out_dir = out_dir or config.KG_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    nc_path = out_dir / "normative_contents.jsonl"
    art_path = out_dir / "articles.jsonl"

    with session._lock:  # noqa: SLF001
        contents = session._conn.execute(  # noqa: SLF001
            "SELECT * FROM normative ORDER BY doc_key, part_index"
        ).fetchall()
        docs = session._conn.execute(  # noqa: SLF001
            "SELECT doc_key, clean_path, normative_type, status FROM docs "
            "WHERE art_status = 'done' AND clean_path IS NOT NULL ORDER BY doc_key"
        ).fetchall()

    by_doc = {(row["doc_key"], row["part_index"]): row for row in contents}

    with nc_path.open("w", encoding="utf-8") as handle:
        for row in contents:
            handle.write(
                json.dumps(
                    {
                        "contentId": row["content_id"],
                        "contentType": row["content_type"],
                        "title": row["title"],
                        "status": row["status"],
                        "promulgatedBy": row["doc_key"],
                        "n_articles": row["n_articles"],
                        "marker": row["marker"],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    written = 0

    with art_path.open("w", encoding="utf-8") as handle:
        for row in docs:
            path = Path(row["clean_path"])

            if not path.is_absolute():
                path = config.ROOT / path

            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for part in _load_parts(session, row["doc_key"]):
                if part.kind == segment.PART_PHU_LUC:
                    continue

                container = by_doc.get((row["doc_key"], part.index))
                parent_id = container["content_id"] if container else row["doc_key"]
                parent_label = "NormativeContent" if container else "Document"

                # Trong một phần vẫn có thể gặp hai `Điều 5`: OCR đọc nhầm số,
                # hoặc bản scan lặp trang. Không phân biệt thì `MERGE` trong
                # Neo4j gộp chúng làm một và mất 72 Article.
                seen: dict[str, int] = {}

                for article in part.articles:
                    number = f"Điều {article.number}{article.suffix}"
                    article_id = f"{parent_id}#{number}"

                    seen[number] = seen.get(number, 0) + 1

                    if seen[number] > 1:
                        article_id += f"~{seen[number]}"

                    handle.write(
                        json.dumps(
                            {
                                "articleId": article_id,
                                "number": number,
                                "heading": article.heading,
                                "text": text[article.start : article.end].strip(),
                                "parentId": parent_id,
                                "parentLabel": parent_label,
                                "is_thi_hanh": article.is_thi_hanh,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    written += 1

    say(f"  {len(contents):>5} NormativeContent -> {nc_path}")
    say(f"  {written:>5} Article          -> {art_path}")

    return {"normative": nc_path, "articles": art_path}


def report(session: KGSession) -> str:
    ensure_schema(session)

    with session._lock:  # noqa: SLF001
        conn = session._conn  # noqa: SLF001
        total = conn.execute("SELECT COUNT(*) AS n FROM normative").fetchone()["n"]

        if not total:
            return "\nChưa dựng NormativeContent — chạy `python run.py kg art`.\n"

        by_type = conn.execute(
            "SELECT content_type, COUNT(*) AS n FROM normative "
            "GROUP BY content_type ORDER BY n DESC"
        ).fetchall()
        arts = conn.execute(
            "SELECT COUNT(*) AS n FROM articles a JOIN parts p "
            "ON p.doc_key = a.doc_key AND p.part_index = a.part_index "
            "WHERE p.kind != 'phu_luc'"
        ).fetchone()["n"]
        in_nc = conn.execute(
            "SELECT COUNT(*) AS n FROM articles a JOIN parts p "
            "ON p.doc_key = a.doc_key AND p.part_index = a.part_index "
            "WHERE p.kind = 'noi_dung'"
        ).fetchone()["n"]
        no_title = conn.execute(
            "SELECT COUNT(*) AS n FROM normative WHERE title = '' OR title IS NULL"
        ).fetchone()["n"]

    lines = [
        "",
        "=" * 62,
        f"BƯỚC 4 — NORMATIVE CONTENT + ARTICLE   ({total} nội dung kèm theo)",
        "=" * 62,
        "",
        "  Loại nội dung (§2.6):",
    ]

    for row in by_type:
        lines.append(f"    {row['content_type']:<24} {row['n']:>5}")

    lines += [
        "",
        f"  Article: {arts:,}  (bỏ phụ lục theo §9)",
        f"    treo vào NormativeContent   {in_nc:>6,}",
        f"    treo thẳng vào Document     {arts - in_nc:>6,}",
    ]

    if no_title:
        lines.append(f"\n  {no_title} nội dung chưa moi được tên — cần soi tay.")

    lines.append("")

    return "\n".join(lines)
