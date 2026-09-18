"""
In ra màn hình và dừng êm bằng Ctrl+C.

Tách khỏi `clean/pipeline.py` vì cả ba tầng — làm sạch, dựng đồ thị, truy hồi —
đều cần in tiến độ và đều cần dừng giữa chừng mà không mất việc đang dở. Để
nguyên trong pipeline thì `kg/` phải import ngược lên tầng làm sạch chỉ để lấy
hai thứ này.
"""

from __future__ import annotations

import signal
import threading

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
