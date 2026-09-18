"""
Bước 2 — trích số hiệu trong thân văn bản và nối vào node `Document`.

Đây là bước đầu tiên sinh ra **cạnh** cho graph. Hai việc:

1. Quét toàn bộ số hiệu xuất hiện trong 448 văn bản, ghi lại kèm **vị trí** —
   rồi hỏi Bước 1 xem vị trí đó nằm ở phần nào, vùng nào, Điều nào.
2. Nối số hiệu đó về một `Document`. Nối không được thì cân nhắc tạo **stub**
   (§1 Ontology: văn bản bị viện dẫn nhưng chưa crawl vẫn là một node).

Bước này chưa phân loại quan hệ — chỉ ghi nhận "có một trích dẫn ở đây, trỏ tới
kia, nằm trong vùng nọ". Bước 3 đọc `context` đã lưu để quyết định đó là
`BASED_ON`, `REPLACES`, `AMENDS`, `REPEALS` hay `REFERENCES`.

---

## Ngưỡng tạo stub

Đo trên kho: **9.025 lần trích dẫn / 2.136 số hiệu phân biệt**, trong đó chỉ
**428 nối được** vào 450 văn bản đã crawl. Tạo stub cho cả 1.708 số hiệu còn
lại thì graph có ~2.150 node mà 3/4 là node rỗng — tra cứu gì cũng đâm vào ngõ
cụt.

Ngưỡng đã chốt: **xuất hiện ≥ 2 lần, HOẶC nằm trong vùng `Căn cứ`.**

Vế sau quan trọng hơn vế trước. Vùng `Căn cứ` là nơi văn bản khai cơ sở pháp lý
của chính nó — một `Luật` chỉ được nhắc đúng một lần ở đó vẫn là mắt xích thật
của chuỗi `BASED_ON`, thứ mà §3 dùng để truy ngược lên văn bản gốc thẩm quyền
cao nhất. Ngược lại, một số hiệu xuất hiện đúng một lần giữa thân văn bản
thường là OCR đọc sai hoặc trích dẫn vụn.

---

## Tự trỏ chính mình

Số hiệu của chính văn bản xuất hiện ít nhất hai lần trong mỗi file: ở header
trang 1, và trong dòng `(Kèm theo Quyết định số ...)` mở đầu phần nội dung kèm
theo. Không lọc thì mỗi `Document` có một cạnh tự trỏ vô nghĩa.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from ..core import config
from ..core.console import STOP, say
from . import norm, segment
from .session import KGSession


# `115/2020/NĐ-CP`, `2347/QĐ-ĐHBK`, `100/2015/QH13`, `3878/BGDĐT-PC`.
#
# Phần đuôi bắt buộc phải có CHỮ CÁI — nếu không, mọi ngày tháng `21/01/2024`
# đều thành trích dẫn. `\d{0,2}` sau cụm chữ là cho khoá Quốc hội (`QH13`).
#
# Cụm chữ phải từ 2 ký tự trở lên. Một chữ cái đơn thì gần như luôn là rác:
# chân trang `CÔNG BÁO Số 291 + 292/Ngày 14-02-2024` cho ra `292/N`, dòng
# `180/N` `4/H` cũng vậy — không có loại văn bản nào mã một chữ trừ `L-CTN`
# (Lệnh), mà cái đó có phần đuôi đi kèm nên vẫn khớp.
_CITE = re.compile(
    r"\b\d{1,4}\s*/\s*(?:\d{4}\s*/\s*)?"
    r"(?:[A-ZĐÐ]{2,8}\d{0,2}|[A-ZĐÐ]\d{0,2}-[A-ZĐÐ]{2,})"
    r"(?:-[A-ZĐÐa-z0-9]{1,15})*"
)

# Ngữ cảnh lưu kèm mỗi trích dẫn để Bước 3 phân loại mà không phải đọc lại file.
# Từ khoá hiệu lực đứng TRƯỚC số hiệu ("thay thế Quyết định số 42/2007/...")
# nên cửa sổ phía trước phải rộng hơn hẳn phía sau.
_CONTEXT_BEFORE = 240
_CONTEXT_AFTER = 80

_MIN_VOTES_FOR_STUB = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS citations (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_key        TEXT,       -- văn bản chứa trích dẫn
    target_key     TEXT,       -- số hiệu được nhắc tới (đã chuẩn hoá)
    surface        TEXT,       -- nguyên văn trong text
    offset         INTEGER,
    part_index     INTEGER,
    part_kind      TEXT,
    zone           TEXT,
    article_seq    INTEGER,
    article_number INTEGER,
    in_thi_hanh    INTEGER,
    context        TEXT,
    resolved       INTEGER,    -- 1 = trỏ tới văn bản đã crawl, 0 = stub
    relation       TEXT,       -- Bước 3 điền
    trigger        TEXT        -- Bước 3 điền
);

CREATE INDEX IF NOT EXISTS idx_cit_doc ON citations(doc_key);
CREATE INDEX IF NOT EXISTS idx_cit_target ON citations(target_key);
CREATE INDEX IF NOT EXISTS idx_cit_rel ON citations(relation);
"""


