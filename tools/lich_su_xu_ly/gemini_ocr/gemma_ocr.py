# -*- coding: utf-8 -*-
"""Duong lui khi Gemini web that bai: goi thang API Gemma 31B (gemma-4-31b-it).

Nguyen tac giu dung yeu cau:
  - GUI THANG FILE PDF (application/pdf), KHONG render anh PNG.
  - Ca file that bai -> CAT PDF thanh nhieu PDF nho hon roi GHEP ket qua lai.
  - Xoay key + KIEM TRA KEY TRUOC KHI REQUEST.

Dung duoc doc lap:
    python gemma_ocr.py "duong_dan.pdf"              # OCR 1 file, in ra man hinh
    python gemma_ocr.py "duong_dan.pdf" --out a.txt
    python gemma_ocr.py --kiem-key                   # chi kiem tra suc khoe key
"""
import argparse
import io
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sach_hoa import lam_sach, kiem_dinh  # noqa: E402

try:
    import pymupdf
except ImportError:
    pymupdf = None

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

MODEL = "gemma-4-31b-it"
PROMPT = "Đọc PDF này cho tôi và OCR ra txt cho tôi (output dưới dạng plaintext để tôi copy)"
SO_TRANG_MOI_KHUC = 5        # cat nho bao nhieu trang mot khuc
# KHONG dat timeout thi mot request treo la ket VINH VIEN (da gap: 25 phut, 2.8s CPU,
# nam cho mang). Ca file thi cho lau hon vi tai lieu dai; tung khuc thi ngan.
TIMEOUT_CA_FILE_MS = 6 * 60 * 1000
TIMEOUT_MOI_KHUC_MS = 4 * 60 * 1000
HOAN_KHI_QUA_TAI = 90        # 429 -> nghi key nay bao nhieu giay
# Han muc thuong la 15 request/phut/key -> moi key nghi it nhat 4.2s giua 2 lan dung.
# Khong chan nhip thi chay song song se dam 429 lien tuc roi phai hoan 90s, cham hon nhieu.
# 4.0 chu khong phai 7.0: gian cach nay cong voi so luong luong quyet dinh thong luong.
# Gemini Flash Lite cho 15 luot/phut moi key (Gemma 31B cho 30), tuc 4 giay mot luot
# van con du bien an toan. Voi 17 key thi suc chua la 17/4 = 4,2 luot/giay.
KHOANG_CACH_MOI_KEY = 4.0
CHO_KEY_TOI_DA = 180         # het key ranh thi CHO, khong bao hong ngay
# Tai lieu dai thi gui ca file GAN NHU CHAC CHAN dinh RECITATION (do lai: 45 trang -> hong).
# Thu roi moi cat la dot toi 6 phut cho mot lan biet truoc la hong -> nhay thang sang cat.
NGUONG_CA_FILE = 8           # tren bao nhieu trang thi BO QUA buoc gui ca file
# Con so 2 nay dat tu hoi chay Gemma 31B mot minh voi it key. Gio co 17 key song va
# uu tien Flash Lite, nut that khong con nam o key nua ma o so luong: 4 luong x 2 khuc
# = 8 luot dong thoi, chi dung 11% suc chua cua bo key. Nang len 3.
SONG_SONG_KHUC = 3
LAN_THU_MOI_LUOT = 3         # so lan thu voi loi THAT SU (khong tinh 429/503/504)
LAN_THU_TAM_THOI = 12        # 429/503/504 la tam thoi -> thu lai nhieu hon, co cho
# 21 key KHONG co nghia la 21 han muc doc lap: nhieu key co the thuoc CUNG mot project
# nen dung chung quota. Do thuc te: 24 request dong thoi -> 429 hang loat.
# Loi CUA DICH VU, khong phai cua key: cho roi thu lai la qua. Phai co ca "500"/"INTERNAL"
# — Gemma tra 500 rai rac tren moi key, thieu no thi vong thu lai thoat ngay o lan dau,
# chua kip lui sang model du phong, va key tot bi danh dau chet oan.
LOI_TAM_THOI = ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "504",
                "DEADLINE_EXCEEDED", "500", "INTERNAL")


