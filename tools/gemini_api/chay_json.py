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
SCHEMA = GOC / "legal_knowledge_graph" / "schema" / "document.schema.json"
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
RPM_MOI_KEY = 15          # han muc that cua flash-lite, do tren bang Google AI Studio
TPM_MOI_KEY = 250_000     # han muc token/phut moi key
TPM_AN_TOAN = 0.8         # chi dung 80%, chua cho phan prompt va sai so uoc luong
TOKEN_MOI_KB = 305        # do that: 62 KB -> 18.821 token


class BeKey:
    """Xoay key, CHAN DUNG han muc tung key thay vi xoay vong mu.

    Moi key duoc 15 luot/phut. Xoay vong khong dem thi vao luc cao diem nhieu
    luong co the dap cung mot key trong cung mot phut -> 429, roi ca be cung
    dinh day chuyen. Dem bang cua so truot 60 giay thi khong bao gio vuot.

    Phai dem CA HAI, vi tran nao chat hon la tuy co van ban:

      - van ban trung vi 29 KB ~ 8.800 token: 250K/8.800 = 28 luot/phut, rong
        hon RPM 15  -> RPM la tran
      - van ban dot 2 co 34.000 token: 15 luot x 34K = 510K, gap doi TPM
        -> TPM la tran

    Chi dem luot thi dot 2 chay den cuoi la dinh 429 hang loat (6 file hong,
    deu la file 100-256 KB). Nen moi cua so 60 giay giu ca so luot lan so
    token da tieu cua tung key.
    """

    def __init__(self, keys, rpm=RPM_MOI_KEY, tpm=int(TPM_MOI_KEY * TPM_AN_TOAN)):
        self.keys = list(keys)
        self.rpm = rpm
        self.tpm = tpm
        self.khoa = threading.Lock()
        self.i = 0
        self.nghi_toi = {}                 # key -> thoi diem duoc dung lai
        self.moc = {k: [] for k in self.keys}   # key -> [(thoi diem, token)]

    def lay(self, uoc_token=0, cho_toi_da=300):
        """Tra ve key con ca suat luot lan suat token. Het thi CHO."""
        # Van ban to hon ca han muc mot phut (0245, 0246) thi khong key nao du
        # suat, vong lap se cho den het gio roi tra None. Ha yeu cau xuong dung
        # bang tran: doi cua so rong roi cho di, de API tu tu choi neu that su
        # qua kho, con hon treo.
        uoc_token = min(uoc_token, self.tpm)
        het = time.time() + cho_toi_da
        while True:
            with self.khoa:
                gio = time.time()
                for _ in range(len(self.keys)):
                    k = self.keys[self.i % len(self.keys)]
                    self.i += 1
                    if self.nghi_toi.get(k, 0) > gio:
                        continue
                    m = self.moc[k] = [x for x in self.moc[k] if x[0] > gio - 60]
                    if len(m) < self.rpm and sum(x[1] for x in m) + uoc_token <= self.tpm:
                        m.append((gio, uoc_token))
                        return k
            if time.time() > het:
                return None
            time.sleep(1.0)

    def phat(self, k, giay=60):
        with self.khoa:
            self.nghi_toi[k] = time.time() + giay

    def bo(self, k):
        """Key chet han — bo khoi be, khong xoay vao nua."""
        with self.khoa:
            if k in self.keys and len(self.keys) > 1:
                self.keys.remove(k)
                self.moc.pop(k, None)
                return len(self.keys)
        return len(self.keys)


def loc_key_song(keys, model):
    """Thu tung key mot lan, bo nhung key bi tu choi han (403 denied access)."""
    body = json.dumps({"contents": [{"parts": [{"text": "ping"}]}],
                       "generationConfig": {"maxOutputTokens": 8}}).encode()

    def thu(k):
        req = urllib.request.Request(
            API % model, data=body,
            headers={"Content-Type": "application/json", "x-goog-api-key": k})
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                r.read()
            return k, None
        except urllib.error.HTTPError as e:
            if e.code == 403:
                return k, "403 " + e.read().decode("utf-8", "replace")[:60]
            return k, None                  # 429/503 la nhat thoi, van giu key
        except Exception:
            return k, None

    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(6) as ex:
        kq = list(ex.map(thu, keys))
    song = [k for k, e in kq if not e]
    for k, e in kq:
        if e:
            noi("[api] bỏ 1 key bị từ chối hẳn: %s"
                % " ".join(e.split())[:90])
    return song


