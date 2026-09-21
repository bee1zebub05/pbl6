"""
Phát hiện `normalizedNumber` bị trùng bởi >=2 file trong một thư mục dữ
liệu — KHÔNG tự sửa, chỉ báo cáo. Người rà soát tự quyết: trùng THẬT (cùng
một văn bản bị crawl/OCR hai lần) thì kệ (build sẽ tự gộp đúng); 2 văn bản
THẬT KHÁC NHAU dùng chung số hiệu (tổ chức đánh số lại theo năm/phiên họp)
thì phải điền `idOverride` khác nhau ở từng file rồi chạy lại, nếu không
build sẽ gộp NHẦM (xem README §10 mục "Data thật đã nạp").
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import config, normalize


def find_collisions(data_dir: Path) -> dict[str, list[tuple[Path, str]]]:
    """Trả về {normalizedNumber: [(đường_dẫn, title), ...]} chỉ cho các khoá
    có >=2 file. Dùng đúng quy tắc quét như validate_dir() (đệ quy, bỏ qua
    thư mục con bắt đầu bằng "_")."""

    files = sorted(
        p for p in data_dir.rglob("*.json")
        if not any(part.startswith("_") for part in p.relative_to(data_dir).parts)
    )

    groups: dict[str, list[tuple[Path, str]]] = {}
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        doc = data.get("document") or {}
        raw = doc.get("documentNumber")
        if not raw:
            continue
        key = doc.get("idOverride") or normalize.normalize_document_number(raw)
        groups.setdefault(key, []).append((f, doc.get("title", "")))

    return {k: v for k, v in groups.items() if len(v) > 1}


def print_report(data_dir: Path, dup: dict[str, list[tuple[Path, str]]]) -> None:
    if not dup:
        print(f"Không có normalizedNumber nào bị trùng trong {data_dir}.")
        return

    print(f"{len(dup)} normalizedNumber bị trùng ({sum(len(v) for v in dup.values())} file):\n")
    for key, entries in dup.items():
        print(f"--- {key} ---")
        for path, title in entries:
            print(f"   {path.relative_to(data_dir)}")
            print(f"      {title[:100]}")
    print(
        "\nBuild sẽ GỘP các file này thành 1 Document node (file đọc sau cùng theo thứ tự "
        "tên thắng ở property phẳng; quan hệ — topics/articles/citations/signers — của "
        "CẢ các file vẫn được giữ, không mất). Nếu đây là 2+ văn bản THẬT KHÁC NHAU dùng "
        "chung số hiệu, phải điền idOverride khác nhau ở từng file rồi chạy lại validate/build."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Báo cáo normalizedNumber bị trùng bởi >=2 file")
    parser.add_argument("--dir", type=Path, default=config.DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)

    dup = find_collisions(args.dir)
    print_report(args.dir, dup)
    return 1 if dup else 0


if __name__ == "__main__":
    raise SystemExit(main())
