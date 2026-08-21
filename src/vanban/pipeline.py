"""
Điều phối pipeline: quét PDF -> OCR -> hiệu đính bằng Gemini -> xuất manifest.

Mọi giai đoạn đều ghi tiến độ vào session sau từng file, nên có thể Ctrl+C
bất kỳ lúc nào và chạy lại để tiếp tục đúng chỗ đang dở.
"""

from __future__ import annotations

import json
import signal
import threading
import time
import unicodedata
from concurrent.futures import (
    FIRST_COMPLETED,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
    wait,
)
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

from . import config, pdf_text
from .naming import parse_pdf_name, sanitize
from .ocr_client import OCRClient, OCRError
from .session import Session

STOP = threading.Event()
_print_lock = threading.Lock()


def install_signal_handler() -> None:
    """Ctrl+C lần 1: dừng êm sau khi xong file đang chạy. Lần 2: thoát ngay."""

    def handler(signum, frame):
        if STOP.is_set():
            say("\n[!] Ctrl+C lần 2 — thoát ngay.")
            raise KeyboardInterrupt

        STOP.set()
        say(
            "\n[!] Đã nhận Ctrl+C — đang hoàn tất các file dở dang rồi dừng."
            "\n    (Ctrl+C lần nữa để thoát ngay lập tức)"
        )

    signal.signal(signal.SIGINT, handler)


def say(message: str) -> None:
    with _print_lock:
        print(message, flush=True)


# ============================================================
# STAGE 1 — SCAN
# ============================================================

def scan(session: Session, pdf_dir: Path | None = None) -> tuple[int, int]:
    """Quét thư mục PDF và nạp vào session. Trả về (mới thêm, tổng)."""

    pdf_dir = pdf_dir or config.PDF_DIR

    if not pdf_dir.exists():
        raise FileNotFoundError(f"Không tìm thấy thư mục PDF: {pdf_dir}")

    files = sorted(pdf_dir.rglob("*.pdf"))

    # metadata.csv của crawler là nguồn chuẩn cho số hiệu / tên / lĩnh vực;
    # tên file chỉ dùng khi CSV thiếu (số hiệu trong tên file đã bị thay "/"
    # thành "_" nên không tách lại được chính xác).
    meta_by_id = _load_metadata_csv()
    records = []

    for index, path in enumerate(files, start=1):
        if index % 50 == 0:
            say(f"    ... đã đọc {index}/{len(files)} file")

        info = parse_pdf_name(path, pdf_dir)
        meta = meta_by_id.get(info.doc_id, {})

        try:
            pages, chars_per_page, vi_score = pdf_text.probe(path)
        except Exception as exc:
            pages, chars_per_page, vi_score = 0, 0, -1.0
            session.log("scan", path.name, "error", f"Không mở được PDF: {exc}")

        records.append(
            {
                "key": path.relative_to(pdf_dir).as_posix(),
                "doc_id": info.doc_id,
                "category": meta.get("linh_vuc") or info.category,
                "so_hieu": meta.get("so_hieu") or info.so_hieu,
                "title": meta.get("ten_van_ban") or info.title,
                "stem": info.stem,
                "broken_name": info.broken_name,
                "size_bytes": path.stat().st_size,
                "pages": pages,
                "native_chars": chars_per_page,
                "vi_score": vi_score,
            }
        )

    added = session.register(records)
    session.set_meta("pdf_dir", str(pdf_dir))

    return added, len(files)


# ============================================================
# STAGE 2 — OCR
# ============================================================

def _raw_path(row) -> Path:
    return (
        config.TEXT_RAW_DIR
        / sanitize(row["category"] or "Khác", 60)
        / f"{row['stem']}.txt"
    )


def _clean_path(row) -> Path:
    return (
        config.TEXT_CLEAN_DIR
        / sanitize(row["category"] or "Khác", 60)
        / f"{row['stem']}.md"
    )


