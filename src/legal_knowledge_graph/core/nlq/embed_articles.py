"""
Backfill embedding cho Article — CLI riêng, chạy TAY (`python run.py lkg
embed-articles`), KHÔNG nằm trong build/all (tránh đốt quota Gemini mỗi
lần build/test, xem plan "Không tự động hoá embed-articles vào build/all").

Tự resumable, không cần file checkpoint: chỉ chọn Article còn
`embedding IS NULL`, embed rồi SET ngay — dừng giữa chừng (Ctrl+C, hết
quota) rồi chạy lại là tự tiếp tục đúng chỗ, không embed lại node đã xong.

Công thức ghép text đưa vào embed CỐ ĐỊNH một lần, dùng xuyên suốt (kể cả
các lần backfill sau khi có Article mới) để vector không bị lệch phân bố
giữa các đợt embed khác nhau.
"""

from __future__ import annotations

import argparse
import sys
import time

from .. import config
from ..graph_loader import run_batched
from . import execute, gemini_client


def _build_embed_input(heading: str | None, text: str) -> str:
    return f"{heading}\n\n{text}" if heading else text


def _fetch_batch(session_, limit: int) -> list[dict]:
    result = session_.run(
        "MATCH (a:Article) WHERE a.embedding IS NULL "
        "RETURN a.articleId AS articleId, a.heading AS heading, a.text AS text "
        "LIMIT $limit",
        limit=limit,
    )
    return [dict(r) for r in result]


def _embed_one_by_one(rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Lô gọi API bị lỗi -> thử lại từng phần tử riêng lẻ, cô lập Article
    bất thường (VD quá dài) thay vì chặn cả lô. Trả (rows đã embed thành
    công, articleId bị bỏ qua vì lỗi)."""

    ok: list[dict] = []
    skipped: list[str] = []
    for row in rows:
        try:
            vec = gemini_client.call_embed(
                [_build_embed_input(row["heading"], row["text"])],
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=config.NLQ_EMBED_DIMENSIONS,
            )[0]
            ok.append({"articleId": row["articleId"], "embedding": vec})
        except gemini_client.GeminiCallError as exc:
            print(f"      BO QUA {row['articleId']}: {exc}", file=sys.stderr)
            skipped.append(row["articleId"])
    return ok, skipped


def run(read_batch_size: int, api_batch_size: int, dry_run: bool, verbose: bool) -> int:
    with execute.session() as session_:
        if dry_run:
            total = session_.run(
                "MATCH (a:Article) WHERE a.embedding IS NULL RETURN count(*) AS n"
            ).single()["n"]
            print(f"{total} Article còn thiếu embedding (chưa gọi Gemini — đây là --dry-run).")
            return 0

        n_done = 0
        n_skipped = 0
        started = time.time()

        while True:
            rows = _fetch_batch(session_, read_batch_size)
            if not rows:
                break

            for start in range(0, len(rows), api_batch_size):
                chunk = rows[start:start + api_batch_size]
                texts = [_build_embed_input(r["heading"], r["text"]) for r in chunk]
                try:
                    vecs = gemini_client.call_embed(
                        texts, task_type="RETRIEVAL_DOCUMENT",
                        output_dimensionality=config.NLQ_EMBED_DIMENSIONS,
                    )
                    to_write = [
                        {"articleId": r["articleId"], "embedding": v}
                        for r, v in zip(chunk, vecs)
                    ]
                except gemini_client.GeminiCallError as exc:
                    if verbose:
                        print(f"    lo ca lo {len(chunk)} bai, thu lai tung bai rieng: {exc}")
                    to_write, skipped_ids = _embed_one_by_one(chunk)
                    n_skipped += len(skipped_ids)

                if to_write:
                    run_batched(
                        session_,
                        "UNWIND $rows AS row MATCH (a:Article {articleId: row.articleId}) "
                        "SET a.embedding = row.embedding",
                        to_write,
                    )
                n_done += len(to_write)

                if verbose:
                    elapsed = time.time() - started
                    print(f"  da xong {n_done} (bo qua {n_skipped}), {elapsed:.1f}s")

        print(f"\nHoan tat: {n_done} Article da embed, {n_skipped} bi bo qua vi loi.")
        return 0 if n_skipped == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill embedding cho Article (chạy tay, không nằm trong build/all)"
    )
    parser.add_argument("--batch-size", type=int, default=config.NLQ_EMBED_API_BATCH_SIZE,
                         help="Số text gộp vào 1 lần gọi embed_content()")
    parser.add_argument("--read-batch-size", type=int, default=config.NLQ_EMBED_READ_BATCH_SIZE,
                         help="Số Article đọc mỗi lượt round-trip Neo4j")
    parser.add_argument("--dry-run", action="store_true",
                         help="Chỉ đếm số Article còn thiếu embedding, KHÔNG gọi Gemini")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    return run(args.read_batch_size, args.batch_size, args.dry_run, args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
