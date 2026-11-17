# -*- coding: utf-8 -*-
"""Cắt lại toàn văn Điều vào JSON v4 sau khi sửa OCR trong text_final — CHỈ thay trường `text`.

    python tools/kiem_tra/cat_lai_dieu.py --chi 0177,0494          # xem trước
    python tools/kiem_tra/cat_lai_dieu.py --chi 0177,0494 --ghi    # ghi vào JSON v4

Vì sao không dùng `chay_json.py --va-lai`: chế độ đó chạy lại cả bước dọn dạng (_don_dang) trên
toàn bộ JSON, có thể đụng vào trường đã đối chiếu ảnh PDF. Ở đây chỉ dùng bộ cắt Điều của
chay_json (_bu_dieu, _quet_duoi_chuong) trên một BẢN SAO, rồi chép đúng `text` của Điều cùng vị trí,
cùng số Điều sang JSON thật. Mọi trường khác giữ nguyên.

Kiểm an toàn: bản cắt từ .txt CŨ (git HEAD) phải trùng `text` đang lưu thì mới thay bằng bản cắt
từ .txt MỚI — Điều nào lưu khác bản cắt cũ (đã có người sửa tay) thì không đụng.
"""
from __future__ import annotations

import argparse
import copy
import io
import json
import subprocess
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GOC / "tools" / "gemini_api"))
import chay_json as CJ  # noqa: E402

V4 = GOC / "data" / "clean" / "json" / "v4"
TXT = GOC / "data" / "clean" / "text_final"


def cat(data, goc):
    d = copy.deepcopy(data)
    CJ._bu_dieu(d, goc)
    CJ._quet_duoi_chuong(d)
    return d


def cac_dieu(d):
    ra = [("a", None, i, a) for i, a in enumerate(d.get("articles") or [])]
    for k, n in enumerate(d.get("normativeContents") or []):
        ra += [("n", k, i, a) for i, a in enumerate(n.get("articles") or [])]
    return ra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chi", required=True)
    ap.add_argument("--ghi", action="store_true")
    a = ap.parse_args()
    for ma in [x.strip() for x in a.chi.split(",") if x.strip()]:
        j = list(V4.rglob(f"{ma}_*.json"))[0]
        t = list(TXT.rglob(f"{ma}_*.txt"))[0]
        data = json.loads(j.read_text(encoding="utf-8"))
        moi_txt = io.open(t, encoding="utf-8").read()
        cu_txt = subprocess.run(["git", "show", "HEAD:" + t.relative_to(GOC).as_posix()], cwd=GOC,
                                capture_output=True).stdout.decode("utf-8")
        cu, moi = cat(data, cu_txt), cat(data, moi_txt)
        that, c_cu, c_moi = cac_dieu(data), cac_dieu(cu), cac_dieu(moi)
        if not (len(that) == len(c_cu) == len(c_moi)):
            print(f"  ? {ma}: số Điều lệch ({len(that)}/{len(c_cu)}/{len(c_moi)}), bỏ qua"); continue
        doi = khop = lech = 0
        for (o, k, i, x), (_, _, _, y), (_, _, _, z) in zip(that, c_cu, c_moi):
            if not (x["number"] == y["number"] == z["number"]):
                lech += 1; continue
            if x["text"] != y["text"]:
                lech += 1; continue          # đã có người sửa tay, hoặc bản lưu khác bản cắt — không đụng
            khop += 1
            if z["text"] != x["text"]:
                doi += 1
                x["text"] = z["text"]
        print(f"  {ma}: {len(that)} Điều | khớp bản cắt cũ {khop} | không đụng {lech} | đổi text {doi}")
        if a.ghi and doi:
            j.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