class CreditGuard:
    """
    Canh credit để dừng lại trước khi tụt xuống dưới mức sàn.

    API tính credit theo TRANG, và mỗi response OCR trả về `remaining_credits`
    thật -> dùng con số đó làm chuẩn, còn số trang của các file đang chạy dở
    thì tạm giữ chỗ (reserve) để không lỡ tay vượt sàn.
    """

    def __init__(self, floor: int, initial: int | None):
        self.floor = floor
        self.start = initial
        self.api_known = initial  # con số API báo về (có độ trễ)
        self.pages_charged = 0  # sổ tự giữ: tổng số trang đã OCR xong
        self.reserved = 0
        self.confirmed = False  # đã nhận được credit thật từ response chưa
        self._lock = threading.Lock()

    def _effective(self) -> int | None:
        """
        Số credit còn lại đáng tin nhất — lấy con số BI QUAN hơn giữa hai nguồn.

        `remaining_credits` trong response bị trễ: đo thực tế một file 10 trang
        chỉ thấy báo trừ 2 credit, nên tin nó là tiêu lố sàn. Sổ tự giữ theo số
        trang thì bám sát thực tế (39 trang đặt chỗ / 37 credit bị trừ).
        """

        if self.start is None:
            return self.api_known

        ledger = self.start - self.pages_charged

        return ledger if self.api_known is None else min(self.api_known, ledger)

    @property
    def known(self) -> int | None:
        return self._effective()

    @property
    def spent(self) -> int:
        current = self._effective()

        if self.start is None or current is None:
            return self.pages_charged

        return max(0, self.start - current)

    def reserve(self, pages: int, probe: bool = False) -> bool:
        """
        Giữ chỗ cho một file. False = sẽ chạm sàn, đừng chạy nữa.

        `probe=True` cho phép chạy một file duy nhất khi con số khởi điểm chưa
        được xác nhận — không có nó, một ước lượng quá thấp (ví dụ sau khi nạp
        thêm credit mà session còn nhớ số cũ) sẽ chặn đứng mọi file và pipeline
        không bao giờ biết được credit thật.
        """

        with self._lock:
            current = self._effective()

            if current is None:  # chưa biết gì -> cứ chạy, sẽ biết sau
                self.reserved += pages
                return True

            if not self.confirmed and self.reserved == 0 and probe:
                self.reserved += pages
                return True

            if current - self.reserved - pages < self.floor:
                return False

            self.reserved += pages

            return True

    def settle(self, pages: int, remaining: int | None, charged: bool = True) -> None:
        """
        Trả chỗ đã giữ và ghi sổ.

        `charged=False` khi OCR thất bại — quan sát thực tế cho thấy request
        hỏng không bị trừ credit.
        """

        with self._lock:
            self.reserved = max(0, self.reserved - pages)

            if charged:
                self.pages_charged += pages

            if remaining is not None:
                self.api_known = remaining
                self.confirmed = True

    def snapshot(self) -> tuple[int | None, int]:
        with self._lock:
            return self._effective(), self.spent


def _initial_credits(session: Session, client: OCRClient) -> int | None:
    """
    Ước lượng credit lúc bắt đầu — lấy con số THẤP hơn giữa hai nguồn.

    Hai nguồn không khớp nhau: `/v1/admin/key-status` chỉ báo số dư của key 0
    trong khi server xoay vòng nhiều key, còn `remaining_credits` trong response
    OCR mới là số của key thật sự phục vụ mình. Lấy số thấp hơn để không lỡ
    tiêu quá sàn; nếu ước lượng thấp hơn thực tế thì file "probe" đầu tiên sẽ
    tự đính chính lại ngay.
    """

    live = client.credits()
    stored = session.get_meta("remaining_credits")

    candidates = [value for value in (live, stored) if value is not None]

    return min(candidates) if candidates else None


