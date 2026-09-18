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

from .core import config
from .clean import pipeline
from .core.session import Session, list_sessions


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


def cmd_kg_segment(args) -> int:
    """Bước 1 — cắt vùng header / căn cứ / thân / ký + danh mục Điều."""

    from .kg import segment

    session = _open_kg(args)

    if session.total() == 0:
        pipeline.say("[KG] Bảng Document rỗng — chạy `python run.py kg docs` trước.")
        session.close()
        return 1

    pipeline.install_signal_handler()

    pipeline.say(
        "\n[KG/1 CẮT VÙNG] Tách văn bản ban hành / nội dung kèm theo, "
        "định vị Căn cứ và Điều"
    )
    pipeline.say("                Ctrl+C để dừng, chạy lại lệnh này để tiếp.\n")

    tally = segment.run(session, limit=args.limit)

    pipeline.say(f"\n  Lần chạy này: {tally or 'không có gì mới'}")

    if not pipeline.STOP.is_set() and not args.no_export:
        pipeline.say("\n[KG/1 XUẤT]")
        segment.export(session)

    pipeline.say(segment.report(session))

    session.close()

    return 0


def cmd_kg_cite(args) -> int:
    """Bước 2 — trích số hiệu trong thân văn bản, nối vào Document + stub."""

    from .kg import citations

    session = _open_kg(args)

    pipeline.install_signal_handler()
    pipeline.say(
        "\n[KG/2 TRÍCH DẪN] Quét số hiệu, tra vùng chứa, nối vào Document\n"
        "                 Ctrl+C để dừng, chạy lại lệnh này để tiếp.\n"
    )

    tally = citations.run(session, limit=args.limit)

    pipeline.say(f"\n  Lần chạy này: {tally or 'không có gì mới'}")
    pipeline.say(citations.report(session))

    session.close()

    return 0


def cmd_kg_rel(args) -> int:
    """Bước 3 — phân loại quan hệ BASED_ON / REPLACES / AMENDS / REPEALS."""

    from .kg import relations

    session = _open_kg(args)

    pipeline.install_signal_handler()
    pipeline.say("\n[KG/3 QUAN HỆ] Phân loại trích dẫn theo vùng + từ khoá\n")

    if args.again:
        with session._lock:  # noqa: SLF001
            n = session._conn.execute(  # noqa: SLF001
                "UPDATE citations SET relation = NULL, trigger = NULL"
            ).rowcount
            session._conn.commit()  # noqa: SLF001

        pipeline.say(f"  Đã xoá nhãn cũ của {n:,} trích dẫn, phân loại lại.\n")

    tally = relations.run(session, limit=args.limit)

    pipeline.say(f"\n  Lần chạy này: {tally or 'không có gì mới'}")

    if not pipeline.STOP.is_set() and not args.no_export:
        pipeline.say("\n[KG/3 XUẤT]")
        relations.export(session)

    pipeline.say(relations.report(session))

    session.close()

    return 0


def cmd_kg_art(args) -> int:
    """Bước 4 — NormativeContent (§2.6) + Article (§2.7)."""

    from .kg import normative

    session = _open_kg(args)

    pipeline.install_signal_handler()
    pipeline.say("\n[KG/4 NỘI DUNG + ĐIỀU] Dựng NormativeContent và Article\n")

    tally = normative.run(session, limit=args.limit)

    pipeline.say(f"\n  Lần chạy này: {tally or 'không có gì mới'}")

    if not pipeline.STOP.is_set() and not args.no_export:
        pipeline.say("\n[KG/4 XUẤT]")
        normative.export(session)

    pipeline.say(normative.report(session))

    session.close()

    return 0


def cmd_kg_load(args) -> int:
    """Bước 5 — nạp graph vào Neo4j."""

    from .kg import neo4j_load

    pipeline.say("\n[KG/5 NEO4J]")

    out = Path(args.output) if args.output else None
    neo4j_load.write_cypher_files(out)

    if args.cypher_only:
        return 0

    try:
        neo4j_load.load(
            uri=args.uri,
            user=args.user,
            password=args.password,
            out_dir=out,
            wipe=args.wipe,
        )
    except Exception as exc:
        pipeline.say(
            f"\n  Không nạp được vào Neo4j: {str(exc)[:200]}"
            f"\n\n  Cần một Neo4j đang chạy. Nhanh nhất:"
            "\n    docker run -d --name neo4j -p 7474:7474 -p 7687:7687 \\"
            "\n        -e NEO4J_AUTH=neo4j/12345678 neo4j:5"
            "\n\n  Rồi chạy lại: python run.py kg load"
            "\n  Hoặc mở data/kg/schema.cypher + queries.cypher chạy tay trong"
            " Neo4j Browser.\n"
        )

        return 1

    pipeline.say("\n  Xong. Mở http://localhost:7474 và thử data/kg/queries.cypher\n")

    return 0


