# -*- coding: utf-8 -*-
"""Dung BAN CUOI CUNG: gop ban OCR tot nhat cua tung van ban vao mot kho duy nhat.

HIEN TRANG. Khong kho nao vua du vua tot:

    text_clean_gemma   460 file — du toan bo kho, nhung OCR kem hon
    text_gemma_moi     287 file — OCR tot hon han (nguoi ky 50% -> 91%), 0 lo
    text_gemma_trang   283 file — nhu tren, them moc tung trang

CACH GOP. Voi moi van ban: lay ban MOI neu no qua duoc cong loc, khong thi giu ban CU.

NAM DIEU KIEN CUA CONG LOC. Bon dieu dau la de KHONG LAM HONG, dieu thu nam la de
viec gop luon DOI LAY MOT THU CU THE:

  1. khong con dau [[KHONG OCR DUOC]]
  2. ty le dau tieng Viet >= 12%   (that thuong 18-23%; duoi 12% la ban hong)
  3. giu duoc >= 85% so CHU CAI cua ban cu
  4. khong mat NGUOI KY ma ban cu doc duoc
  5. PHAI THEM DUOC THONG TIN — nguoi ky, hoac ngay, hoac quan he

Dieu 4 va 5 la phan quan trong. Da do that o dot dau: mot ban moi DAI HON ban cu
nhung lai MAT nguoi ky (0255, vi thieu 4 khuc chua khoi ky). Gop theo do dai la
gop nham.

    python dung_ban_cuoi.py                  # xem truoc
    python dung_ban_cuoi.py --apply
"""
import argparse
import io
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from quan_he_hieu_luc import phan_loai                 # noqa: E402
from trich_do_thi import tim_chu_ky, tim_ngay          # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
CU = GOC / "data" / "processed" / "text_clean_gemma"
TRANG = GOC / "data" / "processed" / "text_gemma_trang"
KHUC = GOC / "data" / "processed" / "text_gemma_moi"
# Dot OCR VET: nhung van ban chua tung OCR lai, hoac con sai ngay. Uu tien cao
# nhat vi day la ban moi nhat va da doi chieu tay.
VET = GOC / "data" / "processed" / "text_gemma_vet"
RA = GOC / "data" / "processed" / "text_final"

HONG = re.compile(r"\[\[KHÔNG OCR ĐƯỢC")
DAU = re.compile(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ"
                 r"ùúủũụưừứửữựỳýỷỹỵđ]", re.I)


def ty_le_dau(t):
    chu = sum(1 for c in t if c.isalpha())
    return len(DAU.findall(t)) / max(1, chu)


def so_chu(t):
    return sum(1 for c in t if c.isalpha())


def do(t):
    """Rut cac truong de so sanh hai ban."""
    ky = tim_chu_ky(t)
    m = tim_ngay(t)
    hop_le = False
    if m:
        try:
            date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            hop_le = True
        except ValueError:
            hop_le = False
    return {
        "nguoi_ky": ky[0],
        "chuc_danh": ky[2],
        "ngay": bool(m),
        "ngay_hop_le": hop_le,
        "quan_he": len(phan_loai(t)),
        "chu": so_chu(t),
        "dau": ty_le_dau(t),
        "lo": len(HONG.findall(t)),
    }


