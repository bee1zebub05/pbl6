# -*- coding: utf-8 -*-
"""Nhan dien DON VI thuoc truong trong van ban — nut DonViLienQuan cua do thi.

VI SAO DUNG TU DIEN THUC THE, KHONG DUNG PhoBERT:
    Tap don vi cua mot truong dai hoc la TAP DONG va nho (~30 don vi). Mo hinh NER hoc
    sau giai bai toan MO — nhan dien ten rieng chua tung thay. O day thi nguoc lai: ta
    biet truoc chinh xac co nhung don vi nao, van de chi la CHUAN HOA cach viet.

    Trong du lieu that, cung mot don vi duoc viet it nhat 3 kieu:
        "Phong KHCN"  =  "Phong Khoa hoc Cong nghe"  =  "Phong KH&CN"
        "Phong TCHC"  =  "Phong To chuc Hanh chinh"
        "Phong CTSV"  =  "Phong Cong tac sinh vien"
    PhoBERT se nhan ra ca ba la thuc the, nhung KHONG biet chung la MOT — van phai co
    tu dien de gop. Nen tu dien lam duoc ca hai viec, con re va kiem chung duoc tung
    dong. Neu hoi dong yeu cau mo hinh hoc sau thi day van la buoc tien xu ly bat buoc.

Chong bat nham: chi nhan cum nam trong TU DIEN, khong bat moi "Phong + chu hoa".
Neu khong thi "Ban Giam hieu Y kien cua", "Ban Giam hieu se cho y" cung thanh don vi
(hai cum nay xuat hien 64 va 49 lan trong du lieu that).

    python trich_don_vi.py                 # thong ke
    python trich_don_vi.py --chi-tiet      # kem vi du tung don vi
    python trich_don_vi.py --ra don_vi.json
"""
import argparse
import io
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
SACH = GOC / "data" / "clean" / "text_final"

# Tu dien don vi: ten chuan -> cac cach viet khac (viet tat, thieu tu, sai chinh ta OCR)
# So khop sau khi BO DAU va thu gon khoang trang, nen khong can liet ke bien the dau.
DON_VI = {
    "Ban Giám hiệu": ["ban giam hieu", "bgh"],
    "Hội đồng trường": ["hoi dong truong", "hdt"],
    "Phòng Đào tạo": ["phong dao tao", "phong dt"],
    "Phòng Khoa học Công nghệ": [
        "phong khoa hoc cong nghe", "phong khcn", "phong kh&cn", "phong kh cn",
        "phong khoa hoc va cong nghe"],
    "Phòng Tổ chức Hành chính": [
        "phong to chuc hanh chinh", "phong tchc", "phong to chuc  hanh chinh"],
    "Phòng Công tác sinh viên": [
        "phong cong tac sinh vien", "phong ctsv", "phong cong tac hoc sinh sinh vien"],
    "Phòng Kế hoạch Tài chính": [
        "phong ke hoach tai chinh", "phong khtc", "phong ke hoach  tai chinh",
        "phong ke hoach va tai chinh"],
    "Phòng Khảo thí và Đảm bảo chất lượng giáo dục": [
        "phong khao thi va dam bao chat luong giao duc", "phong khao thi va dam bao",
        "phong kt&dbclgd", "phong ktdbcl", "phong khao thi"],
    "Phòng Thanh tra Pháp chế": [
        "phong thanh tra phap che", "phong ttpc", "phong thanh tra  phap che"],
    "Phòng Cơ sở vật chất": ["phong co so vat chat", "phong csvc"],
    "Phòng Hợp tác quốc tế": ["phong hop tac quoc te", "phong htqt"],
    "Trung tâm Học liệu và Truyền thông": [
        "trung tam hoc lieu va truyen thong", "trung tam hoc lieu", "tt hoc lieu"],
    "Trung tâm Công nghệ thông tin": [
        "trung tam cong nghe thong tin", "trung tam cntt", "tt cntt"],
    "Ban Thanh tra nhân dân": ["ban thanh tra nhan dan"],
    "Ban Tổ chức Cán bộ": ["ban to chuc can bo", "ban tccb"],
    "Ban Đào tạo": ["ban dao tao"],
    "Ban Khoa học Công nghệ và Môi trường": [
        "ban khoa hoc cong nghe va moi truong", "ban khcn&mt", "ban khcn va mt"],
    "Ban Kế hoạch Tài chính": ["ban ke hoach tai chinh", "ban khtc"],
    "Ban Hợp tác quốc tế": ["ban hop tac quoc te", "ban htqt"],
    "Ban Công tác học sinh sinh viên": [
        "ban cong tac hoc sinh sinh vien", "ban cthssv"],
    "Đảng ủy": ["dang uy"],
    "Công đoàn": ["cong doan truong", "ban chap hanh cong doan"],
    "Đoàn Thanh niên": ["doan thanh nien", "doan tncs ho chi minh"],
    "Hội Sinh viên": ["hoi sinh vien"],
    "Khoa Cơ khí": ["khoa co khi"],
    "Khoa Điện": ["khoa dien"],
    "Khoa Điện tử Viễn thông": ["khoa dien tu vien thong", "khoa dtvt"],
    "Khoa Công nghệ thông tin": ["khoa cong nghe thong tin", "khoa cntt"],
    "Khoa Xây dựng Dân dụng và Công nghiệp": [
        "khoa xay dung dan dung va cong nghiep", "khoa xd ddcn"],
    "Khoa Hóa": ["khoa hoa"],
    "Khoa Môi trường": ["khoa moi truong"],
    "Khoa Kiến trúc": ["khoa kien truc"],
    "Khoa Quản lý dự án": ["khoa quan ly du an"],
    "Khoa Cơ khí Giao thông": ["khoa co khi giao thong"],
    "Khoa Công nghệ Nhiệt Điện lạnh": ["khoa cong nghe nhiet dien lanh"],
    "Viện Khoa học và Công nghệ": ["vien khoa hoc va cong nghe", "vien kh&cn"],
}


