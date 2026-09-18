#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cau_sua_txt.py - May chu hang cho cho viec SUA LOI OCR bang Gemini web.

Khac bridge.py o cho: bridge.py day PDF len de OCR ra text.
Cai nay day TXT DA OCR len de Gemini soat loi chinh ta roi tra ve TXT sach.

Luong:
    CHUA_KIEM_387.csv  ->  hang cho  ->  extension Chrome  ->  Gemini
                                                   |
                       data/processed/text_gemini_sach/<linh vuc>/<ten>.txt

AN TOAN (theo dung luat cua chu du an):
  - KHONG BAO GIO ghi de len text_final. Ghi ra thu muc rieng de nguoi doc duyet.
  - Ban tra ve ngan hon ban goc qua nhieu  -> cho vao  _nghi_ngo/  chu khong nhan.
  - Ban tra ve mat mocic trang [Trang N]   -> canh bao trong bao cao.

Chay:
    python cau_sua_txt.py
    python cau_sua_txt.py --port 8779 --csv F:\\DUT4\\PBL6\\CHUA_KIEM_387.csv
    python cau_sua_txt.py --chi 0114,0439,0403      # chi lam may ma nay
    python cau_sua_txt.py --tu-loi-cao 2.0          # chi lam file >= 2% loi
    python cau_sua_txt.py --chi 0090,0281 --out ...\text_gemini_lan2 \
                          --trang-thai trang_thai_lan2.json   # chay doi chung

API (extension goi vao):
    GET  /                      trang trang thai (HTML)
    GET  /api/stats             so lieu
    GET  /api/next?worker=w1    lay 1 viec
    GET  /api/file/<id>         tai noi dung .txt goc (text/plain)
    POST /api/done   {id,text}  nop ban da sua
    POST /api/fail   {id,error,tam_thoi}
    POST /api/requeue           day lai cac viec that bai vao hang cho
