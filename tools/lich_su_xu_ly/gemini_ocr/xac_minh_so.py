# -*- coding: utf-8 -*-
"""Xac minh cac CHO CO SO dang ngo trong text_raw — chi OCR dung trang can thiet.

Luong lam viec:
    soi_so.py   ->  ngo_so.json   (moi tai lieu kem danh sach trang dang ngo)
    script nay  ->  cat dung nhung trang do thanh PDF nho (gop N trang moi luot)
                ->  goi Gemini 3.5 Flash Lite, hong thi lui ve Gemma 31B
                ->  doi chieu so CU (text_raw) voi so MOI
                ->  xuat BANG DOI CHIEU de nguoi doc duyet

KHONG BAO GIO sua text_raw. Chi ghi ra data/doi_chieu_so/.

CO DIEM LUU — mat dien / dut mang / tat may giua chung thi chay lai la DI TIEP,
khong lam lai tu dau. Ba file trong data/doi_chieu_so/:
    ket_qua.jsonl       moi dong 1 ket qua doi chieu  (ghi them, khong ghi de)
    da_lam.jsonl        moi dong 1 luot da xu ly      (de biet cho nao bo qua)
    chua_xac_minh.json  cac luot that bai ca 2 model  (de goi lai rieng)
CSV va MD la BAN DAN XUAT tu ket_qua.jsonl, sinh lai luc nao cung duoc.

Chay:
    python xac_minh_so.py                       # chay (tu dong tiep tuc neu dang do)
    python xac_minh_so.py --gioi-han 5          # thu 5 tai lieu dau
    python xac_minh_so.py --moi-luot 3          # gop 3 trang moi luot goi
    python xac_minh_so.py --lam-lai-tu-dau      # xoa diem luu, chay lai het
    python xac_minh_so.py --xuat-bang           # chi sinh lai CSV/MD, khong goi API
    python xac_minh_so.py --ngo <chua_xac_minh.json>    # chay lai rieng phan that bai
"""
import argparse
import csv
import difflib
import io as _io
import json
import re
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gemma_ocr import QuanLyKey, _ocr_hai_tang, TIMEOUT_MOI_KHUC_MS   # noqa: E402
from soi_so import MOC_TRANG                                          # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import pymupdf
except ImportError:
    pymupdf = None

GOC = Path(__file__).resolve().parents[2]
RAW_TXT = GOC / "data" / "processed" / "text_raw"
RAW_PDF = GOC / "data" / "raw"
RA = GOC / "data" / "doi_chieu_so"

COT_CSV = ["doc_id", "file", "trang", "so_cu", "so_moi", "khop", "model", "ngu_canh"]

PROMPT = ("Chép lại NGUYÊN VĂN toàn bộ chữ trong các trang PDF này thành plaintext. "
          "Đặc biệt giữ CHÍNH XÁC mọi con số: số hiệu văn bản, ngày tháng năm, số điều khoản. "
          "Không tóm tắt, không thêm bình luận, không giải thích.")

# Token "so" can doi chieu: so hieu van ban va ngay thang
TOKEN = re.compile(
    r"\d{1,5}\s*/\s*[\wĐ\-]{2,}(?:\s*/\s*[\wĐ\-]{2,})?"      # 78/2020/NĐ-CP, 2347/QĐ-ĐHBK
    r"|ngày\s+\S{1,4}\s+tháng\s+\S{1,4}\s+năm\s+\S{1,6}"      # ngày 06 tháng 7 năm 2020
    r"|\d{1,2}/\d{1,2}/\d{4}",                                # 25/01/2022
    re.I)

NGUONG_GIONG = 0.55        # duoi muc nay coi nhu KHONG tim thay doi ung

_khoa = threading.Lock()
_so = {"luot": 0, "xong": 0, "hong": 0, "lech": 0}


# ── tien ich ─────────────────────────────────────────────────────────────────
def chuan(s):
    return re.sub(r"\s+", " ", s or "").strip()


