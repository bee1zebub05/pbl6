# -*- coding: utf-8 -*-
"""Kiem tra sach_hoa.py bang DUNG cac kieu tra loi that cua Gemini da gap.

Chay:  python test_sach_hoa.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sach_hoa import lam_sach, kiem_dinh

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

NOI_DUNG = (
    "BỘ GIÁO DỤC VÀ ĐÀO TẠO\n"
    "Số: 5778/BGDĐT-QLCL\n"
    "V/v ứng dụng công nghệ thông tin trong thực hiện KĐCLGD\n\n"
    "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\n"
    "Độc lập - Tự do - Hạnh phúc\n\n"
    "Hà Nội, ngày 13 tháng 12 năm 2021\n\n"
    + "Nội dung điều khoản cho đủ dài để vượt ngưỡng kiểm định. " * 12
    + "\n\nKT. BỘ TRƯỞNG\nTHỨ TRƯỞNG\nHoàng Minh Sơn"
)

dat = hong = 0


def kiem(ten, dieu_kien, chi_tiet=""):
    global dat, hong
    if dieu_kien:
        print("  ✔ " + ten); dat += 1
    else:
        print("  ✖ " + ten + (("\n      " + chi_tiet) if chi_tiet else "")); hong += 1


def sach(t):
    return lam_sach(t)[0]


print("\n[1] Văn bản thuần — phải giữ nguyên")
r = sach(NOI_DUNG)
kiem("bắt đầu bằng 'BỘ GIÁO DỤC'", r.startswith("BỘ GIÁO DỤC"))
kiem("giữ đủ nội dung", len(r) >= len(NOI_DUNG) - 5)

print("\n[2] Markdown: câu dẫn + rào ```text")
r = sach("Dưới đây là toàn bộ nội dung văn bản được OCR và chuyển sang plaintext:\n\n"
         "```text\n" + NOI_DUNG + "\n```")
kiem("hết câu dẫn", "Dưới đây" not in r)
kiem("hết dấu rào", "```" not in r)
kiem("bắt đầu đúng", r.startswith("BỘ GIÁO DỤC"), r[:60])

print("\n[3] Code Python ghi file (có \"\"\" đóng)")
r = sach('# Read and prepare the OCR text in UTF-8 file\n'
         'text_content = """' + NOI_DUNG + '"""\n\n'
         'filename = "cv.txt"\n'
         'with open(filename, "w", encoding="utf-8") as f:\n'
         '    f.write(text_content)\n\n'
         'print(f"File saved successfully as {filename}")')
kiem("hết 'text_content ='", "text_content =" not in r)
kiem("hết 'with open'", "with open" not in r)
kiem("hết 'File saved'", "File saved" not in r)
kiem("bắt đầu đúng", r.startswith("BỘ GIÁO DỤC"), r[:60])

print("\n[4] Code Python BỊ CẮT CỤT (thiếu \"\"\" đóng)")
r = sach('text_content = """' + NOI_DUNG[:600])
kiem("vẫn bóc được", r.startswith("BỘ GIÁO DỤC"), r[:60])
kiem("hết 'text_content ='", "text_content =" not in r)

print("\n[5] Chuỗi Python 1 dòng, xuống dòng dạng \\n")
r = sach('text_content = "' + NOI_DUNG.replace("\n", "\\n") + '"\n'
         'with open("a.txt","w") as f: f.write(text_content)')
kiem("đã đổi \\n thành xuống dòng thật", r.count("\n") > 5, "chỉ có %d dòng" % r.count("\n"))
kiem("bắt đầu đúng", r.startswith("BỘ GIÁO DỤC"), r[:60])

print("\n[6] Rào markdown NẰM TRONG câu trả lời có cả chữ ở cuối")
r = sach("Đây là kết quả:\n\n```text\n" + NOI_DUNG + "\n```\n\nBạn có cần gì thêm không?")
kiem("hết dấu rào", "```" not in r)
kiem("hết câu hỏi thừa ở cuối", "cần gì thêm" not in r)

print("\n[7] Kiểm định — thứ KHÔNG được phép ghi ra file")
kiem("từ chối text quá ngắn", not kiem_dinh("abc")[0])
kiem("từ chối text vẫn là mã nguồn",
     not kiem_dinh('import os\nfor i in range(10):\n    print(i)\n' + "x" * 300)[0])
kiem("từ chối 20 trang mà chỉ 500 ký tự", not kiem_dinh("BỘ GIÁO DỤC\n" + "a" * 500, so_trang=20)[0])
kiem("chấp nhận văn bản thật", kiem_dinh(NOI_DUNG, so_trang=1)[0])

print("\n[8] Toàn tuyến: bẩn → lam_sach → kiem_dinh phải ĐẠT")
ban = ('Dưới đây là nội dung:\n\n```python\n'
       'text_content = """' + NOI_DUNG + '"""\n'
       'with open("a.txt","w") as f: f.write(text_content)\n```')
r, viec = lam_sach(ban)
ok, vi_sao = kiem_dinh(r, so_trang=1)
kiem("qua được kiểm định", ok, vi_sao)
kiem("sạch hoàn toàn",
     "```" not in r and "text_content" not in r and "with open" not in r, r[:80])
print("      việc đã làm: %s" % ", ".join(viec))

print("\n───────── %d đạt, %d hỏng ─────────\n" % (dat, hong))
sys.exit(1 if hong else 0)