def ensure_schema(session: KGSession) -> None:
    with session._lock:  # noqa: SLF001
        session._conn.executescript(SCHEMA)  # noqa: SLF001
        session._conn.commit()  # noqa: SLF001

    session.add_columns(
        (
            ("is_stub", "INTEGER DEFAULT 0"),
            ("stub_hits", "INTEGER"),
            ("cite_note", "TEXT"),
            ("n_citations", "INTEGER"),
        )
    )


# ============================================================
# QUÉT
# ============================================================

def _load_parts(session: KGSession, doc_key: str) -> list[segment.Part]:
    """Dựng lại cấu trúc Bước 1 từ DB, không phải cắt lại."""

    with session._lock:  # noqa: SLF001
        rows = session._conn.execute(  # noqa: SLF001
            "SELECT * FROM parts WHERE doc_key = ? ORDER BY part_index", (doc_key,)
        ).fetchall()
        arts = session._conn.execute(  # noqa: SLF001
            "SELECT * FROM articles WHERE doc_key = ? ORDER BY part_index, seq",
            (doc_key,),
        ).fetchall()

    by_part: dict[int, list] = defaultdict(list)

    for row in arts:
        by_part[row["part_index"]].append(row)

    parts = []

    for row in rows:
        part = segment.Part(
            index=row["part_index"],
            kind=row["kind"],
            title=row["title"] or "",
            marker=row["marker"] or "",
            start=row["start"],
            end=row["end"],
            zones={
                name: tuple(span)
                for name, span in json.loads(row["zones"] or "{}").items()
            },
            articles=[
                segment.Article(
                    seq=item["seq"],
                    number=item["number"],
                    suffix=item["suffix"] or "",
                    heading=item["heading"] or "",
                    start=item["start"],
                    end=item["end"],
                    is_thi_hanh=bool(item["is_thi_hanh"]),
                )
                for item in by_part[row["part_index"]]
            ],
        )
        parts.append(part)

    return parts


def scan_document(
    session: KGSession,
    doc_key: str,
    text: str,
    parts: list[segment.Part],
) -> list[dict]:
    """Mọi trích dẫn trong một văn bản, kèm vùng chứa nó."""

    found = []

    for match in _CITE.finditer(text):
        surface = match.group(0)
        target = norm.so_hieu_key(surface)

        if not target or target == doc_key:
            continue

        # Số hiệu phải có phần chữ cái thật sự, không phải một mảnh vụn OCR.
        _, _, code, org = norm.split_so_hieu(norm.so_hieu_norm(surface))

        if not code and not org:
            continue

        part, zone, article = segment.zone_at(parts, match.start())

        found.append(
            {
                "doc_key": doc_key,
                "target_key": target,
                "surface": surface,
                "offset": match.start(),
                "part_index": part.index if part else None,
                "part_kind": part.kind if part else None,
                "zone": zone,
                "article_seq": article.seq if article else None,
                "article_number": article.number if article else None,
                "in_thi_hanh": int(bool(article and article.is_thi_hanh)),
                "context": text[
                    max(0, match.start() - _CONTEXT_BEFORE) : match.end() + _CONTEXT_AFTER
                ],
            }
        )

    return found


