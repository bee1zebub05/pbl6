# -*- coding: utf-8 -*-
"""Vet nguoi ky cho nhung van ban chua doc duoc, bang cach OCR LAI trang co khoi ky.

VI SAO CAN. 33 van ban chua doc duoc nguoi ky. Da mo PDF doc tan mat vai cai:
nguoi ky CO TREN GIAY (0229: 'ThS. Nguyễn Thị Hường'), nhung ban OCR hien tai
khong bat duoc — khoi ky bi con dau de len, bi xao do bo cuc hai cot, hoac trang
do khong duoc OCR ky.

CACH LAM. Khong doan tu text cu nua. Xac dinh trang co khoi ky roi OCR LAI RIENG
trang do o do phan giai cao, chi hoi model DUNG MOT VIEC: doc khoi ky.

DINH VI TRANG. Khoi ky nam o cuoi PHAN CHINH VAN, khong phai cuoi file — phan lon
van ban co phu luc dai phia sau. Lay trang chua CHUC DANH cuoi cung trong phan
dau, va thu them vai trang quanh do.

MOT CAI BAY DA GAP: nhieu PDF co kem 'PHIẾU GIẢI QUYẾT VĂN BẢN ĐẾN' o cuoi — to
dinh tuyen noi bo, co chu 'Ban Giám đốc', 'lãnh đạo đơn vị' nen bi cham nham la
khoi ky. To do KHONG co ten nguoi ky.

    python vet_nguoi_ky.py             # xem truoc
    python vet_nguoi_ky.py --apply     # ghi ket qua ra JSON
"""
import argparse
import csv
import glob
import io
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gemma_ocr as G                                   # noqa: E402
from sach_hoa import lam_sach                           # noqa: E402
from trich_do_thi import chuan_chuc_danh, tim_chu_ky    # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import pymupdf
except ImportError:
    pymupdf = None

GOC = Path(__file__).resolve().parents[2]
KHO = GOC / "data" / "processed" / "text_final"
RA = GOC / "data" / "nguoi_ky_vet.json"

# Hoi model DUNG MOT VIEC. Prompt hep thi ket qua sach hon han prompt OCR chung
# chung: khong phai loc khoi ca trang chu.
PROMPT = (
    "Đây là ảnh một trang văn bản hành chính Việt Nam. Hãy tìm KHỐI KÝ ở cuối "
    "văn bản (thường nằm góc dưới bên phải, gồm chức danh in hoa, con dấu đỏ, và "
    "họ tên người ký in bên dưới chữ ký).\n\n"
    "Trả lời ĐÚNG hai dòng, không thêm gì khác:\n"
    "CHUCDANH: <chức danh, ví dụ KT. HIỆU TRƯỞNG hoặc TL. GIÁM ĐỐC>\n"
    "HOTEN: <họ tên đầy đủ người ký, kèm học hàm nếu có>\n\n"
    "Nếu trang này KHÔNG có khối ký thì trả lời đúng một dòng: KHONGCO"
)

MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite",
          "gemma-4-31b-it", "gemma-4-26b-a4b-it"]

CD = re.compile(r"HIEU TRUONG|GIAM DOC|CHU TICH|BO TRUONG|THU TUONG|THU TRUONG|"
                r"TM\.|KT\.|TL\.|CHANH VAN PHONG|TRUONG BAN")
MOC = re.compile(r"-{3,}\s*\[Trang\s+(\d+)\]\s*-{3,}")
# To dinh tuyen noi bo kem trong PDF — khong phai khoi ky
PHIEU = re.compile(r"PHIẾU\s+GIẢI\s+QUYẾT|PHIEU\s+GIAI\s+QUYET", re.I)

DONG_CD = re.compile(r"CHUCDANH\s*:\s*(.+)", re.I)
DONG_TEN = re.compile(r"HOTEN\s*:\s*(.+)", re.I)


def trang_kha_nghi(t, so_trang):
    """-> danh sach trang co the chua khoi ky, uu tien cao xuong thap."""
    from trich_do_thi import _bo_dau

    kd = _bo_dau(t)
    moc = [(m.start(), int(m.group(1))) for m in MOC.finditer(t)]
    ra = []

    for m in CD.finditer(kd):
        truoc = [so for vt, so in moc if vt <= m.start()]
        if truoc:
            ra.append(truoc[-1])

    # trang cuoi phan chinh van thuong la noi co khoi ky; them vai ung vien
    ưu = []
    for x in reversed(ra):
        if x not in ưu:
            ưu.append(x)

    for x in (so_trang, so_trang - 1, 2, 3):
        if 1 <= x <= so_trang and x not in ưu:
            ưu.append(x)

    return ưu[:4]


