# -*- coding: utf-8 -*-
"""Cuu nhung file bi API tu choi xuat vi RECITATION.

RECITATION la gi: model nhan ra noi dung minh sap xuat ra trung voi du lieu huan luyen
(van ban phap luat cong khai thi rat de trung) nen CHAN khong cho xuat. Tra ve rong,
finish_reason = RECITATION.

VI SAO PIPELINE CHINH TRUOT: `LOI_TAM_THOI` chi coi 429/500/503/504 la dang thu lai.
RECITATION khong nam trong do nen roi thang vao nhanh "khuc hong", va vi no la tu choi
CUNG chu khong phai loi tam thoi, ba lan chay lai deu cho ket qua y het nhau (52 ky tu).

CACH THOAT — do bang thuc nghiem tren 0124 va 0328, khong phai doan:

    ca file, moi model            -> RECITATION het
    tung trang, gemini-3.5/3.1    -> van RECITATION
    tung trang, gemma-4-26b-a4b   -> 5/5 trang ra binh thuong

Hai dieu kien phai DONG THOI: chia nho toi TUNG TRANG (mot trang le it giong "doan van
ban thuoc long" hon ca file), va dung Gemma (bo loc recitation khac Gemini).

    python cuu_file_recitation.py --doc 0124 0328
    python cuu_file_recitation.py --doc 0124 0328 --apply
"""
import argparse
import glob
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pymupdf                                        # noqa: E402
from gemma_ocr import PROMPT, QuanLyKey, _goi         # noqa: E402
from sach_hoa import kiem_dinh, lam_sach              # noqa: E402

GOC = Path(__file__).resolve().parents[2]
RA = GOC / "data" / "processed" / "text_gemma_moi"

# Thu tu nay NGUOC voi pipeline chinh (Gemini truoc, Gemma sau) — o day Gemma phai
# di truoc vi chinh Gemini la cai tu choi.
MODELS = ["gemma-4-26b-a4b-it", "gemma-4-31b-it",
          "gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]
MIN_KY_TU_TRANG = 200


def mot_trang(doc, i):
    m = pymupdf.open()
    m.insert_pdf(doc, from_page=i, to_page=i)
    return m.tobytes()


def ocr_trang(keys, by, log):
    """Thu lan luot model x key cho MOT trang. -> (text, model, ly_do_that_bai)."""
    ly = []
    for mo in MODELS:
        for lan in range(3):
            k = keys[(hash((mo, lan, len(by))) % len(keys))]
            try:
                t, kt = _goi(k, mo, by, PROMPT)
                s, _v = lam_sach(t or "")
                kt = str(kt).replace("FinishReason.", "")
                if len(s) >= MIN_KY_TU_TRANG:
                    return s, mo, ""
                ly.append("%s/%s:%s(%d)" % (mo, lan, kt, len(s)))
                if kt == "RECITATION":
                    break             # doi model, thu lai cung model vo ich
            except Exception as e:
                ly.append("%s/%s:%s" % (mo, lan, str(e)[:24]))
                time.sleep(2)
    return "", "", " | ".join(ly[:4])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", nargs="+", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    keys = [k["key"] for k in QuanLyKey().keys]
    print("=" * 84)
    print("CỨU FILE BỊ RECITATION — từng trang, Gemma đi trước")
    print("=" * 84)

    for d in a.doc:
        ds = glob.glob(str(GOC / "data" / "raw" / "pdf" / "**" / ("%s_*.pdf" % d)),
                       recursive=True)
        if not ds:
            print("  %s: không tìm thấy PDF" % d)
            continue
        p = Path(ds[0])
        doc = pymupdf.open(p)
        print("\n  %s — %d trang  %s" % (d, len(doc), p.name[:56]))

        phan, hong = [], []
        for i in range(len(doc)):
            s, mo, ly = ocr_trang(keys, mot_trang(doc, i), print)
            if s:
                print("     trang %-3d OK %6d ký tự  [%s]" % (i + 1, len(s), mo))
                phan.append("--- [Trang %d] ---\n%s" % (i + 1, s))
            else:
                print("     trang %-3d ✖ %s" % (i + 1, ly))
                hong.append(i + 1)
                phan.append("--- [Trang %d] ---\n[[KHÔNG OCR ĐƯỢC TRANG %d]]"
                            % (i + 1, i + 1))

        t = "\n\n".join(phan)
        dat, ly = kiem_dinh(t, so_trang=len(doc))
        print("     → %d/%d trang, %s ký tự | kiểm định: %s %s"
              % (len(doc) - len(hong), len(doc), "{:,}".format(len(t)),
                 "ĐẠT" if dat else "KHÔNG ĐẠT", ly))

        if not a.apply:
            continue
        if not dat:
            print("     KHÔNG ghi: chưa đạt kiểm định")
            continue
        # ghi vao dung thu muc linh vuc nhu pipeline chinh
        thu_muc = RA / p.parent.name
        thu_muc.mkdir(parents=True, exist_ok=True)
        f = thu_muc / (p.stem + ".txt")
        io.open(f, "w", encoding="utf-8", newline="\n").write(t)
        print("     ✔ đã ghi: %s" % f.relative_to(GOC))

    if not a.apply:
        print("\n" + "=" * 84)
        print(">>> Mới là XEM TRƯỚC. Thêm --apply để ghi vào text_gemma_moi.")


if __name__ == "__main__":
    main()