"""

import argparse
import csv
import io
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Goc repo suy tu vi tri file (tools/gemini_web/ -> len 2 cap), de chay duoc tren
# may khac. Dat PBL6_GOC neu muon tro sang cay data lam viec nam ngoai repo.
GOC = Path(os.environ.get("PBL6_GOC") or Path(__file__).resolve().parents[2])
CSV_MAC_DINH = GOC / "data" / "kiem_tra" / "can_sua.csv"
RA_MAC_DINH = GOC / "data" / "interim" / "text_gemini_sach"
TRANG_THAI = Path(__file__).resolve().parent / "trang_thai_sua_txt.json"

# Cau lenh gui kem moi file. Viet ro cac lop loi cua Gemma + cam bia.
PROMPT = (
    "Đây là file tôi OCR ra từ PDF scan không có text layer. Hãy kiểm tra và sửa lại "
    "các lỗi chính tả tiếng Việt dựa vào ngữ cảnh của văn bản, rồi gửi lại tôi file txt "
    "hoàn chỉnh vẫn giữ đúng format file txt ban đầu.\n\n"
    "Các lớp lỗi hay gặp của bản OCR này:\n"
    "- Chữ I hoa lẫn với l thường và dấu / : Iượng→lượng, BÁOISố→BÁO/Số\n"
    "- Dấu móc ư/ơ đặt sai chỗ: truờng→trường, chưong→chương, đuợc→được\n"
    "- Nguyên âm mang 2 dấu bị gộp còn 1: diéu→điều, hién→hiện, quyén→quyền\n"
    "- Nhầm đ/d, ă/â, 0↔O, 1↔l, dính chữ hoặc tách chữ sai\n\n"
    "BẮT BUỘC:\n"
    "1. Giữ nguyên mọi mốc trang dạng ----- [Trang N] ----- , đúng vị trí, đủ số lượng.\n"
    "2. Giữ nguyên toàn bộ con số: số hiệu văn bản, ngày tháng, số tiền, phần trăm, "
    "số Điều/Khoản. Tuyệt đối không đổi.\n"
    "3. Không được xoá, rút gọn hay tóm tắt bất kỳ đoạn nào. Trả về ĐỦ từ đầu đến cuối file.\n"
    "4. Chỗ nào OCR ra chuỗi rác không đoán được thì GIỮ NGUYÊN chuỗi rác đó, không tự bịa.\n"
    "5. Không thêm ghi chú, nhãn hay lời giải thích nào vào trong nội dung file.\n"
    "6. Xuất toàn bộ trong MỘT khối mã plaintext duy nhất.\n"
    "7. KHÔNG dùng Canvas, không dùng bảng markdown, không dùng danh sách đánh số "
    "của markdown — chỉ khối mã plaintext thuần."
)

MOC_TRANG = re.compile(r"-{3,}\s*\[Trang\s+\d+\]\s*-{3,}")
TOI_DA_THU = 3            # mot file thu toi da bay nhieu lan roi moi danh hong
TY_LE_NGAN_NHAT = 0.80   # ban tra ve ngan hon 80% ban goc -> nghi ngo, khong nhan


def noi(*a):
    print(*a, flush=True)


class Kho:
    """Giu hang cho + trang thai, co khoa de nhieu worker goi song song."""

    def __init__(self, csv_path, ra_dir, chi=None, tu_loi_cao=None):
        self.khoa = threading.Lock()
        self.ra_dir = Path(ra_dir)
        self.nghi_ngo_dir = self.ra_dir / "_nghi_ngo"
        self.viec = {}          # ma -> dict
        self.hang = []          # danh sach ma dang cho
        self.dang_lam = {}      # ma -> {worker, luc}
        self.xong = {}          # ma -> {duong_dan, so_ky_tu, luc}
        self.hong = {}          # ma -> loi
        self.so_lan = {}        # ma -> so lan da thu (chi dem loi tam thoi)
        self._nap_csv(csv_path, chi, tu_loi_cao)
        self._nap_trang_thai()

    # ---------- nap du lieu ----------
    def _nap_csv(self, csv_path, chi, tu_loi_cao):
        with io.open(csv_path, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                ma = (r.get("ma") or "").strip()
                if not ma:
                    continue
                if chi and ma not in chi:
                    continue
                if tu_loi_cao is not None:
                    try:
                        if float(r.get("ty_le_loi_phan_tram") or 0) < tu_loi_cao:
                            continue
                    except ValueError:
                        continue
                p = Path(r["duong_dan_txt"])
                if not p.exists():
                    noi("[bo qua] %s khong thay file: %s" % (ma, p))
                    continue
                self.viec[ma] = {
                    "id": ma,
                    "ten_file": r.get("ten_file") or p.name,
                    "linh_vuc": r.get("linh_vuc") or p.parent.name,
                    "duong_dan": str(p),
                    "so_dong": int(r.get("so_dong") or 0),
                    "ty_le_loi": r.get("ty_le_loi_phan_tram") or "",
                }
        noi("[cau] nap %d viec tu CSV" % len(self.viec))

    def _nap_trang_thai(self):
        if TRANG_THAI.exists():
            try:
                d = json.loads(TRANG_THAI.read_text(encoding="utf-8"))
                self.xong = d.get("xong", {})
                self.hong = d.get("hong", {})
                self.so_lan = d.get("so_lan", {})
            except Exception as e:
                noi("[cau] trang thai cu hong (%s), bo qua" % e)
        self.hang = [m for m in sorted(self.viec) if m not in self.xong]
        noi("[cau] %d xong tu truoc, con %d trong hang cho" % (len(self.xong), len(self.hang)))

    def _ghi_trang_thai(self):
        TRANG_THAI.write_text(
            json.dumps({"xong": self.xong, "hong": self.hong, "so_lan": self.so_lan}, ensure_ascii=False, indent=1),
            encoding="utf-8")

    # ---------- hang cho ----------
    def lay_viec(self, worker):
        with self.khoa:
            # Thu hoi viec giao lau ma khong ai nop. Nguong phai RONG: Gemini
            # co the xu ly ca tieng cho file to, thu hoi som la hai luong cung
            # lam mot file. Day chi la luoi an toan cho truong hop Chrome chet.
            gio = time.time()
            for ma, d in list(self.dang_lam.items()):
                if gio - d["luc"] > 180 * 60:
                    noi("[cau] thu hoi %s (qua han)" % ma)
                    self.dang_lam.pop(ma, None)
                    self.hang.insert(0, ma)
            while self.hang:
                ma = self.hang.pop(0)
                if ma in self.xong:
                    continue
                self.dang_lam[ma] = {"worker": worker, "luc": gio}
                v = dict(self.viec[ma])
                v["prompt"] = PROMPT
                v["so_ky_tu_goc"] = len(self._doc(ma))
                return v
            return None

    def _doc(self, ma):
        return io.open(self.viec[ma]["duong_dan"], encoding="utf-8", errors="replace").read()

    def noi_dung(self, ma):
        return self._doc(ma)

    # ---------- nhan ket qua ----------
    def nop(self, ma, text, nguon=None):
        if ma not in self.viec:
            return False, "khong co viec nay"
        goc = self._doc(ma)
        n_goc, n_moi = len(goc), len(text)
        moc_goc = len(MOC_TRANG.findall(goc))
        moc_moi = len(MOC_TRANG.findall(text))

        canh_bao = []
        nghi_ngo = False
        # Canvas la markdown da render, khong phai nguyen van: mat so thu tu danh
        # sach, bang bi ep thanh dong co dau |, dong trong bi gop. Luon de nguoi doc duyet.
        if nguon == "vot_markdown":
            # Ban vot tu <p>/<ol> khi Gemini dat rao ``` sai cho. Noi dung
            # co du nhung <ol><li> bi mat so thu tu "1." "2." vi Chrome
            # khong dua marker vao innerText -> BAT BUOC nguoi doc duyet.
            canh_bao.append("vot tu markdown, danh so trong danh sach co the mat")
            nghi_ngo = True
        if nguon == "canvas":
            canh_bao.append("lay tu Canvas - markdown da bop meo dinh dang")
            nghi_ngo = True
        if n_moi < n_goc * TY_LE_NGAN_NHAT:
            canh_bao.append("ngan hon goc nhieu (%d/%d = %.0f%%)"
                            % (n_moi, n_goc, 100.0 * n_moi / max(n_goc, 1)))
            nghi_ngo = True
        if moc_goc and moc_moi != moc_goc:
            canh_bao.append("moc trang %d -> %d" % (moc_goc, moc_moi))
            nghi_ngo = True

        v = self.viec[ma]
        thu_muc = (self.nghi_ngo_dir if nghi_ngo else self.ra_dir) / v["linh_vuc"]
        thu_muc.mkdir(parents=True, exist_ok=True)
        dich = thu_muc / v["ten_file"]
        io.open(dich, "w", encoding="utf-8", newline="\n").write(text)

        with self.khoa:
            self.dang_lam.pop(ma, None)
            self.hong.pop(ma, None)
            self.xong[ma] = {"duong_dan": str(dich), "so_ky_tu": n_moi,
                             "goc": n_goc, "nghi_ngo": nghi_ngo, "nguon": nguon,
                             "canh_bao": canh_bao, "luc": int(time.time())}
            self._ghi_trang_thai()
        return True, {"duong_dan": str(dich), "nghi_ngo": nghi_ngo, "canh_bao": canh_bao}

    def bao_hong(self, ma, loi, tam_thoi=False):
        with self.khoa:
            self.dang_lam.pop(ma, None)
            if tam_thoi:
                # Khong co nguong nay thi file bi Gemini tu choi se quay vong
                # mai: tu choi -> xep lai hang -> phat lai -> tu choi. Da gap
                # that voi 0112 va 0425.
                n = self.so_lan.get(ma, 0) + 1
                self.so_lan[ma] = n
                if n >= TOI_DA_THU:
                    self.hong[ma] = ("thu %d lan deu hong: %s" % (n, str(loi)))[:500]
                elif ma not in self.hang:
                    self.hang.append(ma)      # cho xuong cuoi, lam lai sau
            else:
                self.hong[ma] = str(loi)[:500]
            self._ghi_trang_thai()

    def day_lai_hong(self):
        with self.khoa:
            n = 0
            for ma in list(self.hong):
                self.hong.pop(ma)
                self.so_lan.pop(ma, None)   # day lai bang tay = cho lam lai tu dau
                if ma not in self.xong:
                    self.hang.append(ma)
                    n += 1
            self._ghi_trang_thai()
            return n

    def so_lieu(self):
        with self.khoa:
            return {"tong": len(self.viec), "cho": len(self.hang),
                    "dang_lam": len(self.dang_lam), "xong": len(self.xong),
                    "hong": len(self.hong),
                    "nghi_ngo": sum(1 for v in self.xong.values() if v.get("nghi_ngo"))}


class Handler(BaseHTTPRequestHandler):
    kho = None

    def log_message(self, *a):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")

    def _json(self, d, ma=200):
        b = json.dumps(d, ensure_ascii=False).encode("utf-8")
        self.send_response(ma)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self._cors()
        self.end_headers()
        self.wfile.write(b)

    def _text(self, s, ctype="text/plain; charset=utf-8"):
        b = s.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self._cors()
        self.end_headers()
        self.wfile.write(b)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        k = Handler.kho
        try:
            if u.path in ("/", "/health"):
                s = k.so_lieu()
                return self._text(
                    "<meta charset=utf-8><title>cau_sua_txt</title>"
                    "<body style='font:14px system-ui;padding:24px'>"
                    "<h2>Hàng chờ sửa lỗi OCR</h2>"
                    "<p>tổng <b>%(tong)d</b> · chờ <b>%(cho)d</b> · đang làm <b>%(dang_lam)d</b>"
                    " · xong <b>%(xong)d</b> · nghi ngờ <b>%(nghi_ngo)d</b> · hỏng <b>%(hong)d</b></p>"
                    "<p><a href='/api/stats'>/api/stats</a></p>"
                    "<script>setTimeout(()=>location.reload(),5000)</script>" % s,
                    "text/html; charset=utf-8")

            if u.path == "/api/stats":
                return self._json({"ok": True, **k.so_lieu()})

            if u.path == "/api/next":
                worker = (q.get("worker") or ["w"])[0]
                v = k.lay_viec(worker)
                if v:
                    noi("[cau] -> phat %s  %s" % (v["id"], v["ten_file"][:60]))
                return self._json({"ok": True, "job": v})

            if u.path.startswith("/api/file/"):
                ma = u.path.rsplit("/", 1)[-1]
                if ma not in k.viec:
                    return self._json({"ok": False, "error": "khong co"}, 404)
                return self._text(k.noi_dung(ma))

            return self._json({"ok": False, "error": "route khong ton tai"}, 404)
        except Exception as e:
            return self._json({"ok": False, "error": "%s: %s" % (type(e).__name__, e)}, 500)

    def do_POST(self):
        u = urlparse(self.path)
        k = Handler.kho
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads((self.rfile.read(n) if n else b"{}").decode("utf-8") or "{}")

            if u.path == "/api/done":
                ma = body.get("id")
                text = body.get("text") or ""
                if len(text.strip()) < 200:
                    k.bao_hong(ma, "text tra ve qua ngan", tam_thoi=True)
                    return self._json({"ok": False, "error": "text qua ngan"}, 400)
                ok, tt = k.nop(ma, text, body.get("nguon"))
                if ok:
                    noi("[cau] %s %s  %d ky tu%s"
                        % ("NGHI NGO" if tt["nghi_ngo"] else "OK      ", ma, len(text),
                           ("  << " + "; ".join(tt["canh_bao"])) if tt["canh_bao"] else ""))
                    return self._json({"ok": True, **tt})
                return self._json({"ok": False, "error": tt}, 400)

            if u.path == "/api/fail":
                ma = body.get("id")
                tam = bool(body.get("tam_thoi"))
                k.bao_hong(ma, body.get("error") or "?", tam_thoi=tam)
                noi("[cau] %s %s: %s" % ("HOAN" if tam else "HONG", ma,
                                         str(body.get("error"))[:120]))
                return self._json({"ok": True, "tam_thoi": tam})

            if u.path == "/api/requeue":
                return self._json({"ok": True, "day_lai": k.day_lai_hong()})

            return self._json({"ok": False, "error": "route khong ton tai"}, 404)
        except Exception as e:
            return self._json({"ok": False, "error": "%s: %s" % (type(e).__name__, e)}, 500)


def main():
    global TRANG_THAI
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8779)
    ap.add_argument("--csv", default=str(CSV_MAC_DINH))
    ap.add_argument("--out", default=str(RA_MAC_DINH))
    ap.add_argument("--chi", default="", help="chi lam nhung ma nay, ngan cach bang dau phay")
    ap.add_argument("--tu-loi-cao", type=float, default=None,
                    help="chi lam file co ty le loi >= nguong nay (vd 2.0)")
    # Chay DOI CHUNG lan 2: phai tach ca thu muc ra LAN file checkpoint, khong thi
    # lan 2 de len lan 1 va mat luon cai can so sanh.
    ap.add_argument("--trang-thai", default=str(TRANG_THAI),
                    help="file checkpoint rieng (dung khi chay doi chung lan 2)")
    a = ap.parse_args()
    TRANG_THAI = Path(a.trang_thai)

    chi = set(x.strip() for x in a.chi.split(",") if x.strip()) or None
    Handler.kho = Kho(a.csv, a.out, chi=chi, tu_loi_cao=a.tu_loi_cao)
    Path(a.out).mkdir(parents=True, exist_ok=True)

    noi("[cau] nghe tai http://127.0.0.1:%d\n[cau] ra: %s\n[cau] checkpoint: %s"
        % (a.port, a.out, TRANG_THAI))
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
