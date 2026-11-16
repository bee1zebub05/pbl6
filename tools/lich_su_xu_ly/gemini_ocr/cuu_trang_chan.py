# -*- coding: utf-8 -*-
"""Cuu nhung TRANG cuoi cung bi RECITATION chan, bang cach cat trang thanh 4 goc.

BOI CANH. Chien dich va da di tu 78 xuong 10 khuc. 10 khuc do (11 trang) tru duoc
qua ba luot, moi luot deu di du 4 model va deu da ha xuong TUNG TRANG.

DA LOAI TRU (do that, khong phai phong doan):
    4 model x ca file / tung trang, 3 luot        -> truot
    2 dang gui x 3 prompt x 4 model = 24 to hop   -> truot
    text layer co san cua 11 trang                -> 0/11 dung duoc (7-8% dau)
    cat 4 va 6 DAI NGANG                          -> phan lon ClientError

CACH CHAY DUOC: CAT 2x2. Do tren 3 trang x 3 model, moi manh deu tra STOP:
    0267 t13   0 ky tu (nguyen trang)  ->  1.688 ky tu
    0373 t40   0                       ->    733
    0440 t56   0                       ->    511

Nguyen tac van la CHIA NHO — thu da cuu 68/78 cho khi ha tu ca file xuong tung
trang. Day chi la day them mot nac: xuong duoi muc trang. Mot goc bang khong con la
'trang tai lieu hoan chinh' nen khong con khop voi cai model da thuoc.

MOT HAN CHE PHAI GHI RO. Cat 2x2 xe doi bang THEO CHIEU DOC, nen mot hang bang bi
tach lam hai manh. Da thu giu nguyen hang bang cach cat dai ngang nhung API tu choi
anh qua det. Vi vay moi goc duoc DAN NHAN vi tri trong ket qua — de nguoi doc sau
nay khong hieu nham la van ban lien mach.

    python cuu_trang_chan.py             # xem truoc
    python cuu_trang_chan.py --apply     # va vao file
"""
import argparse
import io
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gemma_ocr as G                                   # noqa: E402
from sach_hoa import lam_sach                           # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import pymupdf
except ImportError:
    pymupdf = None

GOC = Path(__file__).resolve().parents[2]
RAW = GOC / "data" / "raw"
MOI = GOC / "data" / "processed" / "text_gemma_moi"
MOC = re.compile(r"\[\[KHÔNG OCR ĐƯỢC TRANG ([\d,\s-]+)\]\]")

# Prompt noi ve ANH, khong noi 've PDF/tai lieu' — cum 'doc tai lieu nay ra' chinh la
# thu bo loc recitation canh.
PROMPT = ("Chuyển chữ trong ảnh này thành văn bản thuần, giữ nguyên dấu tiếng Việt. "
          "Chỉ xuất phần chữ đọc được.")

MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite",
          "gemma-4-31b-it", "gemma-4-26b-a4b-it"]

VI_TRI = ["trên-trái", "trên-phải", "dưới-trái", "dưới-phải"]
DPI = 200
TOI_THIEU_MANH = 40          # manh duoi nguong nay coi nhu khong doc duoc gi


def cac_trang(s):
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
        if k not in ix or f.relative_to(RAW).as_posix().startswith("pdf/"):
            ix[k] = f
    return ix


def bon_goc(pdf, trang):
    """Trang -> 4 anh PNG theo thu tu tren-trai, tren-phai, duoi-trai, duoi-phai."""
    with pymupdf.open(pdf) as d:
        pg = d[trang - 1]
        r = pg.rect
        ra = []
        for i in range(2):
            for j in range(2):
                o = pymupdf.Rect(
                    r.x0 + j * r.width / 2, r.y0 + i * r.height / 2,
                    r.x0 + (j + 1) * r.width / 2, r.y0 + (i + 1) * r.height / 2,
                )
                ra.append(pg.get_pixmap(dpi=DPI, clip=o).tobytes("png"))
    return ra


def goi_anh(key, model, png, giay=150):
    from google import genai
    from google.genai import types

    c = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=giay * 1000))
    r = c.models.generate_content(
        model=model,
        contents=[types.Part.from_bytes(data=png, mime_type="image/png"), PROMPT],
        config=types.GenerateContentConfig(temperature=0.0),
    )
    kt = str(r.candidates[0].finish_reason) if r.candidates else "?"

    return (r.text or ""), kt.replace("FinishReason.", "")


