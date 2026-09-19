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
DIEU = re.compile(r"^[ \t]*Điều\s+(\d{1,3}[a-zA-Z]?)\s*(?:[.．:]|\s+(?=[A-ZĐÀ-Ỹ]))", re.M)
# Vien dan: sau "Điều N" la ten mot van ban KHAC chu khong phai tieu de cua Dieu.
#     "Điều 5 của Luật này"        -> tu noi o dau
#     "Điều 7 Nghị định này;"      -> TEN LOAI van ban roi "này" — kieu nay tung lot
#     "Điều 12 Thông tư số 10/2020"
# Lot mot cai la day so Dieu khong con tang deu, keo theo chot an toan chan oan
# ca file (0134, 0139 tung bi chan nham vi dung mot chu "Điều 7 Nghị định này").
_LOAI_VB_VD = (r"Nghị\s*định|Thông\s*tư|Quyết\s*định|Luật|Bộ\s*luật|Quy\s*chế|"
               r"Quy\s*định|Điều\s*lệ|Pháp\s*lệnh|Nghị\s*quyết|Chỉ\s*thị|Hiến\s*pháp")
VIEN_DAN = re.compile(
    r"^\s*(?:của|tại|và|;|,)"
    r"|^\s*[Ll]uật này|^\s*này\b"
    r"|^\s*(?:%s)\s+(?:này|số|\d)" % _LOAI_VB_VD)
MOC_TRANG = re.compile(
    r"^[ 	]*(?:-{3,}[ 	]*)?\[Trang[^\]]*\][ 	]*(?:-{3,}[ 	]*)?$", re.M)
THI_HANH = re.compile(r"hiệu lực thi hành|chịu trách nhiệm thi hành|có hiệu lực kể từ", re.I)


def _cat_dieu(txt: str):
    """-> (dict {'Điều 5': {...}}, day so THO theo thu tu xuat hien).

    Phai tra ve ca day THO: dict da khu trung lap nen nhin vao no thi van ban
    long nhau (Dieu 1-3 roi lai Dieu 1-24) trong nhu tang deu.
    """
    moc = [m for m in DIEU.finditer(txt)
           if not VIEN_DAN.match(txt[m.end():m.end() + 24])]
    tho: list[int] = []
    ra: dict[str, dict] = {}
    for i, m in enumerate(moc):
        het = moc[i + 1].start() if i + 1 < len(moc) else len(txt)
        than = txt[m.start():het]
        than = MOC_TRANG.sub("", than)                  # moc trang khong phai noi dung
        than = re.sub(r"\n{3,}", "\n\n", than).strip()
        # tieu de = phan con lai cua dong dau, sau "Điều N."
        dong1 = than.split("\n", 1)[0]
        tieu = re.sub(r"^\s*Điều\s+\d{1,3}[a-zA-Z]?\s*[.．:]?\s*", "", dong1).strip()
        ten = "Điều %s" % m.group(1)
        tho.append(int(re.match(r"\d+", m.group(1)).group()))
        if ten in ra:                                   # phu luc danh so lai tu dau
            continue
        ra[ten] = {"tieu_de": tieu[:200] or None, "than": than}
    return ra, tho


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
