# -*- coding: utf-8 -*-
"""Ap cac sua doi da xac minh vao text_raw.

Nguon: data/doi_chieu_so/ket_qua.jsonl  (do xac_minh_so.py sinh ra)
Chi ap nhung dong co trang thai LECH:
    - LECH            phan SO trung khit, chi khac phan CHU  -> AN TOAN de sua
    - KHONG THAY      khong co gia tri moi                   -> BO QUA
    - CU BI NGAT DONG chuoi cu chi la mot nua                -> BO QUA (thay vao se hong cau)

An toan:
    - SAO LUU toan bo text_raw sang text_raw_backup_<ngay gio> truoc khi ghi
    - Mac dinh CHI XEM TRUOC. Phai them --apply moi ghi that
    - Khop linh hoat khoang trang: '2344 /QĐ' trong file van tim duoc tu '2344/QĐ'
    - Chi thay trong DUNG TRANG da xac minh, khong thay tran lan ca file

Chay:
    python ap_sua_text_raw.py                 # xem truoc
    python ap_sua_text_raw.py --apply         # ghi that (co sao luu)
    python ap_sua_text_raw.py --doc 0019      # chi 1 tai lieu
"""
import argparse
import io
import json
import re
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from soi_so import MOC_TRANG                    # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
RAW_TXT = GOC / "data" / "processed" / "text_raw"
KQ = GOC / "data" / "doi_chieu_so" / "ket_qua.jsonl"


def bi_cat_cuoi_dong(tok):
    """Token co dau hieu BI NGAT DONG: ket thuc bang '/' '-' hoac qua ngan.

    '103/Q4-' la nua dau cua '103/QĐ-TTg', nua sau ('TTg') nam o dong ke tiep. Thay
    nguyen cum vao se thanh '103/QĐ-TTg' + xuong dong + 'TTg ...' -> NHAN DOI chu.
    Loai nay phai bo qua, khong duoc sua tu dong.
    """
    t = tok.strip()
    return bool(re.search(r"[/\-]\s*$", t)) or len(re.sub(r"\s", "", t)) < 4


def bieu_thuc_linh_hoat(tok):
    """'2344/QĐ-ĐHBK' -> regex cho phep khoang trang tuy y giua cac ky tu.

    text_raw co the ghi '2344 /QĐ-ĐHBK' hoac xuong dong giua chung, trong khi token
    da luu la ban da chuan hoa khoang trang -> so khop chuoi y nguyen se truot.
    """
    phan = [re.escape(c) for c in tok if not c.isspace()]
    return re.compile(r"\s*".join(phan))


