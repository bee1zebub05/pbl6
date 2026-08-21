"""
Chuẩn hoá tên file / phục hồi metadata từ tên file PDF.

Bộ crawler cũ sinh ra 2 dạng tên:

1. Dạng chuẩn:
       0410_5780_QĐ-ĐHBK_Quyết định công bố công khai dự toán....pdf
       -> doc_id = 0410, so_hieu = 5780/QĐ-ĐHBK

2. Dạng hỏng (nằm trong folder "ID", do parse nhầm cả header của bảng):
       ID LĨNH VỰC TÊN VĂN BẢN ... TẢI VỀ 0002 Công tác sinh viên Quy định chế
       độ, chính sách...._TÊN VĂN BẢN_LĨNH VỰC.pdf
       -> vẫn moi được doc_id = 0002 và lĩnh vực = "Công tác sinh viên"
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .config import CATEGORIES

# Lĩnh vực dài trước, ngắn sau -> tránh "Khác" ăn mất "Khảo thí".
_CATEGORIES_BY_LENGTH = sorted(CATEGORIES, key=len, reverse=True)

_BROKEN_PREFIX = re.compile(r"^ID\s+LĨNH VỰC\s+TÊN VĂN BẢN\b.*?TẢI VỀ\s+", re.S)
_BROKEN_SUFFIX = re.compile(r"_TÊN VĂN BẢN_LĨNH VỰC$")

_DOC_ID = re.compile(r"^(\d{3,5})\b")
_INVALID_FS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WS = re.compile(r"\s+")


@dataclass
class DocName:
    """Thông tin moi được từ tên file PDF."""

    doc_id: str
    category: str
    so_hieu: str
    title: str
    stem: str
    broken_name: bool


def sanitize(name: str, max_length: int = 180) -> str:
    """Làm sạch một đoạn text để dùng làm tên file trên Windows/Linux."""

    name = unicodedata.normalize("NFC", str(name)).strip()
    name = _INVALID_FS.sub("_", name)
    name = _WS.sub(" ", name)
    name = name.strip(" .")

    return name[:max_length].strip(" .")


def _split_normal(stem: str) -> tuple[str, str, str]:
    """Tách `<id>_<so_hieu>_<tiêu đề>` -> (doc_id, so_hieu, title)."""

    parts = stem.split("_", 2)

    if len(parts) == 3 and _DOC_ID.match(parts[0]):
        return parts[0], parts[1], parts[2]

    if len(parts) == 2 and _DOC_ID.match(parts[0]):
        return parts[0], parts[1], ""

    return "", "", stem


def parse_pdf_name(pdf_path: Path, pdf_root: Path) -> DocName:
    """Suy ra doc_id / lĩnh vực / số hiệu / tiêu đề từ đường dẫn PDF."""

    stem = unicodedata.normalize("NFC", pdf_path.stem)

    rel_parent = pdf_path.parent.relative_to(pdf_root).as_posix()
    category = rel_parent.split("/")[0] if rel_parent not in (".", "") else "Khác"

    broken = bool(_BROKEN_PREFIX.match(stem))

    if broken:
        # ---- dạng hỏng: gỡ header + footer thừa ----
        stem = _BROKEN_PREFIX.sub("", stem)
        stem = _BROKEN_SUFFIX.sub("", stem).strip()

        match = _DOC_ID.match(stem)
        doc_id = match.group(1) if match else ""

        rest = stem[len(doc_id):].strip() if doc_id else stem

        # Ngay sau doc_id là tên lĩnh vực thật.
        recovered = ""

        for candidate in _CATEGORIES_BY_LENGTH:
            if rest.startswith(candidate):
                recovered = candidate
                rest = rest[len(candidate):].strip()
                break

        category = recovered or "Khác"
        so_hieu = ""
        title = rest

    else:
        doc_id, so_hieu, title = _split_normal(stem)

    doc_id = doc_id.zfill(4) if doc_id.isdigit() else doc_id

    # ---- stem đầu ra: ngắn, ổn định, đọc được ----
    pieces = [p for p in (doc_id, so_hieu) if p]
    prefix = "_".join(pieces)

    short_title = sanitize(title, max_length=90 if prefix else 110)
    out_stem = f"{prefix}_{short_title}" if prefix else short_title
    out_stem = sanitize(out_stem, max_length=120) or pdf_path.stem[:120]

    return DocName(
        doc_id=doc_id,
        category=category,
        so_hieu=so_hieu.replace("_", "/") if so_hieu else "",
        title=title.strip(),
        stem=out_stem,
        broken_name=broken,
    )
