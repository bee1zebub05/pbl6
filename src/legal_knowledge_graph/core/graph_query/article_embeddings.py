"""
Backfill embedding cho Article — CLI riêng, chạy TAY (`python run.py lkg
embed-articles`), KHÔNG nằm trong build/all (tránh đốt quota embedding mỗi
lần build/test). Đổi model / số chiều embedding: chạy với `--reset`.

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

from .. import config, db
from ..llm import embeddings
from . import vector_index
from ..db import run_batched

# Số lượt read-batch LIÊN TIẾP không embed nổi Article nào trước khi dừng:
# bể key cạn quota thì mọi request đều lỗi, chạy tiếp chỉ in BO QUA mãi.
_MAX_CONSECUTIVE_STALLED_BATCHES = 3


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
            vec = embeddings.embed_texts([_build_embed_input(row["heading"], row["text"])], kind="document")[0]
            ok.append({"articleId": row["articleId"], "embedding": vec})
        except embeddings.EmbeddingError as exc:
            print(f"      BO QUA {row['articleId']}: {exc}", file=sys.stderr)
            skipped.append(row["articleId"])
    return ok, skipped


def _check_index(session_, reset: bool) -> bool:
    """Index phải có đúng số chiều của model đang cấu hình — nếu không, vector
    mới không ghi vào index cũ được. -> False nếu phải dừng."""

    if reset:
        removed = vector_index.reset(session_)
        print(f"Đã xoá embedding của {removed} Article và dựng lại vector index {config.EMBED_DIMENSIONS} chiều.")
        return True
    current = vector_index.dimensions(session_)
    if current is None:
        vector_index.ensure(session_)
    elif current != config.EMBED_DIMENSIONS:
        print(f"DUNG: vector index hiện {current} chiều, cấu hình LKG_EMBED_DIMENSIONS={config.EMBED_DIMENSIONS} "
              f"(model {config.EMBED_PROVIDER}/{config.EMBED_MODEL}). Chạy lại với --reset để xoá embedding cũ "
              f"và dựng lại index.", file=sys.stderr)
        return False
    return True


def run(read_batch_size: int, api_batch_size: int, dry_run: bool, verbose: bool, reset: bool = False) -> int:
    with db.session() as session_:
        if not dry_run and not _check_index(session_, reset):
            return 1
        if dry_run:
            total = session_.run(
                "MATCH (a:Article) WHERE a.embedding IS NULL RETURN count(*) AS n"
            ).single()["n"]
            print(f"{total} Article còn thiếu embedding; index hiện {vector_index.dimensions(session_)} chiều, "
                  f"cấu hình {config.EMBED_DIMENSIONS} chiều (--dry-run: không gọi API, không ghi gì).")
            return 0

        n_done = 0
        n_skipped = 0
        started = time.time()
        consecutive_stalled = 0

        while True:
            rows = _fetch_batch(session_, read_batch_size)
            if not rows:
                break
            n_done_before_batch = n_done

            for start in range(0, len(rows), api_batch_size):
                chunk = rows[start:start + api_batch_size]
                texts = [_build_embed_input(r["heading"], r["text"]) for r in chunk]
                try:
                    vecs = embeddings.embed_texts(texts, kind="document")
                    to_write = [
                        {"articleId": r["articleId"], "embedding": v}
                        for r, v in zip(chunk, vecs)
                    ]
                except embeddings.EmbeddingError as exc:
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

            if n_done == n_done_before_batch:
                consecutive_stalled += 1
                if consecutive_stalled >= _MAX_CONSECUTIVE_STALLED_BATCHES:
                    print(
                        f"\nDUNG: {consecutive_stalled} lot lien tiep khong embed "
                        f"duoc Article nao (moi request deu loi) -- kha nang cao be "
                        f"key da het quota hoan toan. Da embed {n_done} Article, "
                        f"phan con lai van thieu embedding -- chay lai lenh nay sau "
                        f"khi quota hoi (resumable, khong mat tien do da co).",
                        file=sys.stderr,
                    )
                    return 1
            else:
                consecutive_stalled = 0

        print(f"\nHoan tat: {n_done} Article da embed, {n_skipped} bi bo qua vi loi.")
        return 0 if n_skipped == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill embedding cho Article (chạy tay, không nằm trong build/all)"
    )
    parser.add_argument("--batch-size", type=int, default=config.EMBED_API_BATCH_SIZE,
                         help="Số text gộp vào 1 lần gọi API embedding")
    parser.add_argument("--read-batch-size", type=int, default=config.EMBED_READ_BATCH_SIZE,
                         help="Số Article đọc mỗi lượt round-trip Neo4j")
    parser.add_argument("--dry-run", action="store_true",
                         help="Chỉ đếm số Article còn thiếu embedding, KHÔNG gọi API")
    parser.add_argument("--reset", action="store_true",
                         help="Xoá MỌI embedding cũ và dựng lại vector index theo LKG_EMBED_DIMENSIONS — "
                              "dùng khi đổi model hoặc số chiều embedding")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    return run(args.read_batch_size, args.batch_size, args.dry_run, args.verbose, args.reset)


if __name__ == "__main__":
    raise SystemExit(main())
