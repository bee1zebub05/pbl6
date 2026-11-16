# -*- coding: utf-8 -*-
"""Do tim cac CHO CO SO trong text_raw co dau hieu OCR sai, kem SO TRANG.

Y tuong: text_raw la ban OCR THO, sai nhieu o cho co so (da thay "ngay A4 thang 11",
"Q4-TTg", "chinF phu"). Thay vi OCR lai ca file 50 trang, chi can biet TRANG NAO co so
dang ngo roi goi model xac minh dung trang do.

text_raw co san moc "----- [Trang N] -----" nen suy ra so trang de dang.

Chay:
    python soi_so.py                     # quet het, in thong ke
    python soi_so.py --chi-tiet          # in tung dong ngo
    python soi_so.py --ra ngo.json       # xuat danh sach (file, trang) de xac minh
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
RAW_TXT = GOC / "data" / "processed" / "text_raw"
RAW_PDF = GOC / "data" / "raw"

MOC_TRANG = re.compile(r"-{3,}\s*\[Trang\s+(\d+)\]\s*-{3,}")

# Ky tu OCR hay doc nham thanh chu: O<->0, l/I<->1, S<->5, B<->8, Z<->2, G<->6, A<->4
NHAM = "OolIiLSsBbZzGgAaq"

# Loai van ban HOP LE co chua chu so — khong duoc bao nham:
#   QH13/QH14/QH15 = Quoc hoi khoa 13/14/15
#   TW, CT-TW, NQ-TW... khong co so
HOP_LE = re.compile(r"^(QH\d{2}|K\d{1,2}|TW\d?)$", re.I)

# Van ban cua DANG danh so kieu <so>-<LOAI>/<CO QUAN>: 29-NQ/TW, 69-KL/TW, 27-CT/TW,
# 01-KH/BCDTW, 15-QDi/TW. Gach ngang chu khong phai gach cheo — bo luat cu doc phan
# truoc dau '/' la '29-NQ' roi bao "khong phai so". Day la dinh dang DUNG, khong phai loi.
DANG_SO = re.compile(r"^\d{1,4}\s*-\s*[A-ZĐ][A-Za-zĐ]{0,4}$")

# Bieu mau de TRONG: "Nghi dinh so ..../2020/ND-CP", "ngay .... thang .... nam ....".
# Ban goc von de trong cho nguoi dien tay. Bo dau cham di ma con lai rong -> mau trong;
# con lai chu so -> mau DA DIEN ("...05....../NQ-HĐT" la so 05, hoan toan dung).
def loc_cham(s):
    """Bo dau cham/gach/khoang trang lam duong ke -> phan con lai."""
    return re.sub(r"[.…\s_]+", "", s or "")


def la_mau_trong(s):
    return bool(re.search(r"(\.\s*){2,}|…", s or "")) and not re.search(r"\d", loc_cham(s))

# Tham chieu NAM GIUA NOI DUNG: "Can cu Nghi dinh so ...", "Theo Quyet dinh so ...",
# "Dua vao Nghi quyet so ...". Day moi la cho hay bi sai nhat va de bo sot nhat.
DAN_CHIEU = re.compile(
    r"(?:căn\s*cứ|theo|dựa\s*vào|kèm\s*theo|quy\s*định\s*tại|tại)\s+"
    r"(?:nghị\s*định|nghị\s*quyết|quyết\s*định|thông\s*tư|thông\s*báo|công\s*văn|"
    r"chỉ\s*thị|luật|kế\s*hoạch|hướng\s*dẫn|văn\s*bản)\s*(?:số)?\s*([^\s,;()]{2,40})",
    re.I)

LUAT = [
    ("dẫn chiếu trong nội dung", DAN_CHIEU, "so_hieu"),
    # (ten, bieu thuc, ham kiem tra dong khop co dang ngo khong)
    ("ngày tháng năm",
     re.compile(r"ngày\s+(\S{1,4})\s+tháng\s+(\S{1,4})\s+năm\s+(\S{1,6})", re.I),
     "ngay_thang"),
    ("số hiệu văn bản",
     re.compile(r"[Ss]ố:?\s*([^\s,;]{2,40})"),
     "so_hieu"),
    ("số hiệu dạng x/yyyy/KH",
     re.compile(r"\b(\d{0,4}[%s\d]{1,6}\s*/\s*[%s\d]{2,4}\s*/\s*[A-ZĐ][\w\-Đ]{1,12})" % (NHAM, NHAM)),
     "so_hieu"),
]


def kiem_ngay(m):
    """-> ly do neu dang ngo, None neu binh thuong"""
    ng, th, na = m.group(1), m.group(2), m.group(3)
    if all(la_mau_trong(x) or not loc_cham(x) for x in (ng, th, na)):
        return None                       # "ngày .... tháng .... năm ...." — mẫu để trống
    for ten, gt, lo, hi in (("ngày", ng, 1, 31), ("tháng", th, 1, 12), ("năm", na, 1900, 2100)):
        gt = gt.strip(".,;:")
        if la_mau_trong(gt):
            continue                      # riêng ô này để trống, các ô khác vẫn kiểm
        gt = loc_cham(gt) or gt           # ".12." -> "12": dấu chấm là đường kẻ, không phải lỗi
        # PHAI kem isascii(): str.isdigit() nhan ca chu so mu ('2018²') va chu so cua
        # bang chu khac ('٢٠١٨') — nhung int() thi nem ValueError voi chu so mu, lam sap
        # ca luot quet. OCR van ban scan sinh ra nhung ky tu nay khong hiem.
        if not (gt.isascii() and gt.isdigit()):
            if any(c in NHAM for c in gt):
                return "%s='%s' lẫn chữ vào số" % (ten, gt)
            return "%s='%s' không phải số" % (ten, gt)
        v = int(gt)
        if not (lo <= v <= hi):
            return "%s=%d ngoài khoảng %d-%d" % (ten, v, lo, hi)
    return None


def kiem_so_hieu(m):
    s = m.group(1).strip(".,;:")
    if len(s) < 2:
        return None
    # phai co it nhat 1 chu so moi coi la so hieu
    if not any(c.isdigit() for c in s):
        return None
    # cum kieu 2347/QĐ-ĐHBK hoac 78/2020/NĐ-CP
    if "/" not in s:
        return None
    dau = s.split("/")[0]
    if la_mau_trong(dau) or not loc_cham(dau):
        return None                       # "..../2020/NĐ-CP" — chỗ để trống trong biểu mẫu
    if DANG_SO.match(dau.strip()):
        return None                       # 29-NQ/TW, 01-KH/BCĐTW — văn bản Đảng, đúng dạng
    dau = loc_cham(dau) or dau            # "...05....." -> "05": mẫu đã điền, số vẫn đọc được
    if not dau.isdigit():
        if any(c in NHAM for c in dau):
            return "phần số '%s' lẫn chữ" % dau
        return "phần số '%s' không phải số" % dau
    # loai van ban: QĐ, NĐ-CP, TT-BGDĐT... neu co chu so xen vao la ngo
    for phan in s.split("/")[1:]:
        phan = phan.strip("().,;:")
        if re.match(r"^\d{4}$", phan):
            continue                      # nam, binh thuong
        if HOP_LE.match(phan):
            continue                      # QH14, QH15... hop le
        if re.search(r"\d", phan):
            return "loại văn bản '%s' lẫn chữ số" % phan
    return None


KIEM = {"ngay_thang": kiem_ngay, "so_hieu": kiem_so_hieu}


def quet_file(f):
    """-> [(trang, ten_luat, ly_do, doan_van)] — da gop cac lan bat trung tren cung 1 dong"""
    ra = []
    da_thay = set()
    trang = 1
    for dong in f.read_text(encoding="utf-8", errors="replace").splitlines():
        mt = MOC_TRANG.search(dong)
        if mt:
            trang = int(mt.group(1))
            continue
        for ten, bt, loai in LUAT:
            for m in bt.finditer(dong):
                ly_do = KIEM[loai](m)
                if not ly_do:
                    continue
                khoa = (trang, m.group(0)[:40], ly_do)
                if khoa in da_thay:     # nhieu luat cung bat 1 cho -> chi tinh 1
                    continue
                da_thay.add(khoa)
                ra.append((trang, ten, ly_do, dong.strip()[:100]))
    return ra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chi-tiet", action="store_true")
    ap.add_argument("--ra", default=None)
    ap.add_argument("--gioi-han", type=int, default=0)
    ap.add_argument("--nguon", default=None,
                    help="thư mục text cần quét (mặc định text_raw)")
    a = ap.parse_args()

    goc_quet = Path(a.nguon) if a.nguon else RAW_TXT
    if not goc_quet.is_absolute():
        goc_quet = GOC / goc_quet
    files = sorted(p for p in goc_quet.rglob("*.txt") if not p.name.endswith(".bak"))
    if a.gioi_han:
        files = files[: a.gioi_han]

    tong_ngo = 0
    theo_file = {}
    dem_ly_do = Counter()
    trang_can = defaultdict(set)

    for f in files:
        ngo = quet_file(f)
        if not ngo:
            continue
        theo_file[f] = ngo
        tong_ngo += len(ngo)
        for tr, ten, ly_do, _d in ngo:
            dem_ly_do[ten + " — " + ly_do.split("'")[0].strip()] += 1
            trang_can[f.relative_to(goc_quet).as_posix()].add(tr)

    so_trang_can = sum(len(v) for v in trang_can.values())
    print("=" * 92)
    print("QUÉT text_raw TÌM CHỖ CÓ SỐ ĐÁNG NGỜ")
    print("=" * 92)
    print("  File đã quét            : %d" % len(files))
    print("  File có chỗ đáng ngờ    : %d (%.0f%%)" % (len(theo_file), 100.0 * len(theo_file) / max(1, len(files))))
    print("  Tổng số chỗ đáng ngờ    : %d" % tong_ngo)
    print("  SỐ TRANG cần xác minh   : %d" % so_trang_can)
    print("-" * 92)
    print("  Kiểu lỗi hay gặp nhất:")
    for ten, n in dem_ly_do.most_common(8):
        print("     %4d  %s" % (n, ten[:76]))
    print("=" * 92)

    if a.chi_tiet:
        for f, ngo in list(theo_file.items())[:15]:
            print("\n%s" % f.name[:86])
            for tr, ten, ly_do, doan in ngo[:6]:
                print("   trang %-3d [%s] %s" % (tr, ten, ly_do))
                print("             | %s" % doan)

    if a.ra:
        d = [{"file": k, "trang": sorted(v)} for k, v in sorted(trang_can.items())]
        Path(a.ra).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print("Đã xuất danh sách (file, trang) -> %s" % a.ra)


if __name__ == "__main__":
    main()