def _ocr_one(
    session: Session,
    client: OCRClient,
    row,
    pdf_dir: Path,
    guard: CreditGuard | None = None,
    pages_reserved: int = 0,
) -> str:
    key = row["key"]
    pdf_path = pdf_dir / key

    session.bump_attempt(key, "ocr")
    started = time.time()

    def on_retry(attempt: int, error: str) -> None:
        say(f"    [retry {attempt}] {row['stem'][:50]} — {error[:120]}")
        session.log("ocr", key, "warn", error)

    status = "done"
    pages: list[str] = []
    remaining: int | None = None
    charged = False

    try:
        try:
            content, data = client.ocr_pdf(pdf_path, on_retry=on_retry)
            charged = True  # OCR chạy được -> credit đã bị trừ
            pages = pdf_text.extract_pages(content)

            if config.OCR_KEEP_PDF:
                target = config.OCR_PDF_DIR / sanitize(row["category"] or "Khác", 60)
                target.mkdir(parents=True, exist_ok=True)
                (target / f"{row['stem']}.pdf").write_bytes(content)

            remaining = data.get("remaining_credits")

            if remaining is not None:
                session.set_meta("remaining_credits", remaining)

        finally:
            # Trả chỗ đã giữ dù thành công hay thất bại, nếu không bộ canh
            # credit sẽ tưởng còn file đang chạy và dừng sớm.
            if guard is not None:
                guard.settle(pages_reserved, remaining, charged=charged)

    except Exception as exc:
        session.log("ocr", key, "error", str(exc))

        # Cứu vãn: dùng lớp text sẵn có của PDF — nhưng CHỈ khi lớp đó lành.
        # Phần lớn PDF cũ ở đây dùng font tiếng Việt đời cũ, copy ra là chữ
        # rác; ghi đại vào sẽ tệ hơn là để trạng thái failed.
        try:
            pages, vi_score = pdf_text.usable_native_text(pdf_path)
        except Exception:
            pages, vi_score = [], -1.0

        if sum(len(p) for p in pages) > 100 and vi_score >= pdf_text.VI_SCORE_OK:
            status = "fallback"
            say(
                f"    [fallback] {row['stem'][:50]} — dùng lớp text sẵn có "
                f"(điểm tiếng Việt {vi_score:.2f})"
            )
        else:
            if pages:
                say(
                    f"    [failed] {row['stem'][:50]} — lớp text sẵn có không "
                    f"dùng được (điểm tiếng Việt {vi_score:.2f}), cần OCR lại"
                )

            session.update(
                key,
                ocr_status="failed",
                ocr_error=str(exc)[:1000],
                ocr_seconds=round(time.time() - started, 1),
            )
            return "failed"

    text = pdf_text.pages_to_text(pages)
    out_path = _raw_path(row)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")

    session.update(
        key,
        ocr_status=status,
        ocr_engine="api",
        ocr_error=None,
        ocr_seconds=round(time.time() - started, 1),
        raw_txt=str(out_path.relative_to(config.ROOT).as_posix()),
        raw_chars=len(text),
    )

    return status


