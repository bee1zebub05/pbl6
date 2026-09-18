# -*- coding: utf-8 -*-
"""Doc TOAN BO ban cuoi va kiem tung truong phuc vu do thi tri thuc.

Kiem sau nhom, moi nhom deu co NGUONG BAO DONG rieng chu khong chi dem:

    1. Suc khoe van ban : do dai, ty le dau tieng Viet, rac con sot
    2. Ngay ban hanh    : co / khong, va ngay co HOP LE khong (khong phai 32/13)
    3. Nguoi ky         : ho ten + chuc danh + hoc ham
    4. Can cu phap ly   : "Can cu <loai> so <X>"
    5. Quan he hieu luc : REPLACES / AMENDS / REPEALS + ba chieu nguoc
    6. Cau truc Dieu    : so Dieu, so Khoan

Van ban KHONG co nguoi ky chua chac la loi: cong van, thong bao, ban sao y deu co
the khong co khoi ky. Nen phan them theo LOAI van ban de biet cho nao dang lo that.

    python kiem_ban_cuoi.py
    python kiem_ban_cuoi.py --ra data/bao_cao_ban_cuoi.csv
"""
import argparse
import csv
import io
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from quan_he_hieu_luc import phan_loai                 # noqa: E402
from trich_dieu_khoan import tach_dieu                 # noqa: E402
from trich_do_thi import (CAN_CU, CAN_CU_TEN, chuan_so,  # noqa: E402
                          don_ten_luat, tach_ten_file, tim_chu_ky, tim_ngay)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
KHO = GOC / "data" / "clean" / "text_final"

DAU = re.compile(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ"
                 r"ùúủũụưừứửữựỳýỷỹỵđ]", re.I)
RAC = [("lỗ chưa OCR", re.compile(r"\[\[KHÔNG OCR ĐƯỢC")),
       ("rào markdown", re.compile("`" * 3)),
       ("thẻ <br>", re.compile(r"<br", re.I)),
       ("markdown đậm", re.compile(r"\*\*")),
       ("lời dẫn model", re.compile(r"chào\s+bạn|bạn\s+cung\s+cấp", re.I))]

# Loai van ban thuong KHONG co khoi ky -> khong co nguoi ky la binh thuong
KHONG_CAN_KY = {"CV", "TB", "BC", "KH", "HD"}


def ngay_hop_le(m):
    try:
        date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        return True
    except ValueError:
        return False


def ngay_iso(m):
    """Ngay dang YYYY-MM-DD cho do thi tri thuc.

    Cot `ngay` giu nguyen chuoi khop de con doi chieu duoc voi ban goc, nhung voi Luat
    thi chuoi do la CA CAU ("Luat nay da duoc Quoc hoi ... thong qua ngay 14 thang 11
    nam 2018") — 50/455 van ban nhu vay. Ben nap do thi khong nen phai tu boc tach lai.
    Ca hai mau NGAY va NGAY_THONG_QUA deu bat (ngay, thang, nam) o nhom 1-2-3.
    """
    if not m or not ngay_hop_le(m):
        return ""
    return "%s-%02d-%02d" % (m.group(3), int(m.group(2)), int(m.group(1)))


