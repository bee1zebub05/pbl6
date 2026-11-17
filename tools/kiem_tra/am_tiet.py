# -*- coding: utf-8 -*-
"""Đo tỷ lệ âm tiết tiếng Việt không hợp lệ trong từng tệp text_final — dấu hiệu lỗi OCR còn sót.

    python tools/kiem_tra/am_tiet.py                 # bảng tóm tắt + 30 tệp tệ nhất
    python tools/kiem_tra/am_tiet.py --csv ra.csv    # ghi tỷ lệ từng tệp
    python tools/kiem_tra/am_tiet.py --chi 0440 --in # in các âm tiết bị bắt của một tệp

Một âm tiết hợp lệ = phụ âm đầu (có thể rỗng) + vần trong bảng hữu hạn + đúng MỘT dấu thanh
(hoặc không dấu). Lỗi OCR hay gặp nhất là `é` đứng thay `ế/ề/ể/ệ` (`tiét`, `diéu`, `quyén`):
`iet`, `ieu`, `ien` không phải vần tiếng Việt (phải là `iêt`, `iêu`, `iên`) nên bị bắt.

Bỏ qua: từ viết hoa toàn bộ (QĐ, BGDĐT), token có chữ số, token không có nguyên âm. Từ nước
ngoài (Internet, Covid, logo) vẫn bị tính là sai — con số là CẬN TRÊN, phải mở tệp ra xem.
Viết lại từ mô tả `am_tiet.py` / `cham_diem2.py` trong TIEN_DO_SUA_OCR.md (bản cũ đã mất).
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import statistics
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
GOC = Path(__file__).resolve().parents[2]
TXT = GOC / "data" / "clean" / "text_final"

DAU = {"̀", "́", "̃", "̉", "̣"}   # huyền sắc ngã hỏi nặng
PHU_AM = sorted("b c ch d đ g gh gi h k kh l m n ng ngh nh p ph qu r s t th tr v x".split(),
                key=len, reverse=True)
VAN = set("""
a ai ao au ay am an ang anh ac ach ap at
ă ăm ăn ăng ăc ăp ăt
â âu ây âm ân âng âc âp ât
e eo em en eng ec ep et
ê êu êm ên ênh êc êch êp êt
i ia iu im in inh ic ich ip it iêu iêm iên iêng iêc iêp iêt
yêu yêm yên yêt y
o oa oai oao oay oam oan oang oanh oac oach oap oat oăm oăn oăng oăc oăt
oe oeo oen oet oi om on ong oc op ot ooc oong
ô ôi ôm ôn ông ôc ôp ôt
ơ ơi ơm ơn ơp ơt
u ua uân uâng uât uây uâ ui um un ung uc up ut uê uêch uênh uơ uy uya uyu uych uyn uynh uyp uyt
uyên uyêt uôi uôm uôn uông uôc uôt uô
ư ưa ưi ưu ưm ưn ưng ưc ưt ươ ươi ươu ươm ươn ương ươc ươp ươt
""".split())
TU = re.compile(r"[^\W\d_]+", re.UNICODE)
NGUYEN_AM = set("aăâeêioôơuưy")


def hop_le(w: str) -> bool:
    nfd = unicodedata.normalize("NFD", w.lower())
    dau = [c for c in nfd if c in DAU]
    if len(dau) > 1:
        return False
    goc = unicodedata.normalize("NFC", "".join(c for c in nfd if c not in DAU))
    if not any(c in NGUYEN_AM for c in goc):
        return True                      # không phải âm tiết (ký hiệu, chữ lẻ)
    for pa in PHU_AM + [""]:
        if goc.startswith(pa) and goc[len(pa):] in VAN:
            return True
        # "gi" + vần bắt đầu bằng i đã nuốt chữ i: gìn = gi + in, giếng = gi + iêng
        if pa == "gi" and goc.startswith("gi") and ("i" + goc[2:]) in VAN:
            return True
    return False


def dem(t: str):
    tong = sai = 0
    xau = []
    for w in TU.findall(t):
        if w.isupper() and len(w) > 1:
            continue
        if not re.search(r"[a-zA-Zà-ỹÀ-Ỹđ]", w):
            continue
        tong += 1
        if not hop_le(w):
            sai += 1
            xau.append(w)
    return tong, sai, xau


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--chi", default="")
    ap.add_argument("--in", dest="in_ra", action="store_true")
    a = ap.parse_args()
    chi = {x.strip() for x in a.chi.split(",") if x.strip()}
    kq = []
    for p in sorted(TXT.rglob("*.txt")):
        if chi and p.name[:4] not in chi:
            continue
        tong, sai, xau = dem(io.open(p, encoding="utf-8", errors="replace").read())
        kq.append((p.name[:4], tong, sai, sai / max(tong, 1), xau))
        if a.in_ra:
            from collections import Counter
            print(p.name[:4], f"{sai}/{tong}", Counter(xau).most_common(60))
    if a.csv:
        with open(a.csv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f); w.writerow(["ma", "am_tiet", "sai", "ty_le"])
            for m, t, s, r, _ in kq:
                w.writerow([m, t, s, f"{r:.4f}"])
    if chi:
        return
    ty = [r for *_, r, _ in kq]
    print(f"{len(kq)} tệp | trung vị {statistics.median(ty):.2%} | trung bình {statistics.mean(ty):.2%} | "
          f">=1%: {sum(r >= .01 for r in ty)} | >=2%: {sum(r >= .02 for r in ty)} | >=3%: {sum(r >= .03 for r in ty)}")
    for m, t, s, r, _ in sorted(kq, key=lambda x: -x[3])[:30]:
        print(f"  {m} {r:6.2%}  ({s}/{t})")


if __name__ == "__main__":
    main()