def _say(msg):
    try:
        print(msg, flush=True)
    except Exception:
        pass


# ── Quan ly key ───────────────────────────────────────────────────────────────
class QuanLyKey:
    """Xoay key theo vong tron, biet key nao chet / dang qua tai.

    VI SAO PHAI KIEM TRA TRUOC: .env co ca key dang 'AQ.Ab...' (khong dung duoc voi
    generativelanguage API) lan key da bi thu hoi. Khong loc truoc thi moi lan OCR
    deu tieu ton mot luot goi that bai roi moi biet.
    """

    def __init__(self, env_path=None, model=MODEL):
        self.model = model
        self.keys = []          # [{"ten","key","song","ly_do","hoan_den","dung","hong"}]
        self._i = 0
        self._lock = threading.RLock()
        self._nap(env_path)

    def _nap(self, env_path):
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path or (Path(__file__).resolve().parents[1] / ".env"))
        except ImportError:
            pass
        for ten, gt in os.environ.items():
            if not ten.startswith("GEMMA_API_KEY") or not gt:
                continue
            gt = gt.strip().strip('"').strip("'")
            if not gt:
                continue
            # KHONG loc theo tien to. Da tung loc "chi nhan AIza" -> bo mat 15/21 key,
            # trong khi key dang AQ.Ab8... goi generativelanguage API binh thuong.
            # Key nao thuc su dung duoc thi kiem_tra() se noi, khong doan theo hinh dang.
            self.keys.append({"ten": ten, "key": gt, "song": None, "ly_do": "",
                              "hoan_den": 0, "dung": 0, "hong": 0, "lan_cuoi": 0.0})

    # -- kiem tra suc khoe --------------------------------------------------
    def kiem_tra_sau(self, hien_thi=True):
        """Goi THAT 1 request sinh noi dung cuc ngan.

        VI SAO CAN: liet ke model van OK voi key ma du an da bi khoa quyen — luc do
        request that moi tra 403 PERMISSION_DENIED. Da gap dung ca nay o GEMMA_API_KEY_17.
        Kiem tra sau tra gia bang 1 request ti hon, doi lai khong phat key chet ra dung.
        """
        from concurrent.futures import ThreadPoolExecutor
        from google import genai
        from google.genai import types

        def _thu(k):
            if k["song"] is False:
                return
            # THU LAI 3 LUOT, CHO 90s: dich vu Gemma hay tra 500 INTERNAL / 504 timeout
            # mot cach ngau nhien. Truoc day chi thu 1 luot voi 30s -> gap dung luc dich
            # vu cham la gach oan hang loat key TOT. Da do that: cung mot bo key, lan
            # kham bao 6/21 song, lan sau bao 17/21 — khac nhau chi vi so luot thu.
            # Loi 401/403 thi dut khoat, khong thu lai (thu cung khong doi).
            s = ""
            for lan in range(3):
                try:
                    c = genai.Client(api_key=k["key"],
                                     http_options=types.HttpOptions(timeout=90 * 1000))
                    r = c.models.generate_content(
                        model=self.model, contents=["ok"],
                        config=types.GenerateContentConfig(temperature=0.0,
                                                           max_output_tokens=5))
                    if not (r.text or "").strip() and not r.candidates:
                        s = "gọi được nhưng không trả nội dung"
                        continue
                    k["song"], k["ly_do"] = True, ""
                    return
                except Exception as e:
                    s = str(e)
                    if any(x in s for x in ("401", "403", "UNAUTHENTICATED",
                                            "PERMISSION_DENIED", "API_KEY_INVALID")):
                        break
                    time.sleep(3)
            # Thu het 3 luot van hong. 429/503/504/500 la loi CUA DICH VU, khong phai key
            # hong: chi hoan lai roi dung tiep. Truoc day gop chung -> mot model cham
            # (gemini-3.7-flash tra 504) giet sach 21 key, 383 file hong ngay lap tuc.
            if _la_tam_thoi(s) or "500" in s or "INTERNAL" in s:
                k["hoan_den"] = time.time() + HOAN_KHI_QUA_TAI
                k["ly_do"] = "dịch vụ bận (%s), hoãn %ds" % (s[:24], HOAN_KHI_QUA_TAI)
            else:
                k["song"], k["ly_do"] = False, s[:110]

        # 21 key goi tuan tu la vai phut. Chay song song, moi key mot luong.
        with ThreadPoolExecutor(max_workers=10) as ex:
            list(ex.map(_thu, self.keys))

        song = [k for k in self.keys if k["song"] is not False]
        if hien_thi:
            _say("Kiểm tra sâu (gọi thật): %d/%d key sinh nội dung được" % (len(song), len(self.keys)))
            for k in self.keys:
                if k["song"] is False or k["hoan_den"] > time.time():
                    _say("   %s %-20s %s" % ("✖" if k["song"] is False else "⏸", k["ten"], k["ly_do"]))
        return len(song)

    def kiem_tra(self, hien_thi=True):
        """Goi 1 request RE (liet ke model) de xac nhan key con dung duoc."""
        import json as _json
        import urllib.error
        import urllib.request

        from concurrent.futures import ThreadPoolExecutor

        def _thu(k):
            u = ("https://generativelanguage.googleapis.com/v1beta/models?key=%s&pageSize=200"
                 % k["key"])
            try:
                d = _json.load(urllib.request.urlopen(u, timeout=25))
                ten_mo_hinh = [m["name"].split("/")[-1] for m in d.get("models", [])]
                if self.model in ten_mo_hinh:
                    k["song"], k["ly_do"] = True, ""
                else:
                    k["song"], k["ly_do"] = False, "không thấy model %s" % self.model
            except urllib.error.HTTPError as e:
                than = e.read().decode("utf-8", "replace")[:120]
                k["song"], k["ly_do"] = False, "HTTP %s %s" % (e.code, than)
            except Exception as e:
                k["song"], k["ly_do"] = False, str(e)[:120]

        with ThreadPoolExecutor(max_workers=10) as ex:
            list(ex.map(_thu, self.keys))

        song = [k for k in self.keys if k["song"]]
        if hien_thi:
            _say("Kiểm tra key: %d/%d dùng được (model %s)" % (len(song), len(self.keys), self.model))
            for k in self.keys:
                if not k["song"]:
                    _say("   ✖ %-20s %s" % (k["ten"], k["ly_do"]))
        return len(song)

    # -- xoay key -----------------------------------------------------------
    def _lay_ngay(self):
        """Key dung duoc NGAY (con song, het hoan, du gian cach nhip). None neu chua co."""
        n = len(self.keys)
        bay = time.time()
        for _ in range(n):
            k = self.keys[self._i % n] if n else None
            self._i += 1
            if not k:
                return None
            if k["song"] is False:
                continue
            if k["hoan_den"] > bay:
                continue
            if bay - k["lan_cuoi"] < KHOANG_CACH_MOI_KEY:
                continue
            k["lan_cuoi"] = bay
            return k
        return None

    def lay(self, cho=True):
        """Key tiep theo. Neu moi key deu dang ban/hoan thi CHO cho toi khi co.

        Truoc day tra None ngay -> job hong oan chi vi dung luc tat ca key ban.
        Gio doi den khi key gan nhat ranh (toi da CHO_KEY_TOI_DA giay).
        """
        han = time.time() + (CHO_KEY_TOI_DA if cho else 0)
        while True:
            with self._lock:
                k = self._lay_ngay()
                if k:
                    return k
                song = [x for x in self.keys if x["song"] is not False]
                if not song:
                    return None
                bay = time.time()
                cho_toi = min(max(x["hoan_den"], x["lan_cuoi"] + KHOANG_CACH_MOI_KEY) for x in song)
            if not cho or time.time() >= han:
                return None
            time.sleep(max(0.3, min(5.0, cho_toi - bay)))

    def bao_loi(self, k, loi):
        s = str(loi)
        with self._lock:
            k["hong"] += 1
            if "429" in s or "RESOURCE_EXHAUSTED" in s or "quota" in s.lower():
                k["hoan_den"] = time.time() + HOAN_KHI_QUA_TAI
            elif "403" in s or "API_KEY_INVALID" in s or "PERMISSION_DENIED" in s:
                k["song"], k["ly_do"] = False, s[:120]

    def bao_xong(self, k):
        with self._lock:
            k["dung"] += 1

    def con_song(self):
        return sum(1 for k in self.keys if k["song"] is not False)

    def tom_tat(self):
        return ", ".join("%s(dùng %d, hỏng %d%s)"
                         % (k["ten"].replace("GEMMA_API_KEY", "K"), k["dung"], k["hong"],
                            "" if k["song"] is not False else ", CHẾT")
                         for k in self.keys)


