"""
Tiện ích text dùng chung cho cả ba tầng.

Bỏ dấu và khoanh vùng header trang 1 vốn nằm trong `clean/normalize.py`, nhưng
`kg/documents.py` cũng cần đúng hai thứ đó để đọc số hiệu và ngày ban hành. Để
nguyên chỗ cũ thì tầng dựng đồ thị phải import ngược lên tầng làm sạch — mà hai
tầng này không có quan hệ gì với nhau.
"""

from __future__ import annotations

import re
import unicodedata

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
# VÙNG HEADER TRANG 1
# ============================================================

_PAGE_1 = re.compile(r"-----\s*\[Trang\s*1\]\s*-----")
_PAGE_2 = re.compile(r"-----\s*\[Trang\s*2\]\s*-----")
_CAN_CU = re.compile(r"\bCan\s*cu\b", re.IGNORECASE)
_HEADER_MAX_CHARS = 1800


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
