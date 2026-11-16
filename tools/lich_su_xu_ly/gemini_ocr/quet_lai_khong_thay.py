# -*- coding: utf-8 -*-
"""Quet lai cac cho KHONG THAY — ghep theo NGU CANH CAU thay vi theo so.

Vi sao can rieng buoc nay: 249 cho bi danh KHONG THAY vi phan SO trong text_raw da
hong san ('25/ND', '212/ IQĐ-ĐHĐN', '2016/TT-BGDĐT') nen quy tac "phan so phai trung"
loai luon ung vien dung. Ghep theo cau chua no thi tim duoc.

Khac voi xac_minh_so.py: lan nay LUU LUON TOAN VAN trang moi OCR (trang_moi.jsonl)
de con doi chung, khong chi luu token.

KHONG sua text_raw. Chi xuat bang de nguoi doc duyet.

    python quet_lai_khong_thay.py                 # chay (tu dong tiep tuc neu dang do)
    python quet_lai_khong_thay.py --gioi-han 5
    python quet_lai_khong_thay.py --xuat-bang     # chi sinh lai bang, khong goi API
"""
import argparse
import csv
import difflib
import io as _io
import json
import re
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gemma_ocr import QuanLyKey, _ocr_hai_tang, TIMEOUT_MOI_KHUC_MS      # noqa: E402
from xac_minh_so import (RA, RAW_TXT, TOKEN, PROMPT, bo_dau_cau, cat_trang,  # noqa: E402
                         chi_muc_pdf, chuan, giong, khoa_luot, loai_token, thanh)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KQ_GOC = RA / "ket_qua.jsonl"
RA2 = RA / "quet_lai"
COT = ["doc_id", "file", "trang", "so_cu", "ung_vien", "do_tin", "moi_tat_ca",
       "cau_cu", "cau_moi"]

_khoa = threading.Lock()
_so = {"luot": 0, "xong": 0, "hong": 0, "tim_thay": 0}


def tu_khoa(cau, tok):
    """Bo token ra khoi cau, giu lai cac tu xung quanh lam moc nhan dang."""
    con = chuan(cau).replace(chuan(tok), " ")
    return re.sub(r"\s+", " ", con).strip()


def tim_theo_ngu_canh(cau_cu, tok_cu, text_moi):
    """Tim token moi bang cach doi chieu CAU chua no.

    -> (token_moi, do_tin 0..1, cau_moi)
    """
    moc = tu_khoa(cau_cu, tok_cu)
    dong_moi = [chuan(x) for x in text_moi.splitlines() if x.strip()]
    if not dong_moi or len(moc) < 12:
        return "", 0.0, "", []

    # cau moi giong cau cu nhat (da bo token de khong bi chinh token lam nhieu)
    diem = [(difflib.SequenceMatcher(None, moc.lower(), tu_khoa(dm, "").lower()).ratio(), dm)
            for dm in dong_moi]
    diem.sort(reverse=True)
    do_tin, cau_moi = diem[0]
    if do_tin < 0.45:
        return "", do_tin, cau_moi, []

    toks = [chuan(t) for t in TOKEN.findall(cau_moi)]
    # BAT BUOC cung loai: so hieu chi ghep voi so hieu, ngay chi ghep voi ngay.
    # Khong loc loai thi '212/ IQĐ-ĐHĐN' (so hieu) bi ghep voi 'ngày 10 tháng 8 năm 2018'.
    lc = loai_token(tok_cu)
    cung_loai = [t for t in toks if loai_token(t) == lc]
    if not cung_loai:
        return "", do_tin, cau_moi, toks
    if len(cung_loai) == 1:
        return cung_loai[0], do_tin, cau_moi, toks
    return max(cung_loai, key=lambda t: giong(tok_cu, t)), do_tin, cau_moi, toks


def nap_diem_luu(p):
    ra, khoa = [], set()
    if p.exists():
        for l in p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                d = json.loads(l)
                ra.append(d)
                khoa.add(d["_khoa"])
            except Exception:
                pass
    return ra, khoa


