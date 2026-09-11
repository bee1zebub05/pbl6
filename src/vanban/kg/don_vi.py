"""
Nhận diện ĐƠN VỊ được nhắc tới trong thân văn bản -> `Organization` (Ontology §2.2).

Khác với `ISSUED_BY` (đơn vị BAN HÀNH, suy được từ số hiệu), đây là đơn vị được
NHẮC TỚI bên trong nội dung: "Phòng Đào tạo chịu trách nhiệm...", "Khoa Cơ khí
phối hợp...". Nhờ nó mới hỏi được "văn bản nào liên quan tới Phòng Khảo thí" —
câu mà tra theo cơ quan ban hành không trả lời nổi.

VÌ SAO DÙNG TỪ ĐIỂN, KHÔNG DÙNG PhoBERT

Tập đơn vị của một trường đại học là tập ĐÓNG và nhỏ (~36 đơn vị). Mô hình NER
học sâu giải bài toán MỞ — nhận diện tên riêng chưa từng thấy. Ở đây thì ngược
lại: ta biết trước chính xác có những đơn vị nào, vấn đề chỉ là CHUẨN HOÁ cách
viết. Trong dữ liệu thật, cùng một đơn vị được viết ít nhất ba kiểu:

    "Phòng KHCN" = "Phòng Khoa học Công nghệ" = "Phòng KH&CN"
    "Phòng TCHC" = "Phòng Tổ chức Hành chính"
    "Phòng CTSV" = "Phòng Công tác sinh viên"

PhoBERT nhận ra cả ba là thực thể, nhưng KHÔNG biết chúng là MỘT — vẫn phải có
từ điển để gộp. Nên từ điển làm được cả hai việc, lại rẻ và kiểm chứng được từng
dòng. Nếu hội đồng yêu cầu mô hình học sâu thì đây vẫn là bước tiền xử lý.

HAI CÁI BẪY, cả hai đều đo được trên dữ liệu thật

1. Chỉ nhận cụm CÓ TRONG TỪ ĐIỂN, không bắt mọi "Phòng + chữ hoa".
   Bắt bừa thì "Ban Giám hiệu ý kiến của", "Ban Giám hiệu sẽ cho ý" cũng thành
   đơn vị — hai cụm này xuất hiện 64 và 49 lần trong kho.

2. BẮT BUỘC có ranh giới từ, không được so khớp chuỗi con.
   Mẫu "khoa hoa" lọt vào "khoa hoặc" (trong "khoa hoặc đơn vị phụ trách"). Đã
   đo: bỏ ranh giới từ thì "Khoa Hóa" ra 51 lượt, thêm vào thì còn 7 — tức 44
   lượt kia đều là bắt nhầm.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

# Tên chuẩn -> các cách viết khác (viết tắt, thiếu từ, sai chính tả do OCR).
# So khớp sau khi BỎ DẤU và thu gọn khoảng trắng, nên không cần liệt kê biến thể dấu.
DON_VI: dict[str, list[str]] = {
    "Ban Giám hiệu": ["ban giam hieu", "bgh"],
    "Hội đồng trường": ["hoi dong truong", "hdt"],
    "Phòng Đào tạo": ["phong dao tao", "phong dt"],
    "Phòng Khoa học Công nghệ": [
        "phong khoa hoc cong nghe", "phong khcn", "phong kh&cn", "phong kh cn",
        "phong khoa hoc va cong nghe"],
    "Phòng Tổ chức Hành chính": [
        "phong to chuc hanh chinh", "phong tchc", "phong to chuc  hanh chinh"],
    "Phòng Công tác sinh viên": [
        "phong cong tac sinh vien", "phong ctsv",
        "phong cong tac hoc sinh sinh vien"],
    "Phòng Kế hoạch Tài chính": [
        "phong ke hoach tai chinh", "phong khtc", "phong ke hoach  tai chinh",
        "phong ke hoach va tai chinh"],
    "Phòng Khảo thí và Đảm bảo chất lượng giáo dục": [
        "phong khao thi va dam bao chat luong giao duc",
        "phong khao thi va dam bao", "phong kt&dbclgd", "phong ktdbcl",
        "phong khao thi"],
    "Phòng Thanh tra Pháp chế": [
        "phong thanh tra phap che", "phong ttpc", "phong thanh tra  phap che"],
    "Phòng Cơ sở vật chất": ["phong co so vat chat", "phong csvc"],
    "Phòng Hợp tác quốc tế": ["phong hop tac quoc te", "phong htqt"],
    "Trung tâm Học liệu và Truyền thông": [
        "trung tam hoc lieu va truyen thong", "trung tam hoc lieu", "tt hoc lieu"],
    "Trung tâm Công nghệ thông tin": [
        "trung tam cong nghe thong tin", "trung tam cntt", "tt cntt"],
    "Ban Thanh tra nhân dân": ["ban thanh tra nhan dan"],
    "Ban Tổ chức Cán bộ": ["ban to chuc can bo", "ban tccb"],
    "Ban Đào tạo": ["ban dao tao"],
    "Ban Khoa học Công nghệ và Môi trường": [
        "ban khoa hoc cong nghe va moi truong", "ban khcn&mt", "ban khcn va mt"],
    "Ban Kế hoạch Tài chính": ["ban ke hoach tai chinh", "ban khtc"],
    "Ban Hợp tác quốc tế": ["ban hop tac quoc te", "ban htqt"],
    "Ban Công tác học sinh sinh viên": [
        "ban cong tac hoc sinh sinh vien", "ban cthssv"],
    "Đảng ủy": ["dang uy"],
    "Công đoàn": ["cong doan truong", "ban chap hanh cong doan"],
    "Đoàn Thanh niên": ["doan thanh nien", "doan tncs ho chi minh"],
    "Hội Sinh viên": ["hoi sinh vien"],
    "Khoa Cơ khí": ["khoa co khi"],
    "Khoa Điện": ["khoa dien"],
    "Khoa Điện tử Viễn thông": ["khoa dien tu vien thong", "khoa dtvt"],
    "Khoa Công nghệ thông tin": ["khoa cong nghe thong tin", "khoa cntt"],
    "Khoa Xây dựng Dân dụng và Công nghiệp": [
        "khoa xay dung dan dung va cong nghiep", "khoa xd ddcn"],
    "Khoa Hóa": ["khoa hoa"],
    "Khoa Môi trường": ["khoa moi truong"],
    "Khoa Kiến trúc": ["khoa kien truc"],
    "Khoa Quản lý dự án": ["khoa quan ly du an"],
    "Khoa Cơ khí Giao thông": ["khoa co khi giao thong"],
    "Khoa Công nghệ Nhiệt Điện lạnh": ["khoa cong nghe nhiet dien lanh"],
    "Viện Khoa học và Công nghệ": ["vien khoa hoc va cong nghe", "vien kh&cn"],
}

# Ontology §2.2 orgType — suy từ tiền tố tên, dùng khi nạp node Organization.
_ORG_TYPE = (
    ("phòng", "phong_ban"),
    ("tổ ", "phong_ban"),
    ("ban ", "don_vi_truc_thuoc"),
    ("khoa", "don_vi_truc_thuoc"),
    ("trung tâm", "don_vi_truc_thuoc"),
    ("viện", "don_vi_truc_thuoc"),
)


def bo_dau(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("đ", "d").replace("Đ", "D").lower()

    return re.sub(r"\s+", " ", s).strip()


def org_type(ten: str) -> str:
    t = (ten or "").lower()

    for tien_to, kieu in _ORG_TYPE:
        if t.startswith(tien_to):
            return kieu

    return "don_vi_truc_thuoc"


# Dùng biến thể DÀI trước: "phong khoa hoc cong nghe" phải khớp trước "phong khcn"
# để không cắt cụt tên.
_MAU: list[tuple[re.Pattern, str, str]] = []

for _chuan, _ds in DON_VI.items():
    for _x in sorted(_ds, key=len, reverse=True):
        _MAU.append(
            (re.compile(r"(?<![a-z0-9])" + re.escape(_x) + r"(?![a-z0-9])"),
             _x, _chuan)
        )

_MAU.sort(key=lambda p: -len(p[1]))


def tim_don_vi(text: str) -> Counter:
    """-> {tên chuẩn: số lần xuất hiện} trong một văn bản."""

    b = bo_dau(text)
    ra: Counter = Counter()

    for bieu_thuc, mau, chuan in _MAU:
        v = list(bieu_thuc.finditer(b))

        if not v:
            continue

        ra[chuan] += len(v)

        # Xoá chỗ đã khớp để biến thể ngắn hơn không đếm lại cùng một chỗ.
        # Thay bằng khoảng trắng cùng độ dài để không xô lệch vị trí các khớp sau.
        b = bieu_thuc.sub(" " * len(mau), b)

    return ra