def run_ocr(
    session: Session,
    limit: int | None = None,
    workers: int | None = None,
    retry_failed: bool = True,
    min_credits: int | None = None,
) -> dict[str, int]:
    pdf_dir = Path(session.get_meta("pdf_dir") or config.PDF_DIR)
    todo = session.todo_ocr(limit=limit, retry_failed=retry_failed)

    if not todo:
        say("  Không còn file nào cần OCR.")
        return {}

    workers = workers or config.OCR_WORKERS
    floor = config.OCR_MIN_CREDITS if min_credits is None else min_credits
    client = OCRClient()

    guard = CreditGuard(floor, _initial_credits(session, client))
    start_credits = guard.known

    say(f"  {len(todo)} file cần OCR, {workers} luồng song song.")

    if start_credits is None:
        say(f"  Chưa biết credit hiện có — sẽ cập nhật sau file đầu tiên.\n")
    else:
        say(
            f"  Credit hiện có: {start_credits:,} — dừng khi còn dưới {floor:,}"
            f" (~{max(0, start_credits - floor):,} trang xử lý được).\n"
        )

    tally: dict[str, int] = {}
    done = 0
    hit_floor = False
    started = time.time()

    queue = list(todo)

    def take_next():
        """
        Lấy file kế tiếp còn vừa hạn mức credit.

        Không dừng ngay khi file đầu hàng đợi quá lớn — dò tiếp xem còn file
        nhỏ nào vừa không, để vét nốt phần credit lẻ trước khi dừng.
        """

        for position, candidate in enumerate(queue):
            need = max(1, candidate["pages"] or 1)

            if guard.reserve(need):
                return queue.pop(position), need

        # Chưa xác nhận được credit thật -> chạy thử file ÍT TRANG NHẤT để biết
        # con số chính xác, tốn ít nhất có thể.
        if not guard.confirmed and queue:
            position = min(
                range(len(queue)), key=lambda i: max(1, queue[i]["pages"] or 1)
            )
            need = max(1, queue[position]["pages"] or 1)

            if guard.reserve(need, probe=True):
                say(f"    [dò] chạy thử 1 file {need} trang để biết credit thật")
                return queue.pop(position), need

        return None, 0

    # Nạp file dần theo hạn mức thay vì đẩy hết vào pool một lúc: có vậy mới
    # kiểm tra được credit trước MỖI file, dựa trên số credit thật vừa nhận về.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        running: dict = {}

        while True:
            while len(running) < workers and queue and not STOP.is_set():
                row, pages = take_next()

                if row is None:
                    hit_floor = True
                    break

                running[
                    pool.submit(_ocr_one, session, client, row, pdf_dir, guard, pages)
                ] = row

            if not running:
                break

            finished, _ = wait(list(running), return_when=FIRST_COMPLETED)

            for future in finished:
                row = running.pop(future)
                done += 1

                try:
                    status = future.result()
                except Exception as exc:
                    status = "failed"
                    session.update(row["key"], ocr_status="failed", ocr_error=str(exc))

                tally[status] = tally.get(status, 0) + 1

                icon = {"done": "OK ", "fallback": "FB ", "failed": "ERR"}.get(
                    status, "?  "
                )
                rate = done / max(time.time() - started, 1) * 60
                left, _ = guard.snapshot()
                credit_note = f" | còn {left:,} credit" if left is not None else ""

                say(
                    f"  [{done}/{len(todo)}] {icon} ({rate:.1f} file/phút"
                    f"{credit_note}) {row['stem'][:60]}"
                )

    remaining, spent = guard.snapshot()

    if spent:
        say(f"\n  Đã tiêu {spent:,} credit trong lần chạy này.")

    if hit_floor:
        session.set_meta("stopped_reason", "credit")
        say(
            f"\n  >> DỪNG VÌ CHẠM SÀN CREDIT (còn {remaining:,}, sàn {floor:,}).\n"
            f"     Còn {len(queue)} file chưa OCR — session đã nhớ.\n"
            f"     Nạp thêm credit rồi chạy lại:  python run.py ocr"
        )
    elif not queue and not STOP.is_set():
        session.set_meta("stopped_reason", "xong")

    return tally


# ============================================================
# STAGE 2b — OCR NỘI BỘ (EasyOCR, CPU, miễn phí)
# ============================================================

