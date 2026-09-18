# -*- coding: utf-8 -*-
"""Trich thuc the va quan he tu text_final -> do thi tri thuc (JSON).

Lam theo luoc do trong 'Xay-dung-graph-db.docx':
  NODE   VanBan, DonViBanHanh, LinhVuc, LoaiVanBan, CanCuPhapLy, DoiTuongApDung
  EDGE   BAN_HANH, THUOC_LINH_VUC, THUOC_LOAI, CAN_CU, THAY_THE, AP_DUNG_CHO

Nguon du lieu cho tung truong:
  so hieu / loai / co quan  <- TEN FILE (do nguoi tao dat, dang tin hon noi dung OCR)
  linh vuc                  <- THU MUC chua file (18 linh vuc)
  ngay ban hanh             <- dong "Da Nang, ngay X thang Y nam Z" trong may trang dau
  nguoi ky                  <- cuoi van ban, sau chuc danh HIEU TRUONG/GIAM DOC...
  CAN_CU                    <- cau "Can cu <loai van ban> so <X>"
  THAY_THE                  <- cau "thay the / bai bo <loai> so <X>"
  DoiTuongApDung            <- tu khoa doi tuong xuat hien trong may trang dau

Quan he CAN_CU tu tro thanh lien ket giua HAI VAN BAN TRONG BO khi so hieu trung khop —
day chinh la "moi lien ket ngam" ma bai bao muon lam ro.

    python trich_do_thi.py
    python trich_do_thi.py --ra do_thi.json
"""
import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trich_don_vi import tim_don_vi                   # noqa: E402
from quan_he_hieu_luc import phan_loai                # noqa: E402
from trich_dieu_khoan import tach_dieu, tach_noi_dung  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
SACH = GOC / "data" / "clean" / "text_final"

MOC_TRANG = re.compile(r"-{3,}\s*\[Trang\s+(\d+)\]\s*-{3,}")

NGAY = re.compile(
    r"ngày\s+(\d{1,2})\s*(?:tháng|[/-])\s*(\d{1,2})\s*(?:năm|[/-])\s*(\d{4})", re.I)

# LUAT khong ghi ngay o dau nhu Quyet dinh. Ngay ban hanh cua Luat nam o CUOI, trong
# cau "Luat nay da duoc Quoc hoi ... thong qua ngay X thang Y nam Z". Dau van ban chi
# co ngay CONG BAO, ma cong bao lai hay viet dang gach noi 'Ngay 14-7-2018'.
# Do duoc: ca 48 van ban thieu ngay deu la Luat, va deu vi hai ly do nay.
NGAY_THONG_QUA = re.compile(
    r"(?:Luật|Bộ\s*luật|Nghị\s*quyết|Pháp\s*lệnh)\s*này\s*(?:đã\s*)?được"
    r"[^.]{0,220}?thông\s*qua\s*(?:ngày)?\s*(\d{1,2})\s*(?:tháng|[/-])\s*(\d{1,2})"
    r"\s*(?:năm|[/-])\s*(\d{4})", re.I | re.S)


def tim_ngay(t):
    """Ngay ban hanh. Uu tien 'thong qua ngay ...' (Luat), roi den dong dau van ban.

    Doi voi Luat thi 'thong qua' moi la ngay ban hanh; ngay o dau chi la ngay dang
    Cong bao, khac nhau vai tuan.
    """
    # LAY LAN KHOP CUOI: dieu khoan thi hanh nam o cuoi van ban. Quet ca van ban ma
    # lay lan dau thi vo phai ngay thong qua cua LUAT DUOC VIEN DAN trong phan can cu
    # — da do: 0282 (10/2022/QH15) ra ngay 14/6/2019, 0246 (12/2017/QH14) ra 27/11/2015.
    # Doi bang duoc cum "Luat NAY ... thong qua" de chac chan la cua chinh no.
    m = None
    for m in NGAY_THONG_QUA.finditer(t):
        pass
    return m or NGAY.search(t[:4000]) or NGAY.search(t)

LOAI_VB = (r"nghị\s*định|nghị\s*quyết|quyết\s*định|thông\s*tư\s*liên\s*tịch|thông\s*tư|"
           r"thông\s*báo|công\s*văn|chỉ\s*thị|luật|kế\s*hoạch|hướng\s*dẫn|"
           r"kết\s*luận|pháp\s*lệnh|điều\s*lệ")
SO_HIEU = r"(\d{1,5}\s*/\s*(?:\d{4}\s*/\s*)?[A-ZĐ][\w\-Đ]{1,20})"

CAN_CU = re.compile(r"[Cc]ăn\s*cứ\s+(%s)[^\d]{0,20}%s" % (LOAI_VB, SO_HIEU), re.I)

