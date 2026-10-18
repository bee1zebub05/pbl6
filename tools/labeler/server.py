#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Máy chủ cho trang gán nhãn khi tự host — lưu nhãn xuống SQLite.

    python3 tools/labeler/server.py                  # cổng 8002, chỉ nghe loopback
    python3 tools/labeler/server.py --cong 9000 --db /mnt/ssd/labeler.db

Vì sao cần: `index.html` vốn viết cho artifact trên claude.ai, nhãn lưu qua
`window.claude.use("db")`. Tự host thì không có runtime đó, trang rơi về lưu
trong bộ nhớ và mất sạch khi tải lại trang (chính nó hiện băng-rôn "Bản xem
thử: nhãn chỉ lưu tạm trong tab này").

File này dựng lại đúng phần API mà trang cần, lưu xuống SQLite. Chỉ dùng thư
viện chuẩn — không phải cài gì trên máy chủ.

Lưu trữ: một bảng duy nhất, khoá là đường dẫn kiểu Firestore.

    docs/0001                  thông tin một văn bản (status, assignee, n...)
    docs/0001/ann/<id>         một nhãn trong văn bản đó

`subDocs` và `subAnn` của trang là đăng ký theo thời gian thực; ở đây trang
hỏi lại mỗi 1,5 giây. Bốn người gán tay thì thế là đủ, mà đổi lại không cần
WebSocket hay thư viện ngoài.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sqlite3
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

GOC = Path(__file__).resolve().parent
DB_MAC_DINH = GOC / "nhan.db"

# Đường dẫn chỉ được gồm chữ, số, gạch, chấm và dấu /
_HOP_LE = re.compile(r"^[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-]+)*$")

_khoa = threading.Lock()


def mo_db(duong_dan: Path) -> sqlite3.Connection:
    duong_dan.parent.mkdir(parents=True, exist_ok=True)
    cn = sqlite3.connect(str(duong_dan), check_same_thread=False)
    cn.execute("PRAGMA journal_mode=WAL")      # nhiều người ghi cùng lúc
    cn.execute("PRAGMA synchronous=NORMAL")
    cn.execute("CREATE TABLE IF NOT EXISTS kv ("
               "  path TEXT PRIMARY KEY,"
               "  data TEXT NOT NULL,"
               "  updated REAL NOT NULL)")
    cn.commit()
    return cn


def _kiem(path: str) -> str:
    path = unquote(path or "").strip("/")
    if not path or not _HOP_LE.match(path) or ".." in path:
        raise ValueError("đường dẫn không hợp lệ: %r" % path)
    return path


class Kho:
    """Chỉ đủ những phép mà index.html thật sự gọi."""

    def __init__(self, cn: sqlite3.Connection):
        self.cn = cn

    def lay(self, path: str):
        r = self.cn.execute("SELECT data FROM kv WHERE path=?", (path,)).fetchone()
        return json.loads(r[0]) if r else None

    def liet_ke(self, prefix: str):
        """Chỉ con TRỰC TIẾP: docs/0001 thuộc docs, docs/0001/ann/x thì không."""
        sau = len(prefix) + 1
        ra = []
        for p, d in self.cn.execute(
                "SELECT path, data FROM kv WHERE path LIKE ? ORDER BY path",
                (prefix + "/%",)):
            if "/" in p[sau:]:
                continue
            ra.append({"id": p[sau:], "data": json.loads(d)})
        return ra

    def dat(self, path: str, data: dict):
        with _khoa:
            self.cn.execute(
                "INSERT INTO kv(path,data,updated) VALUES(?,?,?) "
                "ON CONFLICT(path) DO UPDATE SET data=excluded.data, updated=excluded.updated",
                (path, json.dumps(data, ensure_ascii=False), time.time()))
            self.cn.commit()

    def va(self, path: str, patch: dict):
        """Trộn vào bản cũ. Không có bản cũ thì tạo mới — trang đôi khi update
        trước khi set, và dựng mới vẫn đúng ý hơn là báo lỗi."""
        with _khoa:
            cu = self.lay(path) or {}
            cu.update(patch)
            self.cn.execute(
                "INSERT INTO kv(path,data,updated) VALUES(?,?,?) "
                "ON CONFLICT(path) DO UPDATE SET data=excluded.data, updated=excluded.updated",
                (path, json.dumps(cu, ensure_ascii=False), time.time()))
            self.cn.commit()
            return cu

    def xoa(self, path: str):
        with _khoa:
            self.cn.execute("DELETE FROM kv WHERE path=? OR path LIKE ?",
                            (path, path + "/%"))
            self.cn.commit()

    def them(self, prefix: str, data: dict) -> str:
        aid = uuid.uuid4().hex[:16]
        self.dat(prefix + "/" + aid, data)
        return aid


def dung_handler(kho: Kho, goc_tinh: Path):

    class H(BaseHTTPRequestHandler):
        server_version = "pbl6-labeler"

        def log_message(self, fmt, *a):            # bớt ồn, chỉ in lỗi
            if not str(a[1] if len(a) > 1 else "").startswith(("2", "3")):
                super().log_message(fmt, *a)

        # ---------- tiện ích ----------
        def _json(self, obj, ma=200):
            b = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(ma)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(b)

        def _than(self):
            n = int(self.headers.get("Content-Length") or 0)
            if not n:
                return {}
            return json.loads(self.rfile.read(n).decode("utf-8"))

        def _q(self, ten):
            return parse_qs(urlparse(self.path).query).get(ten, [""])[0]

        # ---------- API ----------
        def _api(self, viec):
            try:
                if viec == "list":
                    return self._json({"docs": kho.liet_ke(_kiem(self._q("path")))})
                if viec == "get":
                    d = kho.lay(_kiem(self._q("path")))
                    return self._json({"exists": d is not None, "data": d})
                if viec == "set":
                    p = _kiem(self._q("path")); kho.dat(p, self._than())
                    return self._json({"ok": True})
                if viec == "update":
                    p = _kiem(self._q("path"))
                    return self._json({"ok": True, "data": kho.va(p, self._than())})
                if viec == "add":
                    p = _kiem(self._q("path"))
                    return self._json({"id": kho.them(p, self._than())})
                if viec == "delete":
                    kho.xoa(_kiem(self._q("path")))
                    return self._json({"ok": True})
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
            except Exception as e:                  # noqa: BLE001
                return self._json({"error": "%s: %s" % (type(e).__name__, e)}, 500)
            self._json({"error": "không rõ phép: %s" % viec}, 404)

        # ---------- file tĩnh ----------
        def _tinh(self):
            p = unquote(urlparse(self.path).path).lstrip("/") or "index.html"
            f = (goc_tinh / p).resolve()
            if goc_tinh not in f.parents and f != goc_tinh:
                return self.send_error(403)
            if f.is_dir():
                f = f / "index.html"
            if not f.is_file():
                return self.send_error(404)
            kieu = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
            b = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", kieu + ("; charset=utf-8" if kieu.startswith(("text/", "application/json")) else ""))
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store" if f.suffix == ".html" else "max-age=60")
            self.end_headers()
            if self.command != "HEAD":        # HEAD chi tra header, khong tra than
                self.wfile.write(b)

        def _dieu_phoi(self):
            d = urlparse(self.path).path
            if d.startswith("/api/"):
                return self._api(d[5:].strip("/"))
            if self.command not in ("GET", "HEAD"):
                return self.send_error(405)
            self._tinh()

        # HEAD phai co: `curl -I` dung method nay, thieu thi BaseHTTPRequestHandler
        # tra 501 du trang van chay binh thuong trong trinh duyet.
        do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = _dieu_phoi

    return H


def main() -> int:
    ap = argparse.ArgumentParser(description="Máy chủ trang gán nhãn, lưu nhãn vào SQLite")
    ap.add_argument("--cong", type=int, default=8002)
    ap.add_argument("--dia-chi", default="127.0.0.1",
                    help="mặc định chỉ nghe loopback — cloudflared chạy cùng máy")
    ap.add_argument("--db", type=Path, default=DB_MAC_DINH,
                    help="file SQLite; trỏ sang ổ SSD nếu muốn")
    a = ap.parse_args()

    if not (GOC / "data" / "index.json").is_file():
        print("THIẾU dữ liệu: chạy  python3 tools/labeler/build_data.py  trước đã.")
        return 1

    kho = Kho(mo_db(a.db))
    srv = ThreadingHTTPServer((a.dia_chi, a.cong), dung_handler(kho, GOC))
    n = kho.cn.execute("SELECT count(*) FROM kv").fetchone()[0]
    print("Trang gán nhãn: http://%s:%d" % (a.dia_chi, a.cong))
    print("Nhãn lưu ở    : %s  (%d bản ghi sẵn có)" % (a.db, n))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\ndừng")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
