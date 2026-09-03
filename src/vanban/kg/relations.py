"""
Bước 3 — phân loại từng trích dẫn thành một quan hệ trong §4 Ontology.

Bước 2 đã ghi mỗi trích dẫn kèm **vùng** chứa nó và **240 ký tự đứng trước**.
Bước này chỉ đọc lại hai thứ đó, không đụng vào file text nữa — nhờ vậy sửa
luật phân loại rồi chạy lại chỉ mất vài giây thay vì quét lại 20 MB.

## Vùng quyết định trước, từ khoá quyết định sau (§5.4)

    Vùng `can_cu`              -> BASED_ON, không cần hỏi gì thêm
    Vùng `than`, có từ khoá    -> REPLACES / AMENDS / REPEALS
    Còn lại                    -> REFERENCES

Thứ tự này không đảo được. Khối "Căn cứ" đầu văn bản có cả những câu như *"Căn
cứ Nghị định 99/2019/NĐ-CP ... **thay thế** Nghị định 141/2013/NĐ-CP"* — bắt từ
khoá trước thì cả hai số hiệu đều thành `REPLACES`, trong khi văn bản đang xét
chẳng thay thế cái nào; nó chỉ **căn cứ** vào một văn bản mà tình cờ trong tên
có chữ "thay thế".

## Ba quan hệ hiệu lực phải tách bạch (§4)

    REPLACES  "thay thế"                    -> B hết hiệu lực, A thế chỗ
    AMENDS    "sửa đổi, bổ sung một số điều"-> B VẪN hiệu lực, chỉ đổi vài điều
    REPEALS   "bãi bỏ" / "huỷ bỏ"           -> B hết hiệu lực, không ai thế chỗ

Gộp ba cái này là hỏng đúng chỗ ontology nhấn mạnh: `AMENDS` không làm B chết,
hai cái kia thì có. Truy vấn "văn bản nào đang còn hiệu lực" sai ngay.

## Từ khoá gần nhất thắng

Một câu điều khoản thi hành hay nhắc nhiều văn bản với nhiều động từ khác nhau:

    "...thay thế Quyết định số 42/2007/QĐ-BGDĐT và bãi bỏ Điều 5
     Thông tư số 10/2011/TT-BGDĐT"

Nên phải lấy từ khoá **gần số hiệu nhất tính ngược về trước**, chứ không phải
từ khoá đầu tiên tìm thấy trong cửa sổ.
"""

from __future__ import annotations

import re
from collections import defaultdict

from ..normalize import deaccent
from ..pipeline import STOP, say
from .session import KGSession

# Quan hệ theo §4 Ontology.
BASED_ON = "BASED_ON"
REFERENCES = "REFERENCES"
REPLACES = "REPLACES"
AMENDS = "AMENDS"
REPEALS = "REPEALS"

# Từ khoá -> quan hệ. Viết không dấu vì so trên bản `deaccent`, và cho phép vài
# ký tự rác chen giữa các từ (OCR).
_W = r"[\s,;_.·-]{0,4}"

_TRIGGERS: tuple[tuple[str, re.Pattern], ...] = (
    # `sửa đổi, bổ sung` phải đứng TRƯỚC `bổ sung` và `thay thế`: câu đầy đủ là
    # "sửa đổi, bổ sung một số điều của..." — bắt `bổ sung` trước thì mất vế
    # `sửa đổi`, mà hai vế này cùng một quan hệ nên không sao; nhưng câu "sửa
    # đổi, bổ sung ... thay thế cụm từ" thì thứ tự lại đổi nghĩa.
    (AMENDS, re.compile(r"sua" + _W + r"doi", re.I)),
    (AMENDS, re.compile(r"bo" + _W + r"sung", re.I)),
    (REPLACES, re.compile(r"thay" + _W + r"the", re.I)),
    (REPEALS, re.compile(r"bai" + _W + r"bo", re.I)),
    (REPEALS, re.compile(r"huy" + _W + r"bo", re.I)),
    (REPEALS, re.compile(r"cham" + _W + r"dut" + _W + r"hieu" + _W + r"luc", re.I)),
)

# Cửa sổ tìm từ khoá, tính ngược từ số hiệu về trước. Rộng hơn thì bắt sang câu
# trước; hẹp hơn thì trượt những câu chèn tên văn bản dài ở giữa
# ("thay thế Quyết định số 42/2007/QĐ-BGDĐT ngày 13 tháng 8 năm 2007 của Bộ
# trưởng Bộ Giáo dục và Đào tạo ban hành Quy chế học sinh, sinh viên...").
_WINDOW = 200

