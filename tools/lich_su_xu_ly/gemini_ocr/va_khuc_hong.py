# -*- coding: utf-8 -*-
"""Ghi lai va VA rieng nhung KHUC BI HONG trong mot dot OCR.

Khi mot khuc that bai, ocr_lai_file_nat.py chen dau '[[KHONG OCR DUOC TRANG a-b]]' vao
dung cho do. Script nay:
  1. Quet ca thu muc, gom moi dau nhu vay thanh MOT DANH SACH luu ra JSON
     -> co so ghi chep de doi chieu ve sau, khong phu thuoc vao viec doc log
  2. Voi --apply: cat DUNG nhung trang do ra roi OCR lai, va vao cho cu

Chien thuat va: thu ca khuc truoc, hong thi thu TUNG TRANG mot. Mot trang le de duoc
chap nhan hon han mot khuc vi noi dung ngan hon, it bi coi la 'chep lai van ban cong
khai' (RECITATION) va it kha nang dinh loi 500/504 giua chung.

    python va_khuc_hong.py --thu-muc data/processed/text_gemma_codoc
    python va_khuc_hong.py --thu-muc data/processed/text_gemma_codoc --apply
"""
import argparse
import io
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gemma_ocr as G                                   # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import pymupdf
except ImportError:
    pymupdf = None

GOC = Path(__file__).resolve().parents[2]
RAW = GOC / "data" / "raw"

MOC = re.compile(r"\[\[KHÔNG OCR ĐƯỢC TRANG ([\d,\s-]+)\]\]")
# THU TU MODEL do nguoi dung chot: Flash truoc cho nhanh, het quota moi lui ve Gemma.
#
# Do duoc tren cac khuc con lai (deu dinh RECITATION), tinh theo TUNG TRANG:
#     gemini-3.5 / 3.1    0/5 dat  — bi chan, NHUNG tra ve NGAY, gan nhu khong ton gio
#     gemma-4-31b-it      2/5      — hay dinh 500 INTERNAL / 504
#     gemma-4-26b-a4b-it  5/5 dat
#
# Dat Flash truoc KHONG lam cham: RECITATION tra ve rong ngay lap tuc chu khong phai
# timeout. Cho that su ton thoi gian la 31b — 500/503/504 duoc xep la loi TAM THOI nen
# moi lan dinh la thu lai toi LAN_THU_TAM_THOI = 12 luot kem cho.
MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite",
          "gemma-4-31b-it", "gemma-4-26b-a4b-it"]


def cac_trang(s):
    """'16-20' hoac '3, 7, 9' -> [16,17,18,19,20] / [3,7,9]"""
    ra = []
    for phan in s.split(","):
        phan = phan.strip()
        if "-" in phan:
            a, b = phan.split("-", 1)
            if a.strip().isdigit() and b.strip().isdigit():
                ra += list(range(int(a), int(b) + 1))
        elif phan.isdigit():
            ra.append(int(phan))
    return ra


def chi_muc_pdf():
    ix = {}
    for f in sorted(RAW.rglob("*.pdf")):
        k = f.name[:4]
        trong_pdf = f.relative_to(RAW).as_posix().startswith("pdf/")
        if k not in ix or trong_pdf:
            ix[k] = f
    return ix


def cat(pdf, trang):
    """Cat cac trang (danh so tu 1) thanh mot PDF nho trong bo nho."""
    import io as _io
    with pymupdf.open(pdf) as d:
        nho = pymupdf.open()
        for t in trang:
            if 1 <= t <= d.page_count:
                nho.insert_pdf(d, from_page=t - 1, to_page=t - 1)
        b = _io.BytesIO()
        nho.save(b)
        nho.close()
    return b.getvalue()


