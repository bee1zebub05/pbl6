# -*- coding: utf-8 -*-
"""Chay Gemma 31B (gemma-4-31b-it) hang loat cho mot so THU MUC, khong qua Gemini web.

Khac voi duong lui trong bridge (chi nhan file da that bai 3 lan), day la chay THANG:
chon thu muc -> OCR het file chua co ket qua -> ghi vao clean_data giu nguyen cay thu muc.

  - Gui THANG file PDF, khong render anh.
  - Ca file hong -> cat thanh PDF nho roi ghep (mac dinh 5 trang/khuc).
  - Xoay 21 key, kiem tra key truoc khi chay.
  - Chay song song nhieu file (mac dinh 4) vi moi file mat 1-3 phut.

Chay:
    python chay_gemma_hangloat.py --thu-muc "pdf/Khảo thí" "pdf/Sở hữu trí tuệ" "pdf/Văn thư, lưu trữ"
    python chay_gemma_hangloat.py --thu-muc "pdf/Đào tạo" --song-song 6
    python chay_gemma_hangloat.py --thu-muc "pdf/Pháp chế" --thu-thoi        # chi liet ke, khong chay
"""
import argparse
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gemma_ocr import MODEL, QuanLyKey, ocr_pdf          # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

GOC = Path(__file__).resolve().parents[2]
SRC = GOC / "data" / "raw"
OUT = GOC / "data" / "clean_data"
EXTS = {".pdf", ".doc", ".docx"}

_khoa = threading.Lock()
_so = {"xong": 0, "hong": 0, "ky_tu": 0}


def duong_dan_dai(p):
    """Windows chan duong dan > 260 ky tu."""
    if os.name != "nt":
        return str(p)
    p = os.path.abspath(str(p))
    return p if p.startswith("\\\\?\\") else "\\\\?\\" + p


