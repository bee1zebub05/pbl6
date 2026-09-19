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
    r"(?:[ \t]*[.．:,;]|[ \t]*\d{0,3}[ \t]*$|[ \t]+(?=[A-ZĐÀ-Ỹ]))", re.M)
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
    r"^\s*(?:của|tại|và|đến|;|,)"
    r"|^\s*[Ll]uật này|^\s*này\b"
    # "Điều 24, Điều 25, Điều 26 Quy chế..." — liet ke vien dan, khong phai tieu
    # de. Phan biet duoc vi sau "Điều"/"Khoản"/"Điểm" la mot CON SO; tieu de
    # that thi la chu ("Điều 38. Điều khoản thi hành").
    r"|^\s*(?:Điều|Khoản|Điểm|Chương|Mục)\s+\d"
    # "Điều 10, 11, 12, 13, 14 và 15 Nghị định này" — sau dau ngan la CHU SO
    # thi chac chan la liet ke vien dan, tieu de that khong bao gio bat dau
    # bang so. Thieu luat nay thi 0134 tut tu 41 xuong 16 Dieu.
    r"|^[ \t]*\d"
    r"|^\s*(?:%s)\s+(?:này|số|\d)" % _LOAI_VB_VD)
MOC_TRANG = re.compile(
    r"^[ 	]*(?:-{3,}[ 	]*)?\[Trang[^\]]*\][ 	]*(?:-{3,}[ 	]*)?$", re.M)
THI_HANH = re.compile(r"hiệu lực thi hành|chịu trách nhiệm thi hành|có hiệu lực kể từ", re.I)


def _cat_dieu(txt: str, gioi_han: int | None = None):
    """-> (dict {'Điều 5': {...}}, day so THO theo thu tu xuat hien).

    Phai tra ve ca day THO: dict da khu trung lap nen nhin vao no thi van ban
    long nhau (Dieu 1-3 roi lai Dieu 1-24) trong nhu tang deu.
    """
    moc = [m for m in DIEU.finditer(txt)
           if not VIEN_DAN.match(txt[m.end():m.end() + 24])]
    if gioi_han is not None:
        moc = moc[:gioi_han]
    tho: list[int] = []
    ra: dict[str, dict] = {}
    for i, m in enumerate(moc):
        het = moc[i + 1].start() if i + 1 < len(moc) else len(txt)
        than = txt[m.start():het]
        than = MOC_TRANG.sub("", than)                  # moc trang khong phai noi dung
        than = re.sub(r"\n{3,}", "\n\n", than).strip()
        # tieu de = phan con lai cua dong dau, sau "Điều N."
        dong1 = than.split("\n", 1)[0]
        tieu = re.sub(r"^\s*Điều\s+\d{1,3}[a-zA-Z]?\s*[.．:,;]?\s*", "", dong1).strip()
        ten = "Điều %s" % m.group(1)
        tho.append(int(re.match(r"\d+", m.group(1)).group()))
        if ten in ra:                                   # phu luc danh so lai tu dau
            continue
        ra[ten] = {"tieu_de": tieu[:200] or None, "than": than}
    return ra, tho


_CHAM = re.compile(r"[.．…]{4,}")


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
    moc = [m for m in DIEU.finditer(txt)
           if not VIEN_DAN.match(txt[m.end():m.end() + 24])]
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
            dong1 = than.split("\n", 1)[0]
            tieu = re.sub(r"^\s*Điều\s+\d{1,3}[a-zA-Z]?\s*[.．:,;]?\s*", "", dong1).strip()
            ten = "Điều %s" % m.group(1)
            so.append(int(re.match(r"\d+", m.group(1)).group()))
            if ten not in d:
                d[ten] = {"tieu_de": tieu[:200] or None, "than": than}
        ra.append((d, so))
    return ra


def _la_bieu_mau(cat) -> bool:
    """Mach nay la bieu mau phu luc chu khong phai van ban quy pham.

    Bieu mau viet kieu "Điều 1. Phê duyệt liên kết ......(6)......" — cho trong
    de dien, nen dac dau cham va rat ngan. Dua vao normativeContents thi do thi
    co them node rac mang so hieu Dieu that.
    """
    than = "\n".join(v["than"] for v in cat.values())
    if not than:
        return True
    cham = sum(len(x) for x in _CHAM.findall(than))
    return len(than) < 1000 or cham > len(than) * 0.03


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
