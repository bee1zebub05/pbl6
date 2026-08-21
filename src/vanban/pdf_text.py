"""
Trích xuất text từ PDF bằng PyMuPDF.

Cảnh báo quan trọng: rất nhiều PDF trong kho này CÓ lớp text nhưng lớp đó
HỎNG — văn bản cũ dùng font tiếng Việt đời cũ (VNI/TCVN3) nên khi copy ra
thành ký tự rác:

    "ĐẠI HỌC ĐÀ NẴNG"  ->  "DI HOC  DA NANG"
    "Nghị định số"      ->  "Ngh/ d/nh sO'"

Đo trên mẫu 60 file: 23/24 PDF có lớp text thì lớp đó hỏng. Vì vậy KHÔNG
được tin vào "có text là dùng được" — phải chấm điểm dấu tiếng Việt trước.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pymupdf

# MuPDF hay in cảnh báo syntax ra stderr với PDF scan lỗi -> tắt cho đỡ nhiễu.
pymupdf.TOOLS.mupdf_display_errors(False)

PAGE_MARKER = "\n\n----- [Trang {n}] -----\n\n"

_TRAILING_WS = re.compile(r"[ \t]+\n")
_MANY_BLANKS = re.compile(r"\n{3,}")


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _TRAILING_WS.sub("\n", text)
    text = _MANY_BLANKS.sub("\n\n", text)

    return text.strip()


def extract_pages(source: Path | bytes) -> list[str]:
    """Trả về text của từng trang."""

    if isinstance(source, (bytes, bytearray)):
        doc = pymupdf.open(stream=source, filetype="pdf")
    else:
        doc = pymupdf.open(source)

    try:
        return [_clean(page.get_text()) for page in doc]
    finally:
        doc.close()


def pages_to_text(pages: list[str], with_markers: bool = True) -> str:
    """Ghép text các trang thành một văn bản."""

    if not with_markers:
        return _clean("\n\n".join(pages))

    parts = []

    for index, page in enumerate(pages, start=1):
        if page:
            parts.append(PAGE_MARKER.format(n=index).strip("\n"))
            parts.append(page)

    return _clean("\n\n".join(parts))


# Nguyên âm + phụ âm mang dấu của tiếng Việt.
_VIETNAMESE_CHARS = set(
    "àáảãạăằắẳẵặâầấẩẫậ"
    "èéẻẽẹêềếểễệ"
    "ìíỉĩị"
    "òóỏõọôồốổỗộơờớởỡợ"
    "ùúủũụưừứửữự"
    "ỳýỷỹỵ"
    "đ"
)


def vietnamese_score(text: str, min_letters: int = 200) -> float:
    """
    Tỷ lệ chữ cái có dấu tiếng Việt — thước đo lớp text có lành lặn không.

    Đo thực tế trên kho này:
        text tiếng Việt bình thường  ~0.25
        lớp text hỏng do font cũ     ~0.00 - 0.09

    Trả về -1.0 nếu quá ít chữ để kết luận.
    """

    letters = [c for c in unicodedata.normalize("NFC", text.lower()) if c.isalpha()]

    if len(letters) < min_letters:
        return -1.0

    return sum(c in _VIETNAMESE_CHARS for c in letters) / len(letters)


# Dưới ngưỡng này coi như lớp text hỏng, phải OCR lại.
VI_SCORE_OK = 0.15


def probe(path: Path, sample_pages: int = 5) -> tuple[int, int, float]:
    """
    Đọc nhanh PDF gốc.

    Trả về (số trang, ký tự trung bình mỗi trang, điểm tiếng Việt).
    Dùng để biết PDF là bản scan, bản số lành, hay bản số có lớp text hỏng.
    """

    doc = pymupdf.open(path)

    try:
        total = len(doc)

        if total == 0:
            return 0, 0, -1.0

        n = min(total, sample_pages)
        texts = [doc[i].get_text() for i in range(n)]
        chars = sum(len(t.strip()) for t in texts)

        return total, chars // n, round(vietnamese_score("".join(texts)), 3)
    finally:
        doc.close()


def usable_native_text(path: Path) -> tuple[list[str], float]:
    """
    Lấy lớp text sẵn có của PDF kèm điểm chất lượng.

    Gọi trước khi quyết định có dùng lớp đó thay cho OCR hay không.
    """

    pages = extract_pages(path)

    return pages, vietnamese_score("\n".join(pages))
