# -*- coding: utf-8 -*-
"""OCR LAI TOAN BO nhung tai lieu co text_raw hong nang, bang Gemma 31B.

Nguon danh sach: ds_nat.json (sinh tu cac cho 'khong tim duoc' con lai)
Ghi ra: data/processed/text_gemma/<cung cay thu muc>.txt   — KHONG ghi de text_raw

Xep theo MAT DO LOI giam dan: file nat nhat chay truoc, dung luc nao cung co gia tri.
Co diem luu: file da xong thi bo qua -> mat dien/tat may van chay tiep duoc.

Moc trang: ghi '----- [Trang N] -----' o dau moi khuc (N la trang dau cua khuc),
de doi chieu duoc voi text_raw. Khuc mac dinh 5 trang.

    python ocr_lai_file_nat.py                 # chay het
    python ocr_lai_file_nat.py --gioi-han 5    # thu 5 file dau
    python ocr_lai_file_nat.py --toi-thieu 0.05  # chi file >= 0.05 loi/trang
"""
import argparse
import io as _io
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gemma_ocr import (QuanLyKey, _cat_pdf, _ocr_hai_tang, PROMPT,      # noqa: E402
                       SO_TRANG_MOI_KHUC, TIMEOUT_MOI_KHUC_MS)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
SRC = GOC / "data" / "raw"
RA = GOC / "data" / "processed" / "text_gemma"
DS = Path(__file__).resolve().parent / "ds_nat.json"

_khoa = threading.Lock()
_so = {"file": 0, "xong": 0, "hong": 0, "khuc_hong": 0, "ky_tu": 0, "trang": 0}


def duong_dan_dai(p):
    if os.name != "nt":
        return str(p)
    p = os.path.abspath(str(p))
    return p if p.startswith("\\\\?\\") else "\\\\?\\" + p