def doc_khoi_ky(qlk, pdf, trang):
    """OCR rieng mot trang, hoi dung khoi ky. -> (chuc danh, ho ten) hoac ('','')."""
    from google import genai
    from google.genai import types

    with pymupdf.open(pdf) as d:
        if not (1 <= trang <= d.page_count):
            return "", "", "ngoài phạm vi"
        png = d[trang - 1].get_pixmap(dpi=200).tobytes("png")

    for mo in MODELS:
        for _ in range(2):
            k = qlk.lay()
            if not k:
                time.sleep(2)
                continue
            try:
                c = genai.Client(api_key=k["key"],
                                 http_options=types.HttpOptions(timeout=120000))
                r = c.models.generate_content(
                    model=mo,
                    contents=[types.Part.from_bytes(data=png, mime_type="image/png"),
                              PROMPT],
                    config=types.GenerateContentConfig(temperature=0.0))
                qlk.bao_xong(k)
                s, _v = lam_sach(r.text or "")

                if "KHONGCO" in s.upper().replace(" ", ""):
                    return "", "", "trang không có khối ký"

                mt = DONG_TEN.search(s)
                mc = DONG_CD.search(s)

                if mt:
                    return ((mc.group(1).strip() if mc else ""),
                            mt.group(1).strip(), mo.split("-")[1])
            except Exception as e:
                qlk.bao_loi(k, e)

    return "", "", "không đọc được"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--song-song", type=int, default=6)
    a = ap.parse_args()

    if not pymupdf:
        print("Thiếu pymupdf.")
        return

    bc = GOC / "data" / "bao_cao_ban_cuoi.csv"
    thieu = [x for x in csv.DictReader(io.open(bc, encoding="utf-8-sig"))
             if not x["nguoi_ky"]]

    ke = []
    for x in thieu:
        p = list(KHO.rglob(x["doc"] + "_*.txt"))
        pdf = glob.glob(str(GOC / "data" / "raw" / "pdf" / "**"
                            / (x["doc"] + "_*.pdf")), recursive=True)
        if not (p and pdf):
            continue
        t = io.open(p[0], encoding="utf-8", errors="replace").read()
        n = len(pymupdf.open(pdf[0]))
        ke.append({"doc": x["doc"], "so_hieu": x["so_hieu"], "pdf": pdf[0],
                   "trang": trang_kha_nghi(t, n), "so_trang": n})

    print("=" * 84)
    print("VÉT NGƯỜI KÝ — OCR lại riêng trang có khối ký")
    print("=" * 84)
    print("  %d văn bản, mỗi cái thử tối đa 4 trang" % len(ke))
    print("-" * 84)

    if not a.apply:
        for x in ke[:12]:
            print("  %s %-20s %3d trang -> thử %s"
                  % (x["doc"], x["so_hieu"], x["so_trang"], x["trang"]))
        print(">>> Mới là XEM TRƯỚC. Thêm --apply để chạy.")
        return

    qlk = G.QuanLyKey()
    qlk.kiem_tra_sau()
    print("-" * 84)

    def lam(x):
        for tr in x["trang"]:
            cd, ten, ghi = doc_khoi_ky(qlk, x["pdf"], tr)
            if ten:
                return x, tr, cd, ten, ghi
        return x, None, "", "", "không thấy khối ký ở 4 trang đã thử"

    kq = {}
    with ThreadPoolExecutor(max_workers=a.song_song) as bom:
        for x, tr, cd, ten, ghi in bom.map(lam, ke):
            if ten:
                kq[x["doc"]] = {"so_hieu": x["so_hieu"], "trang": tr,
                                "chuc_danh": cd, "ho_ten": ten, "model": ghi}
                print("  ✔ %s %-20s t%-3s %-26s %s"
                      % (x["doc"], x["so_hieu"], tr, ten[:26], cd[:24]))
            else:
                print("  ✖ %s %-20s %s" % (x["doc"], x["so_hieu"], ghi))
            sys.stdout.flush()

    RA.parent.mkdir(parents=True, exist_ok=True)
    RA.write_text(json.dumps(kq, ensure_ascii=False, indent=1), encoding="utf-8")
    print("-" * 84)
    print("Vét được %d / %d | ghi: %s" % (len(kq), len(ke), RA.relative_to(GOC)))


if __name__ == "__main__":
    main()