def _save(session: KGSession, doc_key: str, rows: list[dict]) -> None:
    with session._lock:  # noqa: SLF001
        conn = session._conn  # noqa: SLF001

        conn.execute("DELETE FROM citations WHERE doc_key = ?", (doc_key,))

        for row in rows:
            conn.execute(
                "INSERT INTO citations (doc_key, target_key, surface, offset, "
                "part_index, part_kind, zone, article_seq, article_number, "
                "in_thi_hanh, context, resolved) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
                (
                    row["doc_key"],
                    row["target_key"],
                    row["surface"],
                    row["offset"],
                    row["part_index"],
                    row["part_kind"],
                    row["zone"],
                    row["article_seq"],
                    row["article_number"],
                    row["in_thi_hanh"],
                    row["context"],
                ),
            )

        conn.commit()


# ============================================================
# TẠO STUB (§1)
# ============================================================

def _repair_truncated(session: KGSession, known: set[str]) -> int:
    """
    Nối lại các số hiệu bị cắt cụt đuôi về văn bản thật.

    Đuôi số hiệu hay bị xuống dòng hoặc bị OCR nuốt, để lại `115/2020/ND` thay
    vì `115/2020/NĐ-CP`. Đo trên kho: riêng hai dạng cụt `…/ND` và `…/QD` đã
    chiếm 1.554 lượt trích dẫn — bỏ mặc thì chúng thành 470 node stub rỗng,
    không có cả `documentType` lẫn `authority_level`.

    Chỉ vá khi số hiệu cụt là tiền tố của **đúng một** văn bản đã biết. Cụt
    kiểu `32/QD` là tiền tố của hàng chục `32/QD-…` khác nhau — đoán bừa còn
    tệ hơn để nguyên.
    """

    with session._lock:  # noqa: SLF001
        unresolved = [
            row["target_key"]
            for row in session._conn.execute(  # noqa: SLF001
                "SELECT DISTINCT target_key FROM citations"
            )
            if row["target_key"] not in known
        ]

    fixes: list[tuple[str, str]] = []

    for key in unresolved:
        # Chỉ xét dạng cụt: kết thúc bằng cụm chữ, không có dấu `-`.
        if "-" in key.rsplit("/", 1)[-1]:
            continue

        matches = [
            other
            for other in known
            if other.startswith(key + "-") or other.startswith(key + "/")
        ]

        if len(matches) == 1:
            fixes.append((matches[0], key))

    if fixes:
        with session._lock:  # noqa: SLF001
            session._conn.executemany(  # noqa: SLF001
                "UPDATE citations SET target_key = ? WHERE target_key = ?", fixes
            )

            # Vá xong có thể sinh ra cạnh tự trỏ: `1001/QD` cụt được nối về
            # `1001/QD-DHBK`, mà đó chính là văn bản đang chứa trích dẫn.
            session._conn.execute(  # noqa: SLF001
                "DELETE FROM citations WHERE target_key = doc_key"
            )
            session._conn.commit()  # noqa: SLF001

    return len(fixes)


