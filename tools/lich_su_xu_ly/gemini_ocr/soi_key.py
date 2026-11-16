# -*- coding: utf-8 -*-
"""Kham suc khoe TUNG key mot, phan biet ro CHET HAN voi CHI DANG HET HAN MUC.

Hai loai 'khong dung duoc' rat khac nhau:
  - CHET  (403 PERMISSION_DENIED, 400 API_KEY_INVALID, key bi thu hoi) -> phai bo di
  - NGHI  (429 RESOURCE_EXHAUSTED) -> chi la het han muc, mai lai dung duoc

Gop chung hai loai nay tung gay hau qua that: mot model cham tra 504 lam ca 21 key bi
danh dau chet, 383 file hong ngay lap tuc. Nen o day tach bach va noi ro tung key.

    python soi_key.py                 # kham nhanh (chi liet ke model)
    python soi_key.py --sau           # kham sau: goi that 1 request ti hon moi key
    python soi_key.py --model <ten>   # kham voi model khac
"""
import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODEL_MAC_DINH = "gemma-4-31b-it"


def nap_key(env_path=None):
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path or (Path(__file__).resolve().parents[1] / ".env"))
    except ImportError:
        pass
    ra = []
    for ten, gt in os.environ.items():
        if not ten.startswith("GEMMA_API_KEY") or not gt:
            continue
        gt = gt.strip().strip('"').strip("'")
        if gt:
            ra.append({"ten": ten, "key": gt})
    ra.sort(key=lambda k: (len(k["ten"]), k["ten"]))
    return ra


def phan_loai(e):
    """-> (trang thai, ly do ngan). Phan biet key HONG voi dich vu BAN."""
    s = str(e)
    if "429" in s or "RESOURCE_EXHAUSTED" in s:
        return "NGHỈ", "hết hạn mức (429) — mai dùng lại được"
    if "403" in s or "PERMISSION_DENIED" in s:
        return "CHẾT", "bị từ chối quyền (403)"
    if "API_KEY_INVALID" in s or "API key not valid" in s:
        return "CHẾT", "key không hợp lệ"
    if "401" in s or "UNAUTHENTICATED" in s:
        return "CHẾT", "không xác thực được (401)"
    if "404" in s or "NOT_FOUND" in s:
        return "?", "không thấy model (404) — key có thể vẫn tốt"
    if "503" in s or "UNAVAILABLE" in s:
        return "?", "dịch vụ quá tải (503)"
    if "504" in s or "DEADLINE" in s or "timeout" in s.lower():
        return "?", "quá thời gian chờ (504)"
    return "?", s.replace("\n", " ")[:64]


def kham(k, model, sau, timeout_ms=30000):
    from google import genai
    from google.genai import types
    t0 = time.perf_counter()
    try:
        c = genai.Client(api_key=k["key"],
                         http_options=types.HttpOptions(timeout=timeout_ms))
        if sau:
            r = c.models.generate_content(
                model=model, contents=["ok"],
                config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=5))
            ok = bool((r.text or "").strip() or r.candidates)
            tt = ("TỐT", "") if ok else ("?", "gọi được nhưng không trả nội dung")
        else:
            list(c.models.list())
            tt = ("TỐT", "")
    except Exception as e:
        tt = phan_loai(e)
    return tt[0], tt[1], time.perf_counter() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sau", action="store_true", help="gọi thật 1 request tí hon mỗi key")
    ap.add_argument("--model", default=MODEL_MAC_DINH)
    ap.add_argument("--song-song", type=int, default=8)
    a = ap.parse_args()

    keys = nap_key()
    if not keys:
        print("Không tìm thấy biến GEMMA_API_KEY* nào trong .env")
        return

    print("=" * 84)
    print("KHÁM SỨC KHOẺ %d KEY  —  %s%s"
          % (len(keys), "khám sâu (gọi thật)" if a.sau else "khám nhanh (liệt kê model)",
             "  | model %s" % a.model if a.sau else ""))
    print("=" * 84)

    with ThreadPoolExecutor(max_workers=a.song_song) as ex:
        kq = list(ex.map(lambda k: kham(k, a.model, a.sau), keys))

    dem = {}
    for k, (tt, ly, gy) in zip(keys, kq):
        dem[tt] = dem.get(tt, 0) + 1
        bieu = {"TỐT": "✔", "NGHỈ": "⏸", "CHẾT": "✖"}.get(tt, "?")
        print("  %s %-18s %-6s %5.1fs  %s"
              % (bieu, k["ten"], tt, gy, ly[:44]))

    print("-" * 84)
    for t in ("TỐT", "NGHỈ", "CHẾT", "?"):
        if dem.get(t):
            print("  %-6s %2d / %d" % (t, dem[t], len(keys)))
    print("=" * 84)
    if dem.get("NGHỈ"):
        print("  ⏸ NGHỈ = chỉ hết hạn mức trong ngày, KHÔNG phải key hỏng.")
        print("     Hạn mức Google reset theo múi giờ Thái Bình Dương (khoảng 14–15h VN).")
    if dem.get("CHẾT"):
        print("  ✖ CHẾT = cần thay key mới, chạy lại cũng không dùng được.")
    if not a.sau:
        print("  Khám nhanh chỉ kiểm key có gọi được API không. Muốn biết key có thật sự")
        print("  sinh nội dung được không thì chạy:  python soi_key.py --sau")


if __name__ == "__main__":
    main()
