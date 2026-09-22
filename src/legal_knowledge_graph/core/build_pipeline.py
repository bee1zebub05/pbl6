"""
CLI `all` — chạy TRỌN một lượt từ thư mục JSON thô tới graph sẵn sàng query,
1 lệnh duy nhất thay vì phải nhớ đúng thứ tự các lệnh con:

  1) collision_check  — báo cáo normalizedNumber bị trùng (CHỈ CẢNH BÁO,
     không chặn — xem lý do trong collision_check.py)
  2) validate + dựng model trong bộ nhớ (graph_model.collect — tự chặn cứng,
     raise SystemExit nếu có file lỗi schema/cross-field)
  3) build vào Neo4j (mặc định --wipe — xoá sạch trước khi nạp, dùng
     --no-wipe nếu muốn nạp chồng/idempotent-update)
  4) sanity — đếm nhanh theo nhãn + theo loại quan hệ, xác nhận graph đọc
     truy vấn được ngay sau khi nạp

Dùng khi có version dữ liệu mới (v2, v3...) hoặc muốn nạp lại từ đầu:

    python run.py all --dir data/clean/json/v2
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import collision_check, config
from .graph_loader import push
from .graph_model import collect
from .nlq import execute


def _sanity(session) -> None:
    labels = session.run(
        "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS total ORDER BY total DESC"
    ).data()
    rels = session.run(
        "MATCH ()-[r]->() RETURN type(r) AS relationType, count(*) AS total ORDER BY total DESC"
    ).data()

    print("  Node theo nhãn:")
    for row in labels:
        print(f"    {row['label']:<20} {row['total']}")
    print("  Cạnh theo loại quan hệ:")
    for row in rels:
        print(f"    {row['relationType']:<20} {row['total']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Chạy trọn: collision-check -> validate -> build -> sanity"
    )
    parser.add_argument("--dir", type=Path, default=config.DEFAULT_DATA_DIR)
    parser.add_argument(
        "--no-wipe", action="store_true",
        help="Không xoá graph cũ trước khi nạp (mặc định LÀ xoá, --wipe)",
    )
    args = parser.parse_args(argv)

    print(f"[1/4] Kiểm tra trùng normalizedNumber trong {args.dir} ...")
    dup = collision_check.find_collisions(args.dir)
    collision_check.print_report(args.dir, dup)

    print(f"\n[2/4] Validate + dựng model từ {args.dir} ...")
    model = collect(args.dir)  # tự raise SystemExit nếu có file không hợp lệ
    print(
        f"  OK — {len(model.documents)} Document thật, {len(model.orgs)} Organization, "
        f"{len(model.topics)} Topic, {len(model.persons)} Person, "
        f"{len(model.normative_contents)} NormativeContent, {len(model.articles)} Article, "
        f"{len(model.citations)} citations."
    )

    print(f"\n[3/4] Nạp vào Neo4j ({config.NEO4J_URI}, database={config.NEO4J_DATABASE}) ...")
    report = push(model, wipe=not args.no_wipe)
    for name, counters in report.items():
        print(
            f"  {name:<28} {counters['nodes_created']:>4} / "
            f"{counters['relationships_created']:>4} / {counters['properties_set']:>5}"
        )

    print("\n[4/4] Sanity check (graph có đọc truy vấn được không) ...")
    with execute.session() as session:
        _sanity(session)

    print("\nSẵn sàng: python run.py query --source samples|benchmark")
    if dup:
        print(f"Lưu ý: {len(dup)} normalizedNumber bị trùng ở bước 1 — xem cảnh báo phía trên.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
