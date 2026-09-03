"""
Bước 1 — cắt vùng cấu trúc trong từng văn bản.

Bước này KHÔNG tạo node nào. Nó trả lời một câu hỏi duy nhất mà Bước 2 và 3
không thể làm việc nếu thiếu: **một vị trí bất kỳ trong file nằm ở chỗ nào của
văn bản?** Vì theo §5.4 Ontology, cùng một số hiệu được phân loại quan hệ khác
hẳn nhau tuỳ chỗ nó đứng:

    "Căn cứ Nghị định số 99/2019/NĐ-CP..."          -> BASED_ON
    "...thay thế Quyết định số 42/2007/QĐ-BGDĐT"    -> REPLACES

Cùng là `99/2019/NĐ-CP`, nhưng một cái ở khối *Căn cứ* đầu văn bản, một cái ở
*điều khoản thi hành* cuối văn bản. Không biết vùng thì không phân loại được.

---

## Hai văn bản trong một file

Đo trên kho: **176/460 file chứa hai văn bản lồng nhau.** Đây là dạng
"Quyết định ban hành kèm theo Quy chế" (§2.6 — 224 văn bản có nhãn này):

    BỘ GIÁO DỤC VÀ ĐÀO TẠO ...        <- phần 0: văn bản ban hành
    Số: 10/2016/TT-BGDĐT
    THÔNG TƯ
    Căn cứ Luật Giáo dục đại học...
    Điều 1. Ban hành kèm theo Thông tư này Quy chế...
    Điều 2. Thông tư này có hiệu lực... và thay thế Quyết định 42/2007...
    Điều 3. Chánh Văn phòng... chịu trách nhiệm thi hành
    Nơi nhận: ...                      <- chữ ký, hết phần 0

    QUY CHẾ                            <- phần 1: NormativeContent
    Công tác sinh viên...
    (Ban hành kèm theo Thông tư số 10/2016/TT-BGDĐT ...)
    Chương I
    Điều 1. Phạm vi điều chỉnh          <- ĐÁNH SỐ LẠI TỪ ĐẦU
    ...

Không tách hai phần thì "Điều 5" trở nên vô nghĩa — Điều 5 của cái nào? Và
`AMENDS` trỏ tới Article (§4) sẽ trỏ nhầm. Nên ranh giới này phải tìm ở Bước 1,
trước khi đụng tới bất kỳ quan hệ nào.

Ba tín hiệu, đo được trên kho:

| Tín hiệu                          | Số file |
| --------------------------------- | ------- |
| dòng tiêu đề IN HOA (`QUY CHẾ`)   | 167     |
| `(Ban hành kèm theo ...)`         | 166     |
| dãy số Điều tụt về 1              | 176     |
| ít nhất một trong hai cái đầu     | 229     |

Không cái nào đủ một mình: 25 file có dãy Điều tụt lùi mà không có tiêu đề nào
đọc được (OCR nuốt mất), 78 file có tiêu đề mà không tụt số (phụ lục, hoặc bản
Quy chế đứng riêng). Nên dùng cả ba và ghi lại **tín hiệu nào đã quyết định** —
Bước 4 cần biết ranh giới đó chắc tới đâu.

Phụ lục / danh mục cũng bắt đầu bằng một dòng IN HOA giống hệt, nhưng §9 nói rõ
không đưa vào ontology. Vẫn cắt ra thành phần riêng, chỉ là gắn nhãn `phu_luc`
để Bước 2–4 bỏ qua.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .. import config
from ..normalize import deaccent
from ..pipeline import STOP, say
from .session import KGSession


# ============================================================
# MỐC CẤU TRÚC
# ============================================================

# Dấu phân trang do bước OCR chèn. Không bỏ đi (mọi offset phải khớp đúng file
# gốc để Bước 2 tra ngược được), nhưng phải biết nó ở đâu để đừng nhận nhầm là
# nội dung.
_PAGE = re.compile(r"^-{3,}\s*\[Trang\s*\d+\]\s*-{3,}\s*$", re.M)

# `Điều 5.` đầu dòng. Bắt buộc neo đầu dòng và có dấu `.`/`:` ngay sau số —
# nếu không sẽ dính "quy định tại Điều 5 của Luật..." nằm giữa câu.
#
# Chữ cái sau số là cho điều bổ sung (`Điều 5a`), dạng chuẩn của văn bản sửa đổi.
_DIEU = re.compile(r"^[ \t]*Điều\s+(\d+)([a-zA-ZđĐ]?)\s*[.:]\s*(.*)$", re.M)

_CHUONG = re.compile(r"^[ \t]*(?:CHƯƠNG|Chương)\s+([IVXLC]+|\d+)\b(.*)$", re.M)

# Khối căn cứ pháp lý. Tìm trên bản bỏ dấu vì `Căn cứ` bị OCR làm hỏng đủ kiểu.
_CAN_CU = re.compile(r"^[ \t]*Can\s*cu\b", re.M | re.IGNORECASE)

# Dòng tiêu đề IN HOA mở đầu một văn bản con. Khớp trên bản bỏ dấu: chữ IN HOA
# có dấu là chỗ OCR sai nhiều nhất (`ĐÀO TẠO` -> `ĐÀO TAO`).
_NORMATIVE_TITLES = (
    "QUY DINH",
    "QUY CHE",
    "DIEU LE",
    "QUY TRINH",
    "NOI QUY",
    "DE AN",
    "KE HOACH",
    "HUONG DAN",
    "CHUONG TRINH",
)

_APPENDIX_TITLES = ("PHU LUC", "DANH MUC", "BIEU MAU", "MAU")

_TITLE_LINE = re.compile(
    r"^[ \t]*(" + "|".join(_NORMATIVE_TITLES + _APPENDIX_TITLES) + r")\b[ \t]*$",
    re.M,
)

_BAN_HANH_KEM = re.compile(r"\(\s*Ban\s*h[àa]nh\s*k[èe]m\s*theo", re.IGNORECASE)

# `(Kèm theo Quyết định số 1866/QĐ-BGDĐT ngày ...)` — mốc mở đầu văn bản con,
# phủ rộng nhất trong bốn tín hiệu (266/460 file). Khớp trên bản bỏ dấu nên
# viết bằng chữ không dấu.
#
# Đòi bằng được chữ "số" rồi tới chữ số, để loại câu trong Điều 1 của chính
# văn bản ban hành: *"Ban hành kèm theo Thông tư NÀY Quy chế..."* — cụm đó
# không có số hiệu, nếu bắt luôn thì file nào cũng bị cắt ngay tại Điều 1.
#
# Giữa hai chữ của tên loại phải cho phép vài ký tự rác: OCR chèn gạch dưới,
# chấm, gạch ngang vào giữa (`Kèm theo Quyết _ định số 738/QĐ-ĐHĐN`). Đòi
# đúng một dấu cách là trượt mất `738/QĐ-ĐHĐN` — văn bản kèm theo cả một bản
# Chiến lược 96 nghìn ký tự.
_W = r"[\s_.·-]{0,3}"

_KEM_THEO = re.compile(
    r"(?:ban\s*hanh\s*)?kem" + _W + r"theo\s+"
    r"(?:quyet" + _W + r"dinh|thong" + _W + r"tu|nghi" + _W + r"dinh"
    r"|nghi" + _W + r"quyet|chi" + _W + r"thi|ke" + _W + r"hoach"
    r"|cong" + _W + r"van|luat)"
    r"\s*s[o0][^\n]{0,25}?\d",
    re.IGNORECASE,
)

# Khối nơi nhận / chữ ký ở cuối mỗi phần. `Nơi nhận:` là mốc ổn định nhất;
# chức danh người ký thì mỗi cơ quan một kiểu.
_KY = re.compile(r"^[ \t]*N[oơ]i\s*nh[aậ]n\s*[:.]", re.M | re.IGNORECASE)

# Điều khoản thi hành: nơi sống của REPLACES / REPEALS / hiệu lực (§5.4).
_THI_HANH_TRIGGERS = (
    "hieu luc thi hanh",
    "co hieu luc",
    "het hieu luc",
    "thay the",
    "bai bo",
    "chiu trach nhiem thi hanh",
    "trach nhiem thi hanh",
)

# Nhãn phần
PART_VAN_BAN = "van_ban"       # văn bản ban hành (Quyết định / Thông tư / Luật)
PART_NOI_DUNG = "noi_dung"     # NormativeContent kèm theo (§2.6)
PART_PHU_LUC = "phu_luc"       # phụ lục / danh mục — §9 nói không đưa vào graph

ZONES = ("header", "can_cu", "than", "ky")


# ============================================================
# CẤU TRÚC KẾT QUẢ
# ============================================================

@dataclass
class Article:
    """Một Điều trong một phần."""

    seq: int
    number: int
    suffix: str
    heading: str
    start: int
    end: int
    is_thi_hanh: bool = False


@dataclass
class Part:
    """Một văn bản con trong file."""

    index: int
    kind: str
    title: str
    marker: str                 # tín hiệu đã xác định ranh giới
    start: int
    end: int
    zones: dict[str, tuple[int, int]] = field(default_factory=dict)
    articles: list[Article] = field(default_factory=list)


# ============================================================
# TÁCH PHẦN
# ============================================================

def _title_line_of(flat: str, match: re.Match) -> tuple[str, bool]:
    """(tiêu đề, có phải phụ lục không) của một dòng IN HOA."""

    title = match.group(1)

    return title, title in _APPENDIX_TITLES


def _dieu_restart_positions(text: str) -> list[int]:
    """
    Vị trí dãy số Điều **đánh lại từ đầu** — dấu hiệu bắt đầu văn bản con.

    Đòi hỏi đúng `Điều 1` rồi tới `Điều 2`, chứ không phải bất kỳ chỗ nào số
    tụt lùi. Nới ra là hỏng ngay: Bộ luật Hình sự (`100/2015/QH13`, 406 điều
    đọc được) có một chỗ chạy `341, 342, 343, 333, 334` do trang scan lộn thứ
    tự — luật thì không bao giờ "ban hành kèm theo" cái gì cả, mà quy tắc lỏng
    vẫn xẻ nó làm đôi.

    Đo trên kho: quy tắc lỏng cho 258 ranh giới, quy tắc này cho 212 — 46 chỗ
    bị loại gần như đều là số Điều bị OCR đọc sai (`1, 2, 3, 4, 3`).
    """

    matches = list(_DIEU.finditer(text))
    numbers = [int(match.group(1)) for match in matches]
    restarts = []

    for index in range(1, len(numbers)):
        if numbers[index] > numbers[index - 1]:
            continue

        if numbers[index] != 1:
            continue

        # `Điều 1` lẻ loi giữa văn bản vẫn có thể là số đọc sai. Điều kế tiếp
        # phải là `Điều 2` thì mới đúng là một dãy mới bắt đầu.
        if index + 1 < len(numbers) and numbers[index + 1] != 2:
            continue

        restarts.append(matches[index].start())

    return restarts


# Loại văn bản có thể "ban hành kèm theo" một nội dung quy phạm (§2.6). Luật,
# Nghị định, Hiến pháp thì không — mọi thứ đứng sau thân của chúng đều là phụ
# lục, dù có bắt gặp `Điều 1` đánh lại (mẫu biểu trong phụ lục hay có).
_CAN_PROMULGATE = frozenset(
    {
        "Quyết định",
        "Thông tư",
        "Thông tư liên tịch",
        "Nghị quyết",
        "Chỉ thị",
        "Văn bản hợp nhất",
    }
)


def can_promulgate(doc_type: str | None) -> bool:
    """Loại văn bản này có thể ban hành kèm `NormativeContent` không?"""

    return doc_type is None or doc_type in _CAN_PROMULGATE


def _demote_extras(parts: list[Part], allow_normative: bool) -> None:
    """
    Hạ các phần thừa xuống `phu_luc`.

    Ba ràng buộc, đều lấy thẳng từ ontology chứ không phải ngưỡng tự nghĩ ra:

    1. **`PROMULGATES` là 1→1 (§4).** Một văn bản ban hành đúng một nội dung
       quy phạm. Phần `noi_dung` thứ hai trở đi không thể đúng — thực tế đó là
       mẫu biểu trong phụ lục, mỗi cái có `Điều 1, 2, 3` riêng
       (`338/QĐ-ĐHBK` bị cắt thành 8 phần vì 6 biểu mẫu như vậy).
    2. **Phụ lục kéo dài tới hết file.** Đã sang địa phận phụ lục thì không
       quay lại nội dung quy phạm được nữa (`6/2021/TT-TTCP`: PHỤ LỤC rồi 13
       biểu mẫu phía sau).
    3. **Loại văn bản không ban hành kèm** thì mọi phần con đều là phụ lục.
    """

    seen_normative = False
    in_appendix = False

    for part in parts[1:]:
        if in_appendix or not allow_normative or seen_normative:
            part.kind = PART_PHU_LUC

        if part.kind == PART_PHU_LUC:
            in_appendix = True
        elif part.kind == PART_NOI_DUNG:
            seen_normative = True


def _merge_appendices(parts: list[Part]) -> list[Part]:
    """Gộp các phần phụ lục liền nhau thành một — §9 không đưa phụ lục vào graph."""

    merged: list[Part] = []

    for part in parts:
        if (
            merged
            and merged[-1].kind == PART_PHU_LUC
            and part.kind == PART_PHU_LUC
        ):
            merged[-1].end = part.end
            continue

        merged.append(part)

    for index, part in enumerate(merged):
        part.index = index

    return merged


# Độ mạnh của từng tín hiệu ranh giới. Hai tín hiệu chỉ vào cùng một chỗ thì
# giữ cái mạnh hơn — cột `marker` trong DB nói cho Bước 4 biết ranh giới đó
# chắc tới đâu.
_MARKER_RANK = {
    "kem-theo+trang": 4,
    "kem-theo+tieu-de": 3,
    "kem-theo": 3,
    "tieu-de+ban-hanh-kem": 3,
    "tieu-de": 2,
    "so-dieu-danh-lai": 1,
}

# Hai tín hiệu cách nhau dưới ngần này ký tự thì coi là cùng một ranh giới.
# Đo trên kho: từ dòng tiêu đề IN HOA xuống tới `Điều 1` của văn bản con xa
# nhất khoảng 2.500 ký tự (tiêu đề -> tên -> (kèm theo) -> Chương I -> Điều 1).
_SAME_BOUNDARY = 2500

# Phần 0 không thể ngắn hơn ngần này: quốc hiệu + số hiệu + trích yếu + khối
# Căn cứ + vài Điều. Tín hiệu nằm trước mốc này thuộc về khối tiêu đề của chính
# văn bản, không phải ranh giới.
_MIN_PART_0 = 1500


def _starts_line(flat: str, position: int) -> bool:
    """
    Cụm này có đứng đầu dòng không (cho phép dấu mở ngoặc)?

    Đây là chỗ phân biệt sống còn giữa **mốc mở đầu văn bản con**:

        (Kèm theo Quyết định số 1866/QĐ-BGDĐT ngày ...)

    với **một trích dẫn giữa câu** trong khối Căn cứ:

        ...về việc ban hành Quy chế kèm theo Quyết định số 2721/QĐ-ĐHĐN ngày...

    Hai cái giống hệt nhau về mặt từ ngữ. Không lọc thì `1001/QĐ-ĐHBK` bị cắt
    ngay tại dòng Căn cứ thứ ba, mất trắng phần đầu văn bản.
    """

    line_start = flat.rfind("\n", 0, position) + 1
    prefix = flat[line_start:position]

    return len(prefix) <= 12 and not prefix.strip(" \t(")


def _anchor_kem_theo(flat: str, position: int) -> tuple[int, str]:
    """
    Lùi từ cụm `Kèm theo Quyết định số ...` lên đầu khối tiêu đề của văn bản con.

    Cụm đó nằm ở giữa khối tiêu đề, không phải đầu:

        ----- [Trang 3] -----          <- ranh giới thật ở đây
        BỘ GIÁO DỤC VÀ ĐÀO TẠO
        KHUNG KIẾN TRÚC DỮ LIỆU ...
        (Kèm theo Quyết định số 1866/QĐ-BGDĐT ngày ...)   <- tìm thấy ở đây

    Mốc phân trang do OCR chèn là thứ neo tốt nhất vì văn bản con gần như luôn
    bắt đầu ở đầu một trang mới. Xa quá 2.500 ký tự thì mốc đó thuộc về trang
    khác — lúc ấy lùi về dòng tiêu đề IN HOA gần nhất, cùng lắm là về đầu dòng.
    """

    page = None

    for match in _PAGE.finditer(flat, 0, position):
        page = match

    if page and position - page.end() <= _SAME_BOUNDARY:
        return page.start(), "kem-theo+trang"

    title = None

    for match in _TITLE_LINE.finditer(flat, max(0, position - 1500), position):
        title = match

    if title:
        return title.start(), "kem-theo+tieu-de"

    return flat.rfind("\n", 0, position) + 1, "kem-theo"


def split_parts(text: str) -> list[Part]:
    """
    Cắt file thành các phần: văn bản ban hành + nội dung kèm theo + phụ lục.

    Bốn tín hiệu, xếp theo độ tin cậy đo được trên kho:

    | Tín hiệu                            | Số file |
    | ----------------------------------- | ------- |
    | `(Kèm theo Quyết định số ...)`      | **266** |
    | dòng tiêu đề IN HOA (`QUY CHẾ`)     | 167     |
    | dãy số Điều đánh lại từ 1           | 163     |

    Cụm `Kèm theo <loại> số <số hiệu>` phủ rộng nhất vì nó không phụ thuộc vào
    việc phần kèm theo tên là gì. Danh sách tiêu đề IN HOA bỏ sót hẳn những
    trường hợp như `738/QĐ-ĐHĐN` (kèm theo một **CHIẾN LƯỢC**) hay
    `1866/QĐ-BGDĐT` (kèm theo một **KHUNG KIẾN TRÚC DỮ LIỆU**) — hai cái này
    còn không có `Điều` nào nên dãy số Điều cũng chịu.

    Phải phân biệt với câu trong Điều 1 của chính văn bản ban hành: *"Ban hành
    kèm theo Thông tư **này** Quy chế..."* — cụm đó không có chữ "số" và không
    có số hiệu đi kèm, nên regex đòi `số <chữ số>` là đủ loại nó ra.
    """

    flat = deaccent(text)
    candidates: list[tuple[int, str, str, str]] = []

    # --- tín hiệu 1: "(Kèm theo <loại> số ...)" ---
    for match in _KEM_THEO.finditer(flat):
        if not _starts_line(flat, match.start()):
            continue

        start, marker = _anchor_kem_theo(flat, match.start())

        # Phụ lục cũng dùng đúng cụm này. Phân biệt bằng dòng tiêu đề nằm giữa
        # mốc neo và cụm "Kèm theo".
        head = flat[start:match.start()]
        appendix = any(
            re.search(rf"^[ \t]*{title}\b", head, re.M) for title in _APPENDIX_TITLES
        )

        candidates.append(
            (
                start,
                PART_PHU_LUC if appendix else PART_NOI_DUNG,
                "",
                marker,
            )
        )

    # --- tín hiệu 2: dòng tiêu đề IN HOA ---
    for match in _TITLE_LINE.finditer(flat):
        title, is_appendix = _title_line_of(flat, match)

        # `(Ban hành kèm theo ...)` thường nằm ngay dưới tiêu đề, cách vài dòng
        # tên văn bản. 400 ký tự đủ rộng cho cả những cái tên dài nhất.
        confirmed = bool(_BAN_HANH_KEM.search(flat, match.end(), match.end() + 400))

        candidates.append(
            (
                match.start(),
                PART_PHU_LUC if is_appendix else PART_NOI_DUNG,
                title,
                "tieu-de+ban-hanh-kem" if confirmed else "tieu-de",
            )
        )

    # --- tín hiệu 3: dãy số Điều đánh lại ---
    for position in _dieu_restart_positions(text):
        candidates.append((position, PART_NOI_DUNG, "", "so-dieu-danh-lai"))

    candidates = _merge_candidates(candidates)

    # --- dựng phần ---
    parts = [
        Part(index=0, kind=PART_VAN_BAN, title="", marker="dau-file", start=0, end=len(text))
    ]

    for start, kind, title, marker in candidates:
        # Phần 0 luôn là chính văn bản đang xét, không bao giờ là nội dung kèm
        # theo. Tín hiệu nằm quá sát đầu file là khối tiêu đề của chính nó —
        # một bản Quy chế scan riêng thì dòng đầu tiên đúng là chữ `QUY CHẾ`.
        # Văn bản ban hành nào cũng cần chỗ cho quốc hiệu, số hiệu, trích yếu
        # và ít nhất một Điều trước khi có thể kèm theo cái gì.
        if start < _MIN_PART_0:
            continue

        parts[-1].end = start
        parts.append(
            Part(
                index=len(parts),
                kind=kind,
                title=title,
                marker=marker,
                start=start,
                end=len(text),
            )
        )

    return parts


def _merge_candidates(
    candidates: list[tuple[int, str, str, str]],
) -> list[tuple[int, str, str, str]]:
    """Gộp các tín hiệu chỉ vào cùng một ranh giới, giữ cái mạnh nhất."""

    merged: list[tuple[int, str, str, str]] = []

    for candidate in sorted(candidates):
        if merged and candidate[0] - merged[-1][0] <= _SAME_BOUNDARY:
            previous = merged[-1]

            if _MARKER_RANK[candidate[3]] > _MARKER_RANK[previous[3]]:
                # Giữ vị trí của cái đứng trước (nó lùi xa hơn về đầu khối tiêu
                # đề) nhưng lấy nhãn và độ tin cậy của cái mạnh hơn.
                merged[-1] = (
                    previous[0],
                    candidate[1],
                    candidate[2] or previous[2],
                    candidate[3],
                )

            continue

        merged.append(candidate)

    return merged


# ============================================================
# CẮT VÙNG TRONG MỘT PHẦN
# ============================================================

def _find_zones(text: str, flat: str, part: Part, articles: list[Article]) -> None:
    """Điền `part.zones`: header / can_cu / than / ky."""

    body_start = articles[0].start if articles else None

    # --- căn cứ ---
    #
    # Chỉ phần 0 mới có khối căn cứ pháp lý. Nội dung kèm theo thì không —
    # nhưng chữ "Căn cứ" vẫn xuất hiện rải rác trong đó ("Căn cứ vào kết quả
    # học tập..."), và nhận nhầm là 26 vùng căn cứ giả, kéo theo Bước 2 gán
    # nhầm `BASED_ON` cho mọi số hiệu nằm gần đó.
    can_cu_start = None

    if part.index == 0:
        match = _CAN_CU.search(flat, part.start, body_start or part.end)

        if match:
            can_cu_start = match.start()

    # --- ký / nơi nhận: tìm SAU điều cuối cùng ---
    ky_start = None
    search_from = articles[-1].start if articles else part.start
    match = _KY.search(flat, search_from, part.end)

    if match:
        ky_start = match.start()

    # --- ráp lại ---
    header_end = can_cu_start or body_start or ky_start or part.end
    part.zones["header"] = (part.start, header_end)

    if can_cu_start is not None:
        part.zones["can_cu"] = (can_cu_start, body_start or ky_start or part.end)

    if body_start is not None:
        part.zones["than"] = (body_start, ky_start or part.end)

    if ky_start is not None:
        part.zones["ky"] = (ky_start, part.end)


def _find_articles(text: str, flat: str, part: Part) -> list[Article]:
    """Danh mục Điều trong một phần, kèm cờ điều khoản thi hành."""

    matches = [
        match
        for match in _DIEU.finditer(text, part.start, part.end)
    ]

    articles: list[Article] = []

    for seq, match in enumerate(matches):
        end = matches[seq + 1].start() if seq + 1 < len(matches) else part.end

        articles.append(
            Article(
                seq=seq,
                number=int(match.group(1)),
                suffix=match.group(2).lower(),
                heading=match.group(3).strip()[:200],
                start=match.start(),
                end=end,
            )
        )

    # Điều khoản thi hành: nơi REPLACES / REPEALS / hiệu lực trú ngụ (§5.4).
    # Xét trên bản bỏ dấu vì các cụm này hay bị OCR làm hỏng dấu.
    for article in articles:
        body = flat[article.start:article.end].lower()
        article.is_thi_hanh = any(
            trigger in body for trigger in _THI_HANH_TRIGGERS
        )

    return articles


def segment(text: str, doc_type: str | None = None) -> list[Part]:
    """
    Cắt toàn bộ file: phần -> vùng -> Điều.

    `doc_type` (lấy từ bảng Document của Bước 0) quyết định file này có thể
    chứa `NormativeContent` kèm theo hay không — xem `_demote_extras`.
    """

    flat = deaccent(text)
    parts = split_parts(text)

    _demote_extras(parts, allow_normative=can_promulgate(doc_type))
    parts = _merge_appendices(parts)

    for part in parts:
        part.articles = _find_articles(text, flat, part)
        _find_zones(text, flat, part, part.articles)

    return parts


def zone_at(parts: list[Part], offset: int) -> tuple[Part | None, str | None, Article | None]:
    """
    Vị trí `offset` nằm ở phần nào, vùng nào, Điều nào?

    Đây là hàm Bước 2 sẽ gọi cho từng trích dẫn tìm được.
    """

    for part in parts:
        if not part.start <= offset < part.end:
            continue

        zone = next(
            (
                name
                for name, (start, end) in part.zones.items()
                if start <= offset < end
            ),
            None,
        )

        article = next(
            (
                item
                for item in part.articles
                if item.start <= offset < item.end
            ),
            None,
        )

        return part, zone, article

    return None, None, None


# ============================================================
# CHẠY BƯỚC 1
# ============================================================

SCHEMA = """
CREATE TABLE IF NOT EXISTS parts (
    doc_key     TEXT,
    part_index  INTEGER,
    kind        TEXT,
    title       TEXT,
    marker      TEXT,
    start       INTEGER,
    end         INTEGER,
    zones       TEXT,          -- JSON {tên vùng: [đầu, cuối]}
    n_articles  INTEGER,
    PRIMARY KEY (doc_key, part_index)
);