def xuat(hang):
    RA2.mkdir(parents=True, exist_ok=True)
    ds = sorted(hang, key=lambda r: (-float(r.get("do_tin") or 0), r["doc_id"]))
    with open(RA2 / "quet_lai.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COT, extrasaction="ignore")
        w.writeheader()
        w.writerows(ds)
    co = [r for r in ds if r["ung_vien"]]
    with open(RA2 / "quet_lai.md", "w", encoding="utf-8", newline="\n") as f:
        f.write("# Quét lại các chỗ KHÔNG THẤY — ghép theo ngữ cảnh câu\n\n")
        f.write("- Tổng: **%d** chỗ | tìm được ứng viên: **%d** | không tìm được: %d\n\n"
                % (len(ds), len(co), len(ds) - len(co)))
        f.write("> `độ tin` = mức giống nhau giữa câu cũ và câu mới (0–1). "
                "Cao thì gần như chắc chắn cùng một câu.\n")
        f.write("> **Chưa sửa gì vào text_raw.**\n\n")
        f.write("| doc | trang | tin | text_raw (cũ) | ứng viên (mới) | mọi số trong câu | "
                "câu trong PDF gốc |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for r in co:
            f.write("| %s | %s | %.2f | `%s` | `%s` | %s | %s |\n"
                    % (r["doc_id"], r["trang"], float(r["do_tin"]), r["so_cu"],
                       r["ung_vien"], str(r.get("moi_tat_ca", "")).replace("|", " / ")[:44],
                       str(r["cau_moi"]).replace("|", "/")[:64]))
    return RA2 / "quet_lai.csv", RA2 / "quet_lai.md"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--song-song", type=int, default=4)
    ap.add_argument("--model", default="gemini-3.5-flash-lite")
    ap.add_argument("--model-lui", default="gemma-4-31b-it")
    ap.add_argument("--gioi-han", type=int, default=0)
    ap.add_argument("--xuat-bang", action="store_true")
    a = ap.parse_args()

    RA2.mkdir(parents=True, exist_ok=True)
    kq_p, tr_p = RA2 / "ket_qua.jsonl", RA2 / "trang_moi.jsonl"
    hang, da_lam = nap_diem_luu(kq_p)

    if a.xuat_bang:
        c, m = xuat(hang)
        print("Đã sinh lại bảng từ %d dòng đã lưu:\n  %s\n  %s" % (len(hang), c, m))
        return

    goc = [json.loads(l) for l in _io.open(KQ_GOC, encoding="utf-8") if l.strip()]
    can = [r for r in goc if r["khop"] == "KHÔNG THẤY"]

    # gom theo (file, trang) — moi cum chi can OCR 1 lan
    cum = defaultdict(list)
    for r in can:
        cum[(r["file"], r["trang"])].append(r)
    viec = [(f, t, ds) for (f, t), ds in sorted(cum.items())]
    if a.gioi_han:
        viec = viec[: a.gioi_han]
    viec = [v for v in viec if ("%s|%s" % (v[0], v[1])) not in
            {k.rsplit("#", 1)[0] for k in da_lam}]

    ix = chi_muc_pdf()
    tong = len(viec)
    print("=" * 90)
    print("QUÉT LẠI CÁC CHỖ KHÔNG THẤY — ghép theo ngữ cảnh câu")
    print("  Cần xử lý: %d chỗ, gom thành %d lượt OCR" % (len(can), tong))
    print("  Model    : %s → lùi về %s" % (a.model, a.model_lui))
    if da_lam:
        print("  ⏩ TIẾP TỤC: đã có %d dòng từ lần chạy trước" % len(hang))
    print("=" * 90)
    if not tong:
        c, m = xuat(hang)
        print("Không còn lượt nào. Bảng: %s" % m)
        return

    qlk = QuanLyKey(model=a.model)
    qlk.kiem_tra(hien_thi=False)
    qlk.kiem_tra_sau(hien_thi=False)
    print("  Key dùng được: %d/%d" % (qlk.con_song(), len(qlk.keys)))
    print("-" * 90)

    models = [a.model] + ([a.model_lui] if a.model_lui else [])
    f_kq = open(kq_p, "a", encoding="utf-8", newline="\n")
    f_tr = open(tr_p, "a", encoding="utf-8", newline="\n")
    t0 = time.perf_counter()

    def lam(v):
        ten_file, trang_str, ds = v
        ftxt = next((p for p in RAW_TXT.rglob(ten_file)), None)
        m = re.match(r"(\d{4})_", ten_file)
        pdf = ix.get(m.group(1)) if m else None
        cum_trang = [int(t) for t in str(trang_str).split("-") if t.isdigit()]
        if not ftxt or not pdf or not cum_trang:
            with _khoa:
                _so["luot"] += 1
                _so["hong"] += 1
            return
        try:
            b = cat_trang(pdf, cum_trang)
        except Exception:
            with _khoa:
                _so["luot"] += 1
                _so["hong"] += 1
            return

        moi, gc = _ocr_hai_tang(qlk, b, PROMPT, models, len(cum_trang), TIMEOUT_MOI_KHUC_MS,
                                min_ky_tu=max(60, 40 * len(cum_trang)))
        with _khoa:
            _so["luot"] += 1
            if not moi:
                _so["hong"] += 1
            else:
                _so["xong"] += 1
                # LUU TOAN VAN trang moi de con doi chung ve sau
                f_tr.write(json.dumps({"file": ten_file, "trang": trang_str,
                                       "model": gc, "text": moi}, ensure_ascii=False) + "\n")
                f_tr.flush()
                for i, r in enumerate(ds):
                    uv, tin, cau_moi, tat_ca = tim_theo_ngu_canh(r["ngu_canh"], r["so_cu"], moi)
                    if uv:
                        _so["tim_thay"] += 1
                    h = {"_khoa": "%s|%s#%d" % (ten_file, trang_str, i),
                         "doc_id": r["doc_id"], "file": ten_file, "trang": trang_str,
                         "so_cu": r["so_cu"], "ung_vien": uv, "do_tin": round(tin, 2),
                         "moi_tat_ca": " | ".join(tat_ca[:5]),
                         "cau_cu": r["ngu_canh"], "cau_moi": cau_moi[:150], "model": gc}
                    hang.append(h)
                    f_kq.write(json.dumps(h, ensure_ascii=False) + "\n")
                f_kq.flush()

            r_ = _so["luot"]
            dt = time.perf_counter() - t0
            print("  %s %3d/%-3d %5.1f%%  xong %d hỏng %d | tìm được %d | còn ~%.0f phút"
                  % (thanh(r_, tong), r_, tong, 100.0 * r_ / tong, _so["xong"], _so["hong"],
                     _so["tim_thay"], (dt / r_) * (tong - r_) / 60 if r_ else 0))

    try:
        with ThreadPoolExecutor(max_workers=a.song_song) as ex:
            list(ex.map(lam, viec))
    except KeyboardInterrupt:
        print("\n⏸ Dừng tay. Điểm lưu còn nguyên — chạy lại là đi tiếp.")
    finally:
        f_kq.close()
        f_tr.close()

    c, m = xuat(hang)
    print("-" * 90)
    print("Xong %d lượt | tìm được ứng viên cho %d/%d chỗ" % (_so["luot"], _so["tim_thay"], len(can)))
    print("Bảng: %s\n      %s" % (c, m))
    print("Toàn văn trang đã OCR: %s" % tr_p)


if __name__ == "__main__":
    main()
