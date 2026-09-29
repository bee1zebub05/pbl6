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
from .graph_model import GraphModel, collect


def collect_and_summarize(data_dir: Path) -> GraphModel:
    """Validate + dựng model trong bộ nhớ, in dòng tóm tắt số lượng — dùng
    chung bởi `build` (CLI đơn) và `build_pipeline.main()` (CLI `all`,
    trước đây chép tay lại y hệt khối này)."""

    print(f"Đọc + validate {data_dir} ...")
    model = collect(data_dir)
    print(
        f"  {len(model.documents)} Document thật, {len(model.orgs)} Organization, "
        f"{len(model.topics)} Topic, {len(model.persons)} Person, "
        f"{len(model.normative_contents)} NormativeContent, {len(model.articles)} Article, "
        f"{len(model.citations)} citations."
    )
    return model


def push_and_report(model: GraphModel, wipe: bool) -> dict[str, dict[str, int]]:
    """Nạp vào Neo4j + in báo cáo counters — dùng chung, xem
    collect_and_summarize()."""

    print(f"Nạp vào Neo4j ({config.NEO4J_URI}, database={config.NEO4J_DATABASE}) ...")
    report = push(model, wipe=wipe)
    print("\nKết quả (nodes_created / relationships_created / properties_set):")
    for name, counters in report.items():
        print(
            f"  {name:<28} {counters['nodes_created']:>4} / "
            f"{counters['relationships_created']:>4} / {counters['properties_set']:>5}"
        )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nạp JSON gán tay vào Neo4j (instance riêng)")
    parser.add_argument("--dir", type=Path, default=config.DEFAULT_DATA_DIR)
    parser.add_argument("--wipe", action="store_true", help="Xoá sạch graph trước khi nạp")
    args = parser.parse_args(argv)

    model = collect_and_summarize(args.dir)
    push_and_report(model, wipe=args.wipe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