def run_ocr_local(
    session: Session,
    limit: int | None = None,
    workers: int | None = None,
    retry_failed: bool = True,
) -> dict[str, int]:
    """
    OCR bằng EasyOCR ngay trên máy — không tốn credit, không giới hạn.

    Song song ở mức TRANG chứ không phải mức file: văn bản dài nhất trong kho
    có 155 trang, nếu giao trọn cho một tiến trình thì Ctrl+C sẽ mất cả nửa
    tiếng công. Chia theo trang thì lúc dừng chỉ mất vài trang đang dở, mà
    thanh tiến độ cũng chạy đều thay vì đứng im hàng chục phút.
    """

    from . import ocr_local

    problem = ocr_local.check_ready()

    if problem:
        say(f"  {problem}")
        return {}

    pdf_dir = Path(session.get_meta("pdf_dir") or config.PDF_DIR)
    todo = session.todo_ocr(limit=limit, retry_failed=retry_failed)

    if not todo:
        say("  Không còn file nào cần OCR.")
        return {}

    pool_kwargs = ocr_local.worker_kwargs()

    if workers:
        pool_kwargs["max_workers"] = workers

    total_pages = sum(max(1, row["pages"] or 1) for row in todo)

    say(
        f"  {len(todo)} file / {total_pages:,} trang, "
        f"{pool_kwargs['max_workers']} tiến trình x {config.LOCAL_OCR_THREADS} luồng, "
        f"{config.LOCAL_OCR_DPI} DPI."
    )
    say("  Lần đầu chạy sẽ mất ~1 phút nạp model (và tải model nếu chưa có).\n")

    tally: dict[str, int] = {}
    pages_done = 0
    started = time.time()

    with ProcessPoolExecutor(**pool_kwargs) as pool:
        for index, row in enumerate(todo, start=1):
            if STOP.is_set():
                break

            key = row["key"]
            pdf_path = pdf_dir / key
            session.bump_attempt(key, "ocr")
            doc_started = time.time()

            try:
                jobs = ocr_local.page_jobs(pdf_path, max(1, row["pages"] or 1))
                results = dict(pool.map(ocr_local.ocr_page, jobs))
                pages = [results.get(i, "") for i in range(len(jobs))]

            except BrokenProcessPool:
                # Một tiến trình con chết (hết RAM, lỗi native...) là pool hỏng
                # vĩnh viễn. Dừng hẳn thay vì để 272 file lần lượt báo lỗi.
                session.log("ocr", key, "error", "BrokenProcessPool")
                session.update(key, ocr_status="pending", ocr_engine=None)
                say(
                    f"\n  >> POOL HỎNG ở file {row['stem'][:45]}."
                    "\n     Thường là hết RAM — giảm LOCAL_OCR_WORKERS trong .env"
                    " rồi chạy lại."
                    "\n     Session vẫn nhớ chỗ đang dở, không mất gì."
                )
                break

            except Exception as exc:
                session.log("ocr", key, "error", str(exc))
                session.update(
                    key,
                    ocr_status="failed",
                    ocr_engine="local",
                    ocr_error=str(exc)[:1000],
                    ocr_seconds=round(time.time() - doc_started, 1),
                )
                tally["failed"] = tally.get("failed", 0) + 1
                say(f"  [{index}/{len(todo)}] ERR {row['stem'][:60]} — {exc}")
                continue

            text = pdf_text.pages_to_text(pages)
            out_path = _raw_path(row)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text, encoding="utf-8")

            status = "done" if len(text.strip()) > 50 else "failed"

            session.update(
                key,
                ocr_status=status,
                ocr_engine="local",
                ocr_error=None if status == "done" else "OCR ra quá ít chữ",
                ocr_seconds=round(time.time() - doc_started, 1),
                raw_txt=str(out_path.relative_to(config.ROOT).as_posix()),
                raw_chars=len(text),
            )

            tally[status] = tally.get(status, 0) + 1
            pages_done += len(jobs)

            rate = pages_done / max(time.time() - started, 1) * 3600
            left = (total_pages - pages_done) / max(rate, 1)

            say(
                f"  [{index}/{len(todo)}] {'OK ' if status == 'done' else 'ERR'} "
                f"{len(jobs):>3} trang {time.time() - doc_started:5.0f}s "
                f"({rate:.0f} trang/giờ, còn ~{left:.1f}h) {row['stem'][:45]}"
            )

    if not STOP.is_set() and not session.todo_ocr(limit=1):
        session.set_meta("stopped_reason", "xong")

    return tally


# ============================================================
# STAGE 3 — HIỆU ĐÍNH BẰNG GEMINI
# ============================================================

FRONT_MATTER = """\
---
doc_id: "{doc_id}"
so_hieu: "{so_hieu}"
linh_vuc: "{category}"
ten_van_ban: "{title}"
so_trang: {pages}
nguon_pdf: "{key}"
ocr_status: "{ocr_status}"
hieu_dinh: "{model}"
khoi_da_sua: "{ok}/{total}"
---

"""


def _fix_one(session: Session, corrector, row) -> str:
    from .key_pool import NoKeyAvailable

    key = row["key"]
    raw_file = config.ROOT / row["raw_txt"]

    session.bump_attempt(key, "fix")
    started = time.time()

    if not raw_file.exists():
        session.update(key, fix_status="failed", fix_error="Thiếu file text thô")
        return "failed"

    text = raw_file.read_text(encoding="utf-8")

    if len(text.strip()) < 50:
        session.update(key, fix_status="skipped", fix_error="Text quá ngắn")
        return "skipped"

    def on_retry(attempt: int, error: str) -> None:
        say(f"    [retry {attempt}] {row['stem'][:50]} — {error[:120]}")
        session.log("fix", key, "warn", error)

    meta = {
        "title": row["title"],
        "so_hieu": row["so_hieu"],
        "category": row["category"],
    }

    try:
        fixed, ok, total = corrector.fix_document(text, meta, on_retry=on_retry)
    except NoKeyAvailable:
        # Hết sạch key — để run_fix dừng cả mẻ, đừng đánh dấu file là hỏng.
        raise
    except Exception as exc:
        session.log("fix", key, "error", str(exc))
        session.update(
            key,
            fix_status="failed",
            fix_error=str(exc)[:1000],
            fix_seconds=round(time.time() - started, 1),
        )
        return "failed"

    header = FRONT_MATTER.format(
        doc_id=row["doc_id"],
        so_hieu=row["so_hieu"],
        category=row["category"],
        title=(row["title"] or "").replace('"', "'"),
        pages=row["pages"] or 0,
        key=key,
        ocr_status=row["ocr_status"],
        model=corrector.model,
        ok=ok,
        total=total,
    )

    out_path = _clean_path(row)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(header + fixed, encoding="utf-8")

    status = "done" if ok == total else "failed" if ok == 0 else "done"

    session.update(
        key,
        fix_status=status,
        fix_error=None if ok == total else f"{total - ok}/{total} khối không sửa được",
        fix_seconds=round(time.time() - started, 1),
        clean_md=str(out_path.relative_to(config.ROOT).as_posix()),
        clean_chars=len(fixed),
    )

    return status