# Số hiệu khác chen vào trước từ khoá — dùng để kiểm chủ ngữ (xem `classify`).
# Bản không dấu nên `Đ` đã thành `D`.
_CITE_IN_TEXT = re.compile(
    r"\b\d{1,4}\s*/\s*(?:\d{4}\s*/\s*)?[A-Z]{2,8}\d{0,2}(?:-[A-Za-z0-9]{1,15})*"
)


def classify(
    context: str,
    zone: str | None,
    in_thi_hanh: bool = False,
    part_kind: str = "van_ban",
) -> tuple[str, str | None]:
    """
    (quan hệ, từ khoá đã dùng) cho một trích dẫn.

    `context` là đoạn Bước 2 đã lưu; số hiệu nằm ở cuối, cách đuôi chừng 80 ký
    tự. Cửa sổ tìm từ khoá vì vậy đo ngược từ đó.
    """

    if zone == "can_cu":
        return BASED_ON, None

    # Ba quan hệ hiệu lực chỉ được sinh ra trong **điều khoản thi hành** (§5.4).
    #
    # Ngoài vùng đó, từ khoá thường mô tả quan hệ giữa hai văn bản KHÁC, chứ
    # không phải của văn bản đang xét:
    #
    #   "...theo Nghị định số 09/2010/NĐ-CP ... sửa đổi, bổ sung Nghị định số
    #    110/2004/NĐ-CP..."
    #
    # Ở đây người sửa là 09/2010, không phải văn bản đang đọc. Bỏ ràng buộc này
    # thì AMENDS phình từ 631 lên 1.077, gần một nửa là cạnh gán sai chủ thể.
    #
    # Phụ lục thì loại hẳn: §9 không đưa phụ lục vào ontology, và trích dẫn
    # trong đó phần lớn là bảng biểu, chân trang.
    if not in_thi_hanh or part_kind == "phu_luc":
        return REFERENCES, None

    flat = deaccent(context)

    # Số hiệu nằm ở đâu trong context: Bước 2 cắt `_CONTEXT_BEFORE` ký tự phía
    # trước, nên vị trí của nó chính là chiều dài phần đầu.
    cite_at = max(0, len(flat) - 80)
    window = flat[max(0, cite_at - _WINDOW) : cite_at]

    best: tuple[int, str, str] | None = None

    for relation, pattern in _TRIGGERS:
        for match in pattern.finditer(window):
            # Gần số hiệu nhất thắng -> lấy lần khớp cuối cùng của mỗi từ khoá.
            if best is None or match.start() > best[0]:
                best = (match.start(), relation, match.group(0))

    if not best:
        return REFERENCES, None

    # Chủ ngữ của động từ phải là chính văn bản đang xét. Có một số hiệu KHÁC
    # đứng chen giữa đầu câu và từ khoá thì chủ ngữ là văn bản đó:
    #
    #   "Luật số 38/2005/QH11 đã được sửa đổi, bổ sung ... theo Luật số
    #    44/2009/QH12"
    #
    # Người sửa ở đây là 44/2009 và người bị sửa là 38/2005 — văn bản đang đọc
    # (`10/2022/QH15`) không dính dáng gì. Câu thật thì chủ ngữ trống hoặc là
    # "Thông tư này": *"Thông tư này có hiệu lực... và thay thế Thông tư số
    # 08/2014/TT-BGDĐT"* — không có số hiệu nào chen vào trước từ khoá.
    if _CITE_IN_TEXT.search(window, 0, best[0]):
        return REFERENCES, None

    return best[1], best[2]


def run(session: KGSession, limit: int | None = None) -> dict[str, int]:
    """Gán quan hệ cho mọi trích dẫn chưa phân loại."""

    with session._lock:  # noqa: SLF001
        rows = session._conn.execute(  # noqa: SLF001
            "SELECT id, context, zone, in_thi_hanh, part_kind FROM citations "
            "WHERE relation IS NULL"
            + (f" LIMIT {int(limit)}" if limit else "")
        ).fetchall()

    if not rows:
        return {}

    tally: dict[str, int] = defaultdict(int)
    updates = []

    for index, row in enumerate(rows, start=1):
        if STOP.is_set():
            say(f"\n  Dừng theo yêu cầu — còn {len(rows) - index + 1} trích dẫn.")
            break

        relation, trigger = classify(
            row["context"] or "",
            row["zone"],
            in_thi_hanh=bool(row["in_thi_hanh"]),
            part_kind=row["part_kind"] or "van_ban",
        )
        updates.append((relation, trigger, row["id"]))
        tally[relation] += 1

    with session._lock:  # noqa: SLF001
        session._conn.executemany(  # noqa: SLF001
            "UPDATE citations SET relation = ?, trigger = ? WHERE id = ?", updates
        )
        session._conn.commit()  # noqa: SLF001

    # Bảng `docs` giữ trạng thái theo văn bản, không theo trích dẫn — đánh dấu
    # xong cho những văn bản không còn trích dẫn nào chưa phân loại.
    with session._lock:  # noqa: SLF001
        session._conn.execute(  # noqa: SLF001
            "UPDATE docs SET rel_status = 'done' WHERE cite_status = 'done' "
            "AND NOT EXISTS (SELECT 1 FROM citations c "
            "WHERE c.doc_key = docs.doc_key AND c.relation IS NULL)"
        )
        session._conn.commit()  # noqa: SLF001

    tally["da_phan_loai"] = len(updates)

    return dict(tally)


