# -*- coding: utf-8 -*-
"""Nho Gemma doc NGUOI KY tu phan cuoi van ban, cho nhung file mau regex chiu thua.

VI SAO KHONG OCR LAI CA FILE: text da co san va ten nguoi ky VAN NAM TRONG DO — van de
chi la BO CUC bi vo. Ban goc in hai cot canh nhau ("Noi nhan" ben trai, khoi ky ben
phai), OCR doc tron hai cot vao cung mot dong:

    Vơi nhận: KI. BỘ TRCỞNG ỊRƯỞNG
    Ban Tuyên giáo Trung ương Đảng: V
    guyễn Thị Nghĩa            <- chu 'N' bi dinh vao cuoi dong tren

Mau regex doc theo dong nen chiu. Mo hinh ngon ngu doc ca doan thi hieu ngay. Gui
~3.000 ky tu cuoi thay vi OCR lai 30 trang PDF: nhanh hon vai chuc lan, va khong co
rui ro lam hong phan van ban da tot.

CO DIEM LUU: ghi tung dong vao ket qua .jsonl, dut ngang chay lai la di tiep.

    python trich_nguoi_ky.py                 # xem se lam gi
    python trich_nguoi_ky.py --apply         # goi Gemma that
    python trich_nguoi_ky.py --tat-ca        # lam CA file da co nguoi ky (de doi chieu)
"""
import argparse
import io
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trich_do_thi as T                                # noqa: E402
from gemma_ocr import QuanLyKey, _la_tam_thoi           # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
SACH = GOC / "data" / "processed" / "text_clean_gemma"
RA = GOC / "data" / "nguoi_ky"

MODELS = ["gemma-4-31b-it", "gemini-3.5-flash-lite"]
SO_KY_TU_CUOI = 3000

NHAC = """Đây là phần cuối một văn bản hành chính Việt Nam đã được OCR, bố cục có thể bị
vỡ do bản gốc in hai cột (bên trái là "Nơi nhận", bên phải là khối chữ ký).

Hãy cho tôi biết AI LÀ NGƯỜI KÝ văn bản này.

Trả lời DUY NHẤT một dòng theo đúng một trong hai dạng:
  TÊN: <họ và tên đầy đủ>
  KHÔNG RÕ

Quy tắc:
- Chỉ lấy tên người ký thật, bỏ học hàm học vị (PGS, TS, ThS) và chức danh.
- Nếu OCR làm mất chữ cái đầu của họ (ví dụ "guyễn Thị Nghĩa"), hãy khôi phục
  thành họ đúng ("Nguyễn Thị Nghĩa").
- Nếu chữ bị sai dấu, hãy sửa lại cho đúng chính tả tiếng Việt.
- TUYỆT ĐỐI không bịa. Không thấy tên người thì trả lời KHÔNG RÕ.

--- PHẦN CUỐI VĂN BẢN ---
%s"""

_khoa = threading.Lock()
_so = {"xong": 0, "thay": 0, "khong": 0, "hong": 0}


# "Noi nhan:" la moc CHAC CHAN NHAT cua khoi ky trong van ban hanh chinh Viet Nam —
# no luon nam ngay canh chu ky, va co o 345/460 file. Neo vao day chinh xac hon nhieu
# so voi neo vao chuc danh: chuc danh con xuat hien day trong than bai ("... cua Giam
# doc Dai hoc Da Nang"), lay lan khop cuoi cung se roi vao giua tai lieu.
NOI_NHAN = re.compile(r"N[oơốờ]i\s*nh[aậâ]n|V[oơ]i\s*nh[aậ]n|Noi\s*nhan", re.I)


def duoi_van_ban(t, n=SO_KY_TU_CUOI):
    """Lay doan chac chan chua khoi ky. Uu tien 'Noi nhan', roi den chuc danh, roi cuoi file."""
    vt = [m.start() for m in NOI_NHAN.finditer(t)]
    if vt:
        i = vt[-1]
        return t[max(0, i - 400):i + 2600]
    vt = [m.end() for m in T.CHUC_DANH.finditer(t)]
    if vt:
        i = vt[-1]
        return t[max(0, i - 1200):i + 1800]
    return t[-n:]


