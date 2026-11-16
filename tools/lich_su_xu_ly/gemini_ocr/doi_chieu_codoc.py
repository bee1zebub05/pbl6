# -*- coding: utf-8 -*-
"""Doi chieu ban OCR LAI cua 57 van ban co doc voi ban dang dung trong text_clean_gemma.

Muc dich cua dot OCR lai: 31/58 van ban co doc THUC SU co vien dan, nhung OCR cu lam
hong dau ("Hién phap", "Luat To chuc chinh quyen") nen mau trich xuat truot het. OCR lai
bang Gemma de lay ban co dau dung -> trich duoc quan he -> het co doc.

Script nay cham diem tung file theo BA tieu chi roi moi ket luan nen thay hay giu:
  1. so QUAN HE trich duoc  (muc tieu chinh cua ca dot)
  2. ty le ky tu co dau     (duoi 12% la ban hong, khong duoc phep thay)
  3. so CHU CAI             (mat noi dung thi khong duoc phep thay, du co them quan he)

    python doi_chieu_codoc.py             # bang doi chieu
    python doi_chieu_codoc.py --apply     # thay nhung file DAT ca ba tieu chi
"""
import argparse
import io
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trich_do_thi import CAN_CU, CAN_CU_TEN, THAY_THE, don_ten_luat   # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
SACH = GOC / "data" / "processed" / "text_clean_gemma"
MOI = GOC / "data" / "processed" / "text_gemma_codoc"
LUU = GOC / "data" / "_ban_luu_truoc_khi_sua"

DAU = ("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ"
       "ùúủũụưừứửữựỳýỷỹỵđ")
DAU += DAU.upper()

NGUONG_DAU = 12.0        # duoi muc nay la ban hong / font cu
NGUONG_CHU = 0.85        # ban moi phai giu it nhat 85% chu cai cua ban cu


def ty_le_dau(t):
    return 100.0 * sum(1 for c in t if c in DAU) / max(1, len(t))


def so_chu(t):
    return sum(1 for c in t if c.isalpha())


def dem_quan_he(t):
    """So quan he CAN_CU / THAY_THE trich duoc tu van ban. Dung DUNG bo mau cua
    trich_do_thi.py de con so o day khop voi con so trong do thi that."""
    n = len({m.group(2) for m in CAN_CU.finditer(t)})
    n += len({m.group(2) for m in THAY_THE.finditer(t)})
    ten = set()
    for m in CAN_CU_TEN.finditer(t):
        x = don_ten_luat(m.group(1), t[m.end():m.end() + 220])
        if x:
            ten.add(x)
    return n + len(ten)


def tim_cu(doc):
    return next((p for p in SACH.rglob(doc + "_*.txt")), None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    if not MOI.exists():
        print("Chưa có %s" % MOI)
        return

    hang = []
    for fm in sorted(MOI.rglob("*.txt")):
        doc = fm.name[:4]
        fc = tim_cu(doc)
        if not fc:
            continue
        tm = io.open(fm, encoding="utf-8", errors="replace").read()
        tc = io.open(fc, encoding="utf-8", errors="replace").read()
        qc, qm = dem_quan_he(tc), dem_quan_he(tm)
        dm = ty_le_dau(tm)
        tyle = so_chu(tm) / max(1, so_chu(tc))
        thieu = "[[KHÔNG OCR ĐƯỢC" in tm

        if thieu:
            kl, ly = "GIỮ", "bản mới thiếu khúc"
        elif dm < NGUONG_DAU:
            kl, ly = "GIỮ", "dấu chỉ %.1f%%" % dm
        elif tyle < NGUONG_CHU:
            kl, ly = "GIỮ", "chỉ %.0f%% chữ cái" % (100 * tyle)
        elif qm > qc:
            kl, ly = "THAY", "+%d quan hệ" % (qm - qc)
        elif qm == qc and qc > 0:
            kl, ly = "GIỮ", "quan hệ không đổi"
        elif qm == 0:
            kl, ly = "GIỮ", "vẫn không trích được quan hệ"
        else:
            kl, ly = "GIỮ", "bản mới ít quan hệ hơn"

        hang.append({"doc": doc, "fc": fc, "tm": tm, "qc": qc, "qm": qm,
                     "dau": dm, "tyle": tyle, "kl": kl, "ly": ly,
                     "ten": fc.name[5:52]})

    hang.sort(key=lambda r: (r["kl"] != "THAY", -(r["qm"] - r["qc"]), r["doc"]))
    print("=" * 100)
    print("ĐỐI CHIẾU 57 VĂN BẢN CÔ ĐỘC — bản OCR lại so với bản đang dùng")
    print("=" * 100)
    print("%-5s %-6s %-6s %6s %6s  %-24s %s"
          % ("doc", "QH cũ", "QH mới", "dấu", "chữ", "kết luận", "tên"))
    print("-" * 100)
    for r in hang:
        print("%-5s %-6d %-6d %5.1f%% %5.0f%%  %-8s %-15s %s"
              % (r["doc"], r["qc"], r["qm"], r["dau"], 100 * r["tyle"],
                 r["kl"], r["ly"][:15], r["ten"][:34]))

    thay = [r for r in hang if r["kl"] == "THAY"]
    print("-" * 100)
    print("  Nên THAY : %d tài liệu  (+%d quan hệ)"
          % (len(thay), sum(r["qm"] - r["qc"] for r in thay)))
    print("  Nên GIỮ  : %d tài liệu" % (len(hang) - len(thay)))
    print("=" * 100)

    if a.apply:
        for r in thay:
            rel = r["fc"].relative_to(SACH)
            b = LUU / (str(rel) + ".bak5")
            b.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(r["fc"], b)
            r["fc"].write_text(r["tm"], encoding="utf-8", newline="\n")
        print("Đã thay %d file (bản lưu .bak5 trong %s)" % (len(thay), LUU))
    elif thay:
        print(">>> Mới là XEM TRƯỚC. Thêm --apply để thay thật.")


if __name__ == "__main__":
    main()
