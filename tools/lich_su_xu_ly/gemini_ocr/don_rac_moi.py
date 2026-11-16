# -*- coding: utf-8 -*-
"""Don rac cua model con sot trong ban OCR moi.

`lam_sach` bat duoc rao markdown nhung bo sot bon thu duoi day. Chung khong chi
xau ma con LAM LECH viec can moc trang: loi dan nam dau khuc day toan bo noi dung
that xuong, nen ranh gioi trang chieu tu ban cu sang bi tro sai cho.

BON LOAI, va cho phai can than voi tung loai:

  1. LOI DAN cua model — "Chào bạn, dưới đây là toàn bộ nội dung OCR từ 5 trang..."
     KHONG duoc xoa theo mau "Đây là nội dung..." vi trung voi van ban THAT:
         "Đây là nội dung trọng tâm của hạ tầng số. Xây dựng hạ tầng dữ liệu ĐHĐN"
         "đây là báo cáo kết quả xác minh nội dung tố cáo, đề nghị..."
     Chi xoa khi co dau hieu model XUNG HO voi nguoi dung: 'chào bạn', 'bạn cung
     cấp', 'đã được OCR', 'dạng plaintext'. Van ban hanh chinh khong viet the.

  2. NHAI LAI CAU LENH — "ĐỌC VÀ CHUYỂN ĐỔI TOÀN BỘ VĂN BẢN TRONG PDF..."

  3. MOC `**Trang N**` model TU THEM — so trang trong do la so thu tu trang TRONG
     KHUC (1..5), khong phai so trang that cua van ban. De lai thi mau thuan voi
     moc `----- [Trang N] -----` that.

  4. The `<br>` va dong ngang `---` cua markdown.

    python don_rac_moi.py              # xem truoc
    python don_rac_moi.py --apply
"""
import argparse
import io
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
KHO = [GOC / "data" / "processed" / "text_clean_gemma",
       GOC / "data" / "processed" / "text_gemma_moi",
       GOC / "data" / "processed" / "text_gemma_trang",
       GOC / "data" / "processed" / "text_gemma_vet",
       GOC / "data" / "processed" / "text_final"]

# Dau hieu KHONG THE NHAM: model dang noi voi nguoi dung, khong phai noi dung van ban
DAU_HIEU_MODEL = re.compile(
    r"chào\s+bạn|bạn\s+cung\s+cấp|bạn\s+đã\s+cung\s+cấp|đã\s+được\s+OCR|"
    r"dạng\s+plaintext|plaintext\s+sạch|tôi\s+đã\s+(?:OCR|chuyển)", re.I)

# Mot cau/doan mo dau chua dau hieu tren thi bo ca cau do
LOI_DAN = re.compile(
    r"^[^\n]{0,260}?(?:chào\s+bạn|bạn\s+cung\s+cấp|bạn\s+đã\s+cung\s+cấp|"
    r"đã\s+được\s+OCR|dạng\s+plaintext|plaintext\s+sạch)[^\n]{0,200}$",
    re.I | re.M)

NHAI_LENH = re.compile(r"^[^\n]{0,40}ĐỌC VÀ CHUYỂN ĐỔI[^\n]{0,120}$", re.I | re.M)
MOC_MODEL = re.compile(r"[*_]{1,2}\s*Trang\s+\d+\s*[*_]{1,2}")
THE_BR = re.compile(r"<br\s*/?>", re.I)
DONG_NGANG = re.compile(r"^\s*[-*_]{3,}\s*$", re.M)
THUA_DONG = re.compile(r"\n{3,}")

