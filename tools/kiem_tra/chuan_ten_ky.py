# -*- coding: utf-8 -*-
"""Gop cac cach viet khac nhau cua CUNG MOT nguoi ky ve mot ten chuan.

VI SAO CAN: 'Đoàn Quang Vinh' (21 van ban) va 'Doan Quang Winh' (1 van ban) dang la HAI
nut Person khac nhau trong Neo4j. Truy van "van ban nao do Hieu truong X ky" se tra
thieu, va moi so dem ve nguoi ky deu lech. Day la loi OCR, khong phai hai nguoi.

BA MUC DO GOP, tu chac den kem chac:

  1. CHI LECH DAU  — 'Nguyễn Hữu Hiéu' / 'Nguyễn Hữu Hiếu'
     Bo dau ra thi trung khit. Gop vo dieu kien, khong the sai.

  2. LECH MOT KY TU, va do la cap HAY BI OCR DOC NHAM — 'Winh' / 'Vinh' (v↔w)
     KHONG gop bua moi cap lech mot ky tu: 'Lê Văn Hải' va 'Lê Văn Mải' cung lech mot
     ky tu nhung la hai nguoi. Chi gop khi ky tu lech nam trong bang nham cua OCR.

  3. MOT KY TU BI LAP hoac BI NUOT  — 'Thườởng' / 'Thưởng'
     OCR hay nhan doi mot chu khi con dau de len. Gop khi ky tu them vao trung voi
     ky tu ke no.

CHON TEN CHUAN trong moi nhom, theo thu tu:
  a. Ho phai la HO NGUOI VIET that ('Ngụyễn' khong phai ho, 'Nguyễn' moi la)
  b. Xuat hien nhieu lan hon
  c. Con nhieu dau tieng Viet hon (OCR lam MAT dau, khong tu them dau vao)

    python chuan_ten_ky.py              # soi xem gop nhung gi
"""
import difflib
import io
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trich_do_thi import HO_VIET                     # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
GOC = Path(__file__).resolve().parents[2]

# Cap ky tu OCR hay doc nham nhau tren van ban tieng Viet co dau va co con dau do len.
# Moi cap o day deu lay tu loi THAT da gap, khong phai liet ke cho du.
NHAM = [set("vw"), set("ae"), set("ao"), set("eo"), set("il"), set("io"), set("ij"),
        set("un"), set("cg"), set("ce"), set("sf"), set("st"), set("rn"), set("hb"),
        set("gq"), set("pq"), set("uv"), set("mn"), set("dđ"), set("01o"), set("15il")]

DAU = re.compile(r"[̀-ͯ]")

# Tieng Viet: mot AM TIET chi mang DUNG MOT dau thanh. Nam dau thanh la huyen/sac/nga/
# hoi/nang; con mu (U+0302), dau moc (U+031B), dau trang (U+0306) KHONG phai dau thanh.
#   'Nguyễn' = ê(mu) + ngã        -> 1 dau thanh, dung chinh ta
#   'Ngụyễn' = ụ(nặng) + ê + ngã  -> 2 dau thanh, KHONG TON TAI trong tieng Viet
# Day la cho phan biet ban OCR dung voi ban OCR sai, khi ca hai bo dau ra deu giong nhau.
THANH = set("̣̀́̃̉")


def _bo(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D").lower()


def _so_dau(s):
    return len(DAU.findall(unicodedata.normalize("NFD", s or "")))


def _hop_le(s):
    """Moi tu trong ten co dung chinh ta dau thanh khong?

    Khong dem tong so dau (ban OCR sai thuong co NHIEU dau hon ban dung, vi no ram
    them dau vao sai cho) — phai xet dau thanh co qua mot cai tren mot tu hay khong.
    """
    for tu in unicodedata.normalize("NFD", s or "").split():
        if sum(1 for c in tu if c in THANH) > 1:
            return False
    return True


def _ho_that(s):
    return _bo((s or " ").split()[0]) in HO_VIET


def cung_nguoi(a, b):
    """Hai cach viet nay co phai cung mot nguoi? a, b la ten DA BO DAU."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    ops = [o for o in difflib.SequenceMatcher(None, a, b).get_opcodes()
           if o[0] != "equal"]
    if len(ops) != 1:
        return False
    o, i1, i2, j1, j2 = ops[0]
    if max(i2 - i1, j2 - j1) > 1:
        return False

    if o == "replace":
        c = {a[i1], b[j1]}
        return any(c <= n for n in NHAM)

    # them/bot mot ky tu: chi chap nhan khi do la KY TU BI LAP ('Thuoong' <- 'Thuong')
    dai, ngan, vt = (a, b, i1) if len(a) > len(b) else (b, a, j1)
    c = dai[vt]
    return c == dai[vt - 1] if vt else (len(dai) > 1 and c == dai[1])


def gom(ten_dem):
    """{ten: so lan} -> {ten goc: ten chuan}. Ten khong phai gop thi tro ve chinh no."""
    ds = sorted(ten_dem)
    khoa = {t: _bo(t) for t in ds}

    cha = {t: t for t in ds}

    def tim(x):
        while cha[x] != x:
            cha[x] = cha[cha[x]]
            x = cha[x]
        return x

    for i, a in enumerate(ds):
        for b in ds[i + 1:]:
            if cung_nguoi(khoa[a], khoa[b]):
                ra, rb = tim(a), tim(b)
                if ra != rb:
                    cha[rb] = ra

    nhom = defaultdict(list)
    for t in ds:
        nhom[tim(t)].append(t)

    ra = {}
    for _g, v in nhom.items():
        # dung chinh ta dau thanh > ho that > xuat hien nhieu > con nhieu dau
        chuan = max(v, key=lambda t: (_hop_le(t), _ho_that(t), ten_dem[t], _so_dau(t)))
        for t in v:
            ra[t] = chuan
    return ra


def main():
    p = GOC / "data" / "kiem_tra" / "do_thi.json"
    vb = json.loads(io.open(p, encoding="utf-8").read())["van_ban"]
    dem = Counter(v["nguoi_ky"] for v in vb.values() if v["nguoi_ky"])
    m = gom(dem)

    doi = {a: b for a, b in m.items() if a != b}
    print("=" * 84)
    print("CHUẨN HOÁ TÊN NGƯỜI KÝ")
    print("=" * 84)
    print("  Trước: %d tên khác nhau / %d văn bản có người ký"
          % (len(dem), sum(dem.values())))
    print("  Sau  : %d tên  (gộp %d cách viết sai)"
          % (len({m[t] for t in dem}), len(doi)))
    print("-" * 84)
    for a, b in sorted(doi.items(), key=lambda x: -dem[x[0]]):
        print("  %-26s (%2d văn bản)  →  %s" % (a, dem[a], b))
    print("=" * 84)


if __name__ == "__main__":
    main()