def bo_dau_cau(s):
    r"""Bo dau cau/ky tu markdown o hai dau truoc khi SO SANH.

    Bieu thuc bat token dung \S nen nuot luon dau ';' '.' '*' dinh sau nam. Model moi
    tra loi co markdown nen hay them '*' hoac '.' -> hai ben lech nhau o DAU CAU trong
    khi con so giong het. Da bao nham 47 cho vi ly do nay.
    """
    return chuan(s).strip(" .,;:*_`'\"()[]-–—")


def giong(a, b):
    return difflib.SequenceMatcher(None, chuan(a).lower(), chuan(b).lower()).ratio()


def loai_token(t):
    """'ngay' hoac 'so_hieu' — chi doi chieu token CUNG LOAI voi nhau."""
    return "ngay" if re.match(r"^(ngày|\d{1,2}/\d{1,2}/\d{4})", t.strip(), re.I) else "so_hieu"


def thanh(x, t, rong=30):
    n = int(rong * x / t) if t else 0
    return "█" * n + "░" * (rong - n)


def khoa_luot(ten_file, cum):
    return "%s|%s" % (ten_file, "-".join(map(str, cum)))


def chi_muc_pdf():
    """doc_id (4 so dau ten file) -> duong dan PDF.

    Co doc_id nam o nhieu thu muc (0014 o ca pdf/ lan pdf_fixed/, 0193 o ca pdf/ lan
    doc_new/). Lay bua cai nao rglob gap truoc thi co the xac minh nham ban -> uu tien
    thu muc pdf/ vi day la ban chuan.
    """
    ix = {}
    for f in sorted(RAW_PDF.rglob("*.pdf")):
        m = re.match(r"(\d{4})_", f.name)
        if not m:
            continue
        k = m.group(1)
        trong_pdf = f.relative_to(RAW_PDF).as_posix().startswith("pdf/")
        if k not in ix or (trong_pdf and not ix[k][1]):
            ix[k] = (f, trong_pdf)
    return {k: v[0] for k, v in ix.items()}


_nho_text = {}
_khoa_nho = threading.Lock()


def text_theo_trang(f):
    """-> {so_trang: [dong,...]}. Doc 1 lan roi nho: file 95 trang truoc bi doc 19 lan."""
    with _khoa_nho:
        if f in _nho_text:
            return _nho_text[f]
    d = defaultdict(list)
    trang = 1
    for dong in f.read_text(encoding="utf-8", errors="replace").splitlines():
        m = MOC_TRANG.search(dong)
        if m:
            trang = int(m.group(1))
            continue
        if dong.strip():
            d[trang].append(dong.strip())
    with _khoa_nho:
        _nho_text[f] = d
    return d


def gop_trang(trang, moi_luot):
    """[1,2,5,6,7,20] gop 4 -> [[1,2],[5,6,7],[20]]. Danh sach rong -> [] (khong vo)."""
    sach = sorted({int(t) for t in trang if str(t).lstrip("-").isdigit()})
    if not sach:
        return []
    cum, hien = [], [sach[0]]
    for t in sach[1:]:
        if t == hien[-1] + 1 and len(hien) < moi_luot:
            hien.append(t)
        else:
            cum.append(hien)
            hien = [t]
    cum.append(hien)
    return cum


def cat_trang(pdf, ds_trang):
    """Cat cac trang (danh so tu 1) thanh 1 PDF nho trong bo nho."""
    with pymupdf.open(pdf) as d:
        nho = pymupdf.open()
        for t in ds_trang:
            if 1 <= t <= d.page_count:
                nho.insert_pdf(d, from_page=t - 1, to_page=t - 1)
        b = _io.BytesIO()
        nho.save(b)
        nho.close()
    return b.getvalue()