def run_fix(
    session: Session,
    limit: int | None = None,
    workers: int | None = None,
    retry_failed: bool = True,
) -> dict[str, int]:
    from .gemini_fix import GeminiCorrector
    from .key_pool import KeyPool, NoKeyAvailable

    todo = session.todo_fix(limit=limit, retry_failed=retry_failed)

    if not todo:
        say("  Không còn file nào cần hiệu đính.")
        return {}

    # Một bể key dùng chung cho mọi luồng: request được trải đều lên tất cả
    # các key, key nào chạm giới hạn thì tự bị bỏ qua trong lúc nghỉ.
    keypool = KeyPool()
    corrector = GeminiCorrector(pool=keypool)

    workers = workers or config.GEMINI_WORKERS

    say(
        f"  {len(todo)} file cần hiệu đính bằng {corrector.model}, "
        f"{len(keypool)} API key, {workers} luồng song song.\n"
    )

    tally: dict[str, int] = {}
    done = 0
    started = time.time()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}

        for row in todo:
            if STOP.is_set():
                break
            futures[pool.submit(_fix_one, session, corrector, row)] = row

        for future in as_completed(futures):
            row = futures[future]
            done += 1

            try:
                status = future.result()
            except NoKeyAvailable as exc:
                # Trả file về "pending" chứ không phải "failed": không sửa
                # được là tại hết key, không phải tại file.
                status = "failed"
                session.update(row["key"], fix_status="pending", fix_error=str(exc))

                if not STOP.is_set():
                    say(f"\n  >> DỪNG: {exc}")
                    say("     Thêm key vào .env rồi chạy lại: python run.py fix\n")
                    STOP.set()
            except Exception as exc:
                status = "failed"
                session.update(row["key"], fix_status="failed", fix_error=str(exc))

            tally[status] = tally.get(status, 0) + 1

            icon = {"done": "OK ", "skipped": "SKP", "failed": "ERR"}.get(status, "?  ")
            rate = done / max(time.time() - started, 1) * 60

            say(
                f"  [{done}/{len(futures)}] {icon} "
                f"({rate:.1f} file/phút) {row['stem'][:70]}"
            )

    say(f"\n  Key: {keypool.summary()}")

    return tally


# ============================================================
# STAGE 4 — MANIFEST
# ============================================================

def export_manifest(session: Session, path: Path | None = None) -> Path:
    """Gộp trạng thái + metadata thành một file JSONL cho bước xây graph."""

    path = path or config.MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    extra = _load_metadata_csv()
    written = 0

    with path.open("w", encoding="utf-8") as handle:
        for row in session.all_docs():
            record = {
                "doc_id": row["doc_id"],
                "so_hieu": row["so_hieu"],
                "ten_van_ban": row["title"],
                "linh_vuc": row["category"],
                "so_trang": row["pages"],
                "pdf": f"data/raw/pdf/{row['key']}",
                "text_raw": row["raw_txt"],
                "text_clean": row["clean_md"],
                "ocr_status": row["ocr_status"],
                "ocr_engine": row["ocr_engine"],
                "fix_status": row["fix_status"],
                "raw_chars": row["raw_chars"],
                "clean_chars": row["clean_chars"],
                "ten_file_hong": bool(row["broken_name"]),
            }

            record.update(extra.get(row["doc_id"], {}))

            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1

    say(f"  Đã ghi {written} bản ghi -> {path}")

    return path