# ── Goi model ─────────────────────────────────────────────────────────────────
def _goi(key, model, pdf_bytes, prompt, timeout_ms=TIMEOUT_MOI_KHUC_MS):
    from google import genai
    from google.genai import types
    c = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=timeout_ms))
    r = c.models.generate_content(
        model=model,
        contents=[types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"), prompt],
        config=types.GenerateContentConfig(temperature=0.0),
    )
    ket_thuc = str(r.candidates[0].finish_reason) if r.candidates else "?"
    return (r.text or ""), ket_thuc


def _la_tam_thoi(s):
    return any(x in str(s) for x in LOI_TAM_THOI)


def _ocr_hai_tang(qlk, pdf_bytes, prompt, models, so_trang=None,
                  timeout_ms=TIMEOUT_MOI_KHUC_MS, min_ky_tu=None):
    """Thu lan luot tung model trong `models`. Model dau hong thi model sau lam.

    Dung cho yeu cau "chay bang Gemini, hong thi nhay sang Gemma": fallback o muc TUNG
    KHUC chu khong phai ca file — mot khuc dinh RECITATION khong keo ca file sang Gemma.
    """
    ly_do = "chưa thử model nào"
    for i, m in enumerate(models):
        t, gc = _ocr_mot_lan(qlk, pdf_bytes, prompt, m, so_trang, timeout_ms, min_ky_tu)
        if t:
            return t, ("%s/%s" % (m.split("-")[0], gc) if i else gc)
        ly_do = "%s: %s" % (m, gc)
    return None, ly_do


def _ocr_mot_lan(qlk, pdf_bytes, prompt, model, so_trang=None, timeout_ms=TIMEOUT_MOI_KHUC_MS,
                 min_ky_tu=None):
    """-> (text, ghi_chu) hoac (None, ly_do).

    Phan biet loi TAM THOI (429 het han muc, 503/504 qua tai) voi loi THAT (noi dung bi
    chan, ket qua khong dat). Loi tam thoi thi CHO roi thu lai nhieu lan — truoc day
    tinh chung vao 3 luot nen chi can dinh 429 ba lan la mat han mot khuc noi dung.
    """
    ly_do = "không có key dùng được"
    that = 0
    for _ in range(LAN_THU_TAM_THOI):
        if that >= LAN_THU_MOI_LUOT:
            break
        k = qlk.lay()
        if not k:
            break
        try:
            text, ket_thuc = _goi(k["key"], model, pdf_bytes, prompt, timeout_ms)
        except Exception as e:
            qlk.bao_loi(k, e)
            ly_do = "%s: %s" % (k["ten"], str(e)[:120])
            if not _la_tam_thoi(e):
                that += 1
            continue
        if not text.strip():
            qlk.bao_loi(k, ket_thuc)
            ly_do = "rỗng (finish_reason=%s)" % ket_thuc.split(".")[-1]
            # RECITATION = model TU CHOI doc lai noi dung cong khai. Thu lai cung model
            # gan nhu chac chan lai bi tu choi -> di thang sang model du phong, dung dot
            # 3 luot goi cho moi khuc. Van cho 1 lan thu lai vi no khong hoan toan on dinh.
            that += 2 if "RECITATION" in ket_thuc.upper() else 1
            continue
        qlk.bao_xong(k)
        sach, _viec = lam_sach(text)
        dat, vi_sao = kiem_dinh(sach, so_trang, min_ky_tu)
        if not dat:
            ly_do = "không đạt kiểm định: " + vi_sao
            that += 1
            continue
        return sach, k["ten"]
    return None, ly_do


def _cat_pdf(path, moi_khuc=SO_TRANG_MOI_KHUC):
    """Cat thanh nhieu PDF nho (VAN LA PDF, khong render anh) -> [(tu, den, bytes)]."""
    if not pymupdf:
        return []
    ra = []
    with pymupdf.open(path) as d:
        n = d.page_count
        for dau in range(0, n, moi_khuc):
            cuoi = min(dau + moi_khuc - 1, n - 1)
            nho = pymupdf.open()
            nho.insert_pdf(d, from_page=dau, to_page=cuoi)
            buf = io.BytesIO()
            nho.save(buf)
            nho.close()
            ra.append((dau + 1, cuoi + 1, buf.getvalue()))
    return ra


def ocr_pdf(path, prompt=PROMPT, model=MODEL, qlk=None, moi_khuc=SO_TRANG_MOI_KHUC, log=_say,
            model_lui=None):
    """OCR 1 file PDF bang Gemma.

    Buoc 1: gui NGUYEN CA FILE.
    Buoc 2: that bai -> cat thanh nhieu PDF nho, OCR tung khuc roi GHEP lai.

    -> dict {ok, text, che_do, khuc_hong, so_khuc, ly_do, key}
    """
    path = Path(path)
    # Gemma API nhan PDF, KHONG nhan .doc/.docx (Word nhi phan). Gui dai voi mime
    # application/pdf thi hong, ma pymupdf cung khong mo duoc de cat khuc.
    # Duong Gemini web thi dinh thang .doc len duoc -> de duong do lo.
    if path.suffix.lower() != ".pdf":
        return {"ok": False, "text": "", "che_do": "-", "khuc_hong": [], "so_khuc": 0,
                "ly_do": "định dạng %s — Gemma chỉ nhận PDF, dùng đường Gemini web hoặc "
                         "chuyển sang PDF trước" % path.suffix}
    data = path.read_bytes()
    models = [model] + ([model_lui] if model_lui and model_lui != model else [])
    qlk = qlk or QuanLyKey(model=model)
    if all(k["song"] is None for k in qlk.keys):
        qlk.kiem_tra(hien_thi=False)
    if qlk.con_song() == 0:
        return {"ok": False, "ly_do": "không còn key nào dùng được", "che_do": "-",
                "text": "", "khuc_hong": [], "so_khuc": 0}

    trang = 0
    if pymupdf and path.suffix.lower() == ".pdf":
        try:
            with pymupdf.open(path) as d:
                trang = d.page_count
        except Exception:
            trang = 0

    # ── Bước 1: nguyên cả file (chỉ với tài liệu ngắn) ──
    ghi_chu = "bỏ qua (tài liệu dài)"
    if trang and trang > NGUONG_CA_FILE:
        log("  Gemma: %d trang > %d → cắt luôn, khỏi thử cả file" % (trang, NGUONG_CA_FILE))
    else:
        log("  Gemma: gửi nguyên file (%.0f KB, %d trang)..." % (len(data) / 1024, trang))
        t0 = time.perf_counter()
        text, ghi_chu = _ocr_hai_tang(qlk, data, prompt, models, trang, TIMEOUT_CA_FILE_MS)
        if text:
            log("  Gemma: xong nguyên file %.0fs, %d ký tự [%s]"
                % (time.perf_counter() - t0, len(text), ghi_chu))
            return {"ok": True, "text": text, "che_do": "nguyên file", "khuc_hong": [],
                    "so_khuc": 1, "ly_do": "", "key": ghi_chu}

    # ── Bước 2: cắt nhỏ rồi ghép ──
    log("  Gemma: cắt %d trang/khúc (%s)" % (moi_khuc, ghi_chu))
    khuc = _cat_pdf(path, moi_khuc)
    if khuc:
        log("  %d trang → %d khúc, chạy %d khúc cùng lúc, ước %.0f phút"
            % (trang, len(khuc), min(SONG_SONG_KHUC, len(khuc)),
               len(khuc) / max(1, min(SONG_SONG_KHUC, len(khuc))) * 100 / 60.0))
    if not khuc:
        return {"ok": False, "ly_do": "không cắt được PDF (thiếu pymupdf?): " + ghi_chu,
                "che_do": "-", "text": "", "khuc_hong": [], "so_khuc": 0}

    phan, hong = [], []
    for (tu, den, b) in khuc:
        # Nguong theo SO TRANG cua khuc, khong dung nguong ca file: trang ky ten thua chu
        # van la noi dung hop le, loai no la mat that.
        t, gc = _ocr_hai_tang(qlk, b, prompt, models, den - tu + 1, TIMEOUT_MOI_KHUC_MS,
                              min_ky_tu=max(60, 40 * (den - tu + 1)))
        if t:
            phan.append(t.strip())
            log("    trang %2d-%-2d: %5d ký tự [%s]" % (tu, den, len(t), gc))
        else:
            hong.append({"tu": tu, "den": den, "ly_do": gc})
            phan.append("[[TRANG %d-%d KHÔNG OCR ĐƯỢC: %s]]" % (tu, den, gc))
            log("    trang %2d-%-2d: HỎNG (%s)" % (tu, den, gc))

    text = "\n\n".join(phan).strip() + "\n"
    # THIEU DU MOT KHUC LA HONG. Truoc day "vot duoc it nhat 1 khuc la coi nhu xong"
    # -> file mat 15 trang dau van duoc ghi ra va danh dau xong, khong bao gio chay lai.
    ok = not hong
    return {"ok": ok, "text": text, "che_do": "cắt %d trang/khúc" % moi_khuc,
            "models": models,
            "khuc_hong": hong, "so_khuc": len(khuc),
            "ly_do": "" if ok else "thiếu %d/%d khúc (%s)" % (
                len(hong), len(khuc), hong[0]["ly_do"][:60]), "key": ""}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--moi-khuc", type=int, default=SO_TRANG_MOI_KHUC)
    ap.add_argument("--kiem-key", action="store_true", help="chi kiem tra suc khoe key roi thoat")
    a = ap.parse_args()

    qlk = QuanLyKey(model=a.model)
    if not qlk.keys:
        _say("Không thấy GEMMA_API_KEY* dạng AIza trong .env")
        sys.exit(1)
    qlk.kiem_tra()
    if a.kiem_key:
        return
    if not a.pdf:
        ap.error("thiếu đường dẫn PDF")

    r = ocr_pdf(a.pdf, model=a.model, qlk=qlk, moi_khuc=a.moi_khuc)
    _say("-" * 70)
    _say("Kết quả : %s | chế độ: %s | %d ký tự"
         % ("ĐẠT" if r["ok"] else "HỎNG", r["che_do"], len(r.get("text", ""))))
    if r["khuc_hong"]:
        _say("Khúc hỏng: %s" % ", ".join("%d-%d" % (h["tu"], h["den"]) for h in r["khuc_hong"]))
    if not r["ok"]:
        _say("Lý do  : %s" % r["ly_do"])
    _say("Key    : %s" % qlk.tom_tat())
    if r.get("text"):
        if a.out:
            Path(a.out).write_text(r["text"], encoding="utf-8", newline="\n")
            _say("Đã ghi : %s" % a.out)
        else:
            _say("-" * 70)
            _say(r["text"][:1200])


if __name__ == "__main__":
    main()
