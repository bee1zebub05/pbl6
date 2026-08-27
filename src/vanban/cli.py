"""
Giao diện dòng lệnh.

    python run.py scan                 # quét PDF vào session
    python run.py ocr                  # OCR (dừng/tiếp tục được)
    python run.py fix                  # hiệu đính bằng Gemini
    python run.py all                  # chạy tuần tự cả 3 bước + manifest
    python run.py status               # xem tiến độ
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config, pipeline
from .session import Session, list_sessions


def _force_utf8() -> None:
    """Console Windows mặc định cp1252 -> vỡ khi in tiếng Việt."""

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _open_session(args) -> Session:
    session = Session(args.session)

    if not session.get_meta("pdf_dir"):
        session.set_meta("pdf_dir", str(config.PDF_DIR))

    return session


# ============================================================
# COMMANDS
# ============================================================

def cmd_scan(args) -> int:
    session = _open_session(args)

    pdf_dir = Path(args.pdf_dir) if args.pdf_dir else config.PDF_DIR

    pipeline.say(f"\n[SCAN] Đang quét {pdf_dir} ...")
    added, total = pipeline.scan(session, pdf_dir)

    pipeline.say(
        f"[SCAN] Tìm thấy {total} file PDF, thêm mới {added} vào session "
        f"'{session.name}'."
    )
    pipeline.say(pipeline.report(session))

    session.close()

    return 0


def cmd_ocr(args) -> int:
    session = _open_session(args)

    if session.total() == 0:
        pipeline.say("[OCR] Session rỗng — chạy `scan` trước đã.")
        session.close()
        return 1

    engine = (args.engine or config.OCR_ENGINE).lower()

    pipeline.install_signal_handler()
    pipeline.say(
        f"\n[OCR] Bắt đầu ({'EasyOCR tại máy' if engine == 'local' else 'API'})."
        " Ctrl+C để dừng, chạy lại lệnh này để tiếp tục.\n"
    )

    if engine == "local":
        tally = pipeline.run_ocr_local(
            session,
            limit=args.limit,
            workers=args.workers,
            retry_failed=not args.skip_failed,
        )
    else:
        tally = pipeline.run_ocr(
            session,
            limit=args.limit,
            workers=args.workers,
            retry_failed=not args.skip_failed,
            min_credits=args.min_credits,
        )

    pipeline.say(f"\n[OCR] Kết quả lần chạy này: {tally or 'không có gì'}")
    pipeline.say(pipeline.report(session))

    session.close()

    return 0


def cmd_normalize(args) -> int:
    session = _open_session(args)

    pipeline.say(
        "\n[NORMALIZE] Tiêm số hiệu / ngày ban hành từ metadata và chuẩn hoá "
        "trích dẫn.\n"
    )

    tally = pipeline.run_normalize(session, limit=args.limit)

    if not tally:
        pipeline.say("  Không có văn bản nào cần chuẩn hoá.")
        session.close()

        return 0

    pipeline.say(
        f"\n[NORMALIZE] {tally.get('done', 0)} văn bản"
        f"  |  số hiệu {tally.get('so_hieu', 0)}"
        f"  |  ngày {tally.get('ngay', 0)}"
        f"  |  trích dẫn {tally.get('trich_dan', 0)}"
    )

    if tally.get("can_soi"):
        pipeline.say(
            f"            {tally['can_soi']} văn bản có cờ cần soi tay — "
            "xem cột norm_note (`python run.py review`)."
        )

    session.close()

    return 0


def cmd_review(args) -> int:
    """Liệt kê các văn bản bị gắn cờ trong bước chuẩn hoá."""

    session = _open_session(args)

    with session._lock:  # noqa: SLF001
        rows = session._conn.execute(  # noqa: SLF001
            "SELECT doc_id, so_hieu, norm_note FROM docs "
            "WHERE norm_note IS NOT NULL AND norm_note != '' ORDER BY doc_id"
        ).fetchall()

    if not rows:
        pipeline.say("Không có văn bản nào bị gắn cờ.")
        session.close()

        return 0

    pipeline.say(f"\n{len(rows)} văn bản cần soi tay:\n")

    for row in rows:
        pipeline.say(f"  {row['doc_id']}  {(row['so_hieu'] or ''):24}  {row['norm_note']}")

    session.close()

    return 0


def cmd_fix(args) -> int:
    session = _open_session(args)

    pipeline.install_signal_handler()
    pipeline.say("\n[FIX] Hiệu đính bằng Gemini. Ctrl+C để dừng, chạy lại để tiếp.\n")

    try:
        tally = pipeline.run_fix(
            session,
            limit=args.limit,
            workers=args.workers,
            retry_failed=not args.skip_failed,
        )
    except Exception as exc:
        pipeline.say(f"[FIX] {exc}")
        session.close()
        return 1

    pipeline.say(f"\n[FIX] Kết quả lần chạy này: {tally or 'không có gì'}")
    pipeline.say(pipeline.report(session))

    session.close()

    return 0


def cmd_all(args) -> int:
    session = _open_session(args)

    pipeline.install_signal_handler()

    pipeline.say(f"\n[1/5 SCAN] {config.PDF_DIR}")
    added, total = pipeline.scan(session)
    pipeline.say(f"  {total} PDF, thêm mới {added}.")

    engine = (args.engine or config.OCR_ENGINE).lower()

    pipeline.say(f"\n[2/5 OCR] ({'EasyOCR tại máy' if engine == 'local' else 'API'})")

    if engine == "local":
        pipeline.run_ocr_local(session, limit=args.limit, workers=args.workers)
    else:
        pipeline.run_ocr(
            session,
            limit=args.limit,
            workers=args.workers,
            min_credits=args.min_credits,
        )

    if not pipeline.STOP.is_set() and not args.no_fix:
        pipeline.say("\n[3/4 HIỆU ĐÍNH]")

        try:
            pipeline.run_fix(session, limit=args.limit, workers=args.fix_workers)
        except Exception as exc:
            pipeline.say(f"  Bỏ qua bước hiệu đính: {exc}")

    pipeline.say("\n[4/4 MANIFEST]")
    pipeline.export_manifest(session)

    pipeline.say(pipeline.report(session))

    session.close()

    return 0


def cmd_status(args) -> int:
    sessions = list_sessions()

    if args.session == config.DEFAULT_SESSION and not sessions:
        pipeline.say("Chưa có session nào. Chạy `python run.py scan` trước.")
        return 1

    if args.list:
        pipeline.say("\nCác session hiện có:")

        for path in sessions:
            pipeline.say(f"  - {path.name}")

        pipeline.say("")
        return 0

    session = _open_session(args)
    pipeline.say(pipeline.report(session))
    session.close()

    return 0


def cmd_models(args) -> int:
    """Liệt kê model mà API key hiện tại gọi được."""

    if not config.GEMINI_API_KEY:
        pipeline.say("Chưa có API key Gemini nào trong .env.")
        return 1

    # Danh sách model giống nhau giữa các key -> hỏi key đầu là đủ.
    pipeline.say(
        f"Hỏi bằng key {config.GEMINI_API_KEYS[0][0]} "
        f"(tổng cộng {len(config.GEMINI_API_KEYS)} key trong .env)"
    )

    from google import genai

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    gemma, gemini, khac = [], [], []

    try:
        for model in client.models.list():
            actions = getattr(model, "supported_actions", None) or []

            if actions and "generateContent" not in actions:
                continue

            name = model.name.replace("models/", "")

            if args.all or "gemma" in name.lower():
                (gemma if "gemma" in name.lower() else gemini).append(name)
            elif "gemini" in name.lower():
                khac.append(name)
    except Exception as exc:
        pipeline.say(f"Không lấy được danh sách model: {exc}")
        return 1

    pipeline.say("\nCác model GEMMA key này gọi được:")

    for name in sorted(gemma) or ["  (không có)"]:
        mark = "  <- đang dùng" if name == config.GEMINI_MODEL else ""
        pipeline.say(f"  {name}{mark}")

    if args.all and gemini:
        pipeline.say("\nCác model khác:")

        for name in sorted(gemini):
            pipeline.say(f"  {name}")

    pipeline.say(
        f"\nĐang cấu hình: GEMINI_MODEL={config.GEMINI_MODEL}"
        "\nĐổi model: sửa GEMINI_MODEL trong .env\n"
    )

    return 0


def cmd_plan(args) -> int:
    session = _open_session(args)
    pipeline.say(pipeline.plan(session))
    session.close()

    return 0


def cmd_skip_native(args) -> int:
    session = _open_session(args)

    pipeline.say(
        "\n[SKIP-NATIVE] Trích text trực tiếp cho các PDF vốn đã có lớp text "
        "(không tốn credit OCR)...\n"
    )

    done, rejected = pipeline.skip_native(session)

    pipeline.say(f"\n[SKIP-NATIVE] Đã xử lý {done} file.")

    if rejected:
        pipeline.say(
            f"              {rejected} file bị loại: lớp text hỏng "
            "(font tiếng Việt đời cũ) — vẫn phải OCR."
        )

    pipeline.say(pipeline.plan(session))

    session.close()

    return 0


def cmd_export(args) -> int:
    session = _open_session(args)

    pipeline.say("\n[EXPORT]")
    pipeline.export_manifest(session, Path(args.output) if args.output else None)

    session.close()

    return 0


def cmd_reset(args) -> int:
    session = _open_session(args)

    n = session.reset(args.stage, only_failed=not args.all)
    scope = "tất cả" if args.all else "các file lỗi"

    pipeline.say(f"Đã đặt lại {n} bản ghi ({scope}) ở bước '{args.stage}'.")

    session.close()

    return 0


# ============================================================
# KNOWLEDGE GRAPH (rules/Ontology.md)
# ============================================================

def _open_kg(args):
    from .kg.session import KGSession

    return KGSession(args.session)


def cmd_kg_docs(args) -> int:
    """Bước 0 — chốt bảng Document."""

    from .kg import documents

    session = _open_kg(args)

    if args.rebuild:
        removed = session.clear()
        pipeline.say(f"[KG] Đã xoá {removed} bản ghi cũ, dựng lại từ đầu.")

    pipeline.install_signal_handler()

    corpus = Path(args.corpus) if args.corpus else config.KG_CORPUS_DIR

    pipeline.say("\n[KG/0 THU THẬP] Gom văn bản từ kho text + manifest\n")

    try:
        stats = documents.collect(session, corpus)
    except FileNotFoundError as exc:
        pipeline.say(f"  {exc}")
        session.close()
        return 1

    pipeline.say(
        f"\n  {stats['nhom']} văn bản phân biệt"
        f"  |  thêm mới {stats['them_moi']}"
        f"  |  cập nhật {stats['cap_nhat']}"
    )
    pipeline.say(
        f"  {stats['gop_trung']} nhóm gộp từ nhiều doc_id"
        f"  |  {stats['khong_co_text']} chưa có text hiệu đính"
    )

    pipeline.say("\n[KG/0 SUY DIỄN] Bậc thẩm quyền, hiệu lực, đối chiếu header")
    pipeline.say("               Ctrl+C để dừng, chạy lại lệnh này để tiếp.\n")

    tally = documents.build(session, limit=args.limit)

    pipeline.say(f"\n  Lần chạy này: {tally or 'không có gì mới'}")

    if not pipeline.STOP.is_set() and not args.no_export:
        pipeline.say("\n[KG/0 XUẤT NODE]")
        documents.export(session)

    pipeline.say(documents.report(session))

    session.close()

    return 0


def cmd_kg_status(args) -> int:
    from .kg import documents

    session = _open_kg(args)
    pipeline.say(documents.report(session))
    session.close()

    return 0


def cmd_kg_review(args) -> int:
    """Liệt kê văn bản có ghi chú ở bước dựng bảng Document."""

    session = _open_kg(args)
    rows = session.flagged()

    if not rows:
        pipeline.say("Không có văn bản nào bị gắn cờ.")
        session.close()
        return 0

    keyword = (args.grep or "").lower()

    shown = 0

    pipeline.say("")

    for row in rows:
        if keyword and keyword not in (row["doc_note"] or "").lower():
            continue

        pipeline.say(f"  {(row['so_hieu'] or ''):26}  {row['doc_note']}")
        shown += 1

    pipeline.say(f"\n  {shown}/{len(rows)} văn bản có ghi chú.\n")

    session.close()

    return 0


def cmd_kg_export(args) -> int:
    from .kg import documents

    session = _open_kg(args)

    pipeline.say("\n[KG XUẤT NODE]")
    documents.export(session, Path(args.output) if args.output else None)

    session.close()

    return 0


def cmd_kg_reset(args) -> int:
    session = _open_kg(args)

    n = session.reset(args.stage, only_failed=not args.all)
    scope = "tất cả" if args.all else "các bản ghi lỗi"

    pipeline.say(f"Đã đặt lại {n} bản ghi ({scope}) ở bước '{args.stage}'.")

    session.close()

    return 0


def cmd_health(args) -> int:
    from .ocr_client import OCRClient

    try:
        data = OCRClient().health()
        pipeline.say(f"\nOCR API ({config.OCR_BASE_URL}): {data}")
    except Exception as exc:
        pipeline.say(f"\nOCR API không phản hồi: {exc}")
        return 1

    keys = config.GEMINI_API_KEYS

    if not keys:
        pipeline.say("GEMINI: CHƯA có key nào — tạo .env từ .env.example")
        return 1

    pipeline.say(
        f"GEMINI: {len(keys)} key, model {config.GEMINI_MODEL}, "
        f"{config.GEMINI_WORKERS} luồng"
    )

    from google import genai

    ok = 0

    for label, key in keys:
        masked = f"{key[:6]}…{key[-4:]}"

        try:
            # Phải giữ client trong biến: Client tạm bị đóng ngay khi hết tham
            # chiếu, request đang bay theo đó chết luôn.
            client = genai.Client(api_key=key)
            client.models.generate_content(
                model=config.GEMINI_MODEL, contents="ping"
            )
            pipeline.say(f"  {label:<16} {masked}  OK")
            ok += 1
        except Exception as exc:
            pipeline.say(f"  {label:<16} {masked}  HỎNG: {str(exc)[:90]}")

    pipeline.say(f"  -> {ok}/{len(keys)} key dùng được")

    pipeline.say("")

    return 0


# ============================================================
# PARSER
# ============================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="OCR + hiệu đính văn bản pháp quy (có session, dừng/tiếp tục được)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--session",
        default=config.DEFAULT_SESSION,
        help="Tên session (mặc định: %(default)s)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_scan = subparsers.add_parser("scan", help="Quét thư mục PDF vào session")
    p_scan.add_argument("--pdf-dir", help="Ghi đè thư mục PDF")
    p_scan.set_defaults(func=cmd_scan)

    p_ocr = subparsers.add_parser(
        "ocr", help="Chạy OCR (mặc định: EasyOCR tại máy, miễn phí)"
    )
    p_ocr.add_argument("--limit", type=int, help="Chỉ xử lý N file (để chạy thử)")
    p_ocr.add_argument("--workers", type=int, help="Số luồng song song")
    p_ocr.add_argument(
        "--skip-failed",
        action="store_true",
        help="Bỏ qua các file đã lỗi trước đó",
    )
    p_ocr.add_argument(
        "--engine",
        choices=["local", "api"],
        help=(
            f"local = EasyOCR tại máy, miễn phí (mặc định: {config.OCR_ENGINE}); "
            "api = gọi API OCR, tốn credit"
        ),
    )
    p_ocr.add_argument(
        "--min-credits",
        type=int,
        help=(
            "Chỉ áp dụng cho --engine api: dừng khi credit còn dưới mức này "
            f"(mặc định {config.OCR_MIN_CREDITS}). Đặt 0 để chạy đến cạn."
        ),
    )
    p_ocr.set_defaults(func=cmd_ocr)

    p_norm = subparsers.add_parser(
        "normalize",
        help="Tiêm số hiệu / ngày từ metadata + chuẩn hoá trích dẫn (chạy trước fix)",
    )
    p_norm.add_argument("--limit", type=int, help="Chỉ xử lý N văn bản đầu")
    p_norm.set_defaults(func=cmd_normalize)

    p_review = subparsers.add_parser(
        "review", help="Liệt kê văn bản bị gắn cờ ở bước normalize"
    )
    p_review.set_defaults(func=cmd_review)

    p_fix = subparsers.add_parser("fix", help="Hiệu đính text OCR bằng Gemma/Gemini")
    p_fix.add_argument("--limit", type=int, help="Chỉ xử lý N file")
    p_fix.add_argument("--workers", type=int, help="Số luồng song song")
    p_fix.add_argument("--skip-failed", action="store_true")
    p_fix.set_defaults(func=cmd_fix)

    p_all = subparsers.add_parser("all", help="scan -> ocr -> fix -> manifest")
    p_all.add_argument("--limit", type=int)
    p_all.add_argument("--workers", type=int, help="Luồng cho OCR")
    p_all.add_argument("--fix-workers", type=int, help="Luồng cho Gemini")
    p_all.add_argument("--no-fix", action="store_true", help="Chỉ OCR, bỏ Gemini")
    p_all.add_argument("--engine", choices=["local", "api"])
    p_all.add_argument(
        "--min-credits",
        type=int,
        help=f"Chỉ với --engine api (mặc định {config.OCR_MIN_CREDITS})",
    )
    p_all.set_defaults(func=cmd_all)

    p_status = subparsers.add_parser("status", help="Xem tiến độ")
    p_status.add_argument("--list", action="store_true", help="Liệt kê session")
    p_status.set_defaults(func=cmd_status)

    p_models = subparsers.add_parser(
        "models", help="Liệt kê model Gemma/Gemini mà API key gọi được"
    )
    p_models.add_argument(
        "--all", action="store_true", help="Liệt kê cả model không phải Gemma"
    )
    p_models.set_defaults(func=cmd_models)

    p_plan = subparsers.add_parser(
        "plan", help="Còn bao nhiêu trang, mất bao lâu / tốn bao nhiêu credit"
    )
    p_plan.set_defaults(func=cmd_plan)

    p_skip = subparsers.add_parser(
        "skip-native",
        help="Trích text trực tiếp cho PDF đã có lớp text, không tốn credit",
    )
    p_skip.set_defaults(func=cmd_skip_native)

    p_export = subparsers.add_parser("export", help="Xuất data/manifest.jsonl")
    p_export.add_argument("-o", "--output")
    p_export.set_defaults(func=cmd_export)

    p_reset = subparsers.add_parser("reset", help="Đặt lại một bước để chạy lại")
    p_reset.add_argument("stage", choices=["ocr", "fix"])
    p_reset.add_argument(
        "--all",
        action="store_true",
        help="Đặt lại toàn bộ, không chỉ file lỗi",
    )
    p_reset.set_defaults(func=cmd_reset)

    p_health = subparsers.add_parser("health", help="Kiểm tra API OCR + key Gemini")
    p_health.set_defaults(func=cmd_health)

    # ---- knowledge graph ----
    p_kg = subparsers.add_parser(
        "kg", help="Xây knowledge graph từ text đã hiệu đính (rules/Ontology.md)"
    )
    kg_sub = p_kg.add_subparsers(dest="kg_command", required=True)

    p_kg_docs = kg_sub.add_parser(
        "docs", help="Bước 0 — chốt bảng Document (gộp trùng, suy bậc thẩm quyền)"
    )
    p_kg_docs.add_argument(
        "--corpus",
        help=f"Thư mục text đã hiệu đính (mặc định: {config.KG_CORPUS_DIR})",
    )
    p_kg_docs.add_argument("--limit", type=int, help="Chỉ xử lý N văn bản (chạy thử)")
    p_kg_docs.add_argument(
        "--rebuild",
        action="store_true",
        help="Xoá bảng cũ, dựng lại từ đầu (mất tiến độ mọi bước KG)",
    )
    p_kg_docs.add_argument(
        "--no-export", action="store_true", help="Không ghi data/kg/*.jsonl"
    )
    p_kg_docs.set_defaults(func=cmd_kg_docs)

    p_kg_status = kg_sub.add_parser("status", help="Xem tiến độ xây graph")
    p_kg_status.set_defaults(func=cmd_kg_status)

    p_kg_review = kg_sub.add_parser("review", help="Liệt kê văn bản có ghi chú")
    p_kg_review.add_argument(
        "--grep", help="Chỉ hiện ghi chú chứa từ khoá này (vd: header-lech)"
    )
    p_kg_review.set_defaults(func=cmd_kg_review)

    p_kg_export = kg_sub.add_parser("export", help="Xuất lại data/kg/*.jsonl")
    p_kg_export.add_argument("-o", "--output", help="Thư mục đích")
    p_kg_export.set_defaults(func=cmd_kg_export)

    p_kg_reset = kg_sub.add_parser("reset", help="Đặt lại một bước KG để chạy lại")
    p_kg_reset.add_argument("stage", choices=["doc", "seg", "cite", "rel", "art"])
    p_kg_reset.add_argument(
        "--all", action="store_true", help="Đặt lại toàn bộ, không chỉ bản ghi lỗi"
    )
    p_kg_reset.set_defaults(func=cmd_kg_reset)

    return parser


def main(argv: list[str] | None = None) -> int:
    _force_utf8()
    config.ensure_dirs()

    args = build_parser().parse_args(argv)

    try:
        return args.func(args)
    except KeyboardInterrupt:
        pipeline.say("\nĐã dừng. Chạy lại lệnh cũ để tiếp tục.")
        return 130