def quet(thu_muc):
    """-> [{doc, file, moc, trang}] moi dau thieu la mot muc."""
    ra = []
    for f in sorted(Path(thu_muc).rglob("*.txt")):
        t = io.open(f, encoding="utf-8", errors="replace").read()
        for m in MOC.finditer(t):
            tr = cac_trang(m.group(1))
            if tr:
                ra.append({"doc": f.name[:4], "file": str(f), "moc": m.group(0),
                           "trang": tr})
    return ra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thu-muc", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--song-song", type=int, default=8,
                    help="số chỗ vá cùng lúc (mặc định 8)")
    ap.add_argument("--ra", default=None, help="file json ghi danh sach chỗ hỏng")
    a = ap.parse_args()

    tm = Path(a.thu_muc)
    if not tm.is_absolute():
        tm = GOC / tm
    ds = quet(tm)

    so = GOC / "data" / "khuc_hong.json"
    if a.ra:
        so = Path(a.ra) if Path(a.ra).is_absolute() else GOC / a.ra
    so.parent.mkdir(parents=True, exist_ok=True)
    so.write_text(json.dumps(
        [{"doc": x["doc"], "trang": x["trang"], "file": os.path.basename(x["file"])}
         for x in ds], ensure_ascii=False, indent=1), encoding="utf-8")

    print("=" * 86)
    print("KHÚC HỎNG TRONG %s" % tm.name)
    print("=" * 86)
    if not ds:
        print("  Không còn khúc nào hỏng.")
        print("  Đã ghi danh sách rỗng: %s" % so)
        return
    tong = 0
    for x in ds:
        tong += len(x["trang"])
        print("  %s  trang %-16s (%d trang)  %s"
              % (x["doc"], "%d-%d" % (x["trang"][0], x["trang"][-1])
                 if len(x["trang"]) > 1 else str(x["trang"][0]),
                 len(x["trang"]), os.path.basename(x["file"])[5:46]))
    print("-" * 86)
    print("  %d chỗ hỏng, %d trang, trên %d tài liệu"
          % (len(ds), tong, len({x["doc"] for x in ds})))
    print("  Đã ghi danh sách: %s" % so)
    print("=" * 86)

    if not a.apply:
        print(">>> Mới là XEM TRƯỚC. Thêm --apply để OCR lại và vá vào.")
        return

    if not pymupdf:
        print("Thiếu pymupdf.")
        return

    ix = chi_muc_pdf()
    qlk = G.QuanLyKey()
    qlk.kiem_tra_sau()
    print("-" * 86)

    # Chay SONG SONG. Cong viec o day gan nhu toan la CHO MANG — mot trang
    # gemma-26b co the cho toi 4 phut roi timeout — nen CPU nam khong, con 16/17
    # key cung nam khong. Do that: tuan tu di 3 cho trong 67 phut (~22 phut/cho),
    # 36 cho se mat ~13 tieng.
    #
    # Ghi file thi PHAI tuan tu: hai khuc cua CUNG MOT van ban ghi vao cung mot
    # file, chay song song ma khong khoa thi ban ghi sau doc phai noi dung cu va
    # xoa mat ban va cua ban ghi truoc.
    khoa_ghi = threading.Lock()
    dem = {"cuu": 0, "con": 0, "xong": 0}

    def lam_mot(x):
        ghi_log = []
        tr = x["trang"]
        nhan = "%s trang %d-%d" % (x["doc"], tr[0], tr[-1])
        pdf = ix.get(x["doc"])

        if not pdf:
            return nhan, ["  ✖ không thấy PDF gốc"], False, True

        phan = {}
        t, ly_do = G._ocr_hai_tang(qlk, cat(pdf, tr), G.PROMPT, MODELS, len(tr))

        if t:
            phan = {tr[0]: t}
            ghi_log.append("      cả khúc: OK (%d ký tự) [%s]" % (len(t), ly_do))
        elif len(tr) == 1:
            # Khuc CHI CO MOT TRANG thi "thu tung trang" gui lai y het noi dung vua
            # truot — chay lai het cac model voi cung du lieu, gap doi thoi gian ma
            # khong doi duoc gi. Bo qua vong do.
            ghi_log.append("      cả khúc hỏng (%s) — khúc 1 trang, không chia nhỏ được"
                           % str(ly_do)[:44])
        else:
            ghi_log.append("      cả khúc hỏng (%s) → thử từng trang" % str(ly_do)[:44])
            for p in tr:
                tt, gg = G._ocr_hai_tang(qlk, cat(pdf, [p]), G.PROMPT, MODELS, 1,
                                         min_ky_tu=80)
                if tt:
                    phan[p] = tt
                    ghi_log.append("      trang %d: OK (%d ký tự)" % (p, len(tt)))
                else:
                    ghi_log.append("      trang %d: vẫn hỏng (%s)" % (p, str(gg)[:40]))

        if not phan:
            ghi_log.append("      ✖ không cứu được, giữ nguyên dấu thiếu")
            return nhan, ghi_log, False, True

        if len(phan) == 1 and tr[0] in phan:
            moi = phan[tr[0]]
        else:
            moi = "\n\n".join("----- [Trang %d] -----\n\n%s" % (p, phan[p])
                              for p in sorted(phan))

        thieu = [p for p in tr if p not in phan] if len(phan) > 1 else []
        con_thieu = bool(thieu)

        if thieu:
            moi += "\n\n[[KHÔNG OCR ĐƯỢC TRANG %s]]" % ", ".join(map(str, thieu))

        f = Path(x["file"])

        with khoa_ghi:
            noi = io.open(f, encoding="utf-8", errors="replace").read()

            if x["moc"] not in noi:
                ghi_log.append("      ✖ không thấy dấu thiếu trong file (đã đổi?)")
                return nhan, ghi_log, False, True

            io.open(f, "w", encoding="utf-8", newline="\n").write(
                noi.replace(x["moc"], moi, 1))

        ghi_log.append("      ✔ đã vá")
        return nhan, ghi_log, True, con_thieu

    with ThreadPoolExecutor(max_workers=a.song_song) as bom:
        for nhan, ghi_log, ok, thieu in bom.map(lam_mot, ds):
            dem["xong"] += 1
            dem["cuu"] += ok
            dem["con"] += thieu
            print("  ▸ [%d/%d] %s" % (dem["xong"], len(ds), nhan))
            for d in ghi_log:
                print(d)
            sys.stdout.flush()

    cuu, con = dem["cuu"], dem["con"]
    print("-" * 86)
    print("Vá được %d / %d chỗ | còn hỏng %d" % (cuu, len(ds), con))


if __name__ == "__main__":
    main()