def soi(t, ten_file):
    doc_id, so, loai, cq, tieu_de = tach_ten_file(ten_file)
    dau3 = t[:4000]
    mn = tim_ngay(t)

    cc = {chuan_so(m.group(2)) for m in CAN_CU.finditer(t)}
    for m in CAN_CU_TEN.finditer(t):
        x = don_ten_luat(m.group(1), t[m.start():m.start() + 260])
        if x:
            cc.add(x)

    hl = phan_loai(t)
    ky = tim_chu_ky(t)
    dieu = tach_dieu(t)
    chu = sum(1 for c in t if c.isalpha())

    return {
        "doc": doc_id, "so_hieu": so, "loai": loai, "co_quan": cq,
        "ky_tu": len(t),
        "ty_le_dau": len(DAU.findall(t)) / max(1, chu),
        "ngay": (mn.group(0) if mn else ""),
        "ngay_iso": ngay_iso(mn),
        "ngay_hop_le": bool(mn and ngay_hop_le(mn)),
        "nguoi_ky": ky[0], "hoc_ham": ky[1], "chuc_danh": ky[2],
        "can_cu": len(cc),
        "hieu_luc": len(hl),
        "loai_hieu_luc": ",".join(sorted({x[0] for x in hl})),
        "so_dieu": len(dieu),
        "so_khoan": sum(x["so_khoan"] for x in dieu),
        "rac": ";".join(k for k, b in RAC if b.search(t)),
        "_noi_dung": t,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ra", default="data/kiem_tra/bao_cao_ban_cuoi.csv")
    a = ap.parse_args()

    fs = sorted(KHO.rglob("*.txt"))
    ds = []
    for f in fs:
        ds.append(soi(io.open(f, encoding="utf-8", errors="replace").read(), f.name))

    n = len(ds)

    def dem(p):
        return sum(1 for x in ds if p(x))

    def pc(k):
        return "%3d / %d  (%2.0f%%)" % (k, n, 100 * k * 1.0 / n)

    print("=" * 84)
    print("KIỂM BẢN CUỐI — %s (%d văn bản)" % (KHO.name, n))
    print("=" * 84)

    print("1. SỨC KHOẺ VĂN BẢN")
    qua_ngan = dem(lambda x: x["ky_tu"] < 500)
    mat_dau = dem(lambda x: x["ty_le_dau"] < 0.12)
    co_rac = dem(lambda x: x["rac"])
    print("   dài < 500 ký tự          : %s" % pc(qua_ngan))
    print("   tỷ lệ dấu < 12%% (hỏng)   : %s" % pc(mat_dau))
    print("   còn rác                  : %s" % pc(co_rac))
    if co_rac:
        c = Counter(k for x in ds for k in x["rac"].split(";") if k)
        for k, v in c.most_common():
            print("      %-18s %d" % (k, v))

    print()
    print("2. NGÀY BAN HÀNH")
    co_ngay = dem(lambda x: x["ngay"])
    sai_ngay = dem(lambda x: x["ngay"] and not x["ngay_hop_le"])
    print("   đọc được ngày            : %s" % pc(co_ngay))
    print("   ngày KHÔNG hợp lệ        : %s" % pc(sai_ngay))

    print()
    print("3. NGƯỜI KÝ")
    co_ky = dem(lambda x: x["nguoi_ky"])
    print("   đọc được người ký        : %s" % pc(co_ky))
    print("   kèm chức danh            : %s" % pc(dem(lambda x: x["chuc_danh"])))
    print("   kèm học hàm              : %s" % pc(dem(lambda x: x["hoc_ham"])))
    thieu = [x for x in ds if not x["nguoi_ky"]]
    c = Counter(x["loai"] for x in thieu)
    print("   thiếu người ký, theo loại văn bản:")
    for k, v in c.most_common(8):
        tong_loai = sum(1 for x in ds if x["loai"] == k)
        ghi = "  (loại thường không có khối ký)" if k in KHONG_CAN_KY else ""
        print("      %-8s %3d / %-3d %s" % (k or "?", v, tong_loai, ghi))

    print()
    print("4. CĂN CỨ PHÁP LÝ")
    print("   có ít nhất 1 căn cứ      : %s" % pc(dem(lambda x: x["can_cu"])))
    print("   tổng số căn cứ           : %s"
          % "{:,}".format(sum(x["can_cu"] for x in ds)))

    print()
    print("5. QUAN HỆ HIỆU LỰC")
    print("   có ít nhất 1 quan hệ     : %s" % pc(dem(lambda x: x["hieu_luc"])))
    c = Counter(k for x in ds for k in x["loai_hieu_luc"].split(",") if k)
    for k, v in c.most_common():
        print("      %-14s %d văn bản" % (k, v))

    print()
    print("6. CẤU TRÚC ĐIỀU / KHOẢN")
    print("   có cấu trúc Điều         : %s" % pc(dem(lambda x: x["so_dieu"])))
    print("   tổng Điều / Khoản        : %s / %s"
          % ("{:,}".format(sum(x["so_dieu"] for x in ds)),
             "{:,}".format(sum(x["so_khoan"] for x in ds))))

    # --- Hai phep kiem sinh ra tu qua trinh soi, khong co trong ban dau ----------
    print()
    print("7. TRÙNG LẶP  (website nguồn từng gắn một PDF cho nhiều mục)")
    import hashlib
    bam = {}
    for x in ds:
        k = hashlib.md5(x["_noi_dung"].encode("utf-8")).hexdigest()
        bam.setdefault(k, []).append(x["doc"])
    tr = [v for v in bam.values() if len(v) > 1]
    print("   nhóm văn bản TRÙNG NỘI DUNG : %d" % len(tr))
    for v in tr[:6]:
        so = {y["so_hieu"] for y in ds if y["doc"] in v}
        print("      %s  %s" % (sorted(v), "cùng số hiệu" if len(so) == 1
                                else "KHÁC SỐ HIỆU: %s" % sorted(so)))

    print()
    print("8. SỐ HIỆU: tên file có khớp nội dung không")
    import unicodedata as _u

    def _bd(z):
        z = _u.normalize("NFD", z or "")
        z = "".join(c for c in z if _u.category(c) != "Mn")
        return re.sub(r"\s+", "", z.replace("đ", "d").replace("Đ", "D").upper())

    khop = sum(1 for x in ds
               if x["so_hieu"] and "/" in x["so_hieu"]
               and _bd(x["so_hieu"]) in _bd(x["_noi_dung"][:6000]))
    xet = sum(1 for x in ds if x["so_hieu"] and "/" in x["so_hieu"])
    print("   số hiệu xuất hiện ở đầu văn bản : %d / %d  (%.0f%%)"
          % (khop, xet, 100.0 * khop / max(1, xet)))
    print("   (lệch phần lớn do OCR đọc sai chữ số, không phải gắn nhầm file)")

    print()
    print("-" * 84)
    du = dem(lambda x: x["ngay"] and x["nguoi_ky"] and x["can_cu"])
    print("   ĐỦ CẢ ngày + người ký + căn cứ : %s" % pc(du))
    thieu_het = [x for x in ds
                 if not x["ngay"] and not x["nguoi_ky"] and not x["can_cu"]]
    print("   THIẾU CẢ BA                    : %s" % pc(len(thieu_het)))
    for x in thieu_het[:10]:
        print("      %s  %-16s %5d ký tự  %s"
              % (x["doc"], x["so_hieu"] or "?", x["ky_tu"], x["loai"]))

    p = Path(a.ra)
    p = p if p.is_absolute() else GOC / p
    p.parent.mkdir(parents=True, exist_ok=True)
    with io.open(p, "w", encoding="utf-8-sig", newline="") as f:
        cot = [k for k in ds[0] if not k.startswith("_")]
        w = csv.DictWriter(f, fieldnames=cot, extrasaction="ignore")
        w.writeheader()
        w.writerows(ds)
    print("=" * 84)
    print("Bảng chi tiết từng văn bản: %s" % p)


if __name__ == "__main__":
    main()