# ============================================================
# GOI API
# ============================================================
def _quota(than: str) -> str:
    """Rut ten han muc tu than loi 429 cua Google. '' neu khong thay."""
    m = re.search(r"quotaId\"?\s*:\s*\"?([A-Za-z]+)", than)
    if m:
        return m.group(1)
    m = re.search(r"(GenerateRequests?Per[A-Za-z]+)", than)
    if m:
        return m.group(1)
    m = re.search(r"\"message\"\s*:\s*\"([^\"]{0,120})", than)
    return m.group(1) if m else " ".join(than.split())[:90]


def uoc_token(prompt: str) -> int:
    """Uoc so token cua prompt. Khong can chinh xac, chi can khong duoi that."""
    return int(len(prompt) / 1024 * TOKEN_MOI_KB) + 600


def goi_api(model, prompt, be, han_giay=600):
    """-> (text, usage). Tu doi key khi 429/500, chiu thua sau 6 lan."""
    loi_cuoi = ""
    n_tok = uoc_token(prompt)
    for lan in range(8):
        key = be.lay(n_tok)
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
            than = ""
            try:
                than = e.read().decode("utf-8", "replace")
            except Exception:
                pass
            loi_cuoi = "HTTP %s%s" % (e.code, (" " + _quota(than)) if than else "")
            if e.code == 429:
                # Google noi ro dung han nao. Han PHUT thi nghi 90 giay la qua;
                # han NGAY thi cho bao lau cung vo ich — bo key khoi be luon,
                # khong thi 8 lan thu deu dot vao cung mot buc tuong.
                if "PerDay" in than:
                    con = be.bo(key)
                    noi("[api] key hết hạn NGÀY — bỏ khỏi bể, còn %d key" % con)
                else:
                    be.phat(key, 90)
            elif e.code in (500, 503):
                be.phat(key, 20)
            elif e.code == 403:
                # 403 = key bi tu choi han ("project has been denied access"),
                # khong phai het han muc. Bo hen khoi be, giu lai chi to dinh mai.
                con = be.bo(key)
                noi("[api] key dính 403 — bỏ khỏi bể, còn %d key" % con)
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
    try:
        data = json.loads(raw)
        va_nhay = 0
    except json.JSONDecodeError:
        data, va_nhay = CJ._cuu_json(raw)
        if data is None:
            raise
    if not isinstance(data, dict):
        raise RuntimeError("tang ngoai cung khong phai object")
    data["sourceFile"] = "%s/%s" % (tx.parent.name, tx.name)

    _don_dang(data, _goc_khong_co_dieu=("Điều" not in goc))
    n_may = _dem_dieu(data)
    _bu_dieu(data, goc)                     # <- toan van cat tu .txt
    _quet_duoi_chuong(data)
    n_sau = _dem_dieu(data)

    loi = CJ._validate(data)
    if loi:
        raise RuntimeError("sai schema: " + " | ".join(loi[:3]))

    canh_bao, nghi = CJ._soi_them(data, tx)
    if va_nhay:
        canh_bao = list(canh_bao) + ["va %d dau nhay thang khong escape" % va_nhay]
    thu_muc = (RA / "_nghi_ngo" if nghi else RA) / tx.parent.name
    thu_muc.mkdir(parents=True, exist_ok=True)
    dich = thu_muc / (tx.stem + ".json")
    # Lan truoc co the da ghi sang nhanh kia (nghi ngo <-> sach). Khong xoa thi
    # con lai hai ban, --va-lai va bo cham diem deu dem thanh hai file.
    kia = (RA if nghi else RA / "_nghi_ngo") / tx.parent.name / (tx.stem + ".json")
    if kia.exists():
        kia.unlink()
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


def _doc_enum(ten):
    """Lay enum tu schema cua ductran thay vi chep cung vao day."""
    try:
        d = json.loads(io.open(SCHEMA, encoding="utf-8").read())
    except Exception:
        return set()
    ra = set()

    def di(o, k=""):
        if isinstance(o, dict):
            if k == ten and isinstance(o.get("enum"), list):
                ra.update(x for x in o["enum"] if x)
            for a, b in o.items():
                di(b, a)
        elif isinstance(o, list):
            for x in o:
                di(x, k)

    di(d)
    return ra