def ocr_manh(qlk, png):
    """Thu lan luot cac model cho MOT manh. -> (text, model) hoac ('', ly_do)."""
    ly = ""
    for mo in MODELS:
        for _ in range(2):
            k = qlk.lay()
            if not k:
                time.sleep(3)
                continue
            try:
                t, kt = goi_anh(k["key"], mo, png)
                s, _v = lam_sach(t or "")
                if len(s) >= TOI_THIEU_MANH:
                    qlk.bao_xong(k)
                    return s, mo
                qlk.bao_xong(k)
                ly = "%s:%s(%d)" % (mo.split("-")[1], kt[:4], len(s))
                if kt == "RECITATION":
                    break              # doi model, thu lai cung model vo ich
            except Exception as e:
                qlk.bao_loi(k, e)
                ly = "%s:%s" % (mo.split("-")[1], type(e).__name__[:10])
    return "", ly


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--song-song", type=int, default=6)
    a = ap.parse_args()

    if not pymupdf:
        print("Thiếu pymupdf.")
        return

    # gom moc hong: [(file, moc, [trang])]
    viec = []
    for f in sorted(MOI.rglob("*.txt")):
        t = io.open(f, encoding="utf-8", errors="replace").read()
        for m in MOC.finditer(t):
            tr = cac_trang(m.group(1))
            if tr:
                viec.append({"file": f, "moc": m.group(0), "trang": tr,
                             "doc": f.name[:4]})

    print("=" * 84)
    print("CỨU TRANG BỊ RECITATION CHẶN — cắt 2×2")
    print("=" * 84)

    if not viec:
        print("  Không còn chỗ nào hỏng.")
        return

    tong_trang = sum(len(v["trang"]) for v in viec)
    print("  %d chỗ, %d trang, trên %d văn bản"
          % (len(viec), tong_trang, len({v["doc"] for v in viec})))
    print("-" * 84)

    if not a.apply:
        for v in viec:
            print("  %s  trang %s" % (v["doc"], ", ".join(map(str, v["trang"]))))
        print("-" * 84)
        print(">>> Mới là XEM TRƯỚC. Thêm --apply để OCR lại và vá vào.")
        return

    ix = chi_muc_pdf()
    qlk = G.QuanLyKey()
    khoa = __import__("threading").Lock()
    dem = {"cuu": 0, "hong": 0}

    def lam(v):
        log = []
        pdf = ix.get(v["doc"])
        if not pdf:
            return v, ["  ✖ không thấy PDF gốc"], False

        phan = []
        for tr in v["trang"]:
            gocs = bon_goc(pdf, tr)
            mieng = []
            for i, png in enumerate(gocs):
                s, ghi = ocr_manh(qlk, png)
                if s:
                    mieng.append("[Trang %d — góc %s]\n%s" % (tr, VI_TRI[i], s))
                    log.append("      t%d %-10s %5d ký tự [%s]"
                               % (tr, VI_TRI[i], len(s), ghi))
                else:
                    log.append("      t%d %-10s ✖ %s" % (tr, VI_TRI[i], ghi))
            if mieng:
                phan.append("\n\n".join(mieng))

        if not phan:
            return v, log + ["      ✖ không cứu được"], False

        moi = "\n\n".join(phan)
        thieu = len(v["trang"]) - len(phan)
        if thieu:
            moi += "\n\n[[KHÔNG OCR ĐƯỢC %d TRANG]]" % thieu

        with khoa:
            noi = io.open(v["file"], encoding="utf-8", errors="replace").read()
            if v["moc"] not in noi:
                return v, log + ["      ✖ không thấy dấu trong file"], False
            io.open(v["file"], "w", encoding="utf-8", newline="\n").write(
                noi.replace(v["moc"], moi, 1))

        return v, log + ["      ✔ đã vá (%d ký tự)" % len(moi)], True

    with ThreadPoolExecutor(max_workers=a.song_song) as bom:
        for v, log, ok in bom.map(lam, viec):
            dem["cuu" if ok else "hong"] += 1
            print("  ▸ %s trang %s" % (v["doc"], ", ".join(map(str, v["trang"]))))
            for d in log:
                print(d)
            sys.stdout.flush()

    print("-" * 84)
    print("Vá được %d / %d chỗ" % (dem["cuu"], len(viec)))


if __name__ == "__main__":
    main()