def chon(t_cu, t_moi):
    """-> (dung_ban_moi, ly_do)"""
    if t_moi is None:
        return False, "không có bản mới"

    a, b = do(t_cu), do(t_moi)

    if b["lo"]:
        return False, "bản mới còn %d lỗ" % b["lo"]
    if b["dau"] < 0.12:
        return False, "dấu chỉ %.0f%%" % (100 * b["dau"])
    if b["chu"] < a["chu"] * 0.85:
        return False, "mất chữ (còn %.0f%%)" % (100 * b["chu"] / max(1, a["chu"]))
    if a["nguoi_ky"] and not b["nguoi_ky"]:
        return False, "mất người ký (%s)" % a["nguoi_ky"]

    them = []
    if b["nguoi_ky"] and not a["nguoi_ky"]:
        them.append("người ký")
    if b["ngay"] and not a["ngay"]:
        them.append("ngày")
    # Ban cu doc duoc ngay nhung ngay do KHONG TON TAI ('tháng 42', 'ngày 80') ma
    # ban moi doc ra ngay hop le -> phai lay ban moi. Truoc day cong loc chi hoi
    # "co ngay khong", khong hoi "ngay do co that khong", nen giu ban cu sai o
    # 0384 va 0195 trong khi ban Gemma da doc dung san.
    if b["ngay_hop_le"] and a["ngay"] and not a["ngay_hop_le"]:
        them.append("sửa ngày sai")
    # Ban cu HONG DAU (duoi 12%) ma ban moi doc dung dau -> phai lay ban moi, du so
    # chu cai gan bang nhau. Do 0377: ban cu 6,4% dau nhung van co 22.096 chu cai,
    # ban vet 28,3% dau voi 22.245 chu — chenh 0,7% nen dieu kien "+5% chu" khong
    # kich hoat, cong loc giu nguyen ban hong. Khac biet nam o DAU, khong o so chu.
    if a["dau"] < 0.12 <= b["dau"]:
        them.append("sửa mất dấu (%.0f%% -> %.0f%%)" % (100 * a["dau"], 100 * b["dau"]))
    if b["quan_he"] > a["quan_he"]:
        them.append("+%d quan hệ" % (b["quan_he"] - a["quan_he"]))
    if b["chu"] > a["chu"] * 1.05:
        them.append("+%.0f%% chữ" % (100 * (b["chu"] / max(1, a["chu"]) - 1)))

    if not them:
        return False, "không thêm được gì"

    return True, ", ".join(them)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    ix_trang = {f.name[:4]: f for f in TRANG.rglob("*.txt")}
    ix_khuc = {f.name[:4]: f for f in KHUC.rglob("*.txt")}
    ix_vet = {f.name[:4]: f for f in VET.rglob("*.txt")} if VET.exists() else {}

    lay_moi = giu_cu = 0
    ly_do = {}
    them_ky = them_qh = 0

    print("=" * 88)
    print("DỰNG BẢN CUỐI — chọn bản tốt hơn cho từng văn bản")
    print("=" * 88)

    for f in sorted(CU.rglob("*.txt")):
        d = f.name[:4]
        t_cu = io.open(f, encoding="utf-8", errors="replace").read()

        # uu tien ban da can trang; khong co thi dung ban theo khuc
        p_moi = ix_vet.get(d) or ix_trang.get(d) or ix_khuc.get(d)
        t_moi = (io.open(p_moi, encoding="utf-8", errors="replace").read()
                 if p_moi else None)

        dung_moi, vi_sao = chon(t_cu, t_moi)
        t = t_moi if dung_moi else t_cu

        if dung_moi:
            lay_moi += 1
            if "người ký" in vi_sao:
                them_ky += 1
            if "quan hệ" in vi_sao:
                them_qh += 1
        else:
            giu_cu += 1
            ly_do[vi_sao.split(" (")[0]] = ly_do.get(vi_sao.split(" (")[0], 0) + 1

        if a.apply:
            p = RA / f.relative_to(CU)
            p.parent.mkdir(parents=True, exist_ok=True)
            io.open(p, "w", encoding="utf-8", newline="\n").write(t)

    print("  Lấy bản MỚI : %d" % lay_moi)
    print("     trong đó lấy lại được người ký : %d" % them_ky)
    print("     thêm được quan hệ              : %d" % them_qh)
    print("  Giữ bản CŨ  : %d" % giu_cu)
    for k, v in sorted(ly_do.items(), key=lambda x: -x[1]):
        print("     %-28s %d" % (k, v))
    print("=" * 88)
    print("Đã ghi vào %s" % RA if a.apply
          else ">>> Mới là XEM TRƯỚC. Thêm --apply để ghi ra.")


if __name__ == "__main__":
    main()