# REFERENCES (Ontology §4): so hieu nam trong THAN van ban, khong phai can cu, khong keo
# theo thay doi hieu luc. Doi hoi co ten LOAI dung truoc de khoi vo phai so quyet dinh
# tien luong, so tai khoan, ngay thang dang 15/8/2024...
SO_HIEU_THAN = re.compile(r"(?:%s)\s*(?:số\s*)?[:\s]\s*%s" % (LOAI_VB, SO_HIEU), re.I)

# Luat Viet Nam thuong duoc vien dan bang TEN + NGAY, khong bang so hieu:
#   "Can cu Luat To chuc Chinh phu ngay 19 thang 6 nam 2015"
#   "Can cu Hien phap nuoc Cong hoa xa hoi chu nghia Viet Nam"
# Mau SO_HIEU doi dang <so>/<chu> nen truot het loai nay — 94/111 van ban khong trich
# duoc quan he nao la vi ly do do. Bat rieng bang ten.
CAN_CU_TEN = re.compile(
    r"[Cc]ăn\s*cứ\s+((?:Hiến\s*pháp|Bộ\s*luật|Luật|Pháp\s*lệnh|Điều\s*lệ)"
    r"(?:\s+[A-ZĐÀ-Ỹa-zà-ỹ][\wÀ-ỹ]*){0,9})"
    r"(?=\s*(?:ngày|số|;|,|\.|năm\s+\d{4}|$))", re.I | re.M)

# Tu hay dinh vao duoi ten luat do OCR nuot dau cau hoac do cau van tiep dien.
# KHONG cat o "va"/"cua": nhieu luat co san hai tu do trong ten that — "Luat Khoa hoc
# va Cong nghe", "Luat Can bo, cong chuc va Luat Vien chuc" — cat la cut mat ten.
DUOI_THUA = re.compile(r"\s+(?:do|quy\s*định|ban\s*hành|được|đã|này|"
                       r"hiện\s*hành|nêu\s*trên|ngày|năm\s+\d{4})\b.*$", re.I)


# "Luat sua doi, bo sung mot so dieu cua Luat Giao duc dai hoc" — cai duoc vien dan THAT
# SU la Luat Giao duc dai hoc. Lay nguyen phan dau se sinh mot nut "Luat sua doi" gom
# chung moi luat sua doi cua moi linh vuc lai — sai han ve nghia.
LUAT_SUA_DOI = re.compile(r"^(?:Bộ\s*luật|Luật|Pháp\s*lệnh)\s+(?:sửa\s*đổi|bổ\s*sung)", re.I)
CUA_LUAT = re.compile(r"của\s+((?:Bộ\s*luật|Luật|Pháp\s*lệnh)"
                      r"(?:\s+[A-ZĐÀ-Ỹa-zà-ỹ][\wÀ-ỹ]*){1,8}?)"
                      r"(?=\s*(?:ngày|số|năm\s+\d{4}|[;,.]|$))", re.I)


def don_ten_luat(s, ngu_canh=""):
    """Chuan hoa ten luat lam khoa nut. -> '' neu ten khong dung duoc.

    ngu_canh: doan van ngay sau cho khop, de lan ra ten luat goc trong truong hop
    "Luat sua doi, bo sung mot so dieu cua <Luat X>".
    """
    s = re.sub(r"\s+", " ", (s or "").strip(" .,;:*_-"))

    # Xet "Luat sua doi, bo sung..." TRUOC khi cat duoi: DUOI_THUA co ca "sua doi" trong
    # danh sach nen se cat cut thanh moi chu "Luat", khong con gi de lan ra luat goc.
    if LUAT_SUA_DOI.match(s):
        m = CUA_LUAT.search(ngu_canh or "")
        if not m:
            return ""              # khong lan ra luat goc thi bo, hon la tao nut sai
        s = re.sub(r"\s+", " ", m.group(1)).strip(" .,;:*_-")

    s = DUOI_THUA.sub("", s).strip(" .,;:*_-")

    # Moi cach viet Hien phap (co hay khong co "nuoc Cong hoa...") ve chung mot nut
    if re.match(r"^Hiến\s*pháp\b", s, re.I):
        return "Hiến pháp"

    if len(s) < 6 or len(s) > 70:
        return ""
    # OCR nat: ten lan qua nhieu ky tu la thi bo, tranh sinh nut rac
    chu = sum(1 for c in s if c.isalpha() or c.isspace())
    if chu / max(1, len(s)) < 0.9:
        return ""
    return s[0].upper() + s[1:]