def noi_dong_bi_ngat(dong):
    """Noi lai token bi NGAT DONG trong text_raw.

    So hieu '91/2017/NĐ-CP' co the vat qua 2 dong: dong tren ket thuc bang '91/201',
    dong duoi bat dau '7/NĐ-CP'. Bat token tren tung dong rieng le se ra 2 manh vun,
    doi chieu se bao 'lech nang' oan trong khi that ra chi la cho xuong dong.
    Noi khi dong tren ket thuc bang chu so hoac '/' '-' va dong duoi bat dau bang
    chu so hoac chu in hoa.
    """
    ra = []
    for d in dong:
        if ra and re.search(r"[\d/\-]$", ra[-1]) and re.match(r"^[\dA-ZĐ]", d):
            ra[-1] = ra[-1] + d
        else:
            ra.append(d)
    return ra


def phan_so(t):
    """Phan SO dung truoc dau '/' dau tien: '05/NQ-HĐT' -> '05'. Khong co thi ''. """
    m = re.match(r"\s*(\d{1,5})\s*/", bo_dau_cau(t))
    return m.group(1).lstrip("0") or "0" if m else ""


def cung_van_ban(cu, moi):
    """Hai so hieu co phai CUNG MOT van ban khong?

    Voi so hieu, khac o phan SO la KHAC HAN mot van ban ('05/NQ-HĐT' va '04/NQ-HĐT' la
    hai nghi quyet rieng biet), con khac o phan CHU moi la loi OCR ('Q4-TTg' vs 'QĐ-TTg').
    Truoc day ghep theo do giong chung nen '05' bi ghep voi '04' (giong 89%) roi bao
    LECH oan — ap sua theo do se bien so dung thanh so sai.
    """
    a, b = phan_so(cu), phan_so(moi)
    if a and b:
        return a == b
    return True          # khong phai dang x/... thi khong ap dung quy tac nay


def la_bi_cat(cu, moi):
    """Chuoi cu co phai chi la MOT PHAN cua chuoi moi khong (dau hoac duoi)?"""
    a = bo_dau_cau(cu).lower().replace(" ", "")
    b = bo_dau_cau(moi).lower().replace(" ", "")
    return bool(a) and a != b and (b.startswith(a) or b.endswith(a))


def doi_chieu(dong_cu, text_moi):
    """Ghep tung token CU voi token MOI GIONG NHAT cung loai, tim tren toan ban moi.

    KHONG ghep theo thu tu trong dong: ban moi ngat dong khac ban cu nen ghep theo vi
    tri se lech nhip — da do: '2347/QĐ-ĐHBK' bi ghep voi 'ngày 14 tháng 11 năm 2018'.
    Ghep theo do giong thi '70/2014/Q4-TTg' tim dung '70/2014/QĐ-TTg'.

    -> [(token_cu, token_moi, khop, dong_ngu_canh)]
    """
    toks_moi = []
    for x in TOKEN.findall(text_moi):
        x = chuan(x)
        if x not in toks_moi:
            toks_moi.append(x)

    ra, da_ra = [], set()
    for dc in noi_dong_bi_ngat(list(dong_cu)):
        for tc in TOKEN.findall(dc):
            tc = chuan(tc)
            if tc in da_ra:
                continue
            da_ra.add(tc)
            lc = loai_token(tc)
            hop_le = [tm for tm in toks_moi
                      if loai_token(tm) == lc and (lc != "so_hieu" or cung_van_ban(tc, tm))]
            ung_vien = sorted(((giong(tc, tm), tm) for tm in hop_le), reverse=True)
            tm = ung_vien[0][1] if ung_vien and ung_vien[0][0] >= NGUONG_GIONG else ""
            khop = bool(tm) and (bo_dau_cau(tc).lower().replace(" ", "")
                                 == bo_dau_cau(tm).lower().replace(" ", ""))
            ra.append((tc, tm, khop, chuan(dc)[:110]))
    return ra