def cmd_kg_all(args) -> int:
    """Chạy tuần tự Bước 0 -> 4 (không nạp Neo4j)."""

    steps = (
        ("0 DOCS", cmd_kg_docs),
        ("1 SEGMENT", cmd_kg_segment),
        ("2 CITE", cmd_kg_cite),
        ("3 REL", cmd_kg_rel),
        ("4 ART", cmd_kg_art),
    )

    for label, func in steps:
        if pipeline.STOP.is_set():
            pipeline.say(f"\nDừng trước bước {label}. Chạy lại để tiếp.")
            return 130

        pipeline.say(f"\n{'#' * 62}\n# BƯỚC {label}\n{'#' * 62}")

        code = func(args)

        if code:
            return code

    # Bước 0 xuất `documents.jsonl` khi chưa có stub nào (stub do Bước 2 sinh
    # ra). Xuất lại lần cuối để file trên đĩa khớp với DB.
    if not args.no_export:
        pipeline.say(f"\n{'#' * 62}\n# XUẤT LẠI (gồm cả stub của Bước 2)\n{'#' * 62}")
        cmd_kg_export(args)

    return 0


def cmd_kg_status(args) -> int:
    from .kg import citations, documents, normative, relations, segment

    session = _open_kg(args)

    for module in (documents, segment, citations, relations, normative):
        pipeline.say(module.report(session))

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
    from .kg import documents, segment

    session = _open_kg(args)
    out = Path(args.output) if args.output else None

    pipeline.say("\n[KG XUẤT]")
    documents.export(session, out)

    segment.ensure_schema(session)

    if session.counts("seg_status").get("done"):
        segment.export(session, out)

    session.close()

    return 0


def cmd_kg_reset(args) -> int:
    session = _open_kg(args)

    n = session.reset(args.stage, only_failed=not args.all)
    scope = "tất cả" if args.all else "các bản ghi lỗi"

    pipeline.say(f"Đã đặt lại {n} bản ghi ({scope}) ở bước '{args.stage}'.")

    session.close()

    return 0


# ============================================================
# ĐÁNH GIÁ (§6 Ontology)
# ============================================================

def cmd_eval(args) -> int:
    """Khối đánh giá §6 — mọi kết quả ghi ra data/eval/."""

    from .eval import errors as eval_errors
    from .eval import extraction as eval_extraction
    from .eval import runner

    session = _open_kg(args)

    if session.total() == 0:
        pipeline.say("[EVAL] Chưa có graph — chạy `python run.py kg all` trước.")
        session.close()
        return 1

    viec = args.eval_command
    out = Path(args.output) if args.output else config.EVAL_DIR

    try:
        if viec == "all":
            return runner.chay_tat_ca(session, args)

        if viec == "sample":
            pipeline.say("\n[EVAL/6.1] Chọn gold set phân tầng + sinh phiếu gán")
            runner.sample(session, args)

        elif viec == "kappa":
            pipeline.say("\n[EVAL/6.1] Đồng thuận giữa hai người gán")
            eval_extraction.xuat(out, out / "goldset")

        elif viec == "extraction":
            pipeline.say("\n[EVAL/6.2] P/R/F1 từng loại quan hệ")
            eval_extraction.xuat(out, out / "goldset")

        elif viec == "queries":
            pipeline.say("\n[EVAL/6.3] Sinh bộ câu hỏi")
            kq = runner.queries(args)

            if "loi" in kq:
                pipeline.say(f"  {kq['loi']}")
                return 1

        elif viec == "retrieval":
            pipeline.say("\n[EVAL/6.4-6.5] BM25 / KG / Hybrid")
            kq = runner.run_retrieval(args)

            if "loi" in kq:
                pipeline.say(f"  {kq['loi']}")
                return 1

        elif viec == "errors":
            pipeline.say("\n[EVAL/6.6-6.7] Ablation + phân tích lỗi")
            eval_errors.xuat(session, out)

        elif viec == "report":
            path = runner.bao_cao(session, out)
            pipeline.say(f"\n  {path}")

        pipeline.say("")
    finally:
        session.close()

    return 0