def bo_dau(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("đ", "d").replace("Đ", "D").lower()
    return re.sub(r"\s+", " ", s).strip()


# Dung bien the DAI truoc: "phong khoa hoc cong nghe" phai khop truoc "phong khcn"
# de khong cat cut ten. Sap theo do dai giam dan.
# PHAI co ranh gioi tu, khong duoc so khop chuoi con: mau "khoa hoa" khop lot vao
# "khoa hoac" (tu "khoa hoac don vi phu trach") — da do that, 51 luot "Khoa Hoa" thi
# gan het la bat nham kieu nay.
_MAU = []
for chuan, ds in DON_VI.items():
    for x in sorted(ds, key=len, reverse=True):
        _MAU.append((re.compile(r"(?<![a-z0-9])" + re.escape(x) + r"(?![a-z0-9])"),
                     x, chuan))
_MAU.sort(key=lambda p: -len(p[1]))


def tim_don_vi(t):
    """-> {ten chuan: so lan xuat hien} trong mot van ban."""
    b = bo_dau(t)
    ra = Counter()
    for bt, mau, chuan in _MAU:
        v = list(bt.finditer(b))
        if not v:
            continue
        ra[chuan] += len(v)
        # xoa cho da khop de bien the ngan hon khong dem lai cung mot cho
        b = bt.sub(" " * len(mau), b)
    return ra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chi-tiet", action="store_true")
    ap.add_argument("--toi-thieu", type=int, default=2,
                    help="đơn vị phải xuất hiện bấy nhiêu lần mới tính là liên quan")
    ap.add_argument("--ra", default=str(GOC / "data" / "kiem_tra" / "don_vi.json"))
    a = ap.parse_args()

    theo_vb = {}
    dem = Counter()
    so_vb = Counter()
    for f in sorted(SACH.rglob("*.txt")):
        doc = f.name[:4]
        c = tim_don_vi(io.open(f, encoding="utf-8", errors="replace").read())
        giu = {k: v for k, v in c.items() if v >= a.toi_thieu}
        if giu:
            theo_vb[doc] = giu
            dem.update(giu)
            for k in giu:
                so_vb[k] += 1

    p = Path(a.ra)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(theo_vb, ensure_ascii=False, indent=1), encoding="utf-8")

    tong = len(list(SACH.rglob("*.txt")))
    print("=" * 86)
    print("NHẬN DIỆN ĐƠN VỊ THUỘC TRƯỜNG  (từ điển %d đơn vị, %d cách viết)"
          % (len(DON_VI), len(_MAU)))
    print("=" * 86)
    print("  Văn bản nhắc tới ít nhất 1 đơn vị : %d / %d  (%.0f%%)"
          % (len(theo_vb), tong, 100.0 * len(theo_vb) / max(1, tong)))
    print("  Đơn vị khác nhau nhận ra          : %d / %d trong từ điển"
          % (len(dem), len(DON_VI)))
    print("  Tổng lượt nhắc                    : %d" % sum(dem.values()))
    print("-" * 86)
    print("%-46s %8s %10s" % ("ĐƠN VỊ", "số lượt", "số văn bản"))
    print("-" * 86)
    for k, v in dem.most_common():
        print("%-46s %8d %10d" % (k[:46], v, so_vb[k]))
    khong = [k for k in DON_VI if k not in dem]
    if khong:
        print("-" * 86)
        print("  Có trong từ điển nhưng KHÔNG xuất hiện lần nào (%d):" % len(khong))
        for k in khong:
            print("     %s" % k)
    print("=" * 86)
    print("Đã ghi: %s" % p)


if __name__ == "__main__":
    main()