def xuat_bang(hang, so_luot_hong):
    """Sinh CSV + MD tu du lieu da co. Goi duoc bat cu luc nao, ke ca khi dang chay do."""
    RA.mkdir(parents=True, exist_ok=True)
    ds = sorted(hang, key=lambda r: (r["khop"] == "khớp", r["doc_id"], str(r["trang"])))
    # File dang mo trong Excel thi Windows KHOA lai -> ghi de se nem PermissionError va
    # lam hong ca lan xuat bang. Ghi sang ten khac roi bao, thay vi de chuong trinh chet.
    csv_p = RA / "doi_chieu_so.csv"
    try:
        f = open(csv_p, "w", encoding="utf-8-sig", newline="")
    except PermissionError:
        csv_p = RA / "doi_chieu_so_moi.csv"
        f = open(csv_p, "w", encoding="utf-8-sig", newline="")
        print("  ⚠ doi_chieu_so.csv đang mở (Excel?) → ghi sang doi_chieu_so_moi.csv")
    with f:
        w = csv.DictWriter(f, fieldnames=COT_CSV, extrasaction="ignore")
        w.writeheader()
        w.writerows(ds)

    lech = [r for r in ds if r["khop"] == "LỆCH"]
    khong_thay = [r for r in ds if r["khop"] == "KHÔNG THẤY"]
    md_p = RA / "doi_chieu_so.md"
    with open(md_p, "w", encoding="utf-8", newline="\n") as f:
        f.write("# Bảng đối chiếu số — text_raw so với OCR xác minh\n\n")
        f.write("- Tổng token số đã đối chiếu: **%d**\n" % len(ds))
        f.write("- **LỆCH (cần xem): %d**\n" % len(lech))
        f.write("- Không tìm thấy đối ứng: %d\n" % len(khong_thay))
        f.write("- Khớp: %d\n" % (len(ds) - len(lech) - len(khong_thay)))
        if so_luot_hong:
            f.write("- ⚠ **Chưa xác minh được: %d lượt** — xem `chua_xac_minh.json`\n"
                    % so_luot_hong)
        f.write("\n> Chưa sửa gì vào `text_raw`. Duyệt xong mới quyết định áp.\n\n")
        f.write("## Các chỗ LỆCH\n\n")
        f.write("| doc | trang | text_raw (cũ) | OCR xác minh (mới) | ngữ cảnh |\n")
        f.write("|---|---|---|---|---|\n")
        for r in lech:
            f.write("| %s | %s | `%s` | `%s` | %s |\n"
                    % (r["doc_id"], r["trang"], r["so_cu"], r["so_moi"],
                       str(r["ngu_canh"]).replace("|", "/")[:80]))
    return csv_p, md_p


def nap_diem_luu(kq_p, dl_p):
    """-> (danh sach ket qua da co, tap khoa cac luot da lam xong)"""
    hang, da_xong = [], set()
    if kq_p.exists():
        for l in kq_p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                hang.append(json.loads(l))
            except Exception:
                pass        # dong ghi do dang do mat dien -> bo qua, khong lam chet chuong trinh
    if dl_p.exists():
        for l in dl_p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                d = json.loads(l)
                if d.get("ok"):
                    da_xong.add(d["khoa"])
            except Exception:
                pass
    return hang, da_xong


