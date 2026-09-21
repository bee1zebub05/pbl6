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

from core import build, collision_check, pipeline, validate  # noqa: E402
from core.nlq import eval_gold as nlq_eval_gold  # noqa: E402
from core.nlq import pipeline as nlq_pipeline  # noqa: E402
from core.query import runner as query_runner  # noqa: E402


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
    p_query.add_argument("--source", choices=["samples", "benchmark"], default="samples",
                          help="samples = regression 17 mẫu; benchmark = minh hoạ trên data thật")
    p_query.add_argument("--verbose", action="store_true", help="In vài dòng kết quả mẫu mỗi câu")

    p_collisions = sub.add_parser("check-collisions", help="Báo cáo normalizedNumber bị trùng bởi >=2 file")
    p_collisions.add_argument("--dir", type=Path, default=None, help="Mặc định: legal_knowledge_graph/samples")

    p_all = sub.add_parser("all", help="Chạy trọn: check-collisions -> validate -> build -> sanity (1 lệnh)")
    p_all.add_argument("--dir", type=Path, default=None, help="Mặc định: legal_knowledge_graph/samples")
    p_all.add_argument("--no-wipe", action="store_true", help="Không xoá graph cũ trước khi nạp (mặc định LÀ xoá)")

    p_ask = sub.add_parser("ask", help="NLQ: câu hỏi tự nhiên -> Cypher -> kết quả thô (xem core/nlq/)")
    p_ask.add_argument("question", nargs="?", default=None, help="Câu hỏi tự nhiên (Gemini chọn template hoặc tự sinh Cypher)")
    p_ask.add_argument("--template", help="Chạy thủ công 1 template, bỏ qua Gemini, xem core/nlq/templates.py")
    p_ask.add_argument("--param", action="append", default=[], help="key=value, có thể lặp lại (dùng với --template)")
    p_ask.add_argument("--verbose", action="store_true")

    p_nlq_eval = sub.add_parser("nlq-eval", help="Chạy bộ câu hỏi gold cho NLQ (thật qua Gemini + Neo4j)")
    p_nlq_eval.add_argument("--verbose", action="store_true")

    p_api = sub.add_parser("serve-api", help="Chạy FastAPI cho chat UI (core/api/), xem frontend/")
    p_api.add_argument("--host", default="127.0.0.1")
    p_api.add_argument("--port", type=int, default=8000)
    p_api.add_argument("--reload", action="store_true", help="Tự nạp lại khi sửa code (dev)")

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
        argv = ["--source", args.source]
        if args.verbose:
            argv += ["--verbose"]
        return query_runner.main(argv)

    if args.command == "check-collisions":
        argv = ["--dir", str(args.dir)] if args.dir else []
        return collision_check.main(argv)

    if args.command == "all":
        argv = []
        if args.dir:
            argv += ["--dir", str(args.dir)]
        if args.no_wipe:
            argv += ["--no-wipe"]
        return pipeline.main(argv)

    if args.command == "ask":
        argv = []
        if args.question:
            argv.append(args.question)
        if args.template:
            argv += ["--template", args.template]
        for p in args.param:
            argv += ["--param", p]
        if args.verbose:
            argv += ["--verbose"]
        return nlq_pipeline.main(argv)

    if args.command == "nlq-eval":
        argv = ["--verbose"] if args.verbose else []
        return nlq_eval_gold.main(argv)

    if args.command == "serve-api":
        import uvicorn

        # reload_dirs giới hạn watcher trong module này — mặc định uvicorn sẽ
        # theo dõi cả C:\...\pbl6 (cwd khi chạy qua `python run.py lkg ...` ở
        # gốc repo), tức tự nạp lại kể cả khi sửa file bên src/vanban/.
        uvicorn.run(
            "core.api.app:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            reload_dirs=[str(Path(__file__).resolve().parent)] if args.reload else None,
        )
        return 0

    parser.error(f"lệnh không hợp lệ: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
