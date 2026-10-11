#!/usr/bin/env python
"""Điểm vào của pipeline. Xem `python run.py --help`.

`python run.py lkg <lệnh>` chuyển tiếp sang legal_knowledge_graph — module
đồ thị gán tay, độc lập hoàn toàn với pipeline tự động ở trên (Neo4j/Gemini
riêng, xem src/legal_knowledge_graph/README.md). Namespace `lkg` tách biệt
vì `kg` đã là subcommand của pipeline tự động (`python run.py kg ...`).

`python run.py bench <tham số>` chạy bộ đo Cypher (src/cypher_benchmark/) trên
graph của legal_knowledge_graph."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "lkg":
        sys.path.insert(0, str(ROOT / "src" / "legal_knowledge_graph"))
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        import run as lkg_run  # noqa: E402  (src/legal_knowledge_graph/run.py)

        raise SystemExit(lkg_run.main())

    if len(sys.argv) > 1 and sys.argv[1] == "bench":
        from cypher_benchmark.runner import main as bench_main  # noqa: E402

        raise SystemExit(bench_main(sys.argv[2:]))

    from vanban.cli import main  # noqa: E402

    raise SystemExit(main())