# ============================================================
# XUẤT CẠNH
# ============================================================

def export(session: KGSession, out_dir=None):
    """
    Xuất cạnh Document -> Document ra JSONL.

    Gộp các trích dẫn trùng (A nhắc B ba lần trong cùng một vùng với cùng một
    quan hệ thì graph chỉ cần một cạnh) nhưng giữ lại số lần và một ví dụ ngữ
    cảnh để còn kiểm chứng khi đánh giá (§6.2).
    """

    import json

    from .. import config

    out_dir = out_dir or config.KG_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    path = out_dir / "relations.jsonl"

    with session._lock:  # noqa: SLF001
        rows = session._conn.execute(  # noqa: SLF001
            """
            SELECT c.doc_key, c.target_key, c.relation,
                   COUNT(*) AS hits,
                   MIN(c.zone) AS zone,
                   MIN(c.article_number) AS article,
                   MAX(c.in_thi_hanh) AS thi_hanh,
                   MIN(c.surface) AS surface,
                   MIN(c.context) AS context,
                   MAX(d.is_stub) AS target_stub,
                   MAX(s.header_check) AS source_header
            FROM citations c
            LEFT JOIN docs d ON d.doc_key = c.target_key
            LEFT JOIN docs s ON s.doc_key = c.doc_key
            WHERE c.relation IS NOT NULL AND c.resolved = 1
            GROUP BY c.doc_key, c.target_key, c.relation
            ORDER BY c.doc_key, c.relation
            """
        ).fetchall()

    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    {
                        "source": row["doc_key"],
                        "target": row["target_key"],
                        "type": row["relation"],
                        "hits": row["hits"],
                        "zone": row["zone"],
                        "article": row["article"],
                        "in_thi_hanh": bool(row["thi_hanh"]),
                        "surface": row["surface"],
                        "target_is_stub": bool(row["target_stub"]),
                        # Cờ chất lượng: văn bản nguồn có header lệch metadata
                        # thì cạnh này đáng ngờ ngay từ gốc (§4.1 TIEN_DO).
                        "source_header_check": row["source_header"],
                        "context": " ".join((row["context"] or "").split())[:300],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    say(f"  {len(rows):>5} cạnh Document->Document -> {path}")

    return path


def report(session: KGSession) -> str:
    with session._lock:  # noqa: SLF001
        conn = session._conn  # noqa: SLF001

        try:
            total = conn.execute(
                "SELECT COUNT(*) AS n FROM citations WHERE relation IS NOT NULL"
            ).fetchone()["n"]
        except Exception:
            return ""

        if not total:
            return "\nChưa phân loại quan hệ nào — chạy `python run.py kg rel`.\n"

        by_rel = conn.execute(
            "SELECT relation, COUNT(*) AS n, "
            "SUM(resolved) AS noi_duoc FROM citations "
            "WHERE relation IS NOT NULL GROUP BY relation ORDER BY n DESC"
        ).fetchall()
        edges = conn.execute(
            "SELECT COUNT(*) AS n FROM (SELECT DISTINCT doc_key, target_key, relation "
            "FROM citations WHERE relation IS NOT NULL AND resolved = 1)"
        ).fetchone()["n"]

    lines = [
        "",
        "=" * 62,
        f"BƯỚC 3 — QUAN HỆ   ({total:,} trích dẫn -> {edges:,} cạnh)",
        "=" * 62,
        "",
        f"  {'Quan hệ':<14}{'trích dẫn':>12}{'nối được':>12}",
    ]

    for row in by_rel:
        lines.append(
            f"  {row['relation']:<14}{row['n']:>12,}{(row['noi_duoc'] or 0):>12,}"
        )

    lines.append("")

    return "\n".join(lines)