_ORG_TYPE = _doc_enum("orgType")

def _don_dang(d, _goc_khong_co_dieu=False):
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

    # 4a. Ban goc khong he co chu "Điều" ma JSON lai co Dieu -> nhan do model
    #     tu dat. Chi thi / Cong van danh muc "1. 2. 3.", model goi moi muc
    #     thanh mot Dieu. Noi dung that nhung nhan thi bia, ma nhan chinh la
    #     khoa cua node Article trong do thi. Tha khong co Dieu con hon co Dieu
    #     khong ton tai. Do duoc 4 file: 0193, 0332, 0338, 0341.
    if _goc_khong_co_dieu and (d.get("articles") or d.get("normativeContents")):
        d["articles"] = []
        for n in d.get("normativeContents") or []:
            n["articles"] = []

    # 4b. orgType khong co trong enum -> None (truong nay cho phep None).
    #     0246 tra ve 'co_quan_cua_quoc_hoi', model tu nghi ra.
    org = d.get("organization") or {}
    if org.get("orgType") and org["orgType"] not in _ORG_TYPE:
        org["orgType"] = None

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


# Cau ghi chu do chinh bo cat sinh ra. Khong dung [^.]* duoc vi trong cau co
# "ban .txt goc" — dau cham cua .txt cat cau lam doi.
_NOTE_CUA_TA = re.compile(
    r"\s*(?:\d+ Điều (?:lấy toàn văn trực tiếp|thân chính cắt thẳng)"
    r"|Văn bản lồng nhau:"
    r"|\d+ Điều của bản kèm theo được cắt thẳng)"
    r".*?(?:gốc(?: \(gồm cả bản kèm theo\))?\.|không đưa vào\.)")


def _ghi_note(data, cau):
    """Thay cau ghi chu cua BO CAT, giu nguyen phan model tu viet.

    --va-lai chay lai nhieu lan tren cung mot file; noi them moi lan thi note
    phinh ra va cac con so mau thuan nhau.
    """
    cu = _NOTE_CUA_TA.sub("", data.get("note") or "").strip()
    data["note"] = ((cu + " ") if cu else "") + cau

def _lam_dieu(cat, k):
    return {
        "number": k,
        "heading": cat[k]["tieu_de"],
        "text": cat[k]["than"],
        "isImplementationClause": bool(VD.THI_HANH.search(cat[k]["than"])),
    }


def _sap(ds):
    return sorted(ds, key=lambda x: int(
        re.match(r"\d+", x["number"].replace("Điều", "").strip()).group()))


def _gop(cu, cat, bo_qua=None):
    """Gop ban cat vao danh sach Dieu san co. KHONG BAO GIO lam mat Dieu.

    Ban cat la toan van nen thang; Dieu nao model co ma ban cat khong co thi
    GIU LAI — bo cat con sot, ghi de thang tay la tut so Dieu.

    `bo_qua`: ban cat cua CHO KHAC (ban kem theo). Chi bo Dieu nao model dat
    nham sang day THAT, do bang NOI DUNG chu khong bang so: 0227 co Dieu 2 phan
    ngoai ("Quyet dinh nay co hieu luc...") va Dieu 2 ban kem ("Trong Quy dinh
    nay...") — hai Dieu khac han, trung moi cai so.
    """
    def trung_cho_khac(a):
        c = (bo_qua or {}).get(a.get("number"))
        if not c:
            return False
        x = " ".join((a.get("text") or "").split())[:150]
        y = " ".join(c["than"].split())
        return bool(x) and (x in y or y[:150] == x)

    # Dieu model tu cho (ban cat khong co) cung phai cat duoi tieu de chuong:
    # model chep tu .txt nen dinh y het.
    giu = []
    for a in (cu or []):
        if a.get("number") in cat or trung_cho_khac(a):
            continue
        t = a.get("text") or ""
        moi_t = VD._bo_duoi_chuong(t)
        giu.append(dict(a, text=moi_t) if moi_t != t else a)
    # Lay `text` tu ban cat, nhung GIU `heading` va `isImplementationClause`
    # cua model. Tieu de may moc la "phan con lai cua dong dau", con model dat
    # tieu de theo nghia: Dieu 1 cua Quyet dinh ra "Ban hành kèm theo" thay vi
    # ca cau "Ban hành kèm theo Quyết định này Quy định về việc biên soạn...".
    o_cu = {a.get("number"): a for a in (cu or [])}
    ra = []
    for x in cat:
        m = _lam_dieu(cat, x)
        c = o_cu.get(x)
        if c:
            if (c.get("heading") or "").strip():
                m["heading"] = c["heading"]
            if isinstance(c.get("isImplementationClause"), bool):
                m["isImplementationClause"] = c["isImplementationClause"]
        ra.append(m)
    return _sap(ra + giu)


