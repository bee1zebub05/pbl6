"""
Trích người ký từ kho văn bản đã OCR -> JSON để nạp node `Person` (Ontology §2.3).

    python scripts/trich_nguoi_ky.py
    python scripts/trich_nguoi_ky.py --nguon data/clean/text_final
    python scripts/trich_nguoi_ky.py --ra data/kg/nguoi_ky.json --chi-tiet

Tách riêng khỏi `kg/documents.py` để chạy được độc lập trên bất kỳ thư mục text
nào, kể cả bản OCR mới chưa gộp vào kho chính.

Chuẩn hoá tên phải làm SAU KHI quét hết kho, không làm từng file được: muốn
quyết định 'Đoàn Quang Vinh' hay 'Doan Quang Winh' mới là cách viết đúng thì
cần biết cả kho viết thế nào, một file lẻ không đủ căn cứ.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vanban.kg.nguoi_ky import gop_ten_nguoi_ky, tim_nguoi_ky  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nguon", default="data/clean/text_final")
    ap.add_argument("--ra", default="data/kg/nguoi_ky.json")
    ap.add_argument("--chi-tiet", action="store_true")
    args = ap.parse_args()

    nguon = Path(args.nguon)

    if not nguon.is_absolute():
        nguon = ROOT / nguon

    files = sorted(nguon.rglob("*.txt"))

    if not files:
        print(f"Không có .txt nào trong {nguon}")

        return 1

    theo_file: dict[str, dict] = {}
    dem_ten: Counter = Counter()

    for f in files:
        r = tim_nguoi_ky(f.read_text(encoding="utf-8", errors="replace"))
        theo_file[f.stem[:4]] = r | {"file": f.relative_to(nguon).as_posix()}

        if r["ho_ten"]:
            dem_ten[r["ho_ten"]] += 1

    anh_xa = gop_ten_nguoi_ky(dem_ten)

    for r in theo_file.values():
        if r["ho_ten"]:
            r["ho_ten"] = anh_xa.get(r["ho_ten"], r["ho_ten"])

    # Một người giữ nhiều chức danh qua thời gian (Phó hiệu trưởng rồi Hiệu
    # trưởng) -> gom tất cả chức danh gặp được thay vì ghi đè lẫn nhau.
    nguoi: dict[str, dict] = {}

    for r in theo_file.values():
        if not r["ho_ten"]:
            continue

        p = nguoi.setdefault(
            r["ho_ten"], {"ho_ten": r["ho_ten"], "chuc_danh": [], "hoc_ham": "",
                          "so_van_ban": 0}
        )
        p["so_van_ban"] += 1

        if r["chuc_danh"] and r["chuc_danh"] not in p["chuc_danh"]:
            p["chuc_danh"].append(r["chuc_danh"])

        if r["hoc_ham"] and not p["hoc_ham"]:
            p["hoc_ham"] = r["hoc_ham"]

    ra = Path(args.ra)

    if not ra.is_absolute():
        ra = ROOT / ra

    ra.parent.mkdir(parents=True, exist_ok=True)
    ra.write_text(
        json.dumps({"theo_van_ban": theo_file, "nguoi": nguoi},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    co = sum(1 for r in theo_file.values() if r["ho_ten"])
    doi = {a: b for a, b in anh_xa.items() if a != b}

    print("=" * 78)
    print("TRÍCH NGƯỜI KÝ")
    print("=" * 78)
    print(f"  Văn bản           : {len(files)}")
    print(f"  Đọc được người ký : {co} ({100 * co / len(files):.0f}%)")
    print(f"  Người riêng biệt  : {len(nguoi)} "
          f"(đã gộp {len(doi)} cách viết sai do OCR)")
    print(f"  Có chức danh      : "
          f"{sum(1 for r in theo_file.values() if r['chuc_danh'])}")
    print(f"  Có học hàm        : "
          f"{sum(1 for r in theo_file.values() if r['hoc_ham'])}")

    if args.chi_tiet and doi:
        print("-" * 78)

        for a, b in sorted(doi.items()):
            print(f"  {a:<26} -> {b}")

    print("-" * 78)
    print("  Ký nhiều nhất:")

    for p in sorted(nguoi.values(), key=lambda x: -x["so_van_ban"])[:8]:
        cd = ", ".join(p["chuc_danh"]) or "—"
        print(f"  {p['so_van_ban']:>4} văn bản  {p['ho_ten']:<24} {cd}")

    print("=" * 78)
    print(f"Đã ghi: {ra.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