def tach_trang(noi_dung):
    """-> [(la_moc_trang, so_trang, dong)] giu nguyen thu tu de ghep lai duoc."""
    ra, trang = [], 1
    for dong in noi_dung.splitlines(keepends=True):
        m = MOC_TRANG.search(dong)
        if m:
            trang = int(m.group(1))
            ra.append((True, trang, dong))
        else:
            ra.append((False, trang, dong))
    return ra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="ghi that (mac dinh chi xem truoc)")
    ap.add_argument("--doc", default="", help="chi ap cho 1 doc_id, vd 0019")
    ap.add_argument("--xem", type=int, default=12, help="so vi du in ra khi xem truoc")
    a = ap.parse_args()

    if not KQ.exists():
        print("Chưa có %s" % KQ)
        sys.exit(1)

    rows = [json.loads(l) for l in io.open(KQ, encoding="utf-8") if l.strip()]
    can_sua = [r for r in rows if r["khop"] == "LỆCH" and not bi_cat_cuoi_dong(r["so_cu"])]
    bi_cat = [r for r in rows if r["khop"] == "LỆCH" and bi_cat_cuoi_dong(r["so_cu"])]
    if a.doc:
        can_sua = [r for r in can_sua if r["doc_id"] == a.doc]

    bo_qua = {
        "KHÔNG THẤY": sum(1 for r in rows if r["khop"] == "KHÔNG THẤY"),
        "CŨ BỊ NGẮT DÒNG": sum(1 for r in rows if r["khop"] == "CŨ BỊ NGẮT DÒNG"),
    }

    theo_file = defaultdict(list)
    for r in can_sua:
        theo_file[r["file"]].append(r)

    print("=" * 88)
    print("ÁP SỬA VÀO text_raw   %s" % ("(GHI THẬT)" if a.apply else "(chỉ xem trước)"))
    print("  Sẽ sửa : %d chỗ, trong %d tài liệu" % (len(can_sua), len(theo_file)))
    print("  Bỏ qua : %d KHÔNG THẤY | %d CŨ BỊ NGẮT DÒNG | %d cũ đứt cuối dòng"
          % (bo_qua["KHÔNG THẤY"], bo_qua["CŨ BỊ NGẮT DÒNG"], len(bi_cat)))
    print("=" * 88)

    if a.apply and not a.doc:
        dich = RAW_TXT.parent / ("text_raw_backup_" + time.strftime("%Y%m%d_%H%M"))
        if not dich.exists():
            shutil.copytree(RAW_TXT, dich)
            print("Đã sao lưu toàn bộ text_raw → %s" % dich.name)
        print("-" * 88)

    tong_sua = tong_hut = 0
    vi_du = []
    for ten_file, ds in sorted(theo_file.items()):
        f = RAW_TXT / ten_file
        if not f.exists():
            # ten trong ket_qua chi la ten file, tim theo doc_id trong cay
            f = next((p for p in RAW_TXT.rglob(ten_file)), None)
            if not f:
                print("  ⚠ không thấy file: %s" % ten_file[:70])
                tong_hut += len(ds)
                continue

        noi_dung = f.read_text(encoding="utf-8", errors="replace")
        muc = tach_trang(noi_dung)
        theo_trang = defaultdict(list)
        for r in ds:
            for t in str(r["trang"]).split("-"):
                if t.isdigit():
                    theo_trang[int(t)].append(r)

        sua_file = hut_file = 0
        for i, (la_moc, trang, dong) in enumerate(muc):
            if la_moc or trang not in theo_trang:
                continue
            moi_dong = dong
            for r in theo_trang[trang]:
                bt = bieu_thuc_linh_hoat(r["so_cu"])
                if bt.search(moi_dong):
                    thay = re.sub(r"\s*/\s*", "/", r["so_moi"]).strip()
                    moi_dong, n = bt.subn(thay.replace("\\", ""), moi_dong, count=1)
                    if n:
                        sua_file += 1
                        if len(vi_du) < a.xem:
                            vi_du.append((r["doc_id"], trang, r["so_cu"], r["so_moi"]))
            if moi_dong != dong:
                muc[i] = (la_moc, trang, moi_dong)

        hut_file = len(ds) - sua_file
        tong_sua += sua_file
        tong_hut += max(0, hut_file)
        dau = "✔" if hut_file <= 0 else "~"
        print("  %s %-58s sửa %3d/%-3d" % (dau, ten_file[:58], sua_file, len(ds)))

        if a.apply and sua_file:
            f.write_text("".join(d for _l, _t, d in muc), encoding="utf-8", newline="")

    print("-" * 88)
    print("Đã sửa %d chỗ | không tìm thấy chuỗi cũ trong file: %d chỗ" % (tong_sua, tong_hut))
    if vi_du:
        print("\nVí dụ thay thế:")
        for doc, tr, cu, moi in vi_du:
            print("   %s tr.%-3s  %-26s → %s" % (doc, tr, cu[:26], moi[:26]))
    if not a.apply:
        print("\n>>> Đây mới chỉ là XEM TRƯỚC. Thêm --apply để ghi thật (có sao lưu).")


if __name__ == "__main__":
    main()