def _resolve_and_stub(session: KGSession) -> dict[str, int]:
    """
    Chốt xem số hiệu lạ nào được lên node, số hiệu nào bỏ.

    Chạy sau khi đã quét xong toàn kho: ngưỡng "xuất hiện ≥2 lần" chỉ tính
    được khi có đủ phiếu của tất cả văn bản.
    """

    with session._lock:  # noqa: SLF001
        conn = session._conn  # noqa: SLF001
        known = {
            row["doc_key"]
            for row in conn.execute("SELECT doc_key FROM docs WHERE is_stub = 0")
        }
    # Vá số hiệu cụt TRƯỚC khi đếm phiếu: `115/2020/ND` gộp về
    # `115/2020/ND-CP` thì phiếu của nó cộng vào văn bản thật, chứ không đẻ ra
    # một stub song song.
    repaired = _repair_truncated(session, known)

    with session._lock:  # noqa: SLF001
        conn = session._conn  # noqa: SLF001
        rows = conn.execute(
            "SELECT target_key, zone, COUNT(*) AS n FROM citations "
            "GROUP BY target_key, zone"
        ).fetchall()

    hits: Counter[str] = Counter()
    in_can_cu: set[str] = set()

    for row in rows:
        hits[row["target_key"]] += row["n"]

        if row["zone"] == "can_cu":
            in_can_cu.add(row["target_key"])

    unknown = [key for key in hits if key not in known]

    # Ngưỡng: nhắc lại nhiều lần, HOẶC được viện dẫn làm cơ sở pháp lý.
    stubs = [
        key
        for key in unknown
        if hits[key] >= _MIN_VOTES_FOR_STUB or key in in_can_cu
    ]

    stub_set = set(stubs)

    with session._lock:  # noqa: SLF001
        conn = session._conn  # noqa: SLF001

        for key in stubs:
            display = key
            doc_type = norm.doc_type_from_so_hieu(key)
            org = norm.org_from_so_hieu(key)
            org_name = org[0] if org else None
            level, level_note = norm.authority_level(doc_type, org_name)

            conn.execute(
                """
                INSERT INTO docs (
                    doc_key, so_hieu, so_hieu_raw, doc_ids, title, topics,
                    doc_type, org_name, org_id, authority_level, level_note,
                    is_stub, stub_hits,
                    doc_status, seg_status, cite_status, updated_at
                )
                VALUES (?, ?, ?, '[]', '', '[]', ?, ?, ?, ?, ?, 1, ?,
                        'done', 'done', 'done', datetime('now'))
                ON CONFLICT(doc_key) DO UPDATE SET
                    stub_hits       = excluded.stub_hits,
                    doc_type        = excluded.doc_type,
                    org_name        = excluded.org_name,
                    org_id          = excluded.org_id,
                    authority_level = excluded.authority_level,
                    level_note      = excluded.level_note
                """,
                (
                    key,
                    display,
                    display,
                    doc_type,
                    org_name,
                    norm.org_id(org_name) if org_name else None,
                    level,
                    level_note,
                    hits[key],
                ),
            )

        # Stub của lần chạy trước có thể đã hết lý do tồn tại (sửa regex trích
        # dẫn, đổi ngưỡng). Node stub không còn ai trỏ tới là node mồ côi.
        removed = conn.execute(
            "DELETE FROM docs WHERE is_stub = 1 AND doc_key NOT IN "
            "(SELECT DISTINCT target_key FROM citations)"
        ).rowcount

        conn.execute(
            "UPDATE citations SET resolved = "
            "(SELECT COUNT(*) FROM docs d WHERE d.doc_key = citations.target_key)"
        )
        conn.commit()

    return {
        "so_hieu_phan_biet": len(hits),
        "noi_duoc": len(hits) - len(unknown),
        "stub_tao_moi": len(stubs),
        "bo_qua": len(unknown) - len(stubs),
        "stub_vi_can_cu": sum(
            1 for key in stub_set if hits[key] < _MIN_VOTES_FOR_STUB
        ),
        "stub_mo_coi_da_xoa": removed,
        "so_hieu_cut_da-va": repaired,
    }


# ============================================================
# CHẠY BƯỚC 2
# ============================================================

