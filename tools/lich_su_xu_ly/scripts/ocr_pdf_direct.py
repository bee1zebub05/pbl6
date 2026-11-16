"""OCR 1 file PDF bang cach GUI THANG FILE PDF len Gemini API (khong render PNG).

Muc dich: doi chung voi ket qua chay tay tren chat gemini.google.com (qua extension).
Dung dung prompt nguoi dung da dung tren chat.

Chay:
    python ocr_pdf_direct.py "<duong_dan.pdf>" [--out out.txt] [--model gemini-3.5-flash-lite]
"""
import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

MODEL = "gemini-3.5-flash-lite"

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
PROMPT = "Đọc PDF này cho tôi và OCR ra txt cho tôi"


def load_keys():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    keys = []
    for k, v in os.environ.items():
        if k.startswith("GEMMA_API_KEY") and v:
            keys.append((k, v.strip().strip('"').strip("'")))
    return keys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out", default=None)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--prompt", default=PROMPT)
    ap.add_argument("--tries", type=int, default=4, help="so key thu lan luot khi bi loi/chan")
    ap.add_argument("--json", action="store_true",
                    help="Tra ve JSON theo dong. Bo loc RECITATION chan prompt 'tra ve van ban "
                         "thuan' voi van ban phap quy; yeu cau JSON thi vuot qua duoc.")
    a = ap.parse_args()

    if a.json:
        a.prompt = (
            'Trả về JSON {"blocks":[{"index":n,"text":"..."}]} - mỗi dòng văn bản trong file PDF '
            "là một block, index bắt đầu từ 1, text là nội dung dòng đó.\n\n"
            "Quy tắc:\n"
            "- Giữ nguyên tiếng Việt có dấu, số hiệu văn bản, ngày tháng, số thứ tự.\n"
            '- Bảng: mỗi hàng là một block, các ô ngăn bằng " | ".\n'
            "- Không tóm tắt, không thêm bình luận."
        )

    pdf = Path(a.pdf)
    data = pdf.read_bytes()
    print("File   : %s" % pdf.name)
    print("Size   : %.1f KB" % (len(data) / 1024))
    print("Model  : %s" % a.model)
    print("Prompt : %s" % a.prompt)
    print("Gui    : inline PDF (application/pdf) - KHONG render anh")
    print("-" * 70)

    keys = load_keys()
    if not keys:
        print("Khong tim thay GEMMA_API_KEY* trong .env")
        sys.exit(1)
    random.shuffle(keys)

    for name, key in keys[: a.tries]:
        print("[key %s]" % name, end=" ", flush=True)
        try:
            client = genai.Client(api_key=key)
            cfg = types.GenerateContentConfig(temperature=0.0)
            if a.json:
                cfg = types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                    response_schema=SCHEMA,
                )
            t0 = time.perf_counter()
            resp = client.models.generate_content(
                model=a.model,
                contents=[
                    types.Part.from_bytes(data=data, mime_type="application/pdf"),
                    a.prompt,
                ],
                config=cfg,
            )
            dt = time.perf_counter() - t0
        except Exception as e:
            print("LOI: %s" % str(e)[:200])
            continue

        cand = resp.candidates[0] if resp.candidates else None
        fr = str(cand.finish_reason) if cand else "?"
        um = resp.usage_metadata
        text = resp.text or ""
        print("xong %.1fs | finish_reason=%s | in=%s out=%s ky_tu=%d"
              % (dt, fr, getattr(um, "prompt_token_count", "?"),
                 getattr(um, "candidates_token_count", "?"), len(text)))

        if not text:
            print("   -> rong (bi chan?). Thu key khac.")
            continue

        if a.json:
            try:
                blocks = json.loads(text).get("blocks", [])
                text = "\n".join(b.get("text", "") for b in blocks)
                print("       JSON -> %d block, %d ky tu van ban" % (len(blocks), len(text)))
            except json.JSONDecodeError as e:
                print("       JSON hong: %s - giu nguyen text tho" % e)

        out = Path(a.out) if a.out else pdf.with_suffix(".api.txt")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="\n")
        print("Ghi    : %s (%d ky tu)" % (out, len(text)))
        print("-" * 70)
        print(text[:1500])
        return

    print("Tat ca key deu that bai.")
    sys.exit(2)


if __name__ == "__main__":
    main()
