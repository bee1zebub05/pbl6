"""
Xuất `Person` (§2.3) và quan hệ MENTIONS tới `Organization` (§2.2) ra JSONL.

    python scripts/xuat_person_donvi.py
    python run.py kg load          # nạp luôn, neo4j_load tự đọc file mới

Chạy SAU `python run.py kg all` (cần `data/kg/documents.jsonl` để biết văn bản
nào ứng với file text nào), TRƯỚC `kg load`.

Tách thành bước riêng thay vì nhét vào `kg/documents.py`: hai trường này đọc từ
TOÀN VĂN, trong khi `build()` chủ yếu làm việc với metadata. Tách ra thì chạy lại
riêng được mỗi khi sửa từ điển đơn vị hay luật nhận tên, không phải chạy lại cả
bước docs vốn nặng hơn nhiều.

Ba file ghi ra, `neo4j_load` đọc nếu có và bỏ qua nếu không:

    persons.jsonl       {personId, fullName, position[], academicTitle, so_van_ban}
    signed_by.jsonl     {so_hieu_norm, personId}
    mentions.jsonl      {so_hieu_norm, orgId, name, orgType, so_lan}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vanban import config  # noqa: E402
from vanban.kg.don_vi import org_type, tim_don_vi  # noqa: E402
from vanban.kg.nguoi_ky import gop_ten_nguoi_ky, tim_nguoi_ky  # noqa: E402


def _ma(s: str) -> str:
    """Tên -> khoá không dấu, cùng lối với `orgId` sẵn có ('bo_cong_an')."""

    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("đ", "d").replace("Đ", "D").lower()

    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", s)).strip("_")


def ghi(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kg", default=None, help="thư mục data/kg")
    ap.add_argument("--toi-thieu", type=int, default=1,
                    help="số lần nhắc tối thiểu mới tạo cạnh MENTIONS")
    args = ap.parse_args()

    kg = Path(args.kg) if args.kg else config.KG_DIR
    docs_path = kg / "documents.jsonl"

    if not docs_path.exists():
        print(f"Chưa có {docs_path}. Chạy `python run.py kg all` trước.")

        return 1

    docs = [json.loads(l) for l in docs_path.read_text(encoding="utf-8").splitlines()
            if l.strip()]

    # Chỉ xét văn bản đã có text; stub thì chưa crawl nên không có gì để đọc.
    co_text = [d for d in docs if d.get("clean_path")]

    ky_theo_doc: dict[str, dict] = {}
    dem_ten: Counter = Counter()
    nhac: list[dict] = []
    don_vi_gap: dict[str, str] = {}

    for d in co_text:
        p = ROOT / d["clean_path"]

        if not p.exists():
            continue

        text = p.read_text(encoding="utf-8", errors="replace")

        r = tim_nguoi_ky(text)

        if r["ho_ten"]:
            ky_theo_doc[d["so_hieu_norm"]] = r
            dem_ten[r["ho_ten"]] += 1

        for ten, so_lan in tim_don_vi(text).items():
            if so_lan < args.toi_thieu:
                continue

            don_vi_gap[ten] = org_type(ten)
            nhac.append({
                "so_hieu_norm": d["so_hieu_norm"],
                "orgId": _ma(ten),
                "name": ten,
                "orgType": org_type(ten),
                "so_lan": so_lan,
            })

    # Gộp các cách viết sai của cùng một người — phải làm sau khi quét hết kho.
    anh_xa = gop_ten_nguoi_ky(dem_ten)

    nguoi: dict[str, dict] = {}
    ky: list[dict] = []

    for so_hieu, r in ky_theo_doc.items():
        ten = anh_xa.get(r["ho_ten"], r["ho_ten"])
        pid = _ma(ten)

        p = nguoi.setdefault(pid, {
            "personId": pid, "fullName": ten,
            "position": [], "academicTitle": "", "so_van_ban": 0,
        })
        p["so_van_ban"] += 1

        if r["chuc_danh"] and r["chuc_danh"] not in p["position"]:
            p["position"].append(r["chuc_danh"])

        if r["hoc_ham"] and not p["academicTitle"]:
            p["academicTitle"] = r["hoc_ham"]

        ky.append({"so_hieu_norm": so_hieu, "personId": pid})

    ghi(kg / "persons.jsonl", sorted(nguoi.values(), key=lambda x: -x["so_van_ban"]))
    ghi(kg / "signed_by.jsonl", ky)
    ghi(kg / "mentions.jsonl", nhac)

    print("=" * 76)
    print("XUẤT Person + MENTIONS")
    print("=" * 76)
    print(f"  Văn bản có text        : {len(co_text)}")
    print(f"  Đọc được người ký      : {len(ky)} "
          f"({100 * len(ky) / max(1, len(co_text)):.0f}%)")
    print(f"  Person                 : {len(nguoi)} "
          f"(gộp {sum(1 for a, b in anh_xa.items() if a != b)} cách viết sai)")
    print(f"  Đơn vị được nhắc tới   : {len(don_vi_gap)}")
    print(f"  Cạnh MENTIONS          : {len(nhac)}")
    print("-" * 76)

    for p in sorted(nguoi.values(), key=lambda x: -x["so_van_ban"])[:6]:
        print(f"  {p['so_van_ban']:>4} văn bản  {p['fullName']:<24} "
              f"{', '.join(p['position']) or '—'}")

    print("=" * 76)
    print("Đã ghi persons.jsonl, signed_by.jsonl, mentions.jsonl vào "
          f"{kg.relative_to(ROOT) if kg.is_relative_to(ROOT) else kg}")
    print("Nạp vào graph:  python run.py kg load")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
