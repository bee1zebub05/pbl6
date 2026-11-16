"""Thu nghiem OCR PDF bang Gemini 3.5 Flash Lite + thong ke thoi gian.

Ghi chu: prompt OCR dang "tra ve van ban thuan" bi Gemini chan boi bo loc
RECITATION doi voi van ban phap quy cong khai. Yeu cau tra ve JSON theo dong
thi vuot qua duoc bo loc nay -> dung response_mime_type=application/json.
"""
import argparse, json, os, sys, time
from pathlib import Path

import pymupdf
from dotenv import load_dotenv
from google import genai
from google.genai import types

MODEL = "gemini-3.5-flash-lite"
PROMPT = """Trả về JSON {"blocks":[{"index":n,"text":"..."}]} - mỗi dòng văn bản trên ảnh là một block, index bắt đầu từ 1, text là nội dung dòng đó.

Quy tắc:
- Giữ nguyên tiếng Việt có dấu, số hiệu văn bản, ngày tháng, số thứ tự.
- Bảng: mỗi hàng là một block, các ô ngăn bằng " | ".
- Không tóm tắt, không thêm bình luận."""

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


def ocr_page(client, png, retries=3):
    last = None
    for attempt in range(retries):
        t0 = time.perf_counter()
        resp = client.models.generate_content(
            model=MODEL,
            contents=[types.Part.from_bytes(data=png, mime_type="image/png"), PROMPT],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=SCHEMA,
                temperature=0.0,
            ),
        )
        dt = time.perf_counter() - t0
        fr = str(resp.candidates[0].finish_reason)
        if resp.text:
            try:
                blocks = json.loads(resp.text).get("blocks", [])
                lines = [b.get("text", "") for b in blocks]
            except (json.JSONDecodeError, AttributeError):
                lines = [resp.text]
            return "\n".join(lines), dt, resp.usage_metadata, fr, attempt + 1
        last = (dt, resp.usage_metadata, fr)
        time.sleep(1)
    return "", last[0], last[1], last[2], retries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--out", default="data/interim/ocr_test")
    ap.add_argument("--key-var", default="GEMMA_API_KEY_16")
    args = ap.parse_args()

    load_dotenv("project/.env")
    api_key = os.getenv(args.key_var)
    if not api_key:
        sys.exit(f"Khong tim thay {args.key_var} trong project/.env")

    pdf_path, out_dir = Path(args.pdf), Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    doc = pymupdf.open(pdf_path)
    imgs = [pg.get_pixmap(dpi=args.dpi).tobytes("png") for pg in doc]
    t_render = time.perf_counter() - t0
    print(f"[render] {len(imgs)} trang @ {args.dpi} DPI trong {t_render:.2f}s "
          f"({t_render/len(imgs):.2f}s/trang, tb {sum(map(len,imgs))/len(imgs)/1024:.0f} KB/trang)")

    client = genai.Client(api_key=api_key)
    stats, texts = [], []
    t_wall0 = time.perf_counter()

    for i, png in enumerate(imgs, 1):
        text, dt, u, fr, tries = ocr_page(client, png)
        stats.append({
            "page": i, "seconds": round(dt, 2), "png_kb": round(len(png)/1024, 1),
            "chars": len(text), "attempts": tries, "finish_reason": fr,
            "prompt_tokens": u.prompt_token_count or 0,
            "output_tokens": u.candidates_token_count or 0,
            "total_tokens": u.total_token_count or 0,
        })
        texts.append(f"--- Trang {i} ---\n{text}")
        print(f"[trang {i}/{len(imgs)}] {dt:5.2f}s | {len(text):5d} ky tu | "
              f"in={u.prompt_token_count} out={u.candidates_token_count} | {fr.split('.')[-1]}"
              + (f" | retry x{tries}" if tries > 1 else ""))

    t_api = time.perf_counter() - t_wall0
    stem = pdf_path.stem[:60]
    (out_dir / f"{stem}.txt").write_text("\n\n".join(texts), encoding="utf-8")

    summary = {
        "file": pdf_path.name, "model": MODEL, "dpi": args.dpi, "pages": len(imgs),
        "render_seconds": round(t_render, 2), "api_seconds": round(t_api, 2),
        "total_seconds": round(t_render + t_api, 2),
        "seconds_per_page": round((t_render + t_api)/len(imgs), 2),
        "total_tokens": sum(s["total_tokens"] for s in stats),
        "total_chars": sum(s["chars"] for s in stats),
        "per_page": stats,
    }
    (out_dir / f"{stem}.stats.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== THONG KE ===")
    print(f"Render    : {t_render:.2f}s")
    print(f"Goi API   : {t_api:.2f}s (min {min(s['seconds'] for s in stats):.2f}s / "
          f"max {max(s['seconds'] for s in stats):.2f}s / tb {t_api/len(imgs):.2f}s per trang)")
    print(f"Tong cong : {t_render+t_api:.2f}s / {len(imgs)} trang = {(t_render+t_api)/len(imgs):.2f}s per trang")
    print(f"Tokens    : {summary['total_tokens']} (in {sum(s['prompt_tokens'] for s in stats)}, "
          f"out {sum(s['output_tokens'] for s in stats)})")
    print(f"Ket qua   : {out_dir / (stem + '.txt')}")


if __name__ == "__main__":
    main()
