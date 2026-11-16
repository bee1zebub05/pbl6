# -*- coding: utf-8 -*-
"""Loai khoi kho nhung van ban mà WEBSITE NGUON gan nham file.

Day KHONG phai loi OCR. Trang dut.udn.vn gan mot file PDF vao nhieu muc muc luc
khac nhau, nen cung mot noi dung xuat hien duoi NHIEU SO HIEU. Da doi chieu bang
cach md5 toan bo PDF roi MO TUNG FILE DOC tan mat trang 1.

Nam van ban duoi day deu la BAN SAO cua mot van ban khac da co trong kho:

    0326  ghi 51/2012/TT-TTCP    <- PDF that: BỘ GD&ĐT, 51/2012/TT-BGDĐT   (= 0296)
    0327  ghi 39/2013/TT-TTCP    <- PDF that: BỘ GD&ĐT, 39/2013/TT-BGDĐT   (= 0297)
    0329  ghi 23/2016/TT-BGD&ĐT  <- PDF that: BỘ GD&ĐT, 23/2016/TT-BGDĐT   (= 0165)
    0198  ghi 21/2020/TT-BGDĐT   <- PDF that: BỘ NỘI VỤ, 12/2019/TT-BNV    (= 0197)
    0282  ghi 10/2022/QH15       <- PDF that: Luật số 43/2019/QH14 (Luật Giáo dục) (= 0089)

Ba cai dau chi sai MA CO QUAN trong muc luc (TT-TTCP / TT-BGD&ĐT deu khong dung
voi cai in tren giay). Hai cai sau nang hon: file la van ban HOAN TOAN KHAC.

Da thu tai lai ca ba URL — md5 giong het ban cu, tuc loi nam o chinh website chu
khong phai o khau crawl. Trang listing nay cung doi cau truc nen khong do duoc
link thay the.

VI SAO PHAI LOAI. Giu lai thi moi van ban sinh mot node mang so hieu rieng nhung
NOI DUNG TRUNG voi node khac. Canh BASED_ON / AMENDS cua van ban that bi nhan doi
sang node gia, lam lech PageRank, bac vao/ra, va ca bo danh gia retrieval.
`xuat_neo4j.py` gop theo SO HIEU nen khong bat duoc — chung khac so hieu.

CHUYEN vao thu muc cach ly, KHONG xoa han: con lui lai duoc neu ve sau xin duoc
ban PDF dung tu nha truong.

    python loai_ban_sai.py            # xem truoc
    python loai_ban_sai.py --apply
"""
import argparse
import io
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
KHO = GOC / "data" / "processed" / "text_final"
CACH_LY = GOC / "data" / "processed" / "_cach_ly_ban_sai"

SAI = {
    "0326": ("51/2012/TT-TTCP", "0296", "51/2012/TT-BGDĐT", "sai mã cơ quan"),
    "0327": ("39/2013/TT-TTCP", "0297", "39/2013/TT-BGDĐT", "sai mã cơ quan"),
    "0329": ("23/2016/TT-BGD&ĐT", "0165", "23/2016/TT-BGDĐT", "sai mã cơ quan"),
    "0198": ("21/2020/TT-BGDĐT", "0197", "12/2019/TT-BNV", "văn bản khác hẳn"),
    "0282": ("10/2022/QH15", "0089", "43/2019/QH14", "văn bản khác hẳn"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    print("=" * 88)
    print("LOẠI BẢN BỊ WEBSITE GẮN NHẦM FILE")
    print("=" * 88)
    print("%-6s %-20s %-30s %s" % ("doc", "mục lục ghi", "PDF thật là", "trùng với"))
    print("-" * 88)

    thay = []
    for d, (ghi, goc, that, ly) in SAI.items():
        p = list(KHO.rglob(d + "_*.txt"))
        print("%-6s %-20s %-30s %s  (%s)"
              % (d, ghi, that, goc, ly))
        if p:
            thay.append((d, p[0]))
        else:
            print("       ✖ không thấy file trong %s" % KHO.name)

    print("-" * 88)
    print("  Tìm thấy %d / %d file" % (len(thay), len(SAI)))

    if not a.apply:
        print(">>> Mới là XEM TRƯỚC. Thêm --apply để chuyển vào khu cách ly.")
        return

    CACH_LY.mkdir(parents=True, exist_ok=True)
    for d, p in thay:
        ra = CACH_LY / p.name
        shutil.move(str(p), str(ra))
        print("  ✔ %s -> %s" % (d, ra.relative_to(GOC)))

    ghi_chu = ["# Bản bị website nguồn gắn nhầm file", "",
               "Không phải lỗi OCR. `dut.udn.vn` gắn một PDF vào nhiều mục mục lục.",
               "Đã đối chiếu md5 toàn bộ PDF rồi mở từng file đọc tận mắt trang 1.",
               "Đã thử tải lại — md5 giống hệt, tức lỗi ở chính website.", "",
               "| id | Mục lục ghi | PDF thật là | Trùng với | Loại lỗi |",
               "|---|---|---|---|---|"]
    for d, (ghi, goc, that, ly) in SAI.items():
        ghi_chu.append("| `%s` | %s | %s | `%s` | %s |" % (d, ghi, that, goc, ly))
    ghi_chu += ["", "Giữ lại ở đây để còn lùi được nếu xin được bản PDF đúng."]
    io.open(CACH_LY / "README.md", "w", encoding="utf-8", newline="\n").write(
        "\n".join(ghi_chu) + "\n")

    con = len(list(KHO.rglob("*.txt")))
    print("-" * 88)
    print("  Kho còn %d văn bản. Ghi chú: %s"
          % (con, (CACH_LY / "README.md").relative_to(GOC)))


if __name__ == "__main__":
    main()
