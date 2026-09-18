"""
OCR chạy tại chỗ bằng EasyOCR — không tốn credit, không giới hạn.

Vì sao chọn EasyOCR: benchmark trên chính kho văn bản này (xem README mục 5)
cho thấy nó nhận dấu tiếng Việt tốt hơn cả API đang dùng.

    EasyOCR vi     vi_score 0,296 - 0,315
    API (Tesseract) vi_score 0,270 - 0,288
    PaddleOCR vi    vi_score 0,153 - 0,165   (mất dấu nặng hàng loạt)

Hai tham số quan trọng, đều đã đo:

* **DPI = 150.** Quét 120 -> 300 DPI, độ chính xác gần như không đổi
  (vi_score 0,250 - 0,255, số ký tự y hệt) nhưng 300 DPI chậm hơn 2,3 lần.
* **4 tiến trình x 3 luồng torch.** Throughput bão hoà ở đây (431 trang/giờ);
  thêm tiến trình không nhanh hơn vì torch đã ăn hết nhân.
"""

from __future__ import annotations

import os
from pathlib import Path

from ..core import config

# Mỗi tiến trình con giữ riêng một reader + một document đang mở. Nạp model mất
# ~7 giây nên tuyệt đối không tạo lại cho từng trang.
_READER = None
_DOC_CACHE: tuple[str, object] | None = None


def _init_worker(langs: tuple[str, ...], threads: int, gpu: bool = False) -> None:
    """Khởi tạo tiến trình con: ghim số luồng torch rồi nạp model."""

    # Phải đặt TRƯỚC khi import torch, nếu không BLAS tự lấy hết nhân và các
    # tiến trình giành nhau, chậm hơn chạy một mình.
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[var] = str(threads)

    import warnings

    warnings.filterwarnings("ignore")

    import torch

    torch.set_num_threads(threads)

    import easyocr

    global _READER
    _READER = easyocr.Reader(list(langs), gpu=gpu, verbose=False)


def _sorted_text(items) -> str:
    """
    Sắp lại các khối chữ theo thứ tự đọc: trên xuống dưới, trái sang phải.

    EasyOCR trả về theo thứ tự phát hiện, không đảm bảo đúng thứ tự đọc. Gom
    các khối lệch nhau dưới nửa chiều cao thành cùng một hàng rồi mới xếp
    ngang — nhờ vậy phần tiêu ngữ hai cột của công văn không bị trộn lẫn.
    """

    boxes = []

    for item in items:
        box, text = item[0], item[1]

        if not str(text).strip():
            continue

        ys = [point[1] for point in box]
        xs = [point[0] for point in box]
        boxes.append((min(ys), max(ys) - min(ys), min(xs), str(text).strip()))

    if not boxes:
        return ""

    boxes.sort(key=lambda b: b[0])

    heights = sorted(b[1] for b in boxes)
    tolerance = max(8, heights[len(heights) // 2] * 0.6)

    rows: list[list[tuple]] = [[boxes[0]]]

    for box in boxes[1:]:
        if abs(box[0] - rows[-1][0][0]) <= tolerance:
            rows[-1].append(box)
        else:
            rows.append([box])

    lines = []

    for row in rows:
        row.sort(key=lambda b: b[2])
        lines.append(" ".join(b[3] for b in row))

    return "\n".join(lines)


def ocr_page(job: tuple[str, int, int]) -> tuple[int, str]:
    """Chạy trong tiến trình con: OCR một trang. job = (đường dẫn, trang, dpi)."""

    import numpy as np
    import pymupdf

    pymupdf.TOOLS.mupdf_display_errors(False)

    pdf_path, page_index, dpi = job

    global _DOC_CACHE

    if _DOC_CACHE is None or _DOC_CACHE[0] != pdf_path:
        if _DOC_CACHE is not None:
            try:
                _DOC_CACHE[1].close()
            except Exception:
                pass

        _DOC_CACHE = (pdf_path, pymupdf.open(pdf_path))

    doc = _DOC_CACHE[1]

    try:
        pixmap = doc[page_index].get_pixmap(dpi=dpi)
        image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
            pixmap.height, pixmap.width, pixmap.n
        )

        # Bỏ kênh alpha nếu có — EasyOCR chỉ nhận ảnh 1 hoặc 3 kênh.
        if pixmap.n == 4:
            image = image[:, :, :3]

        # paragraph=False: để EasyOCR trả về từng dòng rồi tự gom lại theo toạ
        # độ. Đo thực tế cùng nội dung / cùng vi_score / cùng tốc độ với
        # paragraph=True, nhưng giữ được 29 dòng thay vì gộp còn 4 — cấu trúc
        # Điều/Khoản là thứ bước hiệu đính và knowledge graph cần.
        items = _READER.readtext(image, paragraph=False)

        return page_index, _sorted_text(items)

    except Exception as exc:
        return page_index, f"[LỖI OCR TRANG {page_index + 1}: {exc}]"


def worker_kwargs() -> dict:
    """Tham số khởi tạo ProcessPoolExecutor cho backend này."""

    # Trên GPU thì một tiến trình là đủ — thêm tiến trình chỉ chia nhau VRAM.
    workers = 1 if config.LOCAL_OCR_GPU else config.LOCAL_OCR_WORKERS

    return {
        "max_workers": workers,
        "initializer": _init_worker,
        "initargs": (
            tuple(config.LOCAL_OCR_LANGS),
            config.LOCAL_OCR_THREADS,
            config.LOCAL_OCR_GPU,
        ),
    }


def page_jobs(pdf_path: Path, pages: int) -> list[tuple[str, int, int]]:
    return [(str(pdf_path), i, config.LOCAL_OCR_DPI) for i in range(pages)]


def check_ready() -> str | None:
    """Trả về thông báo lỗi nếu thiếu thư viện, None nếu sẵn sàng."""

    try:
        import easyocr  # noqa: F401
        import torch  # noqa: F401
    except ImportError as exc:
        return (
            f"Thiếu thư viện cho OCR nội bộ ({exc.name}). Cài bằng:\n"
            "    pip install easyocr\n"
            "Lần chạy đầu sẽ tải model tiếng Việt (~100 MB)."
        )

    return None