def _cho_dat(data, cat):
    """Model da dat mach Dieu nay o dau? -> ("articles", None) | ("nd", i).

    Quyet dinh ban hanh kem theo mot Quy che thuong chi co MOT mach Dieu trong
    .txt (Dieu 1-3 cua Quyet dinh nam trong doan van, khong co tieu de rieng),
    va model dat ca mach do vao normativeContents — dung. Cu the ghi vao
    `articles` la thanh hai ban: 0051 tu 28 Dieu thanh 56.
    """
    so = set(cat)
    tot = len(so & {x.get("number") for x in (data.get("articles") or [])})
    cho = ("articles", None)
    for i, n in enumerate(data.get("normativeContents") or []):
        c = len(so & {x.get("number") for x in (n.get("articles") or [])})
        if c > tot:
            tot, cho = c, ("nd", i)
    return cho


def _quet_duoi_chuong(data):
    """Quet lai MOI Dieu, bat ke no den tu duong nao.

    _bu_dieu co nhieu nhanh (mach dau, du bo, ban kem); Dieu nam trong
    normativeContents ma van ban khong co ban kem thi khong nhanh nao cham toi.
    Ham nay chay sau cung nen khong lot. _bo_duoi_chuong luy dang, goi lai
    khong hai gi.
    """
    for nhom in [data.get("articles") or []] + [
            n.get("articles") or [] for n in (data.get("normativeContents") or [])]:
        for a in nhom:
            t = a.get("text") or ""
            m = VD._bo_duoi_chuong(t)
            if m != t:
                a["text"] = m


def _bu_dieu(data, goc):
    """Lay toan van Dieu tu .txt de vao JSON. Van ban nao cung mot duong nay.

    Model chep lai thi hay chuan hoa khoang trang, noi dong, doi khi dien dat
    lai — do tren 0090: 0/3 Dieu khop nguyen van. Ban cat tu .txt thi dung tung
    ky tu. Nen giu `heading` cua model (phan no suy ra tot) va lay `text` tu
    ban cat.

    Mach dau -> articles. Mach thu hai, neu du dai va khong phai bieu mau ->
    normativeContents (ban ban hanh kem theo). Cac mach sau deu la phu luc
    danh so lai, bo.
    """
    if VD._du_bo(goc):
        # Du Dieu ca, chi lech thu tu -> cat thang, khong can theo mach
        cat = VD._cat_tat_ca(goc)
        if len(cat) >= 2:
            o, i = _cho_dat(data, cat)
            if o == "articles":
                data["articles"] = _gop(data.get("articles"), cat)
            else:
                nd = list(data["normativeContents"])
                nd[i] = dict(nd[i], articles=_gop(nd[i].get("articles"), cat))
                data["normativeContents"] = nd
            _ghi_note(data, "%d Điều lấy toàn văn trực tiếp từ bản .txt gốc."
                      % len(cat))
            return

    mach = VD._tach_mach(goc)
    if not mach:
        return
    cat, _ = mach[0]

    kem = ten = loai = None
    if len(mach) > 1:
        c2, _ = mach[1]
        if len(c2) >= 5 and not VD._la_bieu_mau(c2):
            kem = c2
            _, _, ten, loai = VD._tach_ban_kem(goc)

    if len(cat) >= 2:
        o, i = _cho_dat(data, cat)
        if o == "articles":
            data["articles"] = _gop(data.get("articles"), cat, bo_qua=kem)
        else:
            nd = list(data["normativeContents"])
            nd[i] = dict(nd[i], articles=_gop(nd[i].get("articles"), cat))
            data["normativeContents"] = nd

    if kem:
        cu_nd = list(data.get("normativeContents") or [])
        dau = cu_nd[0] if cu_nd else {}
        data["normativeContents"] = [{
            "title": dau.get("title") or ten or "Bản ban hành kèm theo",
            "contentType": dau.get("contentType") or loai or "Quy định",
            "status": dau.get("status"),
            "idOverride": dau.get("idOverride"),
            "articles": _gop(dau.get("articles"), kem),
        }] + cu_nd[1:]

    n = len(cat) + (len(kem) if kem else 0)
    if n:
        _ghi_note(data, "%d Điều lấy toàn văn trực tiếp từ bản .txt gốc%s."
                  % (n, " (gồm cả bản kèm theo)" if kem else ""))


