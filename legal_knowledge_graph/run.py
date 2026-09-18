#!/usr/bin/env python
"""
Điểm vào của legal_knowledge_graph — module độc lập, không đụng gì tới src/vanban/.
Xem `python run.py --help`. Chi tiết workflow: legal_knowledge_graph/README.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Console Windows mặc định cp1252/cp1258 sẽ vỡ khi in tiếng Việt.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from core import build, query_runner, validate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="legal_knowledge_graph", description="Gán tay JSON -> Neo4j (module độc lập với src/vanban)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="Validate file JSON theo schema/document.schema.json")
    p_validate.add_argument("--dir", type=Path, default=None, help="Mặc định: legal_knowledge_graph/samples")

    p_build = sub.add_parser("build", help="Nạp JSON đã validate vào Neo4j (instance riêng)")
    p_build.add_argument("--dir", type=Path, default=None, help="Mặc định: legal_knowledge_graph/samples")
    p_build.add_argument("--wipe", action="store_true", help="Xoá sạch graph trước khi nạp")

    p_query = sub.add_parser("query", help="Chạy bộ Cypher test + báo cáo chất lượng/hiệu năng")
    p_query.add_argument("--verbose", action="store_true", help="In vài dòng kết quả mẫu mỗi câu")

    args = parser.parse_args()

    if args.command == "validate":
        argv = ["--dir", str(args.dir)] if args.dir else []
        return validate.main(argv)

    if args.command == "build":
        argv = []
        if args.dir:
            argv += ["--dir", str(args.dir)]
        if args.wipe:
            argv += ["--wipe"]
        return build.main(argv)

    if args.command == "query":
        argv = ["--verbose"] if args.verbose else []
        return query_runner.main(argv)

    parser.error(f"lệnh không hợp lệ: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
