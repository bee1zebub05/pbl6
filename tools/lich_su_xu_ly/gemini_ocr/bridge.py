#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bridge.py - Local job server cho Gemini OCR Batch extension.

VI SAO CAN: Chrome extension KHONG doc/ghi duoc o dia tuy y. Bridge nay dung giua:
  - Quet cay  data/raw/**  (pdf, doc, docx)  -> phat job cho extension
  - Nhan text OCR tra ve   -> ghi vao  data/clean_data/<DUNG CUNG DUONG DAN>.txt
  - Nho trang thai (state.json) -> chay batch lon, tat may bat lai van resume

Chay:  python bridge.py
       python bridge.py --port 8777 --src data/raw --out data/clean_data
       python bridge.py --flatten-top     # bo cap "pdf/" -> clean_data/<linh vuc>/x.txt
"""

import argparse
import hashlib
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sach_hoa import lam_sach, kiem_dinh          # noqa: E402

try:
    from gemma_ocr import QuanLyKey, ocr_pdf, MODEL as GEMMA_MODEL   # noqa: E402
except Exception as _e:                            # thieu google-genai / dotenv
    QuanLyKey = None
    ocr_pdf = None
    GEMMA_MODEL = "gemma-4-31b-it"
    _loi_gemma = str(_e)

try:
    import pymupdf                                 # dem so trang -> chinh timeout + kiem dinh
except ImportError:
    pymupdf = None

# Console Windows mac dinh la cp1252/cp437 -> print() ten file tieng Viet se nem
# UnicodeEncodeError NGAY GIUA request handler, lam ca response hong (da dinh 1 lan).
# Ep stdout/stderr sang UTF-8, ky tu nao khong ve duoc thi thay the, khong bao gio nem.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def say(msg):
    """print() an toan tuyet doi - log KHONG BAO GIO duoc lam chet job."""
    try:
        print(msg, flush=True)
    except Exception:
        try:
            print(msg.encode("ascii", "replace").decode("ascii"), flush=True)
        except Exception:
            pass


EXTS = {".pdf", ".doc", ".docx"}
LEASE_TIMEOUT = 30 * 60          # job treo qua 30' -> tra lai hang doi
MAX_ATTEMPTS = 3                 # fail qua 3 lan thi bo qua, khong lap vo han
# File vua fail thi HOAN lai, uu tien phat file chua ai dung. Thu lai ngay mot file
# vua timeout 10' la dot 30' lien tuc ma van hong, trong khi con hang tram file chua chay.
RETRY_COOLDOWN = 20 * 60

_lock = threading.RLock()


def duong_dan_dai(p):
    r"""Windows chan duong dan > 260 ky tu -> FileNotFoundError kho hieu (da dinh 1 lan).

    Ten van ban o day dai toi 150 ky tu, cong cay thu muc la sat tran. Tien to \\?\
    bao Windows bo qua gioi han do. Tren Linux/macOS tra ve nguyen xi.
    """
    if os.name != "nt":
        return p
    p = os.path.abspath(p)
    return p if p.startswith("\\\\?\\") else "\\\\?\\" + p


class Store:
    def __init__(self, src, out, state_path, flatten_top, only=""):
        self.src = os.path.abspath(src)
        self.out = os.path.abspath(out)
        self.state_path = os.path.abspath(state_path)
        self.flatten_top = flatten_top
        # Loc theo duong dan tuong doi. Van quet tu goc data/raw nen CAY THU MUC ghi ra
        # clean_data giu nguyen -- khac han viec doi --src vao thang thu muc con (se mat cap).
        self.only = (only or "").replace("\\", "/").strip("/")
        self._cache_trang = {}  # path -> so trang (dem 1 lan roi nho)
        self.jobs = {}          # id -> {"id","rel","abs","name","size"}
        self.leases = {}        # id -> {"worker","ts"}
        self.state = {}         # rel -> {"status","error","attempts","ts","chars"}
        self._load_state()
        self.rescan()

    # -- state ---------------------------------------------------------------
    def _load_state(self):
        if os.path.isfile(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
            except Exception as e:
                say("[bridge] state.json hong (%s) - bat dau lai" % e)
                self.state = {}

    def _save_state(self):
        tmp = self.state_path + ".tmp"
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.state_path)

    # -- quet cay nguon ------------------------------------------------------
    def rescan(self):
        jobs = {}
        for root, _dirs, files in os.walk(self.src):
            for fn in sorted(files):
                if os.path.splitext(fn)[1].lower() not in EXTS:
                    continue
                ap = os.path.join(root, fn)
                rel = os.path.relpath(ap, self.src).replace("\\", "/")
                if self.only and not rel.startswith(self.only):
                    continue
                jid = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:16]
                try:
                    size = os.path.getsize(ap)
                except OSError:
                    continue
                jobs[jid] = {"id": jid, "rel": rel, "abs": ap, "name": fn, "size": size}
        with _lock:
            self.jobs = jobs
        return len(jobs)

    def out_path(self, rel):
        """clean_data giu NGUYEN cay thu muc cua raw, chi doi duoi -> .txt"""
        parts = rel.split("/")
        if self.flatten_top and len(parts) > 1:
            parts = parts[1:]          # bo cap tren cung ("pdf/", "doc_new/")
        parts[-1] = os.path.splitext(parts[-1])[0] + ".txt"
        return os.path.join(self.out, *parts)

    def is_done(self, rel):
        try:
            return os.path.getsize(duong_dan_dai(self.out_path(rel))) > 0
        except OSError:
            return False

    # -- hang doi ------------------------------------------------------------
    def _reap_leases(self):
        now = time.time()
        for jid, ls in list(self.leases.items()):
            if now - ls["ts"] > LEASE_TIMEOUT:
                del self.leases[jid]

    def _co_the_chay(self, jid, j, cho_hoan):
        """cho_hoan=False: bo qua file vua fail (dang trong thoi gian hoan)."""
        if jid in self.leases:
            return None
        rel = j["rel"]
        if self.is_done(rel):
            return None
        st = self.state.get(rel) or {}
        if st.get("status") == "failed":
            if st.get("attempts", 0) >= MAX_ATTEMPTS:
                return None
            if not cho_hoan and time.time() - st.get("ts", 0) < RETRY_COOLDOWN:
                return None
        return st

    def next_job(self, worker):
        with _lock:
            self._reap_leases()
            # Vong 1: file chua ai dung hoac da qua thoi gian hoan.
            # Vong 2: chap nhan ca file vua fail (khi khong con gi khac de lam).
            for cho_hoan in (False, True):
                for jid, j in self.jobs.items():
                    st = self._co_the_chay(jid, j, cho_hoan)
                    if st is None:
                        continue
                    rel = j["rel"]
                    self.leases[jid] = {"worker": worker, "ts": time.time()}
                    lan = st.get("attempts", 0) + 1
                    st["status"] = "processing"
                    st["ts"] = time.time()
                    self.state[rel] = st
                    return {"id": jid, "rel": rel, "name": j["name"], "size": j["size"],
                            "pages": self.so_trang(j["abs"]), "attempt": lan,
                            "out": self.out_path(rel).replace("\\", "/")}
            return None

    def so_trang(self, path):
        """So trang PDF -> extension tu noi timeout cho tai lieu dai."""
        if not pymupdf or not path.lower().endswith(".pdf"):
            return 0
        n = self._cache_trang.get(path)
        if n is None:
            try:
                with pymupdf.open(path) as d:
                    n = d.page_count
            except Exception:
                n = 0
            self._cache_trang[path] = n
        return n

    def finish(self, jid, text):
        with _lock:
            j = self.jobs.get(jid)
            if not j:
                return False, "job id khong ton tai (thu /api/rescan)"
            rel = j["rel"]

            # Lam sach NGAY LUC GHI: cau dan, rao ```, vo boc Python. Lam o day chu khong
            # o extension vi extension co the dang chay ban cu trong bo nho, con bridge thi
            # sua la co hieu luc ngay -> clean_data khong bao gio dinh rac.
            text, viec = lam_sach(text)
            dat, vi_sao = kiem_dinh(text, self.so_trang(j["abs"]))
            if not dat:
                # Khong ghi rac ra clean_data. Danh fail de duoc thu lai.
                self.fail(jid, "khong dat kiem dinh: " + vi_sao)
                return False, "khong dat: " + vi_sao
            if viec:
                say("[bridge] lam sach: %s" % ", ".join(viec))

            path = self.out_path(rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            self.state[rel] = {"status": "done", "chars": len(text),
                               "attempts": (self.state.get(rel) or {}).get("attempts", 0),
                               "ts": time.time(), "out": path.replace("\\", "/")}
            self.leases.pop(jid, None)
            self._save_state()
            return True, path

    def fail(self, jid, error, tam_thoi=False):
        """tam_thoi=True: loi do nguoi dung dung vao trinh duyet (keo tab, dong tab).
        Tra job ve hang doi NGUYEN VEN, khong tinh vao 3 luot thu - khong thi vai lan
        lo tay la file bi danh 'het luot' oan roi day sang Gemma vo co."""
        with _lock:
            j = self.jobs.get(jid)
            if not j:
                return False
            rel = j["rel"]
            st = self.state.get(rel) or {}
            if tam_thoi:
                st["status"] = "pending"
                st["ts"] = time.time()
                st["loi_tam_thoi"] = (error or "")[:200]
                self.state[rel] = st
                self.leases.pop(jid, None)
                self._save_state()
                return True
            st["attempts"] = st.get("attempts", 0) + 1
            st["status"] = "failed"
            st["error"] = (error or "")[:500]
            st["ts"] = time.time()
            self.state[rel] = st
            self.leases.pop(jid, None)
            self._save_state()
            return True

    def requeue_failed(self):
        with _lock:
            n = 0
            for _rel, st in self.state.items():
                if st.get("status") == "failed":
                    st["attempts"] = 0
                    st["status"] = "pending"
                    n += 1
            self._save_state()
            return n

    # -- duong lui Gemma ------------------------------------------------------
    def het_luot(self):
        """File da thu du MAX_ATTEMPTS qua Gemini web ma van hong, chua nho Gemma."""
        with _lock:
            ra = []
            for jid, j in self.jobs.items():
                rel = j["rel"]
                if self.is_done(rel) or jid in self.leases:
                    continue
                st = self.state.get(rel) or {}
                if st.get("status") != "failed":
                    continue
                if st.get("attempts", 0) < MAX_ATTEMPTS:
                    continue
                if st.get("gemma_xong") or st.get("gemma_hong"):
                    continue
                ra.append((jid, j))
            return ra

    def ghi_gemma(self, jid, ket_qua):
        """Ghi ket qua tu Gemma va GHI NHAN ro rang la file nay da phai dung duong lui."""
        with _lock:
            j = self.jobs.get(jid)
            if not j:
                return False
            rel = j["rel"]
            st = self.state.get(rel) or {}
            if not ket_qua.get("ok"):
                st["gemma_hong"] = ket_qua.get("ly_do", "?")
                st["ts"] = time.time()
                self.state[rel] = st
                self._save_state()
                return False

            text = ket_qua["text"]
            path = self.out_path(rel)
            os.makedirs(duong_dan_dai(os.path.dirname(path)), exist_ok=True)
            with open(duong_dan_dai(path), "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            st.update({
                "status": "done",
                "chars": len(text),
                "ts": time.time(),
                "out": path.replace("\\", "/"),
                "nguon": GEMMA_MODEL,             # <- danh dau da fallback
                "gemma_xong": True,
                "gemma_che_do": ket_qua.get("che_do", ""),
                "gemma_khuc_hong": ket_qua.get("khuc_hong", []),
                "loi_gemini": st.get("error", ""),
            })
            self.state[rel] = st
            self._save_state()
            return True

    def danh_sach_gemma(self):
        """Nhung file da phai dung duong lui Gemma - de bao cao lai cho nguoi dung."""
        with _lock:
            ra = []
            for j in self.jobs.values():
                st = self.state.get(j["rel"]) or {}
                if st.get("nguon") == GEMMA_MODEL or st.get("gemma_hong"):
                    ra.append({
                        "rel": j["rel"],
                        "ten": j["name"],
                        "thu_muc": j["rel"].rsplit("/", 1)[0] if "/" in j["rel"] else ".",
                        "trang": self.so_trang(j["abs"]),
                        "xong": bool(st.get("gemma_xong")),
                        "che_do": st.get("gemma_che_do", ""),
                        "khuc_hong": st.get("gemma_khuc_hong", []),
                        "ky_tu": st.get("chars", 0),
                        "loi_gemini": st.get("loi_gemini") or st.get("error", ""),
                        "loi_gemma": st.get("gemma_hong", ""),
                    })
            return sorted(ra, key=lambda x: x["rel"])

    def bao_cao(self):
        """Liet ke file HONG va file CHUA CHAY, gom theo thu muc."""
        with _lock:
            self._reap_leases()
            theo_thu_muc = {}
            for j in self.jobs.values():
                rel = j["rel"]
                thu_muc = rel.rsplit("/", 1)[0] if "/" in rel else "."
                o = theo_thu_muc.setdefault(
                    thu_muc, {"thu_muc": thu_muc, "tong": 0, "xong": 0, "hong": [], "cho": []})
                o["tong"] += 1
                if self.is_done(rel):
                    o["xong"] += 1
                    continue
                st = self.state.get(rel) or {}
                muc = {"ten": j["name"], "rel": rel, "trang": self.so_trang(j["abs"]),
                       "lan_thu": st.get("attempts", 0), "loi": st.get("error", "")}
                if st.get("status") == "failed":
                    muc["het_luot"] = st.get("attempts", 0) >= MAX_ATTEMPTS
                    o["hong"].append(muc)
                else:
                    o["cho"].append(muc)
            ds = sorted(theo_thu_muc.values(), key=lambda x: x["thu_muc"])
            return {
                "thu_muc": ds,
                "tong_hong": sum(len(x["hong"]) for x in ds),
                "tong_cho": sum(len(x["cho"]) for x in ds),
                "tong_xong": sum(x["xong"] for x in ds),
                "tong": sum(x["tong"] for x in ds),
            }

    def stats(self):
        with _lock:
            self._reap_leases()
            total = len(self.jobs)
            done = failed = 0
            failures = []
            for j in self.jobs.values():
                rel = j["rel"]
                if self.is_done(rel):
                    done += 1
                    continue
                st = self.state.get(rel) or {}
                if st.get("status") == "failed" and st.get("attempts", 0) >= MAX_ATTEMPTS:
                    failed += 1
                    failures.append({"rel": rel, "error": st.get("error", "")})
            return {
                "total": total, "done": done, "failed": failed,
                "processing": len(self.leases),
                "pending": max(0, total - done - failed - len(self.leases)),
                "src": self.src, "out": self.out,
                "failures": failures[:50],
            }


class Handler(BaseHTTPRequestHandler):
    store = None
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # tu log gon o duoi, khoi spam

    # -- helpers -------------------------------------------------------------
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _bytes(self, data, ctype, fname=""):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if fname:
            # HTTP header chi chua duoc latin-1. Ten file tieng Viet phai ep ve ASCII,
            # neu khong send_header() nem UnicodeEncodeError -> curl/extension nhan
            # response cut ngang (da dinh: curl exit 8). Ten that van nam trong /api/next.
            safe = re.sub(r"[^A-Za-z0-9._-]", "_", fname.encode("ascii", "ignore").decode("ascii"))
            self.send_header("Content-Disposition", 'inline; filename="%s"' % (safe or "file"))
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    # -- routes --------------------------------------------------------------
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        s = Handler.store
        try:
            if u.path in ("/", "/health"):
                return self._json({"ok": True, "service": "gemini-ocr-bridge", "stats": s.stats()})

            if u.path == "/api/stats":
                d = {"ok": True}
                d.update(s.stats())
                return self._json(d)

            if u.path == "/api/gemma":
                return self._json({"ok": True, "model": GEMMA_MODEL,
                                   "danh_sach": s.danh_sach_gemma()})

            if u.path == "/api/report":
                return self._json({"ok": True, **s.bao_cao()})

            if u.path == "/api/rescan":
                n = s.rescan()
                d = {"ok": True, "found": n}
                d.update(s.stats())
                return self._json(d)

            if u.path == "/api/next":
                worker = (q.get("worker") or ["w"])[0]
                job = s.next_job(worker)
                if job:
                    say("[bridge] -> phat job %s  %s" % (job["id"], job["rel"]))
                return self._json({"ok": True, "job": job})

            if u.path.startswith("/api/file/"):
                jid = u.path.rsplit("/", 1)[-1]
                j = s.jobs.get(jid)
                if not j:
                    return self._json({"ok": False, "error": "not found"}, 404)
                with open(j["abs"], "rb") as f:
                    data = f.read()
                ctype = "application/pdf" if j["name"].lower().endswith(".pdf") else "application/octet-stream"
                return self._bytes(data, ctype, j["name"])

            return self._json({"ok": False, "error": "route khong ton tai"}, 404)
        except Exception as e:
            return self._json({"ok": False, "error": "%s: %s" % (type(e).__name__, e)}, 500)

    def do_POST(self):
        u = urlparse(self.path)
        s = Handler.store
        try:
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            body = json.loads(raw.decode("utf-8") or "{}")

            if u.path == "/api/done":
                jid = body.get("id")
                text = body.get("text") or ""
                if len(text.strip()) < 20:
                    s.fail(jid, "text rong/qua ngan")
                    return self._json({"ok": False, "error": "text qua ngan - coi nhu fail"}, 400)
                ok, info = s.finish(jid, text)
                if ok:
                    say("[bridge] OK %7d ky tu -> %s" % (len(text), info))
                    return self._json({"ok": True, "path": info, "chars": len(text)})
                return self._json({"ok": False, "error": info}, 400)

            if u.path == "/api/fail":
                jid = body.get("id")
                err = body.get("error") or "unknown"
                tam = bool(body.get("tam_thoi"))
                s.fail(jid, err, tam_thoi=tam)
                say("[bridge] %s %s: %s" % ("TAM-HOAN" if tam else "FAIL", jid, err[:160]))
                return self._json({"ok": True, "tam_thoi": tam})

            if u.path == "/api/requeue":
                n = s.requeue_failed()
                return self._json({"ok": True, "requeued": n})

            return self._json({"ok": False, "error": "route khong ton tai"}, 404)
        except Exception as e:
            return self._json({"ok": False, "error": "%s: %s" % (type(e).__name__, e)}, 500)


def tho_gemma(store, moi_khuc, nghi_giay=30):
    """Luong nen: file nao het luot qua Gemini web thi goi Gemma OCR.

    Chay o luong rieng de khong chan HTTP server. Moi lan chi lam 1 file — Gemma cham
    (1-2 phut/file) va con phai chia han muc key voi cac viec khac.
    """
    if ocr_pdf is None:
        say("[gemma] khong nap duoc gemma_ocr (%s) - tat duong lui" % globals().get("_loi_gemma", "?"))
        return
    qlk = QuanLyKey(model=GEMMA_MODEL)
    if not qlk.keys:
        say("[gemma] khong thay GEMMA_API_KEY* trong .env - tat duong lui")
        return
    n_song = qlk.kiem_tra(hien_thi=False)
    say("[gemma] duong lui BAT | model %s | %d/%d key qua kiem tra nhanh"
        % (GEMMA_MODEL, n_song, len(qlk.keys)))
    da_sau = False

    while True:
        try:
            ds = store.het_luot()
            if not ds:
                time.sleep(nghi_giay)
                continue
            # Chi kiem tra SAU (goi that) khi sap dung den — tranh dot han muc luc khong can.
            if not da_sau:
                qlk.kiem_tra_sau(hien_thi=False)
                da_sau = True
                say("[gemma] kiem tra sau: %d/%d key sinh noi dung duoc"
                    % (qlk.con_song(), len(qlk.keys)))

            jid, j = ds[0]
            say("[gemma] nhan lai: %s" % j["rel"])
            kq = ocr_pdf(j["abs"], model=GEMMA_MODEL, qlk=qlk, moi_khuc=moi_khuc,
                         log=lambda m: say("[gemma]" + m))
            if store.ghi_gemma(jid, kq):
                say("[gemma] OK %d ky tu (%s) -> %s" % (len(kq["text"]), kq["che_do"], j["rel"]))
            else:
                say("[gemma] HONG: %s -> %s" % (kq.get("ly_do", "?"), j["rel"]))
        except Exception as e:
            say("[gemma] loi vong lap: %s" % str(e)[:200])
            time.sleep(nghi_giay)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", ".."))   # project/gemini_ocr -> goc repo

    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--src", default=os.path.join(root, "data", "raw"))
    ap.add_argument("--out", default=os.path.join(root, "data", "clean_data"))
    ap.add_argument("--state", default=os.path.join(here, "state.json"))
    ap.add_argument("--only", default="",
                    help='Chi chay cac file co duong dan bat dau bang chuoi nay, '
                         'vd --only "pdf/Khac". Cay thu muc trong clean_data van giu nguyen.')
    ap.add_argument("--khong-gemma", action="store_true",
                    help="Tat duong lui Gemma (mac dinh BAT)")
    ap.add_argument("--gemma-moi-khuc", type=int, default=5,
                    help="Ca file hong thi cat PDF thanh khuc bao nhieu trang (mac dinh 5)")
    ap.add_argument("--flatten-top", action="store_true",
                    help="Bo cap thu muc tren cung (pdf/, doc_new/) khi ghi sang clean_data")
    a = ap.parse_args()

    if not os.path.isdir(a.src):
        say("Khong thay thu muc nguon: %s" % a.src)
        sys.exit(1)

    Handler.store = Store(a.src, a.out, a.state, a.flatten_top, a.only)
    st = Handler.store.stats()
    line = "-" * 68
    say(line)
    say("  Gemini OCR Bridge   http://127.0.0.1:%d" % a.port)
    say("  Nguon : %s" % st["src"])
    say("  Dich  : %s" % st["out"])
    if a.only:
        say("  Loc   : chi duong dan bat dau bang  %s" % a.only)
    say("  File  : %d tai lieu | da xong %d | con %d" % (st["total"], st["done"], st["pending"]))
    say(line)

    if not a.khong_gemma:
        threading.Thread(target=tho_gemma, args=(Handler.store, a.gemma_moi_khuc),
                         daemon=True).start()

    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    srv.daemon_threads = True
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[bridge] dung.")


if __name__ == "__main__":
    main()