# Markdown nhan manh. Bo DAU, giu CHU.
#
# Day khong phai chuyen tham my. Bo trich nguoi ky doi ten NGUOI DUNG MOT MINH tren
# dong, ma model lai boc ten trong dau sao:
#       **CHỦ TỊCH QUỐC HỘI** **Nguyễn Thị Kim Ngân**
#       **BỘ TRƯỞNG** *(Đã ký)* **Nguyễn Kim Sơn**
# nen 38 van ban bi cham la "mat nguoi ky" trong khi ten van nam nguyen trong do.
DAM = re.compile(r"\*\*([^*\n]{1,150})\*\*")
NGHIENG = re.compile(r"(?<!\*)\*([^*\n]{1,100})\*(?!\*)")
TIEU_DE_MD = re.compile(r"^#{1,6}\s+", re.M)

# KHONG dung toi hai thu duoi day, du chung cung la markdown:
#   `| ô | ô |`  — do la cau truc BANG that, bo dau gach dung la dinh lien cac o
#   `- muc`      — van ban hanh chinh von viet '- Các Thứ trưởng;', xoa la hong
#                  noi dung that chu khong phai don dinh dang


def don(t):
    """-> (text da don, {loai: so lan})"""
    dem = {}

    n = len(LOI_DAN.findall(t))
    if n:
        dem["lời dẫn"] = n
        t = LOI_DAN.sub("", t)

    n = len(NHAI_LENH.findall(t))
    if n:
        dem["nhại lệnh"] = n
        t = NHAI_LENH.sub("", t)

    n = len(MOC_MODEL.findall(t))
    if n:
        dem["mốc **Trang N**"] = n
        t = MOC_MODEL.sub("", t)

    n = len(THE_BR.findall(t))
    if n:
        dem["thẻ <br>"] = n
        t = THE_BR.sub("\n", t)

    n = len(DAM.findall(t)) + len(NGHIENG.findall(t)) + len(TIEU_DE_MD.findall(t))
    if n:
        dem["markdown nhấn mạnh"] = n
        t = TIEU_DE_MD.sub("", DAM.sub(r"\1", t))
        t = NGHIENG.sub(r"\1", t)

    # Dong ngang: phai chay SAU khi bo moc model, vi `--- **Trang 1**` sau khi bo
    # moc se con lai `---` tro thanh dong ngang.
    n = len(DONG_NGANG.findall(t))
    if n:
        dem["dòng ngang"] = n
        t = DONG_NGANG.sub("", t)

    t = THUA_DONG.sub("\n\n", t)
    return t.strip() + "\n", dem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    fs = [f for k in KHO if k.exists() for f in sorted(k.rglob("*.txt"))]
    tong = {}
    doi = 0
    truoc = sau = 0

    print("=" * 84)
    print("DỌN RÁC CỦA MODEL")
    print("=" * 84)

    vi_du = []
    for f in fs:
        t = io.open(f, encoding="utf-8", errors="replace").read()
        m, dem = don(t)
        truoc += len(t)
        sau += len(m)

        if not dem:
            continue

        doi += 1
        for k, v in dem.items():
            tong[k] = tong.get(k, 0) + v

        if "lời dẫn" in dem and len(vi_du) < 5:
            for x in LOI_DAN.findall(t)[:1]:
                vi_du.append("%s  %s" % (f.name[:4], re.sub(r"\s+", " ", x)[:88]))

        if a.apply:
            io.open(f, "w", encoding="utf-8", newline="\n").write(m)

    print("  File có rác : %d / %d" % (doi, len(fs)))
    for k, v in sorted(tong.items(), key=lambda x: -x[1]):
        print("     %-20s %6d" % (k, v))
    print("  Ký tự       : %s -> %s  (%+d)"
          % ("{:,}".format(truoc), "{:,}".format(sau), sau - truoc))

    if vi_du:
        print("-" * 84)
        print("  Lời dẫn bị xoá (mẫu):")
        for x in vi_du:
            print("     %s" % x)

    print("=" * 84)
    print("Đã ghi đè." if a.apply else ">>> Mới là XEM TRƯỚC. Thêm --apply để ghi.")


if __name__ == "__main__":
    main()
