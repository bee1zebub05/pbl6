"""OCR PDF bang cach gui TUNG TRANG DUOI DANG PDF 1 TRANG (khong render PNG).

Vi sao tach trang: gui ca file 19 trang thi Gemini tra finish_reason=RECITATION
(bo loc trung lap noi dung voi van ban phap quy cong khai) -> output rong, moi key deu vay.
Tach nho lam giam tin hieu "doc lai nguyen van tai lieu" nen thuong qua duoc.

Moi trang thu 2 buoc:
  1. prompt van ban thuan (dung prompt nguoi dung dung tren chat)
  2. neu RECITATION -> thu lai bang JSON theo dong (cach da chung minh hieu qua)

Chay:
    python ocr_pdf_pages.py "<file.pdf>" --out out.txt
"""
import argparse
import io
import json
import os
import random
import sys
import time
from pathlib import Path

import pymupdf
from dotenv import load_dotenv
from google import genai
from google.genai import types

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

MODEL = "gemini-3.5-flash-lite"
PROMPT_PLAIN = "Đọc PDF này cho tôi và OCR ra txt cho tôi"
PROMPT_JSON = (
    'Trả về JSON {"blocks":[{"index":n,"text":"..."}]} - mỗi dòng văn bản trong file PDF '
    "là một block, index bắt đầu từ 1, text là nội dung dòng đó.\n\n"
    "Quy tắc:\n"
    "- Giữ nguyên tiếng Việt có dấu, số hiệu văn bản, ngày tháng, số thứ tự.\n"
    '- Bảng: mỗi hàng là một block, các ô ngăn bằng " | ".\n'
    "- Không tóm tắt, không thêm bình luận."
)
SCHEMA = {
    "type": "object",
    "properties": {
        "blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"index": {"type": "integer"}, "text": {"type": "string"}},
                "required": ["index", "text"],
            },
        }
    },
    "required": ["blocks"],
}


def load_keys():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    keys = [(k, v.strip().strip('"').strip("'"))
            for k, v in os.environ.items() if k.startswith("GEMMA_API_KEY") and v]
    random.shuffle(keys)
    return keys


def page_to_pdf_bytes(doc, i):
    """Trich 1 trang thanh file PDF doc lap (van la PDF, khong phai anh)."""
    one = pymupdf.open()
    one.insert_pdf(doc, from_page=i, to_page=i)
    buf = io.BytesIO()
    one.save(buf)
    one.close()
    return buf.getvalue()


def ask(client, model, pdf_bytes, prompt, as_json):
    cfg = types.GenerateContentConfig(temperature=0.0)
    if as_json:
        cfg = types.GenerateContentConfig(
            temperature=0.0, response_mime_type="application/json", response_schema=SCHEMA
        )
    resp = client.models.generate_content(
        model=model,
        contents=[types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"), prompt],
        config=cfg,
    )
    cand = resp.candidates[0] if resp.candidates else None
    fr = str(cand.finish_reason) if cand else "?"
    text = resp.text or ""
    if as_json and text:
        try:
            text = "\n".join(b.get("text", "") for b in json.loads(text).get("blocks", []))
        except json.JSONDecodeError:
            pass
    return text, fr, resp.usage_metadata


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--pages", default="", help="vd '1-5' de thu nhanh; bo trong = ca file")
    a = ap.parse_args()

    doc = pymupdf.open(a.pdf)
    first, last = 0, doc.page_count - 1
    if a.pages:
        lo, _, hi = a.pages.partition("-")
        first = int(lo) - 1
        last = int(hi or lo) - 1

    keys = load_keys()
    if not keys:
        print("Khong thay GEMMA_API_KEY* trong .env")
        sys.exit(1)

    print("File  : %s" % Path(a.pdf).name)
    print("Model : %s | trang %d..%d / %d" % (a.model, first + 1, last + 1, doc.page_count))
    print("Gui   : moi trang = 1 file PDF (application/pdf), KHONG render anh")
    print("-" * 74)

    parts, stats = [], {"plain": 0, "json": 0, "fail": 0}
    t_all = time.perf_counter()

    for i in range(first, last + 1):
        pb = page_to_pdf_bytes(doc, i)
        got, mode, err = None, None, ""
        for ki in range(min(3, len(keys))):
            key = keys[(i + ki) % len(keys)][1]
            client = genai.Client(api_key=key)
            for as_json in (False, True):           # thu van ban thuan truoc, roi JSON
                try:
                    t0 = time.perf_counter()
                    text, fr, um = ask(client, a.model, pb, PROMPT_JSON if as_json else PROMPT_PLAIN, as_json)
                    dt = time.perf_counter() - t0
                except Exception as e:
                    err = str(e)[:90]
                    continue
                if text.strip():
                    got, mode = text, ("json" if as_json else "plain")
                    print("  trang %2d: %-5s %5.1fs %6d ky tu  (%s)" % (i + 1, mode, dt, len(text), fr.split(".")[-1]))
                    break
                err = fr.split(".")[-1]
            if got is not None:
                break
        if got is None:
            print("  trang %2d: THAT BAI (%s)" % (i + 1, err))
            stats["fail"] += 1
            parts.append("[[TRANG %d KHONG OCR DUOC: %s]]" % (i + 1, err))
        else:
            stats[mode] += 1
            parts.append(got.strip())

    text = "\n\n".join(parts)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")

    print("-" * 74)
    print("Tong  : %.1fs | plain=%d json=%d fail=%d | %d ky tu"
          % (time.perf_counter() - t_all, stats["plain"], stats["json"], stats["fail"], len(text)))
    print("Ghi   : %s" % out)


if __name__ == "__main__":
    main()
