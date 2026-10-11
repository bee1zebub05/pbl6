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

from core.ingest import build, build_pipeline, collision_check, validate  # noqa: E402
from core.chat import chat_eval  # noqa: E402
from core.chat import cli as chat_cli  # noqa: E402
from core.graph_query import article_embeddings  # noqa: E402


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

    p_collisions = sub.add_parser("check-collisions", help="Báo cáo normalizedNumber bị trùng bởi >=2 file")
    p_collisions.add_argument("--dir", type=Path, default=None, help="Mặc định: legal_knowledge_graph/samples")

    # Bộ đo Cypher (regression/benchmark/scenarios) đã tách ra src/cypher_benchmark/: `python run.py bench`.
    p_all = sub.add_parser("all", help="Chạy trọn: check-collisions -> validate -> build -> sanity (1 lệnh)")
    p_all.add_argument("--dir", type=Path, default=None, help="Mặc định: legal_knowledge_graph/samples")
    p_all.add_argument("--no-wipe", action="store_true", help="Không xoá graph cũ trước khi nạp (mặc định LÀ xoá)")

    p_ask = sub.add_parser("ask", help="Chatbot: hỏi một câu (xem core/chat/)")
    p_ask.add_argument("question", nargs="?", default=None, help="Câu hỏi tiếng Việt tự nhiên")
    p_ask.add_argument("--template", help="Chạy thủ công 1 template, bỏ qua LLM, xem core/graph_query/templates/")
    p_ask.add_argument("--param", action="append", default=[], help="key=value, có thể lặp lại (dùng với --template)")
    p_ask.add_argument("--verbose", action="store_true")

    p_chat = sub.add_parser("chat", help="Chatbot: hội thoại nhiều lượt trong terminal")
    p_chat.add_argument("--verbose", action="store_true")

    p_templates = sub.add_parser("templates", help="Sinh lại docs/TEMPLATES.md (danh mục template) từ core/graph_query/templates/")
    p_templates.add_argument("--stdout", action="store_true", help="In ra màn hình thay vì ghi file")

    p_chat_eval = sub.add_parser("chat-eval", help="Chạy bộ câu hỏi gold cho chatbot (thật qua Gemini + Neo4j)")
    p_chat_eval.add_argument("--verbose", action="store_true")
    p_chat_eval.add_argument("--with-retrieval", action="store_true",
                             help="Bật luôn retrieval ngữ nghĩa (mặc định tắt để đỡ tốn gấp đôi quota)")

    p_embed = sub.add_parser("embed-articles", help="Backfill embedding cho Article (chạy tay, không nằm trong build/all)")
    p_embed.add_argument("--batch-size", type=int, default=None, help="Số text gộp vào 1 lần gọi API embedding")
    p_embed.add_argument("--read-batch-size", type=int, default=None, help="Số Article đọc mỗi lượt round-trip Neo4j")
    p_embed.add_argument("--dry-run", action="store_true", help="Chỉ đếm số Article còn thiếu embedding, KHÔNG gọi API")
    p_embed.add_argument("--reset", action="store_true",
                         help="Xoá MỌI embedding cũ và dựng lại vector index — dùng khi đổi model / số chiều embedding")
    p_embed.add_argument("--verbose", action="store_true")

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

    if args.command == "check-collisions":
        argv = ["--dir", str(args.dir)] if args.dir else []
        return collision_check.main(argv)

    if args.command == "all":
        argv = []
        if args.dir:
            argv += ["--dir", str(args.dir)]
        if args.no_wipe:
            argv += ["--no-wipe"]
        return build_pipeline.main(argv)

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
        return chat_cli.ask_main(argv)

    if args.command == "chat":
        return chat_cli.chat_main(["--verbose"] if args.verbose else [])

    if args.command == "templates":
        from core.graph_query.templates import catalog_markdown

        text = catalog_markdown()
        if args.stdout:
            print(text)
        else:
            target = Path(__file__).resolve().parent / "docs" / "TEMPLATES.md"
            target.write_text(text, encoding="utf-8")
            print(f"Đã ghi {target}")
        return 0

    if args.command == "chat-eval":
        argv = []
        if args.verbose:
            argv += ["--verbose"]
        if args.with_retrieval:
            argv += ["--with-retrieval"]
        return chat_eval.main(argv)

    if args.command == "embed-articles":
        argv = []
        if args.batch_size is not None:
            argv += ["--batch-size", str(args.batch_size)]
        if args.read_batch_size is not None:
            argv += ["--read-batch-size", str(args.read_batch_size)]
        if args.dry_run:
            argv += ["--dry-run"]
        if args.reset:
            argv += ["--reset"]
        if args.verbose:
            argv += ["--verbose"]
        return article_embeddings.main(argv)

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
