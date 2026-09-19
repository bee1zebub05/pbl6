# -*- coding: utf-8 -*-
"""Sinh JSON cho ca kho bang API CHINH THUC, chay da luong voi be key.

    python tools/gemini_api/chay_json.py --toi-kb 100            # dot 1
    python tools/gemini_api/chay_json.py --chi 0295,0090 --luong 2

Khac duong Gemini web o ba cho:

  1. Goi thang API — khong Chrome, khong tab, khong CAPTCHA, dung dieu khoan.
  2. Xoay 17 key, moi key co han muc rieng (15 luot/phut · 250K token/phut).
  3. THAN DIEU KHONG DE MODEL CHEP.

Cho (3) la quan trong nhat. Do duoc tren 0295 (70 Dieu, 62 KB):

    gemini-3.5-flash-lite    4 Dieu ·  1.730 ky tu (3%)   finish=STOP
    gemini-3.1-flash-lite    2 Dieu ·    245 ky tu (0%)   finish=STOP
    gemini-3.5-flash        70 Dieu · 55.176 ky tu (88%)  nhung 116s, 0 citations

Ban lite bat metadata/citations rat tot va nhanh, chi khong chiu chep 70 Dieu.
Ban thuong chiu chep nhung cham gap 30 lan va lai bo citations. Nen: de lite lam
phan no gioi, con toan van Dieu thi CAT THANG TU .txt — nguyen van 100%, khong
phu thuoc model co chiu chep hay khong, va khong the bi dien giai lai.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import queue
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

GOC = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GOC / "tools" / "gemini_web"))
sys.path.insert(0, str(GOC))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import cau_json as CJ          # noqa: E402  — PROMPT, _boc_json, _validate, _soi_them
import va_dieu_thieu as VD     # noqa: E402  — bo cat Dieu tu .txt

KHO_TXT = GOC / "data" / "clean" / "text_final"
RA = GOC / "data" / "kg_json"
ENV = GOC.parent / "project" / ".env"

MODEL_MAC_DINH = "gemini-3.5-flash-lite"
API = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"

_in = threading.Lock()


def noi(*a):
    with _in:
        print(*a, flush=True)


# ============================================================
# BE KEY
# ============================================================
class BeKey:
    """Xoay key theo vong. Key nao dinh 429 thi nghi mot luc roi quay lai."""

    def __init__(self, keys):
        self.keys = list(keys)
        self.khoa = threading.Lock()
        self.i = 0
        self.nghi_toi = {}                 # key -> thoi diem duoc dung lai

    def lay(self):
        with self.khoa:
            for _ in range(len(self.keys)):
                k = self.keys[self.i % len(self.keys)]
                self.i += 1
                if self.nghi_toi.get(k, 0) <= time.time():
                    return k
            return None                    # ca be dang nghi

    def phat(self, k, giay=60):
        with self.khoa:
            self.nghi_toi[k] = time.time() + giay


# ============================================================
# GOI API
# ============================================================
def goi_api(model, prompt, be, han_giay=300):
    """-> (text, usage). Tu doi key khi 429/500, chiu thua sau 6 lan."""
    loi_cuoi = ""
    for lan in range(8):
        key = be.lay()
        if key is None:
            time.sleep(20)
            continue
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 65536,
                                 "responseMimeType": "application/json"},
        }
        req = urllib.request.Request(
            API % model, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=han_giay) as r:
                d = json.loads(r.read().decode("utf-8"))
            cand = (d.get("candidates") or [{}])[0]
            txt = "".join(p.get("text", "")
                          for p in (cand.get("content", {}).get("parts") or []))
            if not txt:
                loi_cuoi = "tra ve rong (finishReason=%s)" % cand.get("finishReason")
                continue
            return txt, d.get("usageMetadata", {})
        except urllib.error.HTTPError as e:
            loi_cuoi = "HTTP %s" % e.code
            if e.code in (429, 500, 503):
                be.phat(key, 90 if e.code == 429 else 20)
            elif e.code == 403:
                # 403 o day = key het han muc ngay, khong phai sai key.
                # Cho key do nghi han, khong thi moi lan xoay lai deu dinh.
                be.phat(key, 3600)
            time.sleep(2.5 * (lan + 1) + random.random() * 2)
        except Exception as e:
            loi_cuoi = "%s: %s" % (type(e).__name__, str(e)[:80])
            time.sleep(1.5 * (lan + 1))
    raise RuntimeError("goi API that bai sau 8 lan — %s" % loi_cuoi)


# ============================================================
# MOT FILE
# ============================================================
def lam_mot(tx: Path, model, be):
    goc = io.open(tx, encoding="utf-8", errors="replace").read()
    txt, use = goi_api(model, CJ.PROMPT + "\n\n--- TOÀN VĂN ---\n\n" + goc, be)

    raw = CJ._boc_json(txt)
    if raw is None:
        raise RuntimeError("khong boc duoc JSON")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError("tang ngoai cung khong phai object")
    data["sourceFile"] = "%s/%s" % (tx.parent.name, tx.name)

    _don_dang(data)                         # <- sua may cho model hay viet sai dang
    n_may = _dem_dieu(data)
    _bu_dieu(data, goc)                     # <- toan van cat tu .txt
    n_sau = _dem_dieu(data)

    loi = CJ._validate(data)
    if loi:
        raise RuntimeError("sai schema: " + " | ".join(loi[:3]))

    canh_bao, nghi = CJ._soi_them(data, tx)
    thu_muc = (RA / "_nghi_ngo" if nghi else RA) / tx.parent.name
    thu_muc.mkdir(parents=True, exist_ok=True)
    dich = thu_muc / (tx.stem + ".json")
    io.open(dich, "w", encoding="utf-8", newline="\n").write(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return n_may, n_sau, nghi, canh_bao, use


_CHI_DIEU = re.compile(r"Điều\s+(\d{1,3}[a-zA-Z]?)")
_NGAY = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")


def _khoa_so(s):
    """Khoá so sánh số hiệu: bỏ dấu cách, hạ chữ thường. 08/NQ-HĐT == 08/nq-hđt."""
    return re.sub(r"\s+", "", (s or "")).lower() or None


def _ngay_that(s):
    m = _NGAY.match(s or "")
    if not m:
        return False
    import datetime
    try:
        datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        return True
    except ValueError:
        return False


def _don_dang(d):
    """Sua may cho model hay viet sai DANG — thuan co hoc, khong doan noi dung.

    Hai loi gap ngay o file dau tien:
      - normativeContents co muc `articles: []` rong  -> schema doi non-empty
      - targetArticle ghi "Khoản 3 Điều 2"            -> schema doi '^Điều N$'
    """
    nd = [n for n in (d.get("normativeContents") or []) if n.get("articles")]
    if nd != (d.get("normativeContents") or []):
        d["normativeContents"] = nd

    minh = _khoa_so(d.get("document", {}).get("documentNumber"))
    ds = []
    for c in d.get("citations") or []:
        ta = c.get("targetArticle")
        if ta:
            m = _CHI_DIEU.search(ta)
            c["targetArticle"] = ("Điều %s" % m.group(1)) if m else None
        # schema đặt trần 400 ký tự cho context; model hay chép nguyên cả câu dài
        ct = c.get("context")
        if ct and len(ct) > 400:
            c["context"] = ct[:397].rstrip() + "…"
        # tự trích dẫn chính mình -> bỏ, loader sẽ sinh vòng lặp
        if minh and _khoa_so(c.get("targetDocumentNumber")) == minh:
            continue
        ds.append(c)
    if len(ds) != len(d.get("citations") or []):
        d["citations"] = ds

    # signers không có tên thì không dựng được node Person
    sg = [s for s in (d.get("signers") or []) if (s.get("fullName") or "").strip()]
    if len(sg) != len(d.get("signers") or []):
        d["signers"] = sg

    # ngày phải đúng dd/mm/yyyy và CÓ THẬT; sai thì để null còn hơn nhập bừa
    doc = d.get("document") or {}
    for k in ("issueDate", "effectiveDate", "expiryDate"):
        if doc.get(k) and not _ngay_that(doc[k]):
            doc[k] = None

    for nhom in [d.get("articles") or []] + [
            n.get("articles") or [] for n in (d.get("normativeContents") or [])]:
        for a in nhom:
            m = _CHI_DIEU.search(a.get("number") or "")
            if m:
                a["number"] = "Điều %s" % m.group(1)


def _dem_dieu(d):
    return len(d.get("articles") or []) + sum(
        len(n.get("articles") or []) for n in d.get("normativeContents") or [])


def _bu_dieu(data, goc):
    """Bu Dieu thieu bang ban cat tu .txt. Dung DUNG chot an toan cua va_dieu_thieu."""
    cat, tho = VD._cat_dieu(goc)
    if len(cat) < 2 or tho != sorted(tho) or len(set(tho)) != len(tho):
        return                              # tron cot / van ban long nhau -> khong dung
    # ĐÈ toàn văn cho cả Điều model đã tự chép, không chỉ bù chỗ thiếu.
    #
    # Model chép lại thì hay chuẩn hoá khoảng trắng, nối dòng, đôi khi diễn đạt
    # lại — đo trên 0090: 0/3 Điều khớp nguyên văn. Bản cắt từ .txt thì đúng
    # từng ký tự. Giữ `heading` và `isImplementationClause` của model vì đó là
    # phần nó suy ra tốt, còn `text` thì lấy bản cắt.
    dat = 0
    for nhom in [data.get("articles") or []] + [
            n.get("articles") or [] for n in (data.get("normativeContents") or [])]:
        for a in nhom:
            c = cat.get(a.get("number"))
            if c and a.get("text") != c["than"]:
                a["text"] = c["than"]
                dat += 1

    co = {a["number"] for a in (data.get("articles") or [])}
    for n in data.get("normativeContents") or []:
        co |= {a["number"] for a in (n.get("articles") or [])}
    them = [{
        "number": k,
        "heading": cat[k]["tieu_de"],
        "text": cat[k]["than"],
        "isImplementationClause": bool(VD.THI_HANH.search(cat[k]["than"])),
    } for k in cat if k not in co]
    if not them:
        if dat:
            cu = (data.get("note") or "").strip()
            data["note"] = (cu + " " if cu else "") + (
                "%d Điều lấy toàn văn trực tiếp từ bản .txt gốc." % dat)
        return
    data["articles"] = sorted(
        (data.get("articles") or []) + them,
        key=lambda x: int(re.match(r"\d+", x["number"].replace("Điều", "").strip()).group()))
    cu = (data.get("note") or "").strip()
    data["note"] = (cu + " " if cu else "") + (
        "%d Điều lấy toàn văn trực tiếp từ bản .txt gốc." % len(them))


# ============================================================
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=MODEL_MAC_DINH)
    ap.add_argument("--luong", type=int, default=3)
    ap.add_argument("--toi-kb", type=float, default=1e9)
    ap.add_argument("--tu-kb", type=float, default=0.0)
    ap.add_argument("--chi", default="")
    ap.add_argument("--lam-lai", action="store_true", help="làm cả file đã có JSON")
    a = ap.parse_args()

    keys = re.findall(r'^GEMMA_API_KEY[_0-9]*\s*=\s*"?([^"\s]+)',
                      io.open(ENV, encoding="utf-8", errors="replace").read(), re.M)
    be = BeKey(keys)

    da_co = {p.name[:4] for p in RA.rglob("*.json")}
    chi = {x.strip() for x in a.chi.split(",") if x.strip()} or None
    viec = []
    for p in sorted(KHO_TXT.rglob("*.txt")):
        ma = p.name[:4]
        if chi and ma not in chi:
            continue
        if not a.lam_lai and ma in da_co:
            continue
        kb = p.stat().st_size / 1024
        if not (a.tu_kb <= kb <= a.toi_kb):
            continue
        viec.append(p)

    noi("[api] %s · %d key · %d luồng" % (a.model, len(keys), a.luong))
    noi("[api] %d file cần làm (đã có %d)" % (len(viec), len(da_co)))
    if not viec:
        return 0

    q = queue.Queue()
    for p in viec:
        q.put(p)
    dem = {"xong": 0, "hong": 0, "nghi": 0}
    hong = []
    t0 = time.time()

    def worker():
        while True:
            try:
                tx = q.get_nowait()
            except queue.Empty:
                return
            ma = tx.name[:4]
            try:
                n_may, n_sau, nghi, cb, use = lam_mot(tx, a.model, be)
                with _in2:
                    dem["xong"] += 1
                    dem["nghi"] += 1 if nghi else 0
                noi("  %s %s  %d→%d Điều%s  [%d/%d]"
                    % ("⚠" if nghi else "✔", ma, n_may, n_sau,
                       ("  " + "; ".join(cb)[:52]) if cb else "",
                       dem["xong"] + dem["hong"], len(viec)))
            except Exception as e:
                with _in2:
                    dem["hong"] += 1
                hong.append((ma, str(e)[:100]))
                noi("  ✖ %s  %s  [%d/%d]"
                    % (ma, str(e)[:78], dem["xong"] + dem["hong"], len(viec)))
            finally:
                q.task_done()

    _in2 = threading.Lock()
    ts = [threading.Thread(target=worker, daemon=True) for _ in range(a.luong)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    phut = (time.time() - t0) / 60
    noi("\n[api] xong %d · nghi ngờ %d · hỏng %d · %.1f phút (%.1f file/phút)"
        % (dem["xong"], dem["nghi"], dem["hong"], phut, dem["xong"] / max(phut, .01)))
    for ma, e in hong[:15]:
        noi("     ✖ %s  %s" % (ma, e))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
