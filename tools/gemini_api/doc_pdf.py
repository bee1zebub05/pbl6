# -*- coding: utf-8 -*-
"""Doc thang tu ban scan PDF bang model thi giac, de doi chieu voi ban .txt.

    python tools/gemini_api/doc_pdf.py 0021 --trang 8-10
    python tools/gemini_api/doc_pdf.py 0246 --trang 236-240 --ra /tmp/a.txt

Dung khi ban .txt co cho nghi la OCR sai ma cac luot OCR san co deu hong nhu
nhau — luc do phai quay ve chinh ban scan. Ket qua GHI RA FILE de nguoi doi
chieu, KHONG tu dong sua gi vao corpus.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import chay_json as CH  # noqa: E402  — dung lai be key va ham goi API

GOC = Path(__file__).resolve().parents[2]
# Ban scan goc nam NGOAI repo (F:/DUT4/PBL6/data/raw), khong phai trong pbl6.
RAW = GOC / "data" / "raw"
if not any(RAW.rglob("*.pdf")):
    RAW = GOC.parent / "data" / "raw"
API = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"

NHAC = """Bạn đang đọc một bản scan văn bản pháp quy tiếng Việt.

Hãy chép lại TOÀN BỘ chữ nhìn thấy trong các trang này, theo đúng thứ tự đọc.

Quy tắc:
- Chép nguyên văn. Không tóm tắt, không diễn đạt lại, không sửa lỗi chính tả
  của bản gốc.
- Trang chia hai cột thì đọc hết cột trái rồi mới sang cột phải.
- Tiêu đề điều giữ nguyên dạng nhìn thấy: "Điều 5." hay "Điều 5" hay "Điều 5:".
- Chỗ nào mờ hoặc không đọc chắc được thì ghi [không đọc được] tại đúng chỗ đó,
  TUYỆT ĐỐI không đoán.
- Mỗi trang bắt đầu bằng một dòng: ----- [Trang N] -----
- Chỉ trả về phần chép, không thêm lời dẫn nào."""


def _cat_trang(pdf: Path, tu: int, den: int) -> bytes:
    import pypdf
    r = pypdf.PdfReader(str(pdf))
    w = pypdf.PdfWriter()
    for i in range(tu - 1, min(den, len(r.pages))):
        w.add_page(r.pages[i])
    b = io.BytesIO()
    w.write(b)
    return b.getvalue()


def doc(pdf: Path, tu: int, den: int, be, model: str, han=600) -> str:
    data = _cat_trang(pdf, tu, den)
    body = {
        "contents": [{"parts": [
            {"inline_data": {"mime_type": "application/pdf",
                             "data": base64.b64encode(data).decode()}},
            {"text": NHAC},
        ]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 65536},
    }
    uoc = len(data) // 3 + 2000
    for lan in range(5):
        key = be.lay(uoc)
        if key is None:
            time.sleep(10)
            continue
        req = urllib.request.Request(
            API % model, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=han) as r:
                d = json.loads(r.read().decode("utf-8"))
            cand = (d.get("candidates") or [{}])[0]
            t = "".join(p.get("text", "")
                        for p in (cand.get("content", {}).get("parts") or []))
            if t:
                return t
            CH.noi("  trả về rỗng (finish=%s), thử lại" % cand.get("finishReason"))
        except urllib.error.HTTPError as e:
            than = ""
            try:
                than = e.read().decode("utf-8", "replace")
            except Exception:
                pass
            CH.noi("  HTTP %s %s" % (e.code, " ".join(than.split())[:70]))
            if e.code == 429:
                be.phat(key, 60)
            elif e.code == 403:
                be.bo(key)
        except Exception as e:
            CH.noi("  %s: %s" % (type(e).__name__, str(e)[:70]))
        time.sleep(3 * (lan + 1))
    raise RuntimeError("đọc trang %d-%d thất bại" % (tu, den))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ma")
    ap.add_argument("--trang", required=True, help="vd 8-10 hoặc 12")
    ap.add_argument("--khoi", type=int, default=6, help="số trang mỗi lượt gọi")
    ap.add_argument("--model", default="gemini-3.5-flash")
    ap.add_argument("--ra", default="")
    a = ap.parse_args()

    fs = [p for p in RAW.rglob(a.ma + "*.pdf")]
    if not fs:
        CH.noi("không tìm thấy PDF cho %s" % a.ma)
        return 1
    pdf = fs[0]
    m = re.match(r"(\d+)(?:-(\d+))?$", a.trang)
    tu, den = int(m.group(1)), int(m.group(2) or m.group(1))

    keys = re.findall(r'^GEMMA_API_KEY[_0-9]*\s*=\s*"?([^"\s]+)',
                      io.open(CH.ENV, encoding="utf-8", errors="replace").read(), re.M)
    be = CH.BeKey(CH.loc_key_song(keys, a.model))
    CH.noi("[pdf] %s · trang %d-%d · %s" % (pdf.name[:40], tu, den, a.model))

    ra = []
    for i in range(tu, den + 1, a.khoi):
        j = min(i + a.khoi - 1, den)
        CH.noi("  đọc trang %d-%d…" % (i, j))
        ra.append(doc(pdf, i, j, be, a.model))
    txt = "\n".join(ra)

    dich = Path(a.ra) if a.ra else (GOC / "data" / "processed" /
                                    ("_doc_lai_pdf/%s_trang%d-%d.txt" % (a.ma, tu, den)))
    dich.parent.mkdir(parents=True, exist_ok=True)
    io.open(dich, "w", encoding="utf-8", newline="\n").write(txt)
    CH.noi("[pdf] ghi %d ký tự -> %s" % (len(txt), dich))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
