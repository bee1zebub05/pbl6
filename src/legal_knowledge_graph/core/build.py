"""
CLI `build` — nạp JSON đã gán tay vào Neo4j (instance riêng).

Chỉ là lớp mỏng nối `graph_model.collect()` (dựng đồ thị trong bộ nhớ, tự
validate trước) với `graph_loader.push()` (ghi vào Neo4j) rồi in báo cáo.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import config
from .graph_loader import push
from .graph_model import collect


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nạp JSON gán tay vào Neo4j (instance riêng)")
    parser.add_argument("--dir", type=Path, default=config.DEFAULT_DATA_DIR)
    parser.add_argument("--wipe", action="store_true", help="Xoá sạch graph trước khi nạp")
    args = parser.parse_args(argv)

    print(f"Đọc + validate {args.dir} ...")
    model = collect(args.dir)
    print(
        f"  {len(model.documents)} Document thật, {len(model.orgs)} Organization, "
        f"{len(model.topics)} Topic, {len(model.persons)} Person, "
        f"{len(model.normative_contents)} NormativeContent, {len(model.articles)} Article, "
        f"{len(model.citations)} citations."
    )

    print(f"Nạp vào Neo4j ({config.NEO4J_URI}, database={config.NEO4J_DATABASE}) ...")
    report = push(model, wipe=args.wipe)

    print("\nKết quả (nodes_created / relationships_created / properties_set):")
    for name, counters in report.items():
        print(
            f"  {name:<28} {counters['nodes_created']:>4} / "
            f"{counters['relationships_created']:>4} / {counters['properties_set']:>5}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