def _load_metadata_csv() -> dict[str, dict]:
    """Đọc metadata.csv của crawler, đánh khoá theo doc_id."""

    if not config.METADATA_CSV.exists():
        return {}

    import csv

    result: dict[str, dict] = {}

    with config.METADATA_CSV.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            doc_id = (row.get("id") or "").strip()

            if not doc_id.isdigit():
                continue

            result[doc_id.zfill(4)] = {
                "so_hieu": (row.get("so_hieu") or "").strip(),
                "ten_van_ban": (row.get("ten_van_ban") or "").strip(),
                "linh_vuc": (row.get("linh_vuc") or "").strip(),
                "ngay_ban_hanh": row.get("ngay_ban_hanh", ""),
                "ngay_hieu_luc": row.get("ngay_hieu_luc", ""),
                "co_quan_ban_hanh": row.get("co_quan_ban_hanh", ""),
                "loai_van_ban": row.get("loai", ""),
                "tinh_trang": row.get("tinh_trang", ""),
                "pdf_url": row.get("pdf_url", ""),
            }

    return result


# ============================================================
# DỰ TOÁN CREDIT
# ============================================================

def plan(session: Session) -> str:
    """
    Ước lượng credit OCR cần dùng.

    API tính credit THEO TRANG chứ không theo file (đo thực tế: OCR 4 file /
    29 trang -> trừ 31 credit). Với ~11.400 trang thì phải canh credit.
    """

    with session._lock:  # noqa: SLF001 - đọc gộp cho nhanh
        rows = session._conn.execute(  # noqa: SLF001
            """
            SELECT ocr_status,
                   COUNT(*)      AS files,
                   SUM(pages)    AS pages
            FROM docs GROUP BY ocr_status
            """
        ).fetchall()

        # Chỉ những file có lớp text LÀNH mới bỏ OCR được.
        native = session._conn.execute(  # noqa: SLF001
            "SELECT COUNT(*) AS files, SUM(pages) AS pages FROM docs "
            "WHERE ocr_status IN ('pending', 'failed') "
            "AND native_chars >= ? AND vi_score >= ?",
            (config.NATIVE_TEXT_THRESHOLD, pdf_text.VI_SCORE_OK),
        ).fetchone()

        broken = session._conn.execute(  # noqa: SLF001
            "SELECT COUNT(*) AS files FROM docs "
            "WHERE native_chars >= ? AND vi_score BETWEEN 0 AND ?",
            (config.NATIVE_TEXT_THRESHOLD, pdf_text.VI_SCORE_OK),
        ).fetchone()

    credits = _initial_credits(session, OCRClient())

    lines = ["", "=" * 62, "DỰ TOÁN OCR", "=" * 62, ""]

    todo_pages = 0

    for row in rows:
        lines.append(
            f"  {row['ocr_status']:<12} {row['files']:>5} file "
            f"{row['pages'] or 0:>7} trang"
        )

        if row["ocr_status"] in ("pending", "failed"):
            todo_pages += row["pages"] or 0

    # 360 trang/giờ — nhịp DUY TRÌ đo trên một lần chạy thật (87 trang liên
    # tục). Benchmark ngắn cho 431 nhưng đó là pool đã ấm, không sát thực tế.
    hours = todo_pages / 360

    lines += [
        "",
        f"  Cần OCR: ~{todo_pages:,} trang",
        "",
        f"  [local] EasyOCR tại máy: ~{hours:.0f} giờ, 0 credit  <- mặc định",
        f"          python run.py ocr",
        "",
        "  [api]   Gọi API: nhanh hơn nhưng tính credit theo TRANG",
    ]

    lines += [
        "",
        f"  Bỏ OCR được (lớp text lành): {native['files'] or 0} file "
        f"(~{native['pages'] or 0:,} trang)  ->  python run.py skip-native",
        f"  Lớp text HỎNG, buộc phải OCR: {broken['files'] or 0} file "
        "(font tiếng Việt đời cũ)",
    ]

    if credits is not None:
        savable = native["pages"] or 0
        floor = config.OCR_MIN_CREDITS
        usable = max(0, credits - floor)

        lines += [
            "",
            f"  Credit còn: {credits:,}   (sàn dừng: {floor:,})",
            f"  Đợt này chạy được ~{usable:,} trang rồi tự dừng.",
        ]

        if credits < todo_pages - savable:
            lines += [
                "",
                f"  !! Credit KHÔNG ĐỦ (thiếu ~{todo_pages - savable - credits:,}).",
                "     Dùng engine local là xong, khỏi cần credit.",
            ]
        else:
            lines.append("  -> Đủ credit cho toàn bộ phần còn lại.")

    lines += ["", "=" * 62, ""]

    return "\n".join(lines)


