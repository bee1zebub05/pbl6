"""
Client cho API OCR (http://<host>/v1/ocr).

Lưu ý về API này:

* Nó xoay vòng nhiều key upstream (iLovePDF). Khi trúng key hỏng nó trả
  HTTP 500 kèm "401 Unauthorized" -> gọi lại lần nữa thường là thành công,
  nên bắt buộc phải retry.
* `download_url` chỉ sống 300 giây và chứa ký tự tiếng Việt chưa encode
  -> phải quote path rồi tải ngay.
"""

from __future__ import annotations

import random
import time
import urllib.parse
from pathlib import Path

import requests

from . import config


class OCRError(RuntimeError):
    """OCR thất bại sau khi đã retry hết số lần cho phép."""


def _encode_url(url: str) -> str:
    """Percent-encode phần path (tên file tiếng Việt) của download_url."""

    parts = urllib.parse.urlsplit(url)

    return urllib.parse.urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            urllib.parse.quote(parts.path, safe="/%"),
            parts.query,
            parts.fragment,
        )
    )


def _backoff(attempt: int) -> float:
    delay = config.OCR_BACKOFF_BASE * (2 ** (attempt - 1))

    return min(delay, config.OCR_BACKOFF_MAX) * (0.6 + random.random() * 0.8)


class OCRClient:
    def __init__(self, session: requests.Session | None = None):
        self.http = session or requests.Session()

    def ocr_pdf(
        self,
        pdf_path: Path,
        languages: list[str] | None = None,
        on_retry=None,
    ) -> tuple[bytes, dict]:
        """
        Đẩy PDF lên OCR rồi tải file PDF đã có lớp text về.

        Trả về (nội dung PDF đã OCR, phần `data` của response).
        """

        languages = languages or config.OCR_LANGUAGES
        last_error = ""

        for attempt in range(1, config.OCR_MAX_ATTEMPTS + 1):
            try:
                with pdf_path.open("rb") as handle:
                    response = self.http.post(
                        config.OCR_ENDPOINT,
                        files={
                            "file": (
                                # Tên ASCII an toàn: server chỉ dùng nó để đặt
                                # tên file tạm, ta tự quản lý tên thật.
                                "document.pdf",
                                handle,
                                "application/pdf",
                            )
                        },
                        data={"ocr_languages": languages},
                        timeout=config.OCR_UPLOAD_TIMEOUT,
                    )

                if response.status_code != 200:
                    last_error = f"HTTP {response.status_code}: {response.text[:300]}"
                    raise OCRError(last_error)

                payload = response.json()
                data = payload.get("data")

                if not data or not data.get("download_url"):
                    last_error = f"Response thiếu download_url: {response.text[:300]}"
                    raise OCRError(last_error)

                content = self._download(data["download_url"])

                if not content.startswith(b"%PDF"):
                    last_error = "File tải về không phải PDF hợp lệ"
                    raise OCRError(last_error)

                return content, data

            except (OCRError, requests.RequestException, ValueError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"

                if attempt >= config.OCR_MAX_ATTEMPTS:
                    break

                if on_retry:
                    on_retry(attempt, last_error)

                time.sleep(_backoff(attempt))

        raise OCRError(
            f"OCR thất bại sau {config.OCR_MAX_ATTEMPTS} lần: {last_error}"
        )

    def _download(self, url: str) -> bytes:
        response = self.http.get(
            _encode_url(url),
            timeout=config.OCR_DOWNLOAD_TIMEOUT,
        )
        response.raise_for_status()

        return response.content

    def credits(self) -> int | None:
        """
        Hỏi số credit còn lại mà không cần OCR file nào.

        Dùng /v1/admin/key-status. Trả về None nếu endpoint không phản hồi —
        khi đó pipeline lấy tạm con số ghi trong session.
        """

        try:
            response = self.http.get(
                f"{config.OCR_BASE_URL}/v1/admin/key-status", timeout=30
            )
            response.raise_for_status()

            status = (response.json().get("data") or {}).get("key_status") or {}

            values = [
                info["remaining_credits"]
                for info in status.values()
                if isinstance(info, dict) and info.get("remaining_credits") is not None
            ]

            return max(values) if values else None

        except (requests.RequestException, ValueError, KeyError, AttributeError):
            return None

    def health(self) -> dict:
        response = self.http.get(
            f"{config.OCR_BASE_URL}/v1/api-key-status", timeout=30
        )
        response.raise_for_status()

        return response.json().get("data", {})
