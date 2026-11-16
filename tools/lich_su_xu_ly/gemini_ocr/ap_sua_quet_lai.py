# -*- coding: utf-8 -*-
"""Ap ket qua QUET LAI (ghep theo ngu canh) vao text_raw — thay CA DONG.

Khac ap_sua_text_raw.py (thay rieng token): o day chuoi cu thuong la MANH VUN
('7 /QD-DHBK', '202/ cua') va dong cu con chua san ban dung dinh lien ('Số: 448/QĐ-ĐHBK4
7 /QD-DHBK'). Thay rieng token se de lai rac -> phai thay NGUYEN DONG bang dong
model doc duoc.

An toan:
  - SAO LUU toan bo text_raw truoc khi ghi
  - Chi thay khi tim thay DUNG dong cu trong DUNG trang
  - Bo ky tu markdown (* _ `) model hay them
  - Mac dinh CHI XEM TRUOC, phai --apply moi ghi

    python ap_sua_quet_lai.py            # xem truoc
    python ap_sua_quet_lai.py --apply    # ghi that
"""
import argparse
import io
import json
import re
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from soi_so import MOC_TRANG                 # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
RAW_TXT = GOC / "data" / "processed" / "text_raw"
KQ = GOC / "data" / "doi_chieu_so" / "quet_lai" / "ket_qua.jsonl"


def bo_markdown(s):
    """Model hay tra loi co markdown: *(Ban hành...)* hoac **Số: 12**. Bo di."""
    s = re.sub(r"\*{1,3}|`{1,3}|_{2,}", "", s or "")
    return re.sub(r"\s+", " ", s).strip()


def chuan(s):
    return re.sub(r"\s+", " ", s or "").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--tin-toi-thieu", type=float, default=0.45)
    ap.add_argument("--xem", type=int, default=10)
    a = ap.parse_args()

    if not KQ.exists():
        print("Chưa có %s" % KQ)
        sys.exit(1)

    rows = [json.loads(l) for l in io.open(KQ, encoding="utf-8") if l.strip()]
    can = [r for r in rows
           if r.get("ung_vien") and float(r.get("do_tin") or 0) >= a.tin_toi_thieu
           and len(bo_markdown(r.get("cau_moi", ""))) >= 8]
    print("=" * 88)
    print("ÁP KẾT QUẢ QUÉT LẠI VÀO text_raw   %s"
          % ("(GHI THẬT)" if a.apply else "(chỉ xem trước)"))
    print("  Có ứng viên : %d | đủ độ tin ≥%.2f : %d"
          % (sum(1 for r in rows if r.get("ung_vien")), a.tin_toi_thieu, len(can)))
    print("  Cách sửa    : thay NGUYÊN DÒNG (thay riêng token sẽ để lại rác)")
    print("=" * 88)

    if a.apply:
        dich = RAW_TXT.parent / ("text_raw_backup_" + time.strftime("%Y%m%d_%H%M%S"))
        shutil.copytree(RAW_TXT, dich)
        print("Đã sao lưu → %s" % dich.name)
        print("-" * 88)

    theo_file = defaultdict(list)
    for r in can:
        theo_file[r["file"]].append(r)

    sua = hut = 0
    vi_du = []
    for ten, ds in sorted(theo_file.items()):
        f = next((p for p in RAW_TXT.rglob(ten)), None)
        if not f:
            print("  ⚠ không thấy file %s" % ten[:64])
            hut += len(ds)
            continue

        dong = f.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        trang, doi_file = 1, 0
        # tra cuu: dong cu (da chuan hoa) -> dong moi
        can_theo_trang = defaultdict(dict)
        for r in ds:
            for t in str(r["trang"]).split("-"):
                if t.isdigit():
                    can_theo_trang[int(t)][chuan(r["cau_cu"])] = r

        for i, d in enumerate(dong):
            m = MOC_TRANG.search(d)
            if m:
                trang = int(m.group(1))
                continue
            r = can_theo_trang.get(trang, {}).get(chuan(d))
            if not r:
                continue
            moi = bo_markdown(r["cau_moi"])
            if not moi:
                continue
            cuoi = "\n" if d.endswith("\n") else ""
            dong[i] = moi + cuoi
            doi_file += 1
            if len(vi_du) < a.xem:
                vi_du.append((r["doc_id"], chuan(d)[:60], moi[:60]))

        sua += doi_file
        hut += len(ds) - doi_file
        print("  %s %-56s sửa %2d/%-2d" % ("✔" if doi_file == len(ds) else "~",
                                           ten[:56], doi_file, len(ds)))
        if a.apply and doi_file:
            f.write_text("".join(dong), encoding="utf-8", newline="")

    print("-" * 88)
    print("Sửa %d dòng | không khớp được dòng cũ: %d" % (sua, hut))
    if vi_du:
        print("\nVí dụ:")
        for doc, cu, moi in vi_du:
            print("   %s  cũ : %s" % (doc, cu))
            print("        mới: %s" % moi)
    if not a.apply:
        print("\n>>> Mới là XEM TRƯỚC. Thêm --apply để ghi thật (có sao lưu).")


if __name__ == "__main__":
    main()