def hoi(qlk, doc, t):
    from google import genai
    from google.genai import types
    ly_do = "không có key"
    # Xoay ca KEY lan MODEL: dich vu Gemma dang tra 500 INTERNAL rai rac, doi key khong
    # cuu duoc vi loi nam o phia model. Lui sang gemini-3.5-flash-lite thi qua duoc.
    for lan in range(10):
        k = qlk.lay()
        if not k:
            break
        model = MODELS[0] if lan < 5 else MODELS[-1]
        try:
            c = genai.Client(api_key=k["key"],
                             http_options=types.HttpOptions(timeout=60000))
            r = c.models.generate_content(
                model=model, contents=[NHAC % t],
                # 512 chu khong phai 60: model sinh vai token dan nhap truoc khi
                # tra loi, dat 60 la cham tran MAX_TOKENS roi tra ve RONG. Da do that.
                config=types.GenerateContentConfig(temperature=0.0,
                                                   max_output_tokens=512))
            qlk.bao_xong(k)
            s = (r.text or "").strip()
            m = re.search(r"TÊN\s*:\s*(.+)", s, re.I)
            if m:
                return re.sub(r"\s+", " ", m.group(1)).strip(" .,;:*"), ""
            if re.search(r"KHÔNG\s*RÕ", s, re.I):
                return "", "model nói không rõ"
            ly_do = "trả lời lạ: %s" % s[:40]
        except Exception as e:
            qlk.bao_loi(k, e)
            ly_do = str(e)[:60]
            if not _la_tam_thoi(e):
                break
        time.sleep(1)
    return None, ly_do


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--tat-ca", action="store_true",
                    help="làm cả file đã có người ký, để đối chiếu")
    ap.add_argument("--song-song", type=int, default=4)
    ap.add_argument("--gioi-han", type=int, default=0)
    a = ap.parse_args()

    RA.mkdir(parents=True, exist_ok=True)
    kq_p = RA / ("tat_ca.jsonl" if a.tat_ca else "thieu.jsonl")

    da_lam = {}
    if kq_p.exists():
        for l in io.open(kq_p, encoding="utf-8"):
            try:
                d = json.loads(l)
                da_lam[d["doc"]] = d
            except Exception:
                pass

    viec = []
    for f in sorted(SACH.rglob("*.txt")):
        doc = f.name[:4]
        t = io.open(f, encoding="utf-8", errors="replace").read()
        cu = T.tim_nguoi_ky(t)
        if cu and not a.tat_ca:
            continue
        if doc in da_lam:
            continue
        viec.append((doc, f, t, cu))
    if a.gioi_han:
        viec = viec[: a.gioi_han]

    print("=" * 90)
    print("HỎI GEMMA NGƯỜI KÝ  %s" % ("(GỌI THẬT)" if a.apply else "(chỉ xem trước)"))
    print("  Phạm vi : %s" % ("TẤT CẢ văn bản" if a.tat_ca else "chỉ file regex không đọc được"))
    print("  Cần làm : %d văn bản" % len(viec))
    if da_lam:
        print("  ⏩ TIẾP TỤC: bỏ qua %d văn bản đã hỏi lần trước" % len(da_lam))
    print("  Ghi ra  : %s" % kq_p)
    print("=" * 90)
    if not a.apply or not viec:
        if not viec:
            print("  Không còn văn bản nào phải làm.")
        else:
            print(">>> Mới là XEM TRƯỚC. Thêm --apply để gọi Gemma thật.")
        return

    qlk = QuanLyKey()
    qlk.kiem_tra(hien_thi=False)
    print("  Key dùng được: %d/%d" % (qlk.con_song(), len(qlk.keys)))
    print("-" * 90)

    f_kq = io.open(kq_p, "a", encoding="utf-8", newline="\n")
    t0 = time.perf_counter()
    tong = len(viec)

    def lam(v):
        doc, f, t, cu = v
        ten, ly = hoi(qlk, doc, duoi_van_ban(t))
        with _khoa:
            _so["xong"] += 1
            if ten is None:
                _so["hong"] += 1
            elif ten:
                _so["thay"] += 1
            else:
                _so["khong"] += 1
            f_kq.write(json.dumps({"doc": doc, "file": f.name, "regex": cu,
                                   "gemma": ten, "ly_do": ly},
                                  ensure_ascii=False) + "\n")
            f_kq.flush()
            r = _so["xong"]
            con = (time.perf_counter() - t0) / r * (tong - r) / 60
            print("  %4d/%-4d  %s  regex=%-20s gemma=%-24s | còn ~%.0f phút"
                  % (r, tong, doc, (cu or "—")[:20],
                     (ten if ten else ("(không rõ)" if ten == "" else "HỎNG"))[:24], con))

    try:
        with ThreadPoolExecutor(max_workers=a.song_song) as ex:
            list(ex.map(lam, viec))
    except KeyboardInterrupt:
        print("\n⏸ Đã dừng tay. Điểm lưu còn — chạy lại là đi tiếp.")
    finally:
        f_kq.close()

    print("-" * 90)
    print("Xong %d | Gemma đọc được tên: %d | model nói không rõ: %d | hỏng: %d"
          % (_so["xong"], _so["thay"], _so["khong"], _so["hong"]))
    print("Kết quả: %s" % kq_p)


if __name__ == "__main__":
    main()
