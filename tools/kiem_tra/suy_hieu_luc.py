#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Suy `document.status` từ quan hệ thay thế trên TOÀN KHO.

    python tools/kiem_tra/suy_hieu_luc.py --dir data/clean/json/v4        # chỉ xem
    python tools/kiem_tra/suy_hieu_luc.py --dir data/clean/json/v4 --sua  # ghi vào

Vì sao phải làm ở tầng kho chứ không sửa prompt: lúc trích xuất, model chỉ
nhìn thấy MỘT văn bản. Văn bản không bao giờ tự nói "ba năm nữa tôi sẽ bị thay
thế" — chính văn bản ĐẾN SAU mới nói "thay thế Quyết định số ...". Nên không
prompt nào biết được điều này, dù viết khéo đến đâu.

Hậu quả đo được: v4 có 16/103 văn bản bị văn bản khác TRONG CÙNG KHO tuyên bố
thay thế mà vẫn ghi CON_HIEU_LUC; v1 và v2 có 52/439. Chatbot phát hiện ra và
nói thẳng với người dùng — core/chat/answering/evidence.py in thêm
"(thuộc tính trong kho vẫn ghi {status})" mỗi khi status lệch effectiveStatus.

GIỚI HẠN phải nhớ: chỉ bắt được thay thế trong phạm vi kho. Một văn bản bị
thay thế bởi thứ chưa nạp vào thì vẫn ghi CON_HIEU_LUC. Đây là "đúng trong
phạm vi kho biết", không phải đúng tuyệt đối.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GOC / "src"))

from legal_knowledge_graph.core import normalize as nz  # noqa: E402

# Chỉ hai quan hệ này mới làm văn bản đích hết hiệu lực. AMENDS thì KHÔNG:
# sửa đổi, bổ sung là văn bản gốc vẫn sống, chỉ đổi vài điều.
LAM_HET = ("REPLACES", "REPEALS")


def doc_json(thu_muc: Path) -> list[Path]:
    """Lấy CẢ file trong thư mục bắt đầu bằng `_` (khác iter_json_files của
    loader): `_nghi_ngo` là hàng đợi soi tay, các file trong đó vẫn hợp lệ và
    quan hệ thay thế của chúng vẫn phải tính."""
    return sorted(thu_muc.rglob("*.json"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--sua", action="store_true", help="ghi vào file; mặc định chỉ xem")
    a = ap.parse_args()

    kho: dict[str, dict] = {}
    for p in doc_json(a.dir):
        d = json.loads(io.open(p, encoding="utf-8").read())
        kho[nz.doc_key(d["document"])] = {"p": p, "d": d}

    # khoá văn bản bị thay thế -> danh sách (số hiệu kẻ thay thế, quan hệ)
    bi_thay: dict[str, list[tuple[str, str]]] = {}
    for k, v in kho.items():
        for c in v["d"].get("citations") or []:
            if c["relationType"] not in LAM_HET:
                continue
            dich = nz.normalize_document_number(c.get("targetDocumentNumber") or "")
            if dich and dich != k:
                bi_thay.setdefault(dich, []).append(
                    (v["d"]["document"]["documentNumber"], c["relationType"]))

    sua = []
    for k, ke in sorted(bi_thay.items()):
        if k not in kho:                      # kẻ bị thay nằm ngoài kho, bỏ qua
            continue
        doc = kho[k]["d"]["document"]
        if doc.get("status") == "HET_HIEU_LUC":
            continue
        sua.append((kho[k]["p"], doc["documentNumber"], doc.get("status"), ke))

    print("%d văn bản | %d bị thay thế/bãi bỏ trong kho | %d cần sửa status"
          % (len(kho), len(bi_thay), len(sua)))
    for p, so, cu, ke in sua:
        print("   %-18s %-14s -> HET_HIEU_LUC   (bị %s)"
              % (so, cu, ", ".join("%s %s" % (x[0], x[1]) for x in ke[:2])))

    if not a.sua:
        print("\n(chỉ xem — thêm --sua để ghi vào file)")
        return 0

    for p, so, _cu, ke in sua:
        d = json.loads(io.open(p, encoding="utf-8").read())
        d["document"]["status"] = "HET_HIEU_LUC"
        ghi_chu = "Hết hiệu lực: bị %s theo %s." % (
            "bãi bỏ" if ke[0][1] == "REPEALS" else "thay thế",
            ", ".join(x[0] for x in ke))
        cu_note = (d.get("note") or "").strip()
        if ghi_chu not in cu_note:
            d["note"] = (cu_note + " " if cu_note else "") + ghi_chu
        io.open(p, "w", encoding="utf-8", newline="\n").write(
            json.dumps(d, ensure_ascii=False, indent=2) + "\n")
    print("\nđã sửa %d file" % len(sua))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