CREATE TABLE IF NOT EXISTS articles (
    doc_key     TEXT,
    part_index  INTEGER,
    seq         INTEGER,
    number      INTEGER,
    suffix      TEXT,
    heading     TEXT,
    start       INTEGER,
    end         INTEGER,
    is_thi_hanh INTEGER,
    PRIMARY KEY (doc_key, part_index, seq)
);

CREATE INDEX IF NOT EXISTS idx_articles_doc ON articles(doc_key);
"""


def ensure_schema(session: KGSession) -> None:
    with session._lock:  # noqa: SLF001
        session._conn.executescript(SCHEMA)  # noqa: SLF001
        session._conn.commit()  # noqa: SLF001


def _save(session: KGSession, doc_key: str, parts: list[Part]) -> None:
    """Ghi kết quả cắt vùng của một văn bản. Xoá bản cũ trước để chạy lại được."""

    with session._lock:  # noqa: SLF001
        conn = session._conn  # noqa: SLF001

        conn.execute("DELETE FROM parts WHERE doc_key = ?", (doc_key,))
        conn.execute("DELETE FROM articles WHERE doc_key = ?", (doc_key,))

        for part in parts:
            conn.execute(
                "INSERT INTO parts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    doc_key,
                    part.index,
                    part.kind,
                    part.title,
                    part.marker,
                    part.start,
                    part.end,
                    json.dumps(part.zones, ensure_ascii=False),
                    len(part.articles),
                ),
            )

            for article in part.articles:
                conn.execute(
                    "INSERT INTO articles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        doc_key,
                        part.index,
                        article.seq,
                        article.number,
                        article.suffix,
                        article.heading,
                        article.start,
                        article.end,
                        int(article.is_thi_hanh),
                    ),
                )

        conn.commit()


def run(session: KGSession, limit: int | None = None) -> dict[str, int]:
    """Cắt vùng cho mọi văn bản đã có text. Dừng / chạy tiếp được."""

    ensure_schema(session)

    rows = session.todo("seg", limit=limit)
    rows = [row for row in rows if row["clean_path"]]

    if not rows:
        return {}

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
            session.log("seg", doc_key, "error", str(exc))
            session.update(doc_key, seg_status="failed")
            tally["failed"] += 1
            continue

        parts = segment(text, doc_type=row["doc_type"])
        _save(session, doc_key, parts)

        notes = []
        n_articles = sum(len(part.articles) for part in parts)
        noi_dung = [part for part in parts if part.kind == PART_NOI_DUNG]

        if not n_articles:
            notes.append("khong-tim-thay-dieu-nao")

        if not any("can_cu" in part.zones for part in parts):
            notes.append("khong-tim-thay-can-cu")

        if noi_dung and all(
            part.marker == "so-dieu-danh-lai" for part in noi_dung
        ):
            notes.append("ranh-gioi-suy-tu-so-dieu")

        session.update(
            doc_key,
            seg_status="done",
            seg_note="; ".join(notes),
            n_parts=len(parts),
            n_articles=n_articles,
        )

        tally["done"] += 1
        tally[f"phan:{len(parts)}"] += 1

        if noi_dung:
            tally["co-noi-dung-kem-theo"] += 1

        if notes:
            tally["co-ghi-chu"] += 1

        if index % 100 == 0:
            say(f"    ... {index}/{len(rows)}")

    return dict(tally)


# ============================================================
# XUẤT + BÁO CÁO
# ============================================================

def export(session: KGSession, out_dir: Path | None = None) -> Path:
    """Xuất cấu trúc đã cắt ra JSONL để soi tay và cho Bước 2–4 dùng."""

    out_dir = out_dir or config.KG_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    path = out_dir / "segments.jsonl"

    with session._lock:  # noqa: SLF001
        parts = session._conn.execute(  # noqa: SLF001
            "SELECT * FROM parts ORDER BY doc_key, part_index"
        ).fetchall()
        articles = session._conn.execute(  # noqa: SLF001
            "SELECT * FROM articles ORDER BY doc_key, part_index, seq"
        ).fetchall()

    by_doc: dict[str, list] = defaultdict(list)

    for row in parts:
        by_doc[row["doc_key"]].append(row)

    arts: dict[tuple[str, int], list] = defaultdict(list)

    for row in articles:
        arts[(row["doc_key"], row["part_index"])].append(row)

    with path.open("w", encoding="utf-8") as handle:
        for doc_key, rows in by_doc.items():
            record = {
                "so_hieu_norm": doc_key,
                "parts": [
                    {
                        "index": row["part_index"],
                        "kind": row["kind"],
                        "title": row["title"],
                        "marker": row["marker"],
                        "span": [row["start"], row["end"]],
                        "zones": json.loads(row["zones"]),
                        "articles": [
                            {
                                "number": f"Điều {item['number']}{item['suffix']}",
                                "heading": item["heading"],
                                "span": [item["start"], item["end"]],
                                "thi_hanh": bool(item["is_thi_hanh"]),
                            }
                            for item in arts[(doc_key, row["part_index"])]
                        ],
                    }
                    for row in rows
                ],
            }

            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    say(f"  {len(by_doc):>4} văn bản đã cắt vùng -> {path}")

    return path


def report(session: KGSession) -> str:
    ensure_schema(session)

    with session._lock:  # noqa: SLF001
        conn = session._conn  # noqa: SLF001
        # Node stub không có text nên không cắt vùng được; đếm chúng vào đây
        # là báo cáo sai độ phủ của bước này.
        done = conn.execute(
            "SELECT COUNT(*) AS n FROM docs WHERE seg_status = 'done' "
            "AND clean_path IS NOT NULL"
        ).fetchone()["n"]
        kinds = conn.execute(
            "SELECT kind, COUNT(*) AS n FROM parts GROUP BY kind"
        ).fetchall()
        markers = conn.execute(
            "SELECT marker, COUNT(*) AS n FROM parts "
            "WHERE kind != 'van_ban' GROUP BY marker ORDER BY n DESC"
        ).fetchall()
        n_articles = conn.execute("SELECT COUNT(*) AS n FROM articles").fetchone()["n"]
        n_thi_hanh = conn.execute(
            "SELECT COUNT(*) AS n FROM articles WHERE is_thi_hanh = 1"
        ).fetchone()["n"]
        zones = conn.execute("SELECT zones FROM parts").fetchall()

    if not done:
        return "\nChưa cắt vùng văn bản nào — chạy `python run.py kg segment`.\n"

    have = defaultdict(int)

    for row in zones:
        for name in json.loads(row["zones"]):
            have[name] += 1

    lines = [
        "",
        "=" * 62,
        f"BƯỚC 1 — CẮT VÙNG   ({done} văn bản)",
        "=" * 62,
        "",
        "  Phần đã tách:",
    ]

    labels = {
        PART_VAN_BAN: "văn bản ban hành",
        PART_NOI_DUNG: "nội dung kèm theo (§2.6)",
        PART_PHU_LUC: "phụ lục / danh mục",
    }

    for row in kinds:
        lines.append(f"    {labels.get(row['kind'], row['kind']):<28} {row['n']:>5}")

    if markers:
        lines += ["", "  Ranh giới văn bản con xác định nhờ:"]

        for row in markers:
            lines.append(f"    {row['marker']:<28} {row['n']:>5}")

    lines += ["", "  Vùng tìm được (trên tổng số phần):"]

    for name in ZONES:
        lines.append(f"    {name:<28} {have.get(name, 0):>5}")

    lines += [
        "",
        f"  Điều đã lập danh mục: {n_articles:,}"
        f"   (trong đó {n_thi_hanh:,} là điều khoản thi hành)",
        "",
    ]

    return "\n".join(lines)