def skip_native(session: Session) -> tuple[int, int]:
    """
    Trích text trực tiếp cho các PDF có lớp text LÀNH, không tốn credit OCR.

    Trả về (số file xử lý được, số file bị loại vì lớp text hỏng).
    """

    pdf_dir = Path(session.get_meta("pdf_dir") or config.PDF_DIR)

    with session._lock:  # noqa: SLF001
        rows = session._conn.execute(  # noqa: SLF001
            "SELECT * FROM docs WHERE ocr_status IN ('pending', 'failed') "
            "AND native_chars >= ? AND vi_score >= ?",
            (config.NATIVE_TEXT_THRESHOLD, pdf_text.VI_SCORE_OK),
        ).fetchall()

    done = 0
    rejected = 0

    for row in rows:
        try:
            pages, vi_score = pdf_text.usable_native_text(pdf_dir / row["key"])
        except Exception as exc:
            session.log("skip-native", row["key"], "error", str(exc))
            continue

        # Kiểm tra lại trên TOÀN BỘ văn bản, không chỉ 5 trang đầu như lúc scan.
        if vi_score < pdf_text.VI_SCORE_OK:
            session.update(row["key"], vi_score=vi_score)
            rejected += 1
            continue

        text = pdf_text.pages_to_text(pages)
        out_path = _raw_path(row)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")

        session.update(
            row["key"],
            ocr_status="fallback",
            ocr_error=None,
            vi_score=vi_score,
            raw_txt=str(out_path.relative_to(config.ROOT).as_posix()),
            raw_chars=len(text),
        )

        done += 1

        if done % 25 == 0:
            say(f"  ... {done}/{len(rows)}")

    return done, rejected


# ============================================================
# BÁO CÁO
# ============================================================

def report(session: Session) -> str:
    total = session.total()
    ocr = session.counts("ocr_status")
    fix = session.counts("fix_status")
    credits = session.get_meta("remaining_credits")

    lines = [
        "",
        "=" * 62,
        f"SESSION: {session.name}   ({total} văn bản)",
        "=" * 62,
        "",
        "  OCR:",
    ]

    labels = {
        "pending": "chờ xử lý",
        "done": "xong",
        "fallback": "dùng text sẵn có",
        "failed": "lỗi",
        "skipped": "bỏ qua",
    }

    for status in ("done", "fallback", "pending", "failed"):
        if ocr.get(status):
            lines.append(f"    {labels[status]:<20} {ocr[status]:>5}")

    lines += ["", "  Hiệu đính (Gemini):"]

    for status in ("done", "pending", "skipped", "failed"):
        if fix.get(status):
            lines.append(f"    {labels[status]:<20} {fix[status]:>5}")

    engines = session.counts("ocr_engine")

    if any(engines.get(name) for name in ("local", "api")):
        parts = [
            f"{name}={engines[name]}" for name in ("local", "api") if engines.get(name)
        ]
        lines += ["", f"  Engine đã dùng: {', '.join(parts)}"]

    if credits is not None:
        lines += ["", f"  Credit OCR còn lại: {credits:,}"]

    if session.get_meta("stopped_reason") == "credit":
        lines += [
            "  Lần chạy trước dừng vì CHẠM SÀN CREDIT.",
            "  Nạp thêm credit rồi chạy lại `python run.py ocr` để đi tiếp.",
        ]

    errors = session.recent_errors(8)

    if errors:
        lines += ["", "  Lỗi gần nhất:"]

        for event in errors:
            lines.append(
                f"    [{event['stage']}] {unicodedata.normalize('NFC', event['key'])[:40]}"
                f" — {event['msg'][:80]}"
            )

    lines += ["", "=" * 62, ""]

    return "\n".join(lines)