def cmd_health(args) -> int:
    from .clean.ocr_client import OCRClient

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

    # ---- đánh giá §6 ----
    p_eval = subparsers.add_parser(
        "eval", help="Khối đánh giá §6 — kết quả ghi ra data/eval/"
    )
    eval_sub = p_eval.add_subparsers(dest="eval_command", required=True)

    viec = {
        "all": "Chạy mọi thứ chạy được + gom BAO_CAO.md",
        "sample": "§6.1 — chọn gold set phân tầng, sinh phiếu gán",
        "kappa": "§6.1 — Cohen's κ giữa hai người gán",
        "extraction": "§6.2 — P/R/F1 từng loại quan hệ",
        "queries": "§6.3 — sinh bộ câu hỏi (tự điền đáp án nhóm metadata)",
        "retrieval": "§6.4–6.5 — chạy BM25 / KG / Hybrid và chấm điểm",
        "errors": "§6.6–6.7 — ablation + phân tích lỗi",
        "report": "Gom số đo đã có thành data/eval/BAO_CAO.md",
    }

    for ten, mo_ta in viec.items():
        sp = eval_sub.add_parser(ten, help=mo_ta)
        sp.add_argument("-o", "--output", help=f"Thư mục đích (mặc định {config.EVAL_DIR})")

        if ten in ("all", "sample"):
            sp.add_argument(
                "--co-mau",
                help="Cỡ ba tầng A,B,C — mặc định 71,30,30 (xem eval/goldset.py)",
            )
            sp.add_argument("--seed", type=int, default=20260827)

        if ten in ("all", "queries"):
            sp.add_argument("--so-cau", type=int, default=45, help="Số câu hỏi")
            sp.add_argument(
                "--lam-lai",
                action="store_true",
                help="Sinh lại bộ câu hỏi, XOÁ đáp án người đã điền",
            )

        sp.set_defaults(func=cmd_eval)

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

    p_kg_seg = kg_sub.add_parser(
        "segment", help="Bước 1 — cắt vùng + danh mục Điều (chạy sau `kg docs`)"
    )
    p_kg_seg.add_argument("--limit", type=int, help="Chỉ xử lý N văn bản (chạy thử)")
    p_kg_seg.add_argument(
        "--no-export", action="store_true", help="Không ghi data/kg/segments.jsonl"
    )
    p_kg_seg.set_defaults(func=cmd_kg_segment)

    p_kg_cite = kg_sub.add_parser(
        "cite", help="Bước 2 — trích số hiệu, nối vào Document, tạo stub"
    )
    p_kg_cite.add_argument("--limit", type=int, help="Chỉ xử lý N văn bản")
    p_kg_cite.set_defaults(func=cmd_kg_cite)

    p_kg_rel = kg_sub.add_parser(
        "rel", help="Bước 3 — phân loại BASED_ON / REPLACES / AMENDS / REPEALS"
    )
    p_kg_rel.add_argument("--limit", type=int, help="Chỉ xử lý N trích dẫn")
    p_kg_rel.add_argument(
        "--again",
        action="store_true",
        help="Xoá nhãn cũ, phân loại lại toàn bộ (dùng khi sửa luật phân loại)",
    )
    p_kg_rel.add_argument(
        "--no-export", action="store_true", help="Không ghi data/kg/relations.jsonl"
    )
    p_kg_rel.set_defaults(func=cmd_kg_rel)

    p_kg_art = kg_sub.add_parser(
        "art", help="Bước 4 — NormativeContent (§2.6) + Article (§2.7)"
    )
    p_kg_art.add_argument("--limit", type=int, help="Chỉ xử lý N văn bản")
    p_kg_art.add_argument("--no-export", action="store_true")
    p_kg_art.set_defaults(func=cmd_kg_art)

    p_kg_load = kg_sub.add_parser("load", help="Bước 5 — nạp graph vào Neo4j")
    p_kg_load.add_argument("--uri", help=f"Mặc định {config.NEO4J_URI}")
    p_kg_load.add_argument("--user", help=f"Mặc định {config.NEO4J_USER}")
    p_kg_load.add_argument("--password", help="Mặc định lấy từ .env")
    p_kg_load.add_argument("-o", "--output", help="Thư mục chứa data/kg/*.jsonl")
    p_kg_load.add_argument(
        "--wipe", action="store_true", help="Xoá sạch graph cũ trước khi nạp"
    )
    p_kg_load.add_argument(
        "--cypher-only",
        action="store_true",
        help="Chỉ sinh schema.cypher + queries.cypher, không kết nối Neo4j",
    )
    p_kg_load.set_defaults(func=cmd_kg_load)

    p_kg_all = kg_sub.add_parser(
        "all", help="Chạy tuần tự Bước 0 -> 4 (không nạp Neo4j)"
    )
    p_kg_all.add_argument("--limit", type=int)
    p_kg_all.add_argument("--corpus")
    p_kg_all.add_argument("--rebuild", action="store_true")
    p_kg_all.add_argument("--no-export", action="store_true")
    p_kg_all.add_argument("--again", action="store_true")
    p_kg_all.add_argument("-o", "--output", help="Thư mục xuất data/kg")
    p_kg_all.set_defaults(func=cmd_kg_all)

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