def run(session: KGSession, limit: int | None = None) -> dict[str, int]:
    ensure_schema(session)

    rows = [row for row in session.todo("cite", limit=limit) if row["clean_path"]]
    tally: dict[str, int] = defaultdict(int)

    for index, row in enumerate(rows, start=1):
        if STOP.is_set():
            say(f"\n  Dừng theo yêu cầu — còn {len(rows) - index + 1} văn bản.")
            return dict(tally)

        doc_key = row["doc_key"]
        path = Path(row["clean_path"])

        if not path.is_absolute():
            path = config.ROOT / path

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            session.log("cite", doc_key, "error", str(exc))
            session.update(doc_key, cite_status="failed")
            tally["failed"] += 1
            continue

        parts = _load_parts(session, doc_key)

        if not parts:
            session.update(doc_key, cite_status="failed", cite_note="chua-cat-vung")
            tally["chua-cat-vung"] += 1
            continue

        found = scan_document(session, doc_key, text, parts)
        _save(session, doc_key, found)

        session.update(
            doc_key,
            cite_status="done",
            n_citations=len(found),
            cite_note="khong-co-trich-dan" if not found else "",
        )

        tally["done"] += 1
        tally["trich_dan"] += len(found)

        for item in found:
            if item["zone"]:
                tally[f"vung:{item['zone']}"] += 1

        if index % 100 == 0:
            say(f"    ... {index}/{len(rows)}")

    if tally.get("done"):
        say("\n  Chốt danh sách stub (cần quét xong cả kho mới đếm được phiếu)...")
        tally.update(_resolve_and_stub(session))

    return dict(tally)


# ============================================================
# BÁO CÁO
# ============================================================

def report(session: KGSession) -> str:
    ensure_schema(session)

    with session._lock:  # noqa: SLF001
        conn = session._conn  # noqa: SLF001
        total = conn.execute("SELECT COUNT(*) AS n FROM citations").fetchone()["n"]

        if not total:
            return "\nChưa trích dẫn nào — chạy `python run.py kg cite`.\n"

        resolved = conn.execute(
            "SELECT COUNT(*) AS n FROM citations WHERE resolved = 1"
        ).fetchone()["n"]
        zones = conn.execute(
            "SELECT zone, COUNT(*) AS n FROM citations GROUP BY zone ORDER BY n DESC"
        ).fetchall()
        kinds = conn.execute(
            "SELECT part_kind, COUNT(*) AS n FROM citations "
            "GROUP BY part_kind ORDER BY n DESC"
        ).fetchall()
        stubs = conn.execute(
            "SELECT COUNT(*) AS n FROM docs WHERE is_stub = 1"
        ).fetchone()["n"]
        real = conn.execute(
            "SELECT COUNT(*) AS n FROM docs WHERE is_stub = 0"
        ).fetchone()["n"]
        top = conn.execute(
            "SELECT target_key, COUNT(*) AS n FROM citations "
            "GROUP BY target_key ORDER BY n DESC LIMIT 5"
        ).fetchall()

    lines = [
        "",
        "=" * 62,
        f"BƯỚC 2 — TRÍCH DẪN   ({total:,} lần)",
        "=" * 62,
        "",
        f"  Nối được vào Document: {resolved:,}/{total:,} "
        f"({100 * resolved // total}%)",
        "",
        f"  Node Document: {real} thật + {stubs} stub "
        f"(tỷ lệ stub/thật {stubs / real:.1f}:1)",
        "",
        "  Trích dẫn theo vùng:",
    ]

    for row in zones:
        lines.append(f"    {str(row['zone']):<24} {row['n']:>6,}")

    lines += ["", "  Theo phần:"]

    for row in kinds:
        lines.append(f"    {str(row['part_kind']):<24} {row['n']:>6,}")

    lines += ["", "  Được nhắc nhiều nhất:"]

    for row in top:
        lines.append(f"    {row['target_key']:<24} {row['n']:>6,}")

    lines.append("")

    return "\n".join(lines)