# ── chuong trinh chinh ───────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ngo", default=str(Path(__file__).resolve().parent / "ngo_so.json"))
    ap.add_argument("--moi-luot", type=int, default=4)
    ap.add_argument("--song-song", type=int, default=4)
    ap.add_argument("--model", default="gemini-3.5-flash-lite")
    ap.add_argument("--model-lui", default="gemma-4-31b-it")
    ap.add_argument("--gioi-han", type=int, default=0)
    ap.add_argument("--lam-lai-tu-dau", action="store_true")
    ap.add_argument("--xuat-bang", action="store_true")
    ap.add_argument("--nguon", default=None,
                    help="thư mục text cần xác minh (mặc định text_raw)")
    ap.add_argument("--ra", default=None,
                    help="thư mục ghi kết quả + ĐIỂM LƯU (mặc định data/doi_chieu_so)")
    a = ap.parse_args()

    # Doi nguon/dich thi doi luon DIEM LUU: moi dot xac minh mot corpus khac nhau phai co
    # so ghi rieng, neu dung chung 'da_lam.jsonl' thi dot sau se tuong cac luot cua dot
    # truoc la da xong roi bo qua het.
    global RAW_TXT, RA
    if a.nguon:
        RAW_TXT = Path(a.nguon) if Path(a.nguon).is_absolute() else GOC / a.nguon
    if a.ra:
        RA = Path(a.ra) if Path(a.ra).is_absolute() else GOC / a.ra

    if not pymupdf:
        print("Thiếu pymupdf trong môi trường Python này.")
        sys.exit(1)

    RA.mkdir(parents=True, exist_ok=True)
    kq_p, dl_p, cx_p = RA / "ket_qua.jsonl", RA / "da_lam.jsonl", RA / "chua_xac_minh.json"

    if a.lam_lai_tu_dau:
        for f in (kq_p, dl_p, cx_p):
            if f.exists():
                f.unlink()
        print("Đã xoá điểm lưu, chạy lại từ đầu.")

    hang, da_xong_khoa = nap_diem_luu(kq_p, dl_p)

    if a.xuat_bang:
        csv_p, md_p = xuat_bang(hang, 0)
        print("Đã sinh lại bảng từ %d kết quả đã lưu:\n  %s\n  %s" % (len(hang), csv_p, md_p))
        return

    ngo = json.loads(Path(a.ngo).read_text(encoding="utf-8"))
    if a.gioi_han:
        ngo = ngo[: a.gioi_han]
    ix = chi_muc_pdf()

    viec, thieu_pdf = [], []
    for muc in ngo:
        ftxt = RAW_TXT / muc["file"]
        m = re.match(r"(\d{4})_", ftxt.name)
        pdf = ix.get(m.group(1)) if m else None
        if not pdf:
            thieu_pdf.append(muc["file"])
            continue
        for cum in gop_trang(muc["trang"], a.moi_luot):
            viec.append((ftxt, pdf, cum))

    tong_goc = len(viec)
    viec = [v for v in viec if khoa_luot(v[0].name, v[2]) not in da_xong_khoa]
    bo_qua = tong_goc - len(viec)
    tong = len(viec)

    print("=" * 92)
    print("XÁC MINH SỐ — chỉ OCR lại những trang đáng ngờ")
    print("  Model    : %s  →  lùi về %s" % (a.model, a.model_lui))
    print("  Gộp      : %d trang mỗi lượt | %d luồng song song" % (a.moi_luot, a.song_song))
    print("  Tài liệu : %d | tổng lượt: %d" % (len(ngo), tong_goc))
    if bo_qua:
        print("  ⏩ TIẾP TỤC: bỏ qua %d lượt đã làm lần trước, còn %d lượt" % (bo_qua, tong))
    if thieu_pdf:
        print("  ⚠ %d tài liệu không tìm thấy PDF gốc, bỏ qua" % len(thieu_pdf))
    print("=" * 92)

    if not tong:
        csv_p, md_p = xuat_bang(hang, 0)
        print("Không còn lượt nào phải chạy.")
        print("Bảng đối chiếu: %s\n                %s" % (csv_p, md_p))
        return

    qlk = QuanLyKey(model=a.model)
    qlk.kiem_tra(hien_thi=False)
    qlk.kiem_tra_sau(hien_thi=False)
    print("  Key dùng được: %d/%d" % (qlk.con_song(), len(qlk.keys)))
    print("-" * 92)

    chua_xong = []
    models = [a.model] + ([a.model_lui] if a.model_lui and a.model_lui != a.model else [])
    f_kq = open(kq_p, "a", encoding="utf-8", newline="\n")
    f_dl = open(dl_p, "a", encoding="utf-8", newline="\n")
    t0 = time.perf_counter()

    def ghi_chua_xong(ftxt, cum, ly_do):
        chua_xong.append({"file": ftxt.relative_to(RAW_TXT).as_posix(),
                          "trang": list(cum), "ly_do": str(ly_do)[:150]})
        gom = {}
        for c in chua_xong:
            g = gom.setdefault(c["file"], {"file": c["file"], "trang": [], "ly_do": c["ly_do"]})
            g["trang"].extend(c["trang"])
        for g in gom.values():
            g["trang"] = sorted(set(g["trang"]))
        cx_p.write_text(json.dumps(sorted(gom.values(), key=lambda x: x["file"]),
                                   ensure_ascii=False, indent=1), encoding="utf-8")

    def lam(v):
        ftxt, pdf, cum = v
        try:
            b = cat_trang(pdf, cum)
        except Exception as e:
            with _khoa:
                _so["luot"] += 1
                _so["hong"] += 1
                ghi_chua_xong(ftxt, cum, "cắt PDF hỏng: %s" % e)
                print("  ✖ %s tr.%s cắt PDF hỏng: %s"
                      % (ftxt.name[:36], "-".join(map(str, cum)), str(e)[:50]))
            return

        moi, gc = _ocr_hai_tang(qlk, b, PROMPT, models, len(cum), TIMEOUT_MOI_KHUC_MS,
                                min_ky_tu=max(60, 40 * len(cum)))
        theo_tr = text_theo_trang(ftxt)
        dong_cu = [d for t in cum for d in theo_tr.get(t, [])]
        cap = doi_chieu(dong_cu, moi) if moi else []

        with _khoa:
            _so["luot"] += 1
            if not moi:
                _so["hong"] += 1
                ghi_chua_xong(ftxt, cum, gc)
            else:
                _so["xong"] += 1
                for tc, tm, khop, nc in cap:
                    if not khop:
                        _so["lech"] += 1
                    h = {"doc_id": ftxt.name[:4], "file": ftxt.name,
                         "trang": "-".join(map(str, cum)), "so_cu": tc,
                         "so_moi": tm or "(không thấy)",
                         "khop": ("khớp" if khop else
                                  "KHÔNG THẤY" if not tm else
                                  "CŨ BỊ NGẮT DÒNG" if la_bi_cat(tc, tm) else "LỆCH"),
                         "model": gc, "ngu_canh": nc}
                    hang.append(h)
                    f_kq.write(json.dumps(h, ensure_ascii=False) + "\n")
                f_kq.flush()

            # danh dau da lam -> lan chay sau bo qua luot nay
            f_dl.write(json.dumps({"khoa": khoa_luot(ftxt.name, cum), "ok": bool(moi)},
                                  ensure_ascii=False) + "\n")
            f_dl.flush()

            r = _so["luot"]
            dt = time.perf_counter() - t0
            con = (dt / r) * (tong - r) / 60 if r else 0
            print("  %s %4d/%-4d %5.1f%%  xong %d hỏng %d LỆCH %d | còn ~%.0f phút | %s tr.%s"
                  % (thanh(r, tong), r, tong, 100.0 * r / tong, _so["xong"], _so["hong"],
                     _so["lech"], con, ftxt.name[:24], "-".join(map(str, cum))))

    try:
        with ThreadPoolExecutor(max_workers=a.song_song) as ex:
            list(ex.map(lam, viec))
    except KeyboardInterrupt:
        print("\n⏸ Đã dừng tay. Điểm lưu vẫn còn — chạy lại lệnh này là đi tiếp.")
    finally:
        f_kq.close()
        f_dl.close()

    csv_p, md_p = xuat_bang(hang, len(chua_xong))
    print("-" * 92)
    print("Lượt này: %d lượt | tổng %d token đối chiếu | %d LỆCH | %.0f phút"
          % (_so["luot"], len(hang), sum(1 for r in hang if r["khop"] == "LỆCH"),
             (time.perf_counter() - t0) / 60))
    if chua_xong:
        print("⚠ %d lượt CHƯA xác minh được → %s" % (len(chua_xong), cx_p))
        print('  chạy lại riêng: python xac_minh_so.py --ngo "%s"' % cx_p)
    print("Bảng đối chiếu: %s" % csv_p)
    print("                %s" % md_p)


if __name__ == "__main__":
    main()
