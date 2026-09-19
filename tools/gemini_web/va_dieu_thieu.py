# -*- coding: utf-8 -*-
"""Va cac Dieu bi Gemini bo sot, bang cach CAT THANG tu file .txt goc.

    python tools/gemini_web/va_dieu_thieu.py           # chi xem
    python tools/gemini_web/va_dieu_thieu.py --ghi     # ghi that, co sao luu

Vi sao lam duoc ma khong can doan:

  Ranh gioi mot Dieu trong van ban phap quy la xac dinh: tu dong `Điều N.` cho
  toi dong `Điều N+1.` ke tiep. Cat ra rồi chep NGUYEN VAN vao `articles[].text`
  — khong tom tat, khong dien giai, khong them mot chu nao.

Chi va nhung Dieu MA JSON KHONG CO. Dieu nao Gemini da lay thi giu nguyen cua
no, vi no con kem `heading` va `isImplementationClause` ma cat may khong suy ra
duoc chac chan.

Khong dung cho van ban ma ban than file .txt da hong (OCR tron cot) — luc do cat
ra cung la rac. Nhung truong hop do se bi danh dau de doc tay.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
KHO_TXT = GOC / "data" / "clean" / "text_final"
RA = GOC / "data" / "kg_json"

# Tieu de Dieu THAT (khong phai vien dan bi ngat dong) — cung luat voi cau_json.py
# Bon dang tieu de gap trong corpus (dem duoc: 10.564 / 111 / 44 / 9 cho):
#   "Điều 1. Ban hành kèm theo..."   - pho bien
#   "Điều 2"                         - tran, het dong (Hien phap 2013, 0130...)
#   "Điều 3 1"                       - tran + so trang OCR dinh vao
#   "Điều 8: ..." / "Điều 56, ..."   - dau bi doc nham
DIEU = re.compile(
    r"^[ \t]*Điều\s+(\d{1,3}[a-zA-Z]?)"
    # Nhom 2 giu lai DAU NGAN. Vien dan thi khong co dau ("Điều 7 Nghị định
    # này"), tieu de that thi co ("Điều 2. Quyết định này có hiệu lực...").
    # Thieu cho nay thi bo loc vien dan an luon tieu de Dieu 2 va Dieu 3 cua
    # gan nhu moi Quyet dinh — ba luot doc tay doc lap deu bao.
    r"(?:[ \t]*([.．:,;])|[ \t]*\d{0,3}[ \t]*$|[ \t]+(?=[A-ZĐÀ-Ỹ]))", re.M)
# Vien dan: sau "Điều N" la ten mot van ban KHAC chu khong phai tieu de cua Dieu.
#     "Điều 5 của Luật này"        -> tu noi o dau
#     "Điều 7 Nghị định này;"      -> TEN LOAI van ban roi "này" — kieu nay tung lot
#     "Điều 12 Thông tư số 10/2020"
# Lot mot cai la day so Dieu khong con tang deu, keo theo chot an toan chan oan
# ca file (0134, 0139 tung bi chan nham vi dung mot chu "Điều 7 Nghị định này").
_LOAI_VB_VD = (r"Nghị\s*định|Thông\s*tư|Quyết\s*định|Luật|Bộ\s*luật|Quy\s*chế|"
               r"Quy\s*định|Điều\s*lệ|Pháp\s*lệnh|Nghị\s*quyết|Chỉ\s*thị|Hiến\s*pháp")
VIEN_DAN = re.compile(
    # "Điều 32 đến Điều 42, các điều 44, 45..." — vien dan khoang. Sot mot chu
    # "đến" nay tung lam 0280 mat 170/173 Dieu: day so gay dung mot cho, chot
    # an toan chan ca file.
    r"^\s*(?:của|tại|và|đến|các|khoản|điểm|;|,)"
    r"|^\s*[Ll]uật này|^\s*này\b"
    # "Điều 24, Điều 25, Điều 26 Quy chế..." — liet ke vien dan, khong phai tieu
    # de. Phan biet duoc vi sau "Điều"/"Khoản"/"Điểm" la mot CON SO; tieu de
    # that thi la chu ("Điều 38. Điều khoản thi hành").
    r"|^\s*(?:Điều|Khoản|Điểm|Chương|Mục)\s+\d"
    # "Điều 10, 11, 12, 13, 14 và 15 Nghị định này" — sau dau ngan la CHU SO
    # thi chac chan la liet ke vien dan, tieu de that khong bao gio bat dau
    # bang so. Thieu luat nay thi 0134 tut tu 41 xuong 16 Dieu.
    r"|^[ \t]*\d{1,3}[ \t]*(?:[,;]|và\b|hoặc\b)"
    r"|^\s*(?:%s)\s+(?:này|số|\d)" % _LOAI_VB_VD)
MOC_TRANG = re.compile(
    r"^[ 	]*(?:-{3,}[ 	]*)?\[Trang[^\]]*\][ 	]*(?:-{3,}[ 	]*)?$", re.M)
THI_HANH = re.compile(r"hiệu lực thi hành|chịu trách nhiệm thi hành|có hiệu lực kể từ", re.I)


_TU_CHUONG = r"(?:Chương|CHƯƠNG|Mục|MỤC|Tiểu mục|TIỂU MỤC|Phần|PHẦN)"
# Dong tieu de chuong/muc. Ba dang gap trong corpus:
#   "Chương III"                         - sach
#   "Chương II - TỔ CHỨC VÀ QUẢN LÝ"     - gach noi, tieu de cung dong (0054)
#   "Chương III Ẽ ;" / "Chương IV 1"     - OCR ban hoac dinh so trang (0137)
# Bo chi bat dang sach thi 0054 bi nuot 14 tieu de, 0137 nuot 2.
MOC_CHUONG = re.compile(
    r"^[ \t]*" + _TU_CHUONG + r"[ \t]+(?:[IVXLCDM]+|[0-9]{1,2})"
    r"(?:[ \t]*$|[ \t]*[-–—][ \t]*[A-ZĐÀ-Ỹ]|[ \t]+[^\n]{0,6}$)",
    re.M)


def _bo_duoi_chuong(than: str) -> str:
    """Bo tieu de Chuong/Muc cua chuong KE TIEP dinh o cuoi than Dieu.

    Dieu cuoi cua mot chuong chay den tan tieu de chuong sau, vi moc cat la
    "Điều" ke tiep chu khong phai "Chương". The la than Dieu 6 cua 0013 co
    duoi "Chương III / HỆ THỐNG TỔ CHỨC, QUẢN LÝ" — tieu de cua chuong sau,
    khong phai noi dung Dieu 6. Do tren corpus: 1.420 Dieu o 234 file.

    Phai cat tu moc SOM NHAT con hop le, khong phai moc cuoi: 0087 Dieu 12
    co duoi bon dong long nhau "Chương III / HỢP ĐỒNG LAO ĐỘNG / Mục 1 /
    GIAO KẾT HỢP ĐỒNG LAO ĐỘNG"; cat tu moc cuoi thi con lai hai dong dau.

    Hop le = tu do den het toi da 4 dong, moi dong duoi 100 ky tu, cac dong
    khong phai moc thi chu yeu la CHU HOA. Con van xuoi thi giu nguyen —
    tha thua con hon cat nham.
    """
    for m in MOC_CHUONG.finditer(than):
        dong = [x.strip() for x in than[m.start():].strip().splitlines() if x.strip()]
        if len(dong) > 4 or any(len(x) > 100 for x in dong):
            continue
        if all(MOC_CHUONG.match(x) or _phan_lon_hoa(x) for x in dong[1:]):
            return than[:m.start()].rstrip()
    return than


def _phan_lon_hoa(dong: str) -> bool:
    chu = [c for c in dong if c.isalpha()]
    return bool(chu) and sum(1 for c in chu if c.isupper()) >= 0.8 * len(chu)

_CHUC_KY = (r"(?:KT\.[ \t]*)?(?:TM\.[ \t]*)?"
            r"(?:HIỆU TRƯỞNG|PHÓ HIỆU TRƯỞNG|GIÁM ĐỐC|PHÓ GIÁM ĐỐC|BỘ TRƯỞNG"
            r"|THỨ TRƯỞNG|THỦ TƯỚNG|PHÓ THỦ TƯỚNG|CHÁNH VĂN PHÒNG|CHỦ NHIỆM"
            r"|CỤC TRƯỞNG|VỤ TRƯỞNG|TỔNG GIÁM ĐỐC|CHÁNH THANH TRA|VIỆN TRƯỞNG"
            r"|TỔNG CỤC TRƯỞNG|TRƯỞNG BAN|THỦ TRƯỞNG ĐƠN VỊ"
            r"|CHỦ TỊCH[^\n]{0,44})")

# Tu moc nay tro di la phan HANH CHINH o cuoi van ban, khong con la noi dung
# Dieu nua.
DUOI_HANH_CHINH = re.compile(
    r"^[ \t]*(?:"
    r"Nơi nhận[ \t]*:"
    r"|" + _CHUC_KY + r"[ \t]*$"
    r"|\([ \t]*(?:Đã ký|Ký tên)[^\n]*$"
    r"|CỘNG[ \t]*HÒA[ \t]*XÃ[ \t]*HỘI"
    r"|(?i:PHỤ[ \t]*LỤC)[ \t]*[IVXLCDM0-9]{0,4}[ \t]*$"
    r"|(?i:MẪU[ \t]*SỐ|BIỂU[ \t]*MẪU|PHIẾU[ \t]*(?:GIẢI QUYẾT|CHUYỂN))"
    r")", re.M)


def _bo_duoi_hanh_chinh(than: str) -> str:
    """Cat tu moc hanh chinh dau tien den het than Dieu.

    Moc cat Dieu la "Điều" ke tiep, nen Dieu CUOI chay den het file: nuot
    "Nơi nhận", chu ky, roi ca phu luc va ca phieu xu ly van ban di kem ban
    scan. Do that: 0069 Dieu 3 dai 82.372 ky tu trong khi than that ~170;
    0201 Dieu 3 dai 125.235 thay vi ~151. Dieu 3 cua moi Quyet dinh cung dinh
    "Nơi nhận" + chu ky + khoi tieu de cua ban Quy dinh kem theo.

    Ba luot doc tay doc lap bao loi nay tren 33/33 file ho kiem.
    """
    m = DUOI_HANH_CHINH.search(than)
    if not m or m.start() == 0:
        return than
    return than[:m.start()].rstrip()

def _la_tieu_de(txt: str, m) -> bool:
    """Moc nay la tieu de Dieu that, hay chi la vien dan giua van?

    Dau cham hoac hai cham ngay sau so Dieu thi chac chan la tieu de. Vien
    dan khong viet the: "Điều 7 Nghị định này", "Điều 5 của Luật này". Nho
    vay "Điều 2. Quyết định này có hiệu lực..." khong con bi luat
    "<loai van ban> này" cua VIEN_DAN an mat.

    Dau phay va cham phay thi VAN mo ho ("Điều 10, 11, 12 và 15 Nghị định
    này" la liet ke vien dan, con "Điều 56, Quyền và nghĩa vụ..." la tieu de
    bi OCR doc nham dau), nen van phai hoi VIEN_DAN.
    """
    if m.group(2) in (".", "．", ":"):
        return True
    return not VIEN_DAN.match(txt[m.end():m.end() + 24])

def _cat_dieu(txt: str, gioi_han: int | None = None):
    """-> (dict {'Điều 5': {...}}, day so THO theo thu tu xuat hien).

    Phai tra ve ca day THO: dict da khu trung lap nen nhin vao no thi van ban
    long nhau (Dieu 1-3 roi lai Dieu 1-24) trong nhu tang deu.
    """
    moc = [m for m in DIEU.finditer(txt) if _la_tieu_de(txt, m)]
    if gioi_han is not None:
        moc = moc[:gioi_han]
    tho: list[int] = []
    ra: dict[str, dict] = {}
    for i, m in enumerate(moc):
        het = moc[i + 1].start() if i + 1 < len(moc) else len(txt)
        than = txt[m.start():het]
        than = MOC_TRANG.sub("", than)                  # moc trang khong phai noi dung
        than = re.sub(r"\n{3,}", "\n\n", than).strip()
        than = _bo_duoi_chuong(than)
        than = _bo_duoi_hanh_chinh(than)
        # tieu de = phan con lai cua dong dau, sau "Điều N."
        dong1 = than.split("\n", 1)[0]
        tieu = re.sub(r"^\s*Điều\s+\d{1,3}[a-zA-Z]?\s*[.．:,;]?\s*", "", dong1).strip()
        ten = "Điều %s" % m.group(1)
        tho.append(int(re.match(r"\d+", m.group(1)).group()))
        if ten in ra:                                   # phu luc danh so lai tu dau
            continue
        ra[ten] = {"tieu_de": tieu[:200] or None, "than": than}
    return ra, tho


_CHO_TRONG = re.compile(r"[.．…]{3,}|_{3,}")


def _tach_mach(txt: str):
    """Tach van ban thanh cac MACH Dieu danh so lien tiep. -> list[(dict, [so])].

    Mot van ban .txt thuong chua nhieu hon mot mach: Quyet dinh (Dieu 1-3) roi
    Quy dinh ban hanh kem theo (Dieu 1-N) roi mot loat bieu mau phu luc, moi
    cai lai bat dau tu "Điều 1.". Truoc day chot an toan thay day so khong tang
    deu la bo ca file — do tren corpus la 176 file bi chan.

    Cach doc day so o day:
      - so dung bang ky vong, hoac vuot khong qua 2  -> nhan (chua 1-2 tieu de
        OCR lam mat, van la mot mach)
      - so ve 1                                      -> mach moi bat dau
      - con lai                                      -> bo qua, gan nhu chac
        chan la vien dan lot luoi (0090 co "1 2 19 22 3", 0255 co "1 26 2 3")

    Nho vay mot vien dan lot khong con pha ca file nua, va van ban long nhau
    thi moi mach ve dung cho cua no.
    """
    moc = [m for m in DIEU.finditer(txt) if _la_tieu_de(txt, m)]
    mach, hien, ky_vong = [], [], 1
    for idx, m in enumerate(moc):
        n = int(re.match(r"\d+", m.group(1)).group())
        if ky_vong <= n <= ky_vong + 2:
            hien.append(idx)
            ky_vong = n + 1
        elif n == 1 and hien:
            mach.append(hien)
            hien, ky_vong = [idx], 2
    if hien:
        mach.append(hien)

    ra = []
    for nhom in mach:
        d, so = {}, []
        for vt, idx in enumerate(nhom):
            m = moc[idx]
            ke = nhom[vt + 1] if vt + 1 < len(nhom) else None
            het = moc[ke].start() if ke is not None else (
                moc[idx + 1].start() if idx + 1 < len(moc) else len(txt))
            than = MOC_TRANG.sub("", txt[m.start():het])
            than = re.sub(r"\n{3,}", "\n\n", than).strip()
            than = _bo_duoi_chuong(than)
            than = _bo_duoi_hanh_chinh(than)
            dong1 = than.split("\n", 1)[0]
            tieu = re.sub(r"^\s*Điều\s+\d{1,3}[a-zA-Z]?\s*[.．:,;]?\s*", "", dong1).strip()
            ten = "Điều %s" % m.group(1)
            so.append(int(re.match(r"\d+", m.group(1)).group()))
            if ten not in d:
                d[ten] = {"tieu_de": tieu[:200] or None, "than": than}
        ra.append((d, so))
    return ra


def _do_phu(txt: str):
    """-> (so moc, so Dieu duy nhat, so lon nhat). Dung de biet van ban co du
    Dieu khong, khong quan tam thu tu."""
    moc = [m for m in DIEU.finditer(txt) if _la_tieu_de(txt, m)]
    so = [int(re.match(r"\d+", m.group(1)).group()) for m in moc]
    return (len(so), len(set(so)), max(so)) if so else (0, 0, 0)


def _du_bo(txt: str) -> bool:
    """Van ban co du Dieu 1..N, chi lech thu tu o vai cho.

    Ban scan hai cot doi khi dao cot o mot vai trang: 0245 (Bo luat Hinh su)
    chay 332 -> 339 -> ... -> 333 -> ... -> 338 -> 344. Doc theo mach thi mat
    87 Dieu, nhung tap so Dieu van du 1..426 va khong trung — nghia la khong
    Dieu nao thieu, chi la thu tu trong file khac thu tu danh so. Than moi
    Dieu van lien mach trong file nen cat van dung.

    Khac han 0196, bi tron cot nang: 42 moc cho 96 Dieu, phu 44%. Cho nay
    doi phu >= 95% nen 0196 khong lot.
    """
    # "Điều 1" xuat hien hai lan nghia la file chua HAI van ban, khong phai
    # mot van ban lech thu tu. 0196 la mot so Cong bao in ca Luat sua doi
    # (Dieu 1-2) lan Luat Thi dua khen thuong hop nhat (Dieu 1-103): day so
    # van phu 100% nen hai dieu kien kia deu qua, nhung go het vao mot ro thi
    # 103 Dieu cua luat NAY lai gan cho luat KIA.
    moc = [m for m in DIEU.finditer(txt) if _la_tieu_de(txt, m)]
    if sum(1 for m in moc if int(re.match(r"\d+", m.group(1)).group()) == 1) > 1:
        return False
    n, duy, lon = _do_phu(txt)
    # n ~ duy: gan nhu khong co so nao xuat hien hai lan. Thieu dieu kien nay
    # thi 0133 (89 moc cho 67 Dieu, phan thua la bieu mau danh so lai) cung lot
    # vao day, va _cat_tat_ca se lay nham than bieu mau de len Dieu that.
    return lon >= 20 and duy >= 0.95 * lon and n <= 1.02 * duy


def _cat_tat_ca(txt: str):
    """Cat moi moc theo dung thu tu xuat hien trong file. -> dict.

    Chi dung cho van ban da qua _du_bo. Moc trung so thi giu ban DAI hon, vi
    ban ngan gan nhu chac chan la vien dan lot luoi.
    """
    moc = [m for m in DIEU.finditer(txt) if _la_tieu_de(txt, m)]
    ra = {}
    for i, m in enumerate(moc):
        het = moc[i + 1].start() if i + 1 < len(moc) else len(txt)
        than = MOC_TRANG.sub("", txt[m.start():het])
        than = re.sub(r"\n{3,}", "\n\n", than).strip()
        than = _bo_duoi_chuong(than)
        than = _bo_duoi_hanh_chinh(than)
        dong1 = than.split("\n", 1)[0]
        tieu = re.sub(r"^\s*Điều\s+\d{1,3}[a-zA-Z]?\s*[.．:,;]?\s*", "", dong1).strip()
        ten = "Điều %s" % m.group(1)
        if ten in ra and len(ra[ten]["than"]) >= len(than):
            continue
        ra[ten] = {"tieu_de": tieu[:200] or None, "than": than}
    return ra

# Dau hieu bieu mau: cho dien ten/chu ky, huong dan dien.
_DAU_BIEU_MAU = re.compile(
    r"Bên A|Bên B|\(ghi rõ|\(Ký tên|Ký, ghi rõ|đóng dấu\)"
    r"|Mẫu số|MẪU SỐ|\.\.\.\.", re.I)


def _la_bieu_mau(cat) -> bool:
    """Mach nay la bieu mau phu luc chu khong phai van ban quy pham.

    Do HAI tin hieu tren 1000 ky tu: mat do CHO TRONG ("....."/"____") va mat
    do DAU HIEU BIEU MAU ("Bên A", "(ghi rõ", "(Ký tên", "đóng dấu)").
    Do lai tren 16 mach da dan nhan tay, sau khi than Dieu da duoc cat duoi:

        ban kem THAT   cho trong 0.00-0.19   dau hieu 0.00-0.07
        bieu mau       cho trong 1.59-14.85  dau hieu 7.37-235.70

    Phai do CA HAI. Ban truoc chi do cho trong voi nguong 3.2, va sau khi
    _bo_duoi_hanh_chinh cat bot phan dien cho trong o duoi thi mau hop dong
    cua 0380 tut tu 3.38 xuong 1.59 — lot luoi, 8 Dieu mau hop dong chui vao
    normativeContents. Dau hieu van con 7.37 nen bat duoc.
    """
    than = "\n".join(v["than"] for v in cat.values())
    if len(than) < 1000:
        return True
    trong = 1000.0 * len(_CHO_TRONG.findall(than)) / len(than)
    dau = 1000.0 * len(_DAU_BIEU_MAU.findall(than)) / len(than)
    # Mach tu 10 Dieu tro len thi gan nhu chac chan la van ban that, noi tay.
    if len(cat) >= 10:
        return trong >= 4.0 or dau >= 8.0
    return trong >= 1.0 or dau >= 2.0

# Tieu de ban ban hanh kem theo, dung MOT MINH tren dong va in HOA.
TIEU_DE_ND = re.compile(
    r"^[ \t]*(QUY\s*CHẾ|QUY\s*ĐỊNH|ĐIỀU\s*LỆ|QUY\s*TRÌNH|NỘI\s*QUY|ĐỀ\s*ÁN|"
    r"CHƯƠNG\s*TRÌNH)[ \t]*$", re.M)
_LOAI_ND = {"QUY CHẾ": "Quy chế", "QUY ĐỊNH": "Quy định", "ĐIỀU LỆ": "Điều lệ",
            "QUY TRÌNH": "Quy trình", "NỘI QUY": "Nội quy", "ĐỀ ÁN": "Đề án",
            "CHƯƠNG TRÌNH": "Chương trình"}


def _tach_ban_kem(txt: str):
    """Tach phan ban hanh kem theo. -> (dict Dieu, day tho, ten, loai) hoac (None,...).

    Lay tieu de in hoa CUOI CUNG — van ban long ba lop (0013) co ca Quyet dinh
    goc chep lai o giua, cat o moc dau tien la van con lan.
    """
    ms = list(TIEU_DE_ND.finditer(txt))
    if not ms:
        return None, None, None, None
    m = ms[-1]
    than = txt[m.end():]
    goc, tho = _cat_dieu(than)
    if len(goc) < 5 or tho != sorted(tho) or len(set(tho)) != len(tho):
        return None, None, None, None
    # ten = may dong ngay sau tieu de, truoc "Chương" hoac "Điều 1"
    sau = than[:400].strip().split("\n")
    ten = " ".join(x.strip() for x in sau[:3]
                   if x.strip() and not re.match(r"^(Chương|Điều)\b", x.strip()))
    khoa = re.sub(r"\s+", " ", m.group(1).upper())
    return goc, tho, (ten[:200] or khoa.title()), _LOAI_ND.get(khoa, "Quy định")


def _ghi_nd(js, d, goc, thieu, ten, loai):
    them = [{
        "number": k,
        "heading": goc[k]["tieu_de"],
        "text": goc[k]["than"],
        "isImplementationClause": bool(THI_HANH.search(goc[k]["than"])),
    } for k in thieu]
    nd = (d.get("normativeContents") or [])
    if nd:
        nd[0]["articles"] = sorted(
            (nd[0].get("articles") or []) + them,
            key=lambda x: int(re.match(r"\d+", x["number"].replace("Điều", "").strip()).group()))
    else:
        nd = [{"title": ten, "contentType": loai, "status": None,
               "idOverride": None, "articles": them}]
    d["normativeContents"] = nd
    cu = (d.get("note") or "").strip()
    d["note"] = (cu + " " if cu else "") + (
        "%d Điều của bản kèm theo được cắt thẳng từ bản .txt gốc." % len(them))
    shutil.copy2(js, str(js) + ".truoc_khi_va")
    io.open(js, "w", encoding="utf-8", newline="\n").write(
        json.dumps(d, ensure_ascii=False, indent=2) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ghi", action="store_true")
    ap.add_argument("--chi", default="", help="chi va nhung ma nay")
    a = ap.parse_args()
    chi = {x.strip() for x in a.chi.split(",") if x.strip()} or None

    tong_va = 0
    doc_tay = []
    for js in sorted(RA.rglob("*.json")):
        ma = js.name[:4]
        if chi and ma not in chi:
            continue
        tx = next((p for p in KHO_TXT.rglob("*.txt") if p.name.startswith(ma)), None)
        if not tx:
            continue

        d = json.load(io.open(js, encoding="utf-8"))
        co = {a_["number"] for a_ in (d.get("articles") or [])}
        for n in d.get("normativeContents") or []:
            co |= {a_["number"] for a_ in (n.get("articles") or [])}

        goc, tho = _cat_dieu(io.open(tx, encoding="utf-8", errors="replace").read())
        thieu = [k for k in goc if k not in co]
        if not thieu or len(goc) < 5:
            continue

        # Van ban LONG NHAU van va duoc, mien la tach dung ranh gioi truoc.
        # Hinh dang: Quyet dinh (Dieu 1-3) ... "QUY CHẾ" ... Dieu 1-24 cua Quy che.
        # Cac Dieu SAU tieu de in hoa do thuoc `normativeContents`, khong phai
        # `articles` cua Quyet dinh. Tach xong thi moi ben lai tang deu.
        if tho != sorted(tho):
            goc2, tho2, ten_nd, loai_nd = _tach_ban_kem(
                io.open(tx, encoding="utf-8", errors="replace").read())
            if goc2 is not None:
                co_nd = set()
                for n in d.get("normativeContents") or []:
                    co_nd |= {a_["number"] for a_ in (n.get("articles") or [])}
                thieu_nd = [k for k in goc2 if k not in co_nd]
                if thieu_nd:
                    print("%s  bản kèm theo %r: vá %d/%d Điều vào normativeContents"
                          % (ma, ten_nd[:40], len(thieu_nd), len(goc2)))
                    tong_va += len(thieu_nd)
                    if a.ghi:
                        _ghi_nd(js, d, goc2, thieu_nd, ten_nd, loai_nd)
                    continue

        # CHOT AN TOAN: chi va khi so Dieu TANG DEU tu dau den cuoi file.
        #
        # Khong tang deu co dung hai nguyen nhan, ca hai deu cam va tu dong:
        #   - OCR tron cot  -> "Điều 4" roi "Điều 3" (0196). Cat ra la rac.
        #   - Van ban long nhau -> Quyet dinh (Dieu 1-3) + Phu luc co Quyet dinh
        #     khac (Dieu 1-3) + Quy che (Dieu 1..24) — so quay ve 1 giua chung
        #     (0013). Va thang vao `articles` la tron ba van ban lam mot.
        if tho != sorted(tho) or len(set(tho)) != len(tho):
            doc_tay.append((ma, len(thieu), "số Điều không tăng đều — trộn cột hoặc văn bản lồng nhau"))
            continue

        # Cat ra ma qua ngan thi ban .txt cho do cung hong.
        xau = sum(1 for k in thieu if len(goc[k]["than"]) < 60)
        if xau > len(thieu) * 0.3:
            doc_tay.append((ma, len(thieu), "%d chỗ cắt ra dưới 60 ký tự" % xau))
            continue

        print("%s  thiếu %d/%d Điều  ->  vá: %s%s"
              % (ma, len(thieu), len(goc), ", ".join(thieu[:6]),
                 " …" if len(thieu) > 6 else ""))
        tong_va += len(thieu)

        if a.ghi:
            them = [{
                "number": k,
                "heading": goc[k]["tieu_de"],
                "text": goc[k]["than"],
                "isImplementationClause": bool(THI_HANH.search(goc[k]["than"])),
            } for k in thieu]
            d["articles"] = sorted(
                (d.get("articles") or []) + them,
                key=lambda x: int(re.match(r"\d+", x["number"].replace("Điều", "").strip()).group()))
            cu = (d.get("note") or "").strip()
            d["note"] = (cu + " " if cu else "") + (
                "%d Điều được cắt thẳng từ bản .txt gốc do lượt trích xuất bỏ sót."
                % len(them))
            shutil.copy2(js, str(js) + ".truoc_khi_va")
            io.open(js, "w", encoding="utf-8", newline="\n").write(
                json.dumps(d, ensure_ascii=False, indent=2) + "\n")

    if doc_tay:
        print("\nPHẢI ĐỌC TAY (bản .txt gốc hỏng, cắt máy ra rác):")
        for ma, n, ly in doc_tay:
            print("   %s  thiếu %d Điều — %s" % (ma, n, ly))

    print("\n%d Điều %s" % (tong_va, "ĐÃ VÁ (sao lưu .truoc_khi_va)" if a.ghi
                            else "sẽ vá — thêm --ghi để ghi thật"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
