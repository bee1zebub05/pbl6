"""
Chuẩn hoá text OCR trước khi đưa qua Gemini hiệu đính.

Kho này có hai lớp lỗi số liệu hoàn toàn khác bản chất, phải xử lý ngược nhau:

**1. Số hiệu + ngày ban hành ở đầu trang 1 — CHỮ VIẾT TAY.**

Biểu mẫu in sẵn `Số:      /QĐ-ĐHĐN` và `ngày ... tháng ... năm 20..`, phần
trống điền tay sau khi in. EasyOCR train trên chữ in nên đọc sai gần hết —
nét viết tay ra ký tự chữ cái:

    Số:234+ /QĐ-ĐHBK  ngày A4 tháng 11    thật: 2347/QĐ-ĐHBK, ngày 14
    Số: 138 IQĐ-ĐHĐN                      thật: 738/QĐ-ĐHĐN
    Số:24S3/QĐ-ĐHĐN   ngày 26 tháng G     thật: 2453/…
    Số:   /9A IQĐ-ĐHĐN ngày /6 tháng 01   thật: 191/QĐ-ĐHĐN, ngày 16

Đo trên 501 văn bản đã OCR: **số hiệu đúng 23,4%, ngày ban hành đúng 36,5%**,
trong khi hậu tố in (`QĐ-ĐHĐN`) đúng 75,2%. Chênh lệch đó chính là ranh giới
giữa phần in và phần viết tay trên cùng một dòng.

Không OCR lại phần này. Crawler đã có sẵn đáp án trong `metadata.csv` cho cả
501 văn bản, nên ghi đè thẳng — chính xác tuyệt đối, chi phí bằng 0.

**2. Trích dẫn văn bản khác trong nội dung — CHỮ IN.**

4.571 lần / 501 văn bản (~9,1 mỗi văn bản), không có đáp án ở đâu cả. Nhưng
chúng lặp lại giữa các văn bản: 193/728 trích dẫn xuất hiện >= 3 lần, cao nhất
`115/2020/NĐ-CP` 79 lần. Nên sửa bằng bỏ phiếu chéo — một biến thể hỏng xuất
hiện 1 lần thua bản đúng xuất hiện 79 lần.

Quy tắc an toàn bắt buộc: **chỉ sửa trích dẫn có ký tự không thể là chữ số.**
`l15/2020/NĐ-CP` sửa được vì `l` không phải chữ số. `15/2020/NĐ-CP` thì KHÔNG
đụng tới — nó có thể là một văn bản khác thật, không có cách nào phân biệt.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field


# ============================================================
# BỎ DẤU GIỮ NGUYÊN ĐỘ DÀI
# ============================================================

def _build_ascii_map() -> dict[int, str]:
    """
    Bảng đổi 1 ký tự có dấu -> 1 ký tự ASCII.

    Bắt buộc 1:1 để `str.translate` không đổi độ dài chuỗi — nhờ vậy vị trí
    tìm được trên bản bỏ dấu dùng thẳng được trên bản gốc, không phải map lại.
    """

    table: dict[int, str] = {}

    for code in range(0x00C0, 0x1EF9 + 1):
        decomposed = unicodedata.normalize("NFD", chr(code))

        if decomposed and decomposed[0].isascii() and decomposed[0].isalpha():
            table[code] = decomposed[0]

    # Đ / đ không tự tách trong NFD nên phải khai riêng. Ð (eth, U+00D0) cũng
    # vậy — OCR hay trả về nó thay cho Đ.
    for char, base in (("Đ", "D"), ("đ", "d"), ("Ð", "D"), ("ð", "d")):
        table[ord(char)] = base

    return table


_ASCII_MAP = _build_ascii_map()


def deaccent(text: str) -> str:
    """Bỏ dấu tiếng Việt, giữ nguyên độ dài chuỗi."""

    return text.translate(_ASCII_MAP)


# ============================================================
# PHẦN 1 — TIÊM SỐ HIỆU / NGÀY TỪ METADATA
# ============================================================

_PAGE_1 = re.compile(r"-----\s*\[Trang\s*1\]\s*-----")
_PAGE_2 = re.compile(r"-----\s*\[Trang\s*2\]\s*-----")

# Phần "Căn cứ ..." cũng viết "ngày 04 tháng 04 năm 1994" — nhưng đó là chữ in
# của văn bản KHÁC được trích dẫn. Ghi đè vào đó là phá dữ liệu, nên vùng
# header phải dừng lại trước nó.
_CAN_CU = re.compile(r"\bCan\s*cu\b", re.IGNORECASE)

_HEADER_MAX_CHARS = 1800

# Neo vào HẬU TỐ (`/QĐ-ĐHBK`) chứ không vào chữ "Số:".
#
# Lý do: "Số" là chữ in nhưng nhỏ, OCR trả về đủ kiểu — `S6:`, `$6:`, `Sô`,
# có file mất hẳn (`J|J`fạ /QD-DHBK`). Neo vào đó thì trượt 66/457 file.
# Hậu tố dài hơn nên đọc ổn định hơn, và nó là mốc duy nhất chắc chắn nằm
# ngay sau con số viết tay.
#
# Chấp nhận cả `QD` lẫn biến thể hỏng (`Q4`, `QÐ`, `PHBK` do Đ -> P).
#
# Dấu `/` là nét sổ mảnh nên OCR trả về `I`, `J`, `l`, `|` hoặc nuốt hẳn —
# `Số: 861 JQĐ-TTg`, `Số: /X99 IQĐ-ĐHBK`, `Sô: 9+3 QĐ-DHDN`. Vì vậy dấu phân
# cách phải để tuỳ chọn, không được bắt buộc là `/`.
_SO_HIEU_SPAN = re.compile(
    r"(?:[S$5]\s*[o0O6]\s*[:.]?)?"        # "Số:" nếu đọc được
    r"[^\n]{0,24}?"                        # phần viết tay bị đọc sai
    r"[/IJl|\\]?\s*"                       # dấu `/` hoặc thứ OCR nhìn ra
    r"[A-Z0-9]{2,6}\s*-\s*[A-Za-z0-9\-]{2,20}",
)

# Dạng ba phần của văn bản cấp bộ / quốc hội: `16/2015/TT-BGDĐT`. Toàn chữ in
# nên thường đã đúng, tiêm vào chỉ để thống nhất định dạng.
_SO_HIEU_3P = re.compile(
    r"(?:[S$5]\s*[o0O6]\s*[:.]?)?"
    r"[^\n]{0,12}?"
    r"/\s*\d{4}\s*/\s*[A-Z0-9]{2,6}(?:\s*-\s*[A-Z0-9\-]{2,20})?",
)

# Chức danh người ký là chữ IN trong thân văn bản, đọc rất ổn định. Dùng nó
# để bắt lỗi của chính metadata: doc 0439 metadata ghi QĐ-ĐHBK trong khi bản
# scan lẫn người ký đều là Đại học Đà Nẵng.
_SIGNER_ORG = (
    ("DHDN", re.compile(r"GIAM\s+DOC\s+DAI\s+HOC\s+DA\s+N", re.IGNORECASE)),
    ("DHBK", re.compile(r"HIEU\s+TRUONG\s+TRUONG\s+DAI\s+HOC\s+BACH", re.IGNORECASE)),
)

# Cả ba chữ mốc đều bị OCR làm hỏng: `tháng` -> `cháng` / `háng`,
# `năm` -> `nàm` / `năr` / `nem`, chữ số năm có khi đứt (`202/`, `20`).
#
# Ô ngày/tháng phải cho phép NHIỀU token: nét viết tay bị tách rời thành
# mấy mảnh rồi chèn cả xuống dòng — `ngay\n§ ( thang 12`, `ngay ) X thang (`,
# `ngay / / thang 5`. Dùng `\S` một token là trượt hết những ca này.
_NGAY_SPAN = re.compile(
    r"ng[aà]y\s*[^\n]{0,8}?\s*[ct]?hang\s*[^\n]{0,8}?\s*n[aăeê][mr]\s*\S{1,6}",
    re.IGNORECASE,
)

_DATE_VN = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")


@dataclass
class HeaderResult:
    """Kết quả tiêm header cho một văn bản."""

    text: str
    so_hieu_fixed: bool = False
    ngay_fixed: bool = False
    notes: list[str] = field(default_factory=list)


def _header_span(text: str) -> tuple[int, int]:
    """Trả về (đầu, cuối) của vùng header trang 1."""

    start = 0
    match = _PAGE_1.search(text)

    if match:
        start = match.end()

    end = len(text)
    match = _PAGE_2.search(text)

    if match:
        end = match.start()

    flat = deaccent(text)
    match = _CAN_CU.search(flat, start, end)

    if match:
        end = match.start()

    return start, min(end, start + _HEADER_MAX_CHARS)


def fix_header(
    text: str,
    so_hieu: str | None,
    ngay_ban_hanh: str | None,
) -> HeaderResult:
    """
    Ghi đè số hiệu và ngày ban hành ở header trang 1 bằng giá trị từ crawler.

    Chỉ đụng vào vùng header. Không tìm thấy chỗ để thay thì bỏ qua và ghi
    chú — thà không sửa còn hơn sửa nhầm vào phần căn cứ pháp lý.
    """

    result = HeaderResult(text=text)
    start, end = _header_span(text)

    if end <= start:
        result.notes.append("khong-tim-thay-header")
        return result

    flat = deaccent(text)

    # --- số hiệu -------------------------------------------------
    if so_hieu:
        pattern = _SO_HIEU_3P if so_hieu.count("/") >= 2 else _SO_HIEU_SPAN
        match = pattern.search(flat, start, end)

        if match:
            result.text = (
                result.text[:match.start()]
                + f"Số: {so_hieu}"
                + result.text[match.end():]
            )
            result.so_hieu_fixed = True

            # Thay đổi độ dài -> mọi vị trí sau đây phải tính lại.
            flat = deaccent(result.text)
            start, end = _header_span(result.text)
        else:
            result.notes.append("khong-tim-thay-so-hieu")

        expected = deaccent(so_hieu).upper()

        # Chỉ soi trong vùng header. Phần "Căn cứ" phía dưới thường dẫn quyết
        # định của Giám đốc ĐHĐN, soi cả thân văn bản là báo động giả hàng loạt.
        head_start, head_end = _header_span(result.text)
        head = deaccent(result.text)[head_start:head_end]

        for org, signer in _SIGNER_ORG:
            other = "DHBK" if org == "DHDN" else "DHDN"

            if other in expected and org not in expected and signer.search(head):
                result.notes.append(f"metadata-nghi-ngo: nguoi-ky-la-{org}")

    # --- ngày ban hành -------------------------------------------
    if ngay_ban_hanh:
        match = _DATE_VN.match(ngay_ban_hanh.strip())

        if not match:
            result.notes.append(f"ngay-khong-doc-duoc: {ngay_ban_hanh!r}")
            return result

        day, month, year = (int(match.group(1)), int(match.group(2)), match.group(3))
        match = _NGAY_SPAN.search(flat, start, end)

        if match:
            result.text = (
                result.text[:match.start()]
                + f"ngày {day:02d} tháng {month:02d} năm {year}"
                + result.text[match.end():]
            )
            result.ngay_fixed = True
        else:
            result.notes.append("khong-tim-thay-ngay")

    return result


# ============================================================
# PHẦN 2 — BỎ PHIẾU CHÉO CHO TRÍCH DẪN
# ============================================================

# Ký tự OCR hay trả về thay cho chữ số. Chỉ gồm những cặp đã thực sự gặp
# trong kho này hoặc là nhầm lẫn mặt chữ kinh điển.
_DIGIT_LOOKALIKE = {
    "O": "0", "o": "0", "Q": "0", "D": "0",
    "I": "1", "l": "1", "i": "1", "|": "1", "!": "1",
    "Z": "2", "z": "2",
    "A": "4",
    "S": "5", "s": "5",
    "G": "6", "b": "6",
    "T": "7", "+": "7", "?": "7",
    "B": "8",
    "g": "9", "q": "9",
}

# "số 115/2020/NĐ-CP" — cho phép chữ số lẫn ký tự OCR nhầm ở phần số và năm.
_CITE = re.compile(
    r"(?P<num>[0-9OoQDIliZzASsGbT+?B|!]{1,4})"
    r"\s*/\s*"
    r"(?P<year>[0-9OoIlZzASsGbTB]{4})"
    r"\s*/\s*"
    r"(?P<kind>[A-ZĐ]{2}[A-ZĐ0-9\-]{0,10})"
)

_MIN_VOTES = 3
_YEAR_RANGE = range(1945, 2036)


def _to_digits(token: str) -> str | None:
    """Đổi token sang chữ số thuần. None nếu có ký tự không quy đổi được."""

    out = []

    for char in token:
        if char.isdigit():
            out.append(char)
        elif char in _DIGIT_LOOKALIKE:
            out.append(_DIGIT_LOOKALIKE[char])
        else:
            return None

    return "".join(out)


def _key(num: str, year: str, kind: str) -> str | None:
    """
    Khoá gom phiếu: bỏ số 0 đứng đầu để `08/2014` và `8/2014` cùng một rổ.

    None nếu không quy đổi được hoặc năm vô lý.
    """

    num_d, year_d = _to_digits(num), _to_digits(year)

    if not num_d or not year_d:
        return None

    if int(year_d) not in _YEAR_RANGE or int(num_d) == 0:
        return None

    return f"{int(num_d)}/{year_d}/{kind}"


class CitationIndex:
    """
    Từ điển trích dẫn dựng từ chính kho văn bản, dùng để bỏ phiếu chéo.

    Chỉ những lần xuất hiện SẠCH (số và năm toàn chữ số) mới được bỏ phiếu.
    Bản hỏng không tự bầu cho mình được, nếu không lỗi sẽ tự củng cố lẫn nhau.
    """

    def __init__(self) -> None:
        self.votes: Counter[str] = Counter()

        # Khoá bỏ số 0 đầu để gom phiếu, nhưng đầu ra phải giữ đúng dạng viết
        # thật — `08/2014/NĐ-CP` là số hiệu hợp lệ, ép về `8/2014` là sai.
        # Nên với mỗi khoá còn đếm riêng các dạng bề mặt đã gặp.
        self.forms: dict[str, Counter[str]] = {}

    def add(self, text: str) -> None:
        for match in _CITE.finditer(text):
            num, year = match.group("num"), match.group("year")

            if not (num.isdigit() and year.isdigit()):
                continue

            key = _key(num, year, match.group("kind"))

            if not key:
                continue

            self.votes[key] += 1
            surface = f"{num}/{year}/{match.group('kind')}"
            self.forms.setdefault(key, Counter())[surface] += 1

    def trusted(self) -> dict[str, int]:
        return {k: v for k, v in self.votes.items() if v >= _MIN_VOTES}

    def surface(self, key: str) -> str:
        """Dạng viết phổ biến nhất của một trích dẫn."""

        forms = self.forms.get(key)

        return forms.most_common(1)[0][0] if forms else key

    def apply(self, text: str) -> tuple[str, list[tuple[str, str]]]:
        """
        Sửa các trích dẫn hỏng trong `text`.

        Trả về (text đã sửa, danh sách (trước, sau)).
        """

        trusted = self.trusted()
        changes: list[tuple[str, str]] = []

        def replace(match: re.Match) -> str:
            num, year = match.group("num"), match.group("year")

            # An toàn: số đã toàn chữ số thì không có cơ sở nào để sửa —
            # 15/2020/NĐ-CP và 115/2020/NĐ-CP là hai văn bản khác nhau.
            if num.isdigit() and year.isdigit():
                return match.group(0)

            key = _key(num, year, match.group("kind"))

            if not key or key not in trusted:
                return match.group(0)

            fixed = self.surface(key)
            changes.append((match.group(0), fixed))

            return fixed

        return _CITE.sub(replace, text), changes


def suspicious_dates(text: str) -> list[str]:
    """
    Tìm ngày tháng bất khả thi còn sót lại (tháng > 12, ngày > 31).

    Chỉ gắn cờ, không tự sửa: `tháng 42` gần như chắc là `tháng 12`, nhưng
    `ngày 34` có thể là 31, 14 hay 24 — đoán bừa còn tệ hơn để nguyên.
    """

    found = []
    flat = deaccent(text)

    for match in re.finditer(
        r"ngay\s*(\d{1,3})\s*thang\s*(\d{1,3})\s*nam\s*(\d{4})",
        flat,
        re.IGNORECASE,
    ):
        day, month = int(match.group(1)), int(match.group(2))

        if not (1 <= month <= 12) or not (1 <= day <= 31):
            found.append(text[match.start():match.end()])

    return found