def _bo_dau(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D").upper()


# So khop chuc danh SAU KHI BO DAU. OCR khoi ky rat hay sai dau vi con dau do de len
# chu ("HIEU TRUơNG" thay vi "HIEU TRUỞNG"); doi dau dung la truot het.
CHUC_DANH_KHONG_DAU = re.compile(
    r"HIEU\s*TRUONG|GIAM\s*DOC|CHU\s*TICH|BO\s*TRUONG|THU\s*TUONG|"
    r"TRUONG\s*BAN|CHANH\s*VAN\s*PHONG|CHU\s*NHIEM|THU\s*TRUONG|"
    r"TONG\s*THANH\s*TRA|VIEN\s*TRUONG|TM\.\s*HOI\s*DONG|"
    # Bo sung sau khi soi khoi ky that: 'CUC TRUONG' va 'TRUONG PHONG' bi thieu,
    # nen 2085/QLCL-KDCLGD (KT. CUC TRUONG - PHO CUC TRUONG) khong doc duoc nguoi ky.
    r"CUC\s*TRUONG|TRUONG\s*PHONG|TONG\s*CUC\s*TRUONG|TO\s*TRUONG")


class CHUC_DANH:                      # giu nguyen ten goi cu de khong phai sua cho khac
    @staticmethod
    def search(d):
        return CHUC_DANH_KHONG_DAU.search(_bo_dau(d))

    @staticmethod
    def finditer(t):
        return CHUC_DANH_KHONG_DAU.finditer(_bo_dau(t))
# "Đã ký: Nguyễn Sinh Hùng" — ban sao y ghi thang ten sau hai cham
DA_KY = re.compile(r"[ĐD]ã\s*ký\s*:?\s*(.+)$", re.I)
# Hoc ham dung truoc ten. OCR hay doc "PGS.TS." thanh "PGS FS.", "PGS. IS.", "PGSTS"
# -> cho phep mot ky tu bat ky o vi tri chu T va dau cham tuy y.
# "TS" hay bi doc thanh "FS", "IS", "T5" vi con dau de len. Cho phep bien the do,
# nhung KHONG mo rong thanh ky tu bat ky — se an mat tu dau cua ten that.
HOC_HAM = r"(?P<hh>(?:(?:PGS|GS|[TFI][S5]|ThS|Th\.S|CN)[\s.,]*){0,3})"
# Chu dau ten co the bi CON DAU nuot mat ("guyen Kim Son" thay vi "Nguyen Kim Son")
# -> chap nhan tu dau bat dau bang chu thuong, mien la cac tu sau deu viet hoa dung.
# CHI tu dau moi duoc phep viet thuong (do con dau nuot mat chu cai dau). Moi tu sau
# bat buoc viet hoa dung — neu khong thi cum "Ho tro sinh Vi" cung lot qua, vi "Ho"
# bo dau ra dung bang ho "Ho".
TEN_NGUOI = re.compile(
    r"^" + HOC_HAM +
    r"(?P<ten>[A-ZĐÀ-Ỹa-zà-ỹ][a-zà-ỹ]+(?:\s+[A-ZĐÀ-Ỹ][a-zà-ỹ]+){1,4})\s*$")

# Ho nguoi Viet la TAP DONG va rat nho -> dung lam bo loc chinh xac cao. Khong co no
# thi mau ten bat nham ca "Ho tro sinh Vi", "Dai hoc Da", "hoat dong" — nhung cum chu
# hoa binh thuong nam ngay duoi khoi ky.
HO_VIET = {
    "nguyen", "tran", "le", "pham", "hoang", "huynh", "phan", "vu", "vo", "dang",
    "bui", "do", "ho", "ngo", "duong", "ly", "doan", "dinh", "truong", "lam",
    "mai", "cao", "ta", "chu", "to", "thai", "kieu", "giang", "la", "quach",
    "tu", "ha", "luu", "vuong", "diep", "chuong", "trinh", "trieu", "khong",
    "nghiem", "luong", "thach", "bach", "au", "chau", "cu", "danh", "hua",
    "khuat", "lai", "lanh", "mac", "nong", "ong", "pho", "quang", "sy", "tang",
    "tong", "tinh", "ung", "van", "xa",
    # Bo sung sau khi quet ca kho: ho xuat hien ngay sau chuc danh ma danh sach
    # chua co. Chi 'phung' la ho that (Phùng Xuân Nhạ, Bộ trưởng Bộ GD&ĐT);
    # 'Pkan', 'Ngfi', 'Bl' trong ket qua quet deu la rac OCR nen khong them.
    # Them kem vai ho pho bien khac cho chac, deu la ho hiem gap lam tu thuong.
    "phung", "ton", "ninh", "uong", "thieu", "tieu",
}


def _sua_ho(tu):
    """Sua tu ho bi CON DAU nuot mat chu dau: 'guyen' -> 'Nguyen'. -> '' neu khong phai ho."""
    k = _bo_dau(tu).lower()
    if k in HO_VIET:
        return tu
    # con dau che mat 1-2 chu cai dau: tim ho nao ket thuc bang phan con lai
    if len(k) >= 3:
        hop = [h for h in HO_VIET if h.endswith(k) and 0 < len(h) - len(k) <= 2]
        if len(hop) == 1:
            # gan lai chu cai bi mat vao DAU TU GOC de giu nguyen dau tieng Viet:
            # 'guyễn' + thieu 'n' -> 'Nguyễn', khong phai 'Nguyen' khong dau
            thieu = hop[0][: len(hop[0]) - len(k)]
            return thieu.capitalize() + tu
    return ""


DOI_TUONG = [
    ("Sinh viên", r"sinh\s*viên"),
    ("Học viên cao học", r"học\s*viên\s*cao\s*học|trình\s*độ\s*thạc\s*sĩ"),
    ("Nghiên cứu sinh", r"nghiên\s*cứu\s*sinh|trình\s*độ\s*tiến\s*sĩ"),
    ("Giảng viên", r"giảng\s*viên"),
    ("Viên chức, người lao động", r"viên\s*chức|người\s*lao\s*động"),
    ("Đơn vị thuộc trường", r"các\s*(?:đơn\s*vị|khoa|phòng|trung\s*tâm)"),
]

CO_QUAN = {
    "ĐHBK": "Trường Đại học Bách khoa – ĐHĐN",
    "ĐHĐN": "Đại học Đà Nẵng",
    "BGDĐT": "Bộ Giáo dục và Đào tạo",
    "BGDDT": "Bộ Giáo dục và Đào tạo",
    "TTg": "Thủ tướng Chính phủ",
    "CP": "Chính phủ",
    "QH13": "Quốc hội khoá XIII",
    "QH14": "Quốc hội khoá XIV",
    "QH15": "Quốc hội khoá XV",
    "BNV": "Bộ Nội vụ",
    "BTC": "Bộ Tài chính",
    "BLĐTBXH": "Bộ Lao động – Thương binh và Xã hội",
    "TTCP": "Thanh tra Chính phủ",
    "BKHCN": "Bộ Khoa học và Công nghệ",
    "BTTTT": "Bộ Thông tin và Truyền thông",
    "BYT": "Bộ Y tế",
    "HĐT": "Hội đồng trường ĐHBK",
    "HĐĐH": "Hội đồng Đại học Đà Nẵng",
    "UBND": "Uỷ ban nhân dân",
    "TW": "Ban Chấp hành Trung ương",
    "NHNN": "Ngân hàng Nhà nước",
}
TEN_LOAI = {
    "QĐ": "Quyết định", "NĐ": "Nghị định", "NQ": "Nghị quyết", "TT": "Thông tư",
    "TTLT": "Thông tư liên tịch", "CT": "Chỉ thị", "KH": "Kế hoạch", "HD": "Hướng dẫn",
    "HĐ": "Hướng dẫn", "KL": "Kết luận", "TB": "Thông báo", "CV": "Công văn",
    "QC": "Quy chế", "PL": "Pháp lệnh", "L": "Luật", "BC": "Báo cáo", "TTr": "Tờ trình",
}


def chuan_so(s):
    """Chuan hoa so hieu de doi chieu: bo khoang trang, viet hoa, bo so 0 dan dau."""
    s = re.sub(r"\s+", "", (s or "").strip(" .,;:*"))
    s = unicodedata.normalize("NFC", s).upper()
    p = s.split("/")
    if p and p[0].isdigit():
        p[0] = str(int(p[0]))
    return "/".join(p)


# Ma LOAI van ban hop le xuat hien trong so hieu. Thieu ma nao thi van ban do bi coi
# la cong van — nen chi them khi that su gap, dung doan truoc.
LOAI_MA = {"QĐ", "TT", "TTLT", "NĐ", "NQ", "CT", "KH", "HD", "VBHN", "QC", "PL",
           "TB", "CV", "L", "QĐ-TTg"}

# Ba ten file viet sai ma co quan. Khong doi ten file (se dut lien ket sang PDF goc va
# cac tang xu ly truoc), chuan hoa ngay luc doc:
#   0158  TT-BGDÐT   chu "Ð" U+00D0 (eth) thay vi "Đ" U+0110
#   0289  QĐ-BGDDT   mat dau
#   0328  TT-BGD&ĐT  thua dau &
# De nguyen thi KG sinh ra ba node co quan ma, tach roi khoi BGDĐT that.
SUA_MA_CQ = {"BGD" + chr(0x00D0) + "T": "BGDĐT", "BGDDT": "BGDĐT", "BGD&ĐT": "BGDĐT"}


def tach_ten_file(ten):
    """Tach metadata tu ten file.

    Hai dang:  <id>_<so>_<LOAI-CQ>_<tieu de>
               <id>_<so>_<nam>_<LOAI-CQ>_<tieu de>   (van ban cap bo co nam trong so hieu)
    """
    p = ten[:-4].split("_")
    if len(p) < 3:
        return p[0], "", "", "", ten[:-4]
    doc_id = p[0]
    if len(p) >= 4 and re.fullmatch(r"\d{4}", p[2]):
        so, tieu_de, ma = "%s/%s/%s" % (p[1], p[2], p[3]), "_".join(p[4:]), p[3]
    else:
        so, tieu_de, ma = "%s/%s" % (p[1], p[2]), "_".join(p[3:]), p[2]
    for sai, dung in SUA_MA_CQ.items():
        if sai in ma:
            ma = ma.replace(sai, dung)
            so = so.replace(sai, dung)
    loai = ma.split("-")[0]
    cq = ma.split("-", 1)[1] if "-" in ma else ""
    if re.fullmatch(r"QH\d{2}", loai):
        loai, cq = "L", loai
    elif loai.upper().replace(" ", "").startswith("HIẾNPHÁP"):
        loai, cq = "HP", "QH"
    elif loai not in LOAI_MA:
        # CONG VAN: so hieu la "<so>/<co quan>-<don vi soan thao>", khong co ma loai.
        #   4079/ĐHĐN-TCCB, 3878/BGDĐT-PC, 2085/QLCL-KĐCLGD
        # Bo trich cu lay ve trai lam `loai` -> 21 van ban co loai la "ĐHĐN"/"BGDĐT".
        # Dung ra: loai = CV, co quan ban hanh = ve trai. Don vi soan thao van con
        # nguyen trong `so` nen khong mat thong tin.
        loai, cq = "CV", loai
    return doc_id, chuan_so(so), loai, cq, tieu_de.strip()


def trang_dau(t, n=3):
    phan = MOC_TRANG.split(t)
    return t[:6000] if len(phan) < 3 else "".join(phan[1:2 * n + 1])[:9000]


def _ten(s):
    m = TEN_NGUOI.match((s or "").strip())
    if not m:
        return ""
    tu = m.group("ten").split()
    if not (2 <= len(tu) <= 5):
        return ""
    ho = _sua_ho(tu[0])
    if not ho:
        return ""                  # tu dau khong phai ho nguoi Viet -> khong phai ten
    tu[0] = ho if _bo_dau(tu[0]).lower() in HO_VIET else ho.capitalize()
    return " ".join(tu)


# Ontology §2.3: Person co ca `position` va `academicTitle`. Truoc day HOC_HAM bi coi la
# rac va vut di, con chuc danh thi chi dung de DINH VI chu ky roi bo luon — mat sach hai
# truong ma lo do da bat duoc san.
CHUAN_CHUC_DANH = [
    ("HIEU TRUONG", "Hiệu trưởng"), ("GIAM DOC", "Giám đốc"),
    ("CHU TICH", "Chủ tịch"), ("BO TRUONG", "Bộ trưởng"),
    ("THU TUONG", "Thủ tướng"), ("TRUONG BAN", "Trưởng ban"),
    ("CHANH VAN PHONG", "Chánh Văn phòng"), ("CHU NHIEM", "Chủ nhiệm"),
    ("THU TRUONG", "Thứ trưởng"), ("TONG THANH TRA", "Tổng Thanh tra"),
    ("VIEN TRUONG", "Viện trưởng"), ("HOI DONG", "TM. Hội đồng"),
]


def chuan_chuc_danh(d):
    """Dong chuc danh trong khoi ky -> ten chuc danh chuan. '' neu khong nhan ra.

    'KT. HIEU TRUONG' / 'PHO HIEU TRUONG' deu ve 'Phó Hiệu trưởng': ky thay (KT.) nghia
    la nguoi ky khong phai truong don vi. Doc sai cho nay thi gan nham quyen han cho
    mot pho hieu truong.
    """
    kd = _bo_dau(d)
    for mau, ten in CHUAN_CHUC_DANH:
        if re.search(mau.replace(" ", r"\s*"), kd):
            if re.search(r"\bKT\.|\bPHO\b|\bTL\.", kd):
                return "Phó " + ten[0].lower() + ten[1:]
            return ten
    return ""


def chuan_hoc_ham(s):
    """'PGS FS.' / 'PGS. IS.' -> 'PGS.TS.' — OCR de con dau len chu T rat hay sai."""
    hh = re.sub(r"[\s.,]+", "", (s or "").upper())
    hh = re.sub(r"[TFI][S5]", "TS", hh)
    ra = [x for x in ("PGS", "GS", "TS", "THS", "CN") if x in hh]
    if "PGS" in ra and "GS" in ra:
        ra.remove("GS")           # 'PGS' chua chuoi con 'GS', khong phai hai hoc ham
    return ".".join({"THS": "ThS"}.get(x, x) for x in ra)


# Ten viet TOAN CHU HOA: 'LÊ KIM HÙNG', 'ĐOÀN QUANG VINH'. Rat pho bien trong khoi
# ky cua van ban noi bo. Mau TEN_NGUOI doi chu dau hoa roi CAC CHU SAU THUONG nen
# truot het — da do: 42 Quyet dinh bi cham la 'khong co nguoi ky' trong khi ten nam
# ngay do.
TEN_HOA = re.compile(r"^([A-ZĐÀ-Ỹ][A-ZĐÀ-Ỹ]+(?:\s+[A-ZĐÀ-Ỹ]+){1,4})$")

# Hoc ham co the dung TRUOC hoac SAU ten: 'PGSTS. ĐOÀN QUANG VINH' va
# 'ĐOÀN QUANG VINH PGSTS' deu gap trong du lieu that.
HOC_HAM_ROI = re.compile(
    r"^\s*((?:(?:PGS|GS|[TFI][S5]|ThS|Th\.S|CN)[\s.,]*)+)|"
    r"((?:(?:PGS|GS|[TFI][S5]|ThS|Th\.S|CN)[\s.,]*)+)\s*$")


def _boc_hoc_ham(s):
    """Go hoc ham o CA HAI DAU. -> (phan con lai, hoc ham)"""
    s = (s or "").strip()
    hh = []
    for _ in range(2):
        m = HOC_HAM_ROI.search(s)
        if not m:
            break
        x = m.group(1) or m.group(2)
        if not x or not x.strip(" .,"):
            break
        hh.append(x)
        s = (s[:m.start()] + s[m.end():]).strip(" .,")
    return s, chuan_hoc_ham(" ".join(hh))


# Tu KHONG BAO GIO nam trong ten nguoi. Can vi nhieu ho nguoi Viet cung la tu
# thong thuong: 'truong' (Truong/Truong), 'danh', 'ly', 'doan', 'bach'.
# CHI liet ke tu CHAC CHAN khong bao gio la ten nguoi. Danh sach dai hon la hong:
# 'Thanh', 'Nam', 'Viet', 'Dinh', 'Thanh', 'Doan', 'Khoa', 'Truong' deu la ten dem
# hoac ten that cua nguoi Viet — cam chung la cam luon 'Nguyễn Thanh Bình',
# 'Lê Việt Hùng'. Da do that: danh sach dai lam tut 402 -> 247 van ban.
KHONG_PHAI_TEN = {
    "hoc", "muc", "nganh", "lich", "che", "quyet", "cuc", "tiet", "bieu",
    "luc", "tam",
}


def _ten_hh(s, toan_van=None):
    """-> (ten, hoc ham). Tach mot lan, khong quet lai hai lan hai ham khac nhau.

    `toan_van`: ca van ban, de loc ten TO CHUC ra khoi nhanh chu hoa (xem duoi).
    """
    m = TEN_NGUOI.match((s or "").strip())
    if m:
        return _ten(s), chuan_hoc_ham(m.group("hh"))

    # Nhanh TOAN CHU HOA. Van di qua bo loc HO_VIET nhu nhanh thuong, nen tieu de
    # kieu 'QUYẾT ĐỊNH', 'BAN HÀNH QUY CHẾ' khong lot duoc — 'quyet', 'ban' khong
    # phai ho nguoi Viet.
    con, hh = _boc_hoc_ham(s)
    m = TEN_HOA.match(con)
    if not m:
        return "", ""

    tu = m.group(1).split()
    if not (2 <= len(tu) <= 5):
        return "", ""
    if not _sua_ho(tu[0].capitalize()):
        return "", ""

    # Tu nao trong cum cung khong duoc la tu khong bao gio co trong ten nguoi
    if any(_bo_dau(w).lower() in KHONG_PHAI_TEN for w in tu[1:]):
        return "", ""

    # TAN SUAT la dau hieu phan biet tot nhat: ten nguoi ky xuat hien mot hai lan
    # o khoi ky, con ten TO CHUC va TIEU DE thi lap di lap lai khap van ban.
    # Nho cho nay ma 'Truong Dai Hoc Bach Khoa', 'Danh Muc Nganh Thi Diem',
    # 'Ly Lich Khoa Hoc' bi loai — ca ba deu lot qua bo loc ho nguoi Viet.
    if toan_van and _bo_dau(m.group(1)) in _bo_dau(toan_van):
        if _bo_dau(toan_van).count(_bo_dau(m.group(1))) > 3:
            return "", ""

    return " ".join(w.capitalize() for w in tu), hh


def tim_nguoi_ky(t):
    return tim_chu_ky(t)[0]


def tim_chu_ky(t):
    """-> (ten nguoi ky, hoc ham, chuc danh).

    Ten nguoi ky nam ngay duoi CHUC DANH o khoi ky cuoi phan chinh van.

    KHONG chi doc 40 dong cuoi file: hau het van ban co PHU LUC dai dang sau khoi ky,
    nen chu ky nam o giua file chu khong o cuoi (364/455 file truot vi ly do nay).
    Quet toan bo, lay lan khop CUOI CUNG — la nguoi ky ban chinh, khong phai nguoi ky
    cac van ban duoc trich dan o phan can cu.
    """
    dong = [d.strip() for d in t.splitlines() if d.strip()]
    thay = hh_thay = cd_thay = ""
    for i, d in enumerate(dong):
        m = DA_KY.search(d)
        if m:
            ten, hh = _ten_hh(m.group(1), t)
            if ten:
                thay, hh_thay, cd_thay = ten, hh, ""
                continue

        # Chuc danh phai DUNG MOT MINH tren dong thi moi la khoi ky. "... cua Bo truong
        # Bo Giao duc va Dao tao)" giua than bai khong phai chu ky — truoc day bat ca
        # nhung cho nhu vay roi lay lan khop CUOI CUNG nen hay tro ra giua tai lieu.
        if not CHUC_DANH.search(d) or len(d) > 34:
            continue
        if re.search(r"(của|theo|tại|do)\s*$", dong[i - 1] if i else "", re.I):
            continue
        if re.search(r"[)（].*$|^\(", d):
            continue

        # Quet 14 dong thay vi 6: giua chuc danh va ten thuong co CON DAU tron, OCR
        # be no thanh 5-8 manh vun ('TRUÈAG', 'ĐẠI 18il HỌz', 'BÁCH', 'HOC Đ~').
        # Voi 6 dong thi ten that nam ngoai tam voi — da do o 0082, ten
        # 'PGS.TS. Doan Quang Vinh' nam o dong thu 8 sau chuc danh.
        for e in dong[i + 1:i + 15]:
            m2 = DA_KY.search(e)
            ten, hh = _ten_hh(m2.group(1) if m2 else e, t)
            if ten:
                thay, hh_thay, cd_thay = ten, hh, chuan_chuc_danh(d)
                break
    return thay, hh_thay, cd_thay


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ra", default=str(GOC / "data" / "kiem_tra" / "do_thi.json"))
    a = ap.parse_args()

    vb = {}
    for f in sorted(SACH.rglob("*.txt")):
        t = f.read_text(encoding="utf-8", errors="replace")
        doc_id, so, loai, cq, tieu_de = tach_ten_file(f.name)
        dau = trang_dau(t)
        mn = tim_ngay(t)
        ngay = ("%04d-%02d-%02d" % (int(mn.group(3)), int(mn.group(2)), int(mn.group(1)))
                if mn else "")

        cc = []
        for m in CAN_CU.finditer(t):
            cc.append({"loai": re.sub(r"\s+", " ", m.group(1)).strip().lower(),
                       "so": chuan_so(m.group(2))})
        for m in CAN_CU_TEN.finditer(t):
            ten = don_ten_luat(m.group(1), t[m.start():m.start() + 260])
            if ten:
                cc.append({"loai": "luật", "so": ten, "theo_ten": True})
        cc = [x for i, x in enumerate(cc) if x["so"] != so and x not in cc[:i]]

        # Ba quan he hieu luc tach bach (Ontology §4) thay cho mot THAY_THE gop chung
        hl = [{"quan_he": qh, "so": s, "vi_tri": round(vt, 1), "doan": d}
              for qh, s, vt, d in phan_loai(t) if s != so]

        # REFERENCES = so hieu XUAT HIEN TRONG THAN nhung khong phai can cu, khong phai
        # quan he hieu luc. Vien dan tham chieu don thuan ("theo quy dinh tai QD 1234").
        da_co = {x["so"] for x in cc} | {x["so"] for x in hl} | {so}
        tk = []
        for m in SO_HIEU_THAN.finditer(t):
            x = chuan_so(m.group(1))
            if x in da_co or not re.search(r"[A-ZĐ]", x):
                continue
            da_co.add(x)
            tk.append({"so": x})

        ky = tim_chu_ky(t)
        ds_dieu = tach_dieu(t)
        nd = tach_noi_dung(t, ds_dieu)
        # Chi giu phan khung cua Dieu (so, tieu de, so khoan) — than Dieu 18 MB, khong
        # nhet vao do_thi.json duoc; ai can toan van thi doc dieu_khoan.json.
        dieu = [{"so": x["so"], "tieu_de": x["tieu_de"], "khoi": x["khoi"],
                 "so_khoan": x["so_khoan"]} for x in ds_dieu]
        noi_dung = nd[0] if nd else None

        vb[doc_id] = {
            "doc_id": doc_id, "so_hieu": so, "loai": loai,
            "ten_loai": TEN_LOAI.get(loai, loai),
            "co_quan": cq, "ten_co_quan": CO_QUAN.get(cq, cq or "Không rõ"),
            "tieu_de": tieu_de, "linh_vuc": f.parent.name,
            "ngay": ngay, "nguoi_ky": ky[0], "hoc_ham": ky[1], "chuc_danh": ky[2],
            "so_trang": len(MOC_TRANG.findall(t)) or 1,
            "so_ky_tu": len(t), "duong_dan": f.relative_to(GOC).as_posix(),
            "doi_tuong": [ten for ten, bt in DOI_TUONG if re.search(bt, dau, re.I)],
            # DonViLienQuan: nhan dien bang tu dien thuc the (xem trich_don_vi.py)
            "don_vi": sorted(tim_don_vi(t)),
            "can_cu": cc, "hieu_luc": hl, "tham_khao": tk,
            # Article / NormativeContent — Ontology §2.6, §2.7
            "dieu": dieu, "noi_dung": noi_dung,
        }

    # Gop cac cach viet sai cua cung mot nguoi ky ('Doan Quang Winh' -> 'Đoàn Quang
    # Vinh'). Phai lam SAU khi quet het kho, vi quyet dinh cach viet nao dung thi can
    # biet ca kho viet the nao — mot file le khong du can cu.
    from chuan_ten_ky import gom                      # noqa: E402  (tranh vong nhap)
    anh_xa = gom(Counter(v["nguoi_ky"] for v in vb.values() if v["nguoi_ky"]))
    for v in vb.values():
        if v["nguoi_ky"]:
            v["nguoi_ky"] = anh_xa.get(v["nguoi_ky"], v["nguoi_ky"])

    ix = {v["so_hieu"]: k for k, v in vb.items() if v["so_hieu"]}
    canh, ngoai = [], Counter()
    for k, v in vb.items():
        nhom = [("BASED_ON", v["can_cu"]), ("REFERENCES", v["tham_khao"])]
        nhom += [(x["quan_he"], [x]) for x in v["hieu_luc"]]
        for ten_qh, ds in nhom:
            for c in ds:
                dich = ix.get(c["so"])
                if dich and dich != k:
                    canh.append({"tu": k, "den": dich, "quan_he": ten_qh, "trong_bo": True})
                else:
                    canh.append({"tu": k, "den": c["so"], "quan_he": ten_qh,
                                 "trong_bo": False, "loai": c.get("loai", "")})
                    ngoai[c["so"]] += 1

    do_thi = {"van_ban": vb, "canh": canh,
              "can_cu_ngoai": [{"so": s, "so_lan": n} for s, n in ngoai.most_common()]}
    p = Path(a.ra)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(do_thi, ensure_ascii=False, indent=1), encoding="utf-8")

    n = len(vb)
    tr = sum(1 for c in canh if c["trong_bo"])
    print("=" * 86)
    print("TRÍCH ĐỒ THỊ TRI THỨC")
    print("=" * 86)
    print("  Văn bản              : %d" % n)
    print("  Có ngày ban hành     : %d (%.0f%%)"
          % (sum(1 for v in vb.values() if v["ngay"]),
             100.0 * sum(1 for v in vb.values() if v["ngay"]) / n))
    print("  Có người ký          : %d (%.0f%%)"
          % (sum(1 for v in vb.values() if v["nguoi_ky"]),
             100.0 * sum(1 for v in vb.values() if v["nguoi_ky"]) / n))
    print("  Lĩnh vực             : %d" % len({v["linh_vuc"] for v in vb.values()}))
    print("  Loại văn bản         : %d" % len({v["ten_loai"] for v in vb.values()}))
    print("  Đơn vị ban hành      : %d" % len({v["ten_co_quan"] for v in vb.values()}))
    print("-" * 86)
    print("  Cạnh quan hệ           : %d" % len(canh))
    print("     nối 2 văn bản TRONG bộ (liên kết ngầm): %d" % tr)
    print("     trỏ ra văn bản ngoài bộ               : %d" % (len(canh) - tr))
    dq = Counter(c["quan_he"] for c in canh)
    for qh, m in dq.most_common():
        print("     %-14s %5d  (trong bộ %d)"
              % (qh, m, sum(1 for c in canh if c["quan_he"] == qh and c["trong_bo"])))
    print("  Điều (Article)         : %s trong %d văn bản"
          % ("{:,}".format(sum(len(v["dieu"]) for v in vb.values())),
             sum(1 for v in vb.values() if v["dieu"])))
    print("  NormativeContent       : %d văn bản ban hành kèm Quy định/Quy chế"
          % sum(1 for v in vb.values() if v["noi_dung"]))
    print("  Căn cứ ngoài được viện dẫn nhiều nhất:")
    for x in do_thi["can_cu_ngoai"][:8]:
        print("     %3d lần  %s" % (x["so_lan"], x["so"]))
    print("=" * 86)
    print("Đã ghi: %s" % p)


if __name__ == "__main__":
    main()