def da_xong(dich):
    try:
        return os.path.getsize(duong_dan_dai(dich)) > 0
    except OSError:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thu-muc", nargs="*", default=[],
                    help='duong dan tuong doi trong data/raw, vd "pdf/Khảo thí"')
    ap.add_argument("--thu-muc-file", default=None,
                    help="file text, moi dong mot thu muc. Dung cai nay khi ten co DAU CACH: "
                         "PowerShell cat tham so theo dau cach nen 'pdf/To chuc, hanh chinh' "
                         "bi vo thanh 4 tham so roi.")
    ap.add_argument("--song-song", type=int, default=4)
    ap.add_argument("--moi-khuc", type=int, default=5)
    ap.add_argument("--model", default=MODEL, help="model chinh")
    ap.add_argument("--model-lui", default=None,
                    help="model du phong khi model chinh hong tung khuc, vd gemma-4-31b-it")
    ap.add_argument("--thu-thoi", action="store_true", help="chi liet ke viec, khong goi API")
    a = ap.parse_args()

    dsm = list(a.thu_muc)
    if a.thu_muc_file:
        dsm += [l.strip() for l in
                Path(a.thu_muc_file).read_text(encoding="utf-8").splitlines() if l.strip()]
    if not dsm:
        ap.error("cần --thu-muc hoặc --thu-muc-file")
    loc = [t.replace("\\", "/").strip("/") for t in dsm]
    viec, bo_qua = [], []
    for f in sorted(SRC.rglob("*")):
        if f.suffix.lower() not in EXTS:
            continue
        rel = f.relative_to(SRC).as_posix()
        # So theo TUNG DOAN duong dan, khong so theo tien to chuoi: "pdf" ma so tien to
        # thi khop luon "pdf_fixed/..." — khong phai thu muc minh chon.
        if not any(rel == t or rel.startswith(t + "/") for t in loc):
            continue
        dich = OUT / Path(rel).with_suffix(".txt")
        if da_xong(dich):
            continue
        if f.suffix.lower() != ".pdf":
            bo_qua.append(rel)          # .doc/.docx: Gemma khong nhan
            continue
        viec.append((rel, f, dich))

    # XEP FILE NHO TRUOC. Truoc day duyet theo alphabet -> 4 file dau lai la 23/22/39/95
    # trang, moi file 4-16 phut, nen thanh tien do dung im rat lau du he thong chay dung.
    # Chay nho truoc thi ket qua ra lien tuc, va neu het quota giua chung cung xong duoc
    # nhieu file hon.
    viec.sort(key=lambda x: x[1].stat().st_size)

    print("=" * 84)
    print("Chay hang loat | model chinh: %s%s | %d luong song song"
          % (a.model, (" -> lui ve: " + a.model_lui) if a.model_lui else "", a.song_song))
    for t in loc:
        n = sum(1 for r, _f, _d in viec if r.startswith(t))
        print("   %-52s %3d file cần chạy" % (t, n))
    print("   %-52s %3d" % ("TỔNG", len(viec)))
    if bo_qua:
        print("   Bỏ qua %d file KHÔNG phải PDF (Gemma chỉ nhận PDF):" % len(bo_qua))
        for r in bo_qua:
            print("      · %s" % r[-70:])
        print("      → dùng đường Gemini web cho những file này, hoặc chuyển sang PDF")
    print("=" * 84)
    if not viec:
        print("Không có file nào cần chạy (đã xong hết).")
        return
    if a.thu_thoi:
        for rel, _f, _d in viec[:40]:
            print("   " + rel)
        if len(viec) > 40:
            print("   … và %d file nữa" % (len(viec) - 40))
        return

    qlk = QuanLyKey(model=a.model)
    if not qlk.keys:
        print("Không thấy GEMMA_API_KEY* trong .env")
        sys.exit(1)
    qlk.kiem_tra(hien_thi=False)
    qlk.kiem_tra_sau(hien_thi=False)
    print("Key dùng được: %d/%d" % (qlk.con_song(), len(qlk.keys)))
    print("-" * 84)

    t0 = time.perf_counter()
    tong = len(viec)

    def lam(mv):
        rel, f, dich = mv
        # Ma ngan de nhan ra file trong log khi 4 luong ghi xen ke nhau
        ma = rel.rsplit("/", 1)[-1][:4]
        with _khoa:
            print("  … [%s] bắt đầu: %s" % (ma, rel[-58:]))

        def ghi(m):
            # Log TUNG KHUC. Truoc day tat het -> khong biet request dang o dau,
            # file chay 5 phut ma im lang hoan toan, khong phan biet duoc dang chay
            # hay da treo.
            with _khoa:
                print("     [%s]%s" % (ma, m))

        try:
            kq = ocr_pdf(f, model=a.model, qlk=qlk, moi_khuc=a.moi_khuc, log=ghi,
                         model_lui=a.model_lui)
        except Exception as e:
            with _khoa:
                _so["hong"] += 1
                print("  ✖ %-56s lỗi: %s" % (rel[-56:], str(e)[:60]))
            return
        with _khoa:
            if kq.get("ok") and kq.get("text"):
                os.makedirs(duong_dan_dai(dich.parent), exist_ok=True)
                with open(duong_dan_dai(dich), "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(kq["text"])
                _so["xong"] += 1
                _so["ky_tu"] += len(kq["text"])
                kh = kq.get("khuc_hong") or []
                print("  ✔ [%3d/%3d] %-46s %7d ký tự | %s%s"
                      % (_so["xong"] + _so["hong"], tong, rel[-46:], len(kq["text"]),
                         kq.get("che_do", ""),
                         (" | THIẾU khúc %s" % ", ".join("%d-%d" % (h["tu"], h["den"]) for h in kh)) if kh else ""))
            else:
                _so["hong"] += 1
                print("  ✖ [%3d/%3d] %-46s %s"
                      % (_so["xong"] + _so["hong"], tong, rel[-46:], kq.get("ly_do", "?")[:40]))

    with ThreadPoolExecutor(max_workers=a.song_song) as ex:
        list(ex.map(lam, viec))

    dt = time.perf_counter() - t0
    print("-" * 84)
    print("Xong %d | hỏng %d | %s ký tự | %.0f phút (%.0f giây/file)"
          % (_so["xong"], _so["hong"], "{:,}".format(_so["ky_tu"]), dt / 60, dt / max(1, tong)))
    print("Key: %s" % qlk.tom_tat())


if __name__ == "__main__":
    main()
