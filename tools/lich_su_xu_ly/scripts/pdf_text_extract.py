"""Trich xuat van ban tu PDF co san lop text (khong goi OCR).

Xu ly theo toa do thay vi theo thu tu content-stream, de:
  - Bat duoc so hieu / ngay thang duoc dat de len o trong (chung nam o block rieng).
  - Tach dung vung 2 cot: quoc hieu dau trang, "Noi nhan" / chu ky cuoi trang.
  - Gop cac dong bi ngat giua cau thanh mot doan van hoan chinh.

Dung:
    python project/scripts/pdf_text_extract.py                 # 186 file co lop text
    python project/scripts/pdf_text_extract.py --overwrite
    python project/scripts/pdf_text_extract.py --report        # chi thong ke, khong ghi
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

# --- tham so hinh hoc, don vi point (kho A4 = 595 x 842) ---
LINE_TOL = 3.0        # chenh y toi da de coi hai word la cung mot dong
COL_GAP_MIN = 40.0    # be rong toi thieu cua hanh lang trang giua hai cot
COL_RUN_MIN = 2       # so dong lien tiep toi thieu de coi la vung 2 cot
INDENT_MIN = 8.0      # thut dau dong toi thieu de coi la mo doan moi
PARA_GAP = 1.6        # khoang cach dong > 1.6 x line-height => doan moi
DUP_OVERLAP = 0.6     # ty le chong lan de coi hai word la ban sao (PDF gia-dam)

# Dong mo dau mot don vi cau truc thi khong duoc gop vao doan phia truoc.
STRUCT_RE = re.compile(
    r"^\s*("
    r"(Phần|PHẦN)\s+[IVXLC\d]"
    r"|(Chương|CHƯƠNG)\s+[IVXLC\d]"
    r"|(Mục|MỤC)\s+\d"
    r"|(Điều|ĐIỀU)\s+\d+"
    r"|\d+\s*[.)]"
    r"|[a-zđ]\s*\)"
    r"|[-+•*]\s"
    r"|Kính\s+gửi"
    r"|Nơi\s+nhận"
    r"|Căn\s+cứ\s"
    r"|Xét\s+đề\s+nghị"
    r"|Điều\s+khoản"
    r")",
    re.UNICODE,
)

TERMINAL = '.:;!?…"”)'
PAGENUM_RE = re.compile(r"^\d{1,3}$")


@dataclass
class Line:
    x0: float
    x1: float
    y: float
    h: float
    text: str
    gaps: list[tuple[float, float]] = field(default_factory=list)


def norm(s: str) -> str:
    """Chuan hoa NFC + bo khoang trang la; tieng Viet co the toi o dang NFD."""
    s = unicodedata.normalize("NFC", s)
    s = s.replace(" ", " ").replace("﻿", "")
    return re.sub(r"[ \t]+", " ", s).strip()


def drop_duplicate_words(words: list) -> list:
    """Bo word trung do PDF ve chong hai lan de gia lam chu dam."""
    out = []
    for w in words:
        if out:
            p = out[-1]
            if p[4] == w[4]:
                ov = min(p[2], w[2]) - max(p[0], w[0])
                width = max(w[2] - w[0], 1e-6)
                if ov / width >= DUP_OVERLAP:
                    continue
        out.append(w)
    return out


def build_lines(page) -> list[Line]:
    """Gom word theo toa do thanh dong, kem cac khoang trong ngang trong dong."""
    words = [w for w in page.get_text("words") if w[4].strip()]
    if not words:
        return []
    words.sort(key=lambda w: (round(w[1] / LINE_TOL), w[0]))

    groups, cur, cur_y = [], [], None
    for w in words:
        if cur_y is None:
            cur, cur_y = [w], w[1]
        elif abs(w[1] - cur_y) <= LINE_TOL:
            cur.append(w)
        else:
            groups.append(cur)
            cur, cur_y = [w], w[1]
    if cur:
        groups.append(cur)

    lines = []
    for grp in groups:
        grp.sort(key=lambda w: w[0])
        grp = drop_duplicate_words(grp)
        text = norm(" ".join(w[4] for w in grp))
        if not text:
            continue
        gaps = [
            (a[2], b[0]) for a, b in zip(grp, grp[1:]) if b[0] - a[2] >= COL_GAP_MIN
        ]
        lines.append(
            Line(
                x0=min(w[0] for w in grp),
                x1=max(w[2] for w in grp),
                y=min(w[1] for w in grp),
                h=max(w[3] for w in grp) - min(w[1] for w in grp),
                text=text,
                gaps=gaps,
            )
        )
    lines.sort(key=lambda l: l.y)
    return lines


def split_columns(lines: list[Line]) -> list[list[Line]]:
    """Chia trang thanh cac khoi; khoi 2 cot duoc tach thanh khoi trai roi khoi phai."""
    out: list[list[Line]] = []
    pending: list[Line] = []
    i = 0
    while i < len(lines):
        if lines[i].gaps:
            lo = max(g[0] for g in lines[i].gaps)
            hi = min(g[1] for g in lines[i].gaps)
            j = i + 1
            while j < len(lines) and lines[j].gaps:
                nlo = max(lo, max(g[0] for g in lines[j].gaps))
                nhi = min(hi, min(g[1] for g in lines[j].gaps))
                if nhi - nlo < COL_GAP_MIN:
                    break
                lo, hi, j = nlo, nhi, j + 1
            if j - i >= COL_RUN_MIN:
                if pending:
                    out.append(pending)
                    pending = []
                mid = (lo + hi) / 2
                grp = lines[i:j]
                left = [l for l in grp if l.x0 < mid]
                right = [l for l in grp if l.x0 >= mid]
                if left:
                    out.append(left)
                if right:
                    out.append(right)
                i = j
                continue
        pending.append(lines[i])
        i += 1
    if pending:
        out.append(pending)
    return out


def to_paragraphs(groups: list[list[Line]]) -> list[str]:
    """Gop dong ngat giua cau thanh doan, dua vao thut dau dong + khoang cach dong."""
    paras: list[str] = []
    for lines in groups:
        if not lines:
            continue
        base = Counter(round(l.x0 / 2) * 2 for l in lines).most_common(1)[0][0]
        # Khoi co dung thut dau dong hay khong: quyet dinh co bat heuristic dau cau.
        uses_indent = any(l.x0 - base >= INDENT_MIN for l in lines)
        heights = [l.h for l in lines if l.h > 0]
        lh = sum(heights) / len(heights) if heights else 12.0

        buf, prev = "", None
        for l in lines:
            new_para = (
                prev is None
                or bool(STRUCT_RE.match(l.text))
                or (l.x0 - base) >= INDENT_MIN
                or (l.y - prev.y) > lh * PARA_GAP
                or (
                    not uses_indent
                    and buf
                    and buf[-1] in TERMINAL
                    and l.text[:1].isupper()
                )
            )
            if new_para:
                if buf:
                    paras.append(buf)
                buf = l.text
            else:
                buf = f"{buf} {l.text}"
            prev = l
        if buf:
            paras.append(buf)
        paras.append("")  # ngan cach giua cac khoi / cot
    return paras


def extract(pdf: Path, keep_pagenum: bool = False) -> str:
    doc = pymupdf.open(pdf)
    chunks = []
    for pno, page in enumerate(doc, 1):
        lines = build_lines(page)
        if not keep_pagenum:
            h = page.rect.height
            lines = [
                l
                for l in lines
                if not (PAGENUM_RE.match(l.text) and (l.y < 80 or l.y > h - 80))
            ]
        if not lines:
            continue
        body = "\n".join(to_paragraphs(split_columns(lines))).strip()
        body = re.sub(r"\n{3,}", "\n\n", body)
        chunks.append(f"----- [Trang {pno}] -----\n\n{body}")
    return "\n\n".join(chunks) + "\n"


def has_text_layer(pdf: Path, min_chars: int = 50) -> bool:
    try:
        doc = pymupdf.open(pdf)
    except Exception:
        return False
    return len(doc) > 0 and all(len(p.get_text().strip()) >= min_chars for p in doc)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="data/raw/pdf")
    ap.add_argument("--dst", default="data/clean_data")
    ap.add_argument("--all", action="store_true", help="xu ly ca PDF thieu lop text")
    ap.add_argument("--keep-pagenum", action="store_true")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--report", action="store_true", help="chi thong ke, khong ghi file")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    src, dst = Path(args.src), Path(args.dst)
    if not src.is_dir():
        sys.exit(f"Khong thay thu muc nguon: {src}")

    done = skipped_nolayer = skipped_exists = failed = 0
    chars = 0
    for pdf in sorted(src.rglob("*.pdf")):
        if args.limit and done >= args.limit:
            break
        if not args.all and not has_text_layer(pdf):
            skipped_nolayer += 1
            continue
        out = dst / pdf.relative_to(src).with_suffix(".txt")
        if out.exists() and not args.overwrite and not args.report:
            skipped_exists += 1
            continue
        try:
            text = extract(pdf, args.keep_pagenum)
            if not args.report:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(text, encoding="utf-8")
            done += 1
            chars += len(text)
            print(f"[{done:3d}] {pdf.relative_to(src)}  ({len(text):,} ky tu)")
        except Exception as e:
            failed += 1
            print(f"LOI  {pdf.relative_to(src)}: {type(e).__name__}: {e}", file=sys.stderr)

    print(
        f"\nXong: {done} file"
        + ("" if args.report else f" -> {dst}")
        + f" | {chars:,} ky tu"
        f" | bo qua {skipped_nolayer} (thieu lop text)"
        f" + {skipped_exists} (da co)"
        f" | loi {failed}"
    )


if __name__ == "__main__":
    main()