def thanh(x, t, rong=28):
    n = int(rong * x / t) if t else 0
    return "█" * n + "░" * (rong - n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--song-song", type=int, default=4)
    ap.add_argument("--moi-khuc", type=int, default=SO_TRANG_MOI_KHUC)
    # Chuoi model theo THU TU UU TIEN, ngan cach bang dau phay. Het han muc model dau
    # thi tu dong lui xuong model sau. Flash Lite nhanh hon Gemma nhieu nhung han muc
    # ngay thap hon (500 RPD/key so voi 14.400), nen dat truoc de dung het phan nhanh
    # roi moi rot xuong phan cham ma nhieu.
    ap.add_argument("--models",
                    default="gemini-3.5-flash-lite,gemini-3.1-flash-lite,"
                            "gemma-4-31b-it,gemma-4-26b-a4b-it")
    ap.add_argument("--model", default=None, help="(cũ) model chính")
    ap.add_argument("--model-lui", default=None, help="(cũ) model lùi")
    ap.add_argument("--gioi-han", type=int, default=0)
    ap.add_argument("--toi-thieu", type=float, default=0.0, help="loc theo mat do loi/trang")
    ap.add_argument("--ds", default=None, help="file json danh sach can chay (mac dinh ds_nat.json)")
    ap.add_argument("--ra", default=None, help="thu muc ghi ket qua (mac dinh text_gemma)")
    a = ap.parse_args()

    # Dat NGAY SAU parse_args: dong in thu tu model o phia tren can bien nay.
    if a.model:
        models = [a.model] + ([a.model_lui] if a.model_lui else [])
    else:
        models = [x.strip() for x in a.models.split(",") if x.strip()]

    # Doi dich ghi thi doi luon DIEM LUU: script coi 'file da ton tai o dich' la da xong.
    # Ghi de len text_gemma se lam mat ban doi chieu cu, nen moi dot phai co thu muc rieng.
    global RA
    if a.ra:
        RA = Path(a.ra) if Path(a.ra).is_absolute() else GOC / a.ra

    ds = json.loads((Path(a.ds) if a.ds else DS).read_text(encoding="utf-8"))
    for x in ds:
        x["mat_do"] = x["so_loi"] / max(1, x["trang"])
    ds = [x for x in ds if x["mat_do"] >= a.toi_thieu]
    ds.sort(key=lambda x: -x["mat_do"])          # nat nhat chay truoc

    viec = []
    da_co = 0
    for x in ds:
        # ds_nat.json luu duong dan TUONG DOI (sinh tu thu muc goc) -> phai noi lai
        pdf = Path(x["pdf"])
        if not pdf.is_absolute():
            pdf = GOC / pdf
        rel = pdf.relative_to(SRC).with_suffix(".txt")
        dich = RA / rel
        try:
            if dich.stat().st_size > 0:
                da_co += 1
                continue
        except OSError:
            pass
        viec.append((x, pdf, dich))
    if a.gioi_han:
        viec = viec[: a.gioi_han]

    tong = len(viec)
    tong_trang = sum(x["trang"] for x, _p, _d in viec)
    print("=" * 92)
    print("OCR LẠI — thứ tự model: %s" % "  →  ".join(models))
    print("  Cần chạy : %d tài liệu, %d trang (~%d khúc)"
          % (tong, tong_trang, tong_trang / max(1, a.moi_khuc)))
    if da_co:
        print("  ⏩ TIẾP TỤC: bỏ qua %d tài liệu đã có kết quả" % da_co)
    print("  Ghi ra   : %s  (KHÔNG đụng text_raw)" % RA)
    print("=" * 92)
    if not tong:
        print("Không còn tài liệu nào cần chạy.")
        return

    qlk = QuanLyKey(model=models[0])
    qlk.kiem_tra(hien_thi=False)
    qlk.kiem_tra_sau(hien_thi=False)
    print("  Key dùng được: %d/%d" % (qlk.con_song(), len(qlk.keys)))
    print("-" * 92)

    t0 = time.perf_counter()

    def lam(mv):
        x, pdf, dich = mv
        ma = x["doc"]
        try:
            khuc = _cat_pdf(pdf, a.moi_khuc)
        except Exception as e:
            with _khoa:
                _so["file"] += 1
                _so["hong"] += 1
                print("  ✖ [%s] cắt PDF hỏng: %s" % (ma, str(e)[:60]))
            return

        phan, hong = [], 0
        for (tu, den, b) in khuc:
            t, _gc = _ocr_hai_tang(qlk, b, PROMPT, models, den - tu + 1,
                                   TIMEOUT_MOI_KHUC_MS, min_ky_tu=max(60, 40 * (den - tu + 1)))
            if t:
                phan.append("----- [Trang %d] -----\n\n%s" % (tu, t.strip()))
            else:
                hong += 1
                phan.append("----- [Trang %d] -----\n\n[[KHÔNG OCR ĐƯỢC TRANG %d-%d]]" % (tu, tu, den))

        text = "\n\n".join(phan).strip() + "\n"
        with _khoa:
            _so["file"] += 1
            if hong == len(khuc):
                _so["hong"] += 1
                print("  ✖ [%s] mọi khúc đều hỏng" % ma)
            else:
                os.makedirs(duong_dan_dai(dich.parent), exist_ok=True)
                with open(duong_dan_dai(dich), "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(text)
                _so["xong"] += 1
                _so["khuc_hong"] += hong
                _so["ky_tu"] += len(text)
                _so["trang"] += x["trang"]
            r = _so["file"]
            dt = time.perf_counter() - t0
            print("  %s %3d/%-3d %5.1f%% | [%s] %2d trang %6d ký tự%s | còn ~%.0f phút"
                  % (thanh(r, tong), r, tong, 100.0 * r / tong, ma, x["trang"], len(text),
                     (" | THIẾU %d khúc" % hong) if hong else "",
                     (dt / r) * (tong - r) / 60 if r else 0))

    try:
        with ThreadPoolExecutor(max_workers=a.song_song) as ex:
            list(ex.map(lam, viec))
    except KeyboardInterrupt:
        print("\n⏸ Dừng tay. File đã xong vẫn giữ — chạy lại là đi tiếp.")

    dt = time.perf_counter() - t0
    print("-" * 92)
    print("Xong %d | hỏng %d | %d khúc thiếu | %s ký tự | %d trang | %.0f phút"
          % (_so["xong"], _so["hong"], _so["khuc_hong"], "{:,}".format(_so["ky_tu"]),
             _so["trang"], dt / 60))
    print("Kết quả: %s" % RA)


if __name__ == "__main__":
    main()
