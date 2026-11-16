# -*- coding: utf-8 -*-
"""Don ba loai rac cuoi cung trong kho: watermark trang luat, the HTML, loi dan model.

VI SAO WATERMARK LA RAC NGUY. Nhieu PDF trong kho tai tu ThuVienPhapLuat nen co dai
quang cao doc le trang. OCR keo no vao GIUA CAU:

    '...thu hoi von. LawSoft 09468765 Tel: +84-8-3930 3279 www.ThuVienPhapLuat.vn
     Dieu 12. ...'

De lai thi no vao than Dieu, vao trich yeu, vao ca chuoi tim kiem — moi truy van
'dieu nao noi ve thu hoi von' deu keo theo so dien thoai quang cao.

BA THU KHONG DUOC DUNG TOI, du bo soi bao la 'rac':

  1. DAU CHAM DAN trong MUC LUC ('Dieu 1 ......... 5') va CHO TRONG bieu mau.
     136 file dinh, nhung day la cach trinh bay THAT cua van ban hanh chinh.
  2. Khoi 'lap lai' ma bo do bat duoc — deu la chinh may dong cham do.
  3. Chu Cyrillic trong 4 file: 'ТРКИ Тест по русскому языку' — ten ky thi tieng
     Nga, duoc liet ke trong quy dinh chung chi ngoai ngu. NOI DUNG THAT.

    python don_watermark.py            # xem truoc
    python don_watermark.py --apply
"""
import argparse
import io
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
KHO = GOC / "data" / "processed" / "text_final"

# Model doi khi tu chu thich '(Thông tin watermark ở lề phải: ...)' — bo ca cum do
CHU_THICH = re.compile(
    r"\(\s*(?:Thông\s*tin\s*)?(?:watermark|lề\s*trang|lề\s*phải|thông\s*tin\s*lề)"
    r"[^)]{0,160}\)", re.I)

# Dai quang cao: ten trang + dien thoai + ma so, dinh nhau hoac roi rac
WATERMARK = re.compile(
    r"\s*(?:THƯ\s*VIỆN\s*PHÁP\s*LUẬT|THƯ\s*VIEN\s*PHAP\s*LUAT|LawSoft|LAWSOFT)?"
    r"\s*(?:\+?\s*84[\s-]?\d{1,2}[\s-]?\d{3,4}[\s-]?\d{3,4})?"
    r"\s*(?:Te[klb]?\s*:?)?"
    r"\s*(?:www\.)?ThuVienPhapLuat(?:\.(?:vn|com|VI|V|v))?\s*",
    re.I)

# Con sot khi cum tren khong dinh lien
# OCR lam vo chinh dai watermark: 'THƯ VIEN PHÁP LUẬ T', 'THƯ VIỆN PHAP LUAT?',
# 'Tet +84-28', 'pLuat.VI', 'www.ThuVie' (cut giua chung). Mau phai chiu duoc
# nhung bien the do — cho phep thieu dau, chen khoang trang, cut duoi.
VO = [
    re.compile(r"\s*TH[ƯU]\s*VI[ỆEÊ]N\s*PH[ÁA]P\s*LU[ẬAÂ][TÂ]?\s*[?.,]?\s*", re.I),
    re.compile(r"\s*Te[tkl]\s*:?\s*\+?\s*1?84\s*[-\s]?\d{1,2}\s*[-\s]?\d{3,4}"
               r"\s*[-\s]?\d{3,4}\s*", re.I),
    re.compile(r"\s*(?:www\.)?Thu\s*Vie\w*\s*", re.I),
    re.compile(r"\s*p?Luat\.(?:vn|VI|com|v)\s*", re.I),
]

RIENG = [
    re.compile(r"\s*(?:THƯ\s*VIỆN\s*PHÁP\s*LUẬT|THƯ\s*VIEN\s*PHAP\s*LUAT)\s*", re.I),
    re.compile(r"\s*LawSoft\s*\+?\s*", re.I),
    re.compile(r"\s*Te[klb]?\s*:?\s*\+?\s*84[\s-]?\d{1,2}[\s-]?\d{3,4}[\s-]?\d{3,4}\s*",
               re.I),
    re.compile(r"(?<![\d/])09\d{6}(?![\d/])"),
]

# The HTML: bo THE, giu CHU ben trong ('<u>Ghi chú:</u>' -> 'Ghi chú:')
THE = re.compile(r"</?(?:br|p|div|span|b|i|u|em|strong)\b[^>]{0,20}>", re.I)

LOI_DAN = re.compile(
    r"^[^\n]{0,260}?(?:chào\s+bạn|bạn\s+cung\s+cấp|bạn\s+đã\s+cung\s+cấp|"
    r"đã\s+được\s+OCR|dạng\s+plaintext)[^\n]{0,200}$", re.I | re.M)

THUA = re.compile(r"[ \t]{2,}")


def giu_xuong_dong(m):
    """Thay watermark bang chinh so DAU XUONG DONG no nuot.

    Watermark hay nam GIUA chuc danh va ten nguoi ky:
        THỨ TRƯỞNG
        THƯ VIEN PHAP LUAT Tek +84-28-3930 3279
        Nguyễn Hữu Độ
    Thay bang khoang trang thi ba dong don thanh mot, ma bo trich doi TEN DUNG MOT
    MINH tren dong -> mat nguoi ky. Da do that: 452 -> 446 van ban.
    """
    n = m.group(0).count("\n")
    return "\n" * n if n else " "


def don(t):
    dem = {}

    for ten, bt in (("chú thích watermark", CHU_THICH),
                    ("dải watermark", WATERMARK),
                    ("lời dẫn model", LOI_DAN)):
        n = len(bt.findall(t))
        if n:
            dem[ten] = dem.get(ten, 0) + n
            t = bt.sub(giu_xuong_dong, t)

    n = len(THE.findall(t))
    if n:
        dem["thẻ HTML"] = n
        t = THE.sub("", t)

    for bt in VO + RIENG:
        n = len(bt.findall(t))
        if n:
            dem["mảnh watermark"] = dem.get("mảnh watermark", 0) + n
            t = bt.sub(giu_xuong_dong, t)

    t = THUA.sub(" ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"[ \t]+\n", "\n", t)

    return t.strip() + "\n", dem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    fs = sorted(KHO.rglob("*.txt"))
    tong = {}
    doi = 0
    truoc = sau = 0
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

        if len(vi_du) < 5 and "dải watermark" in dem:
            i = WATERMARK.search(t)
            if i:
                vi_du.append((f.name[:4],
                              re.sub(r"\s+", " ", t[max(0, i.start() - 40):
                                                    i.end() + 30])))

        if a.apply:
            io.open(f, "w", encoding="utf-8", newline="\n").write(m)

    print("=" * 84)
    print("DỌN WATERMARK / THẺ HTML / LỜI DẪN")
    print("=" * 84)
    print("  File đụng tới : %d / %d" % (doi, len(fs)))
    for k, v in sorted(tong.items(), key=lambda x: -x[1]):
        print("     %-22s %5d" % (k, v))
    print("  Ký tự : %s -> %s  (%+d)"
          % ("{:,}".format(truoc), "{:,}".format(sau), sau - truoc))

    if vi_du:
        print("-" * 84)
        for d, s in vi_du:
            print("     [%s] %s" % (d, s[:76]))

    print("=" * 84)
    print("Đã ghi đè." if a.apply else ">>> Mới là XEM TRƯỚC. Thêm --apply để dọn.")


if __name__ == "__main__":
    main()
