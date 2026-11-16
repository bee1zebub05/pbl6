# -*- coding: utf-8 -*-
"""Dung lai TOAN BO kho cuoi tu nguon, theo dung thu tu, roi kiem.

Chay lai duoc nhieu lan ma khong tich luy loi — moi buoc deu doc tu NGUON chu khong
sua chong len ket qua buoc truoc. Da can den dieu nay khi mot ban don watermark
nuot dau xuong dong lam mat 6 nguoi ky: chi viec chay lai chuoi nay la sach.

    1. dung_ban_cuoi   : chon ban tot hon cho tung van ban -> text_final
    1b. loai_ban_sai   : bo 5 file website gan nham PDF (460 -> 455)
    2. nap_nguoi_ky_vet: chen khoi ky OCR lai duoc
    3. (noi bo)        : chen 4 khoi ky da xac minh bang mat
    4. don_watermark   : don watermark / the HTML / loi dan
    5. kiem_ban_cuoi   : bao cao

    python dung_lai_tat_ca.py
"""
import glob
import io
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
GOC = HERE.parents[1]
PY = sys.executable

# Bon khoi ky khong tu dong doc duoc, da mo PDF doc tan mat hoac lay tu OCR co san
XAC_MINH_TAY = {
    "0004": ("KT. THỦ TƯỚNG\nPHÓ THỦ TƯỚNG", "Trương Hòa Bình",
             "2 (đọc tận mắt PDF; bộ vét thử trang 151/150/114/111 vì chức danh "
             "khớp nhầm trong 153 trang phụ lục)"),
    "0152": ("KT. BỘ TRƯỞNG\nTHỨ TRƯỞNG", "Nguyễn Văn Phúc",
             "8 (đọc tận mắt PDF; tên không có trong text layer, bị con dấu đè)"),
    "0463": ("KT. BỘ TRƯỞNG\nTHỨ TRƯỞNG", "Phạm Ngọc Thưởng",
             "7 (có sẵn trong OCR nhưng bị xáo vào cột Nơi nhận)"),
    "0379": ("TỔ TRƯỞNG TỔ CÔNG TÁC", "Nguyễn Chí Dũng",
             "1 (có sẵn trong OCR; chức danh TỔ TRƯỞNG trước đây thiếu trong bảng)"),
}

MOC = "----- [Khối ký — xác minh tay, trang %s] -----"


def chay(ten, *args):
    print("\n>>> %s" % ten, flush=True)
    r = subprocess.run([PY, "-B", str(HERE / ten)] + list(args),
                       cwd=str(HERE), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    for d in out.splitlines():
        if d.strip() and "Direct use of automatic" not in d:
            print("    " + d)
    return r.returncode


def chen_tay():
    print("\n>>> chèn 4 khối ký đã xác minh bằng mắt", flush=True)
    n = 0
    for doc, (cd, ten, ghi) in XAC_MINH_TAY.items():
        f = glob.glob(str(GOC / "data" / "processed" / "text_final" / "**"
                          / ("%s_*.txt" % doc)), recursive=True)
        if not f:
            print("    ✖ %s: không thấy file" % doc)
            continue
        t = io.open(f[0], encoding="utf-8", errors="replace").read()
        if "Khối ký — xác minh tay" in t:
            continue
        io.open(f[0], "w", encoding="utf-8", newline="\n").write(
            t.rstrip() + "\n\n%s\n%s\n%s\n" % (MOC % ghi, cd, ten))
        n += 1
        print("    ✔ %s  %s" % (doc, ten))
    print("    chèn %d khối" % n)


def main():
    print("=" * 84)
    print("DỰNG LẠI TOÀN BỘ KHO CUỐI")
    print("=" * 84)
    chay("dung_ban_cuoi.py", "--apply")
    # PHAI chay ngay sau dung_ban_cuoi: buoc do dung lai tu text_clean_gemma nen
    # tao lai ca 5 file bi website gan nham. Quen buoc nay thi kho quay ve 460.
    chay("loai_ban_sai.py", "--apply")
    chay("nap_nguoi_ky_vet.py", "--apply")
    chen_tay()
    chay("don_watermark.py", "--apply")
    chay("kiem_ban_cuoi.py")


if __name__ == "__main__":
    main()