def va_lai(chi=None) -> int:
    """Chay lai _don_dang + _bu_dieu tren JSON DA CO, khong goi API.

    Bo cat Dieu con sua tiep (loc moc trang, phan biet trich dan voi tieu de...).
    Moi lan no kha len thi cac JSON cu van mang ban cat cu. Mode nay cat lai tu
    .txt goc va ghi de — mien phi, vi toan van von khong den tu model.
    """
    txt_theo_ma = {}
    for p in KHO_TXT.rglob("*.txt"):
        txt_theo_ma.setdefault(p.name[:4], p)

    sua = giu = hong = doi = 0

    def _doi_cho(cu, moi):
        moi.parent.mkdir(parents=True, exist_ok=True)
        cu.replace(moi)

    for j in sorted(RA.rglob("*.json")):
        ma = j.name[:4]
        if chi and ma not in chi:
            continue
        tx = txt_theo_ma.get(ma)
        if tx is None:
            noi("  ? %s  khong tim thay .txt goc" % ma)
            continue
        data = json.loads(io.open(j, encoding="utf-8").read())
        truoc = json.dumps(data, ensure_ascii=False, sort_keys=True)

        goc = io.open(tx, encoding="utf-8", errors="replace").read()
        _don_dang(data, _goc_khong_co_dieu=("Điều" not in goc))
        _bu_dieu(data, goc)
        _quet_duoi_chuong(data)

        _, nghi = CJ._soi_them(data, tx)
        dung = (RA / "_nghi_ngo" if nghi else RA) / tx.parent.name / j.name
        if json.dumps(data, ensure_ascii=False, sort_keys=True) == truoc:
            if dung != j:
                _doi_cho(j, dung)
                doi += 1
            else:
                giu += 1
            continue
        loi = CJ._validate(data)
        if loi:
            hong += 1
            noi("  x %s  va xong lai truot schema, giu nguyen ban cu: %s"
                % (ma, loi[0][:80]))
            continue
        dung.parent.mkdir(parents=True, exist_ok=True)
        io.open(dung, "w", encoding="utf-8", newline="\n").write(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        if dung != j:
            j.unlink()
            doi += 1
        sua += 1
        noi("  v %s  da va lai%s" % (ma, " (chuyen sang %s)" % (
            "nghi ngo" if nghi else "sach") if dung != j else ""))

    noi("[va-lai] sua %d · khong doi %d · xep lai thu muc %d · "
        "bo qua vi truot schema %d" % (sua, giu, doi, hong))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=MODEL_MAC_DINH)
    ap.add_argument("--luong", type=int, default=3)
    ap.add_argument("--toi-kb", type=float, default=1e9)
    ap.add_argument("--tu-kb", type=float, default=0.0)
    ap.add_argument("--chi", default="")
    ap.add_argument("--lam-lai", action="store_true", help="làm cả file đã có JSON")
    ap.add_argument("--va-lai", action="store_true",
                    help="cắt lại Điều cho JSON đã có, không gọi API")
    a = ap.parse_args()

    chi_ma = {x.strip() for x in a.chi.split(",") if x.strip()} or None
    if a.va_lai:
        return va_lai(chi_ma)

    keys = re.findall(r'^GEMMA_API_KEY[_0-9]*\s*=\s*"?([^"\s]+)',
                      io.open(ENV, encoding="utf-8", errors="replace").read(), re.M)
    noi("[api] thử %d key…" % len(keys))
    keys = loc_key_song(keys, a.model)
    be = BeKey(keys)

    da_co = {p.name[:4] for p in RA.rglob("*.json")}
    chi = chi_ma
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

    noi("[api] %s · %d key sống · %d luồng · trần %d lượt/phút"
        % (a.model, len(keys), a.luong, RPM_MOI_KEY * len(keys)))
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
