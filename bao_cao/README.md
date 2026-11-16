# Báo cáo PBL6

| Tệp | Nội dung |
|---|---|
| `Bao_cao_PBL6.docx` | Bản báo cáo đầy đủ, 42 trang, dựng trên mẫu của Khoa (16/11/2026) |
| `Mau_bao_cao_PBL6_KhoaCNTT.docx` | Mẫu gốc của Khoa, chưa sửa |

Việc còn lại trước khi nộp: xem [TODO.md](../TODO.md) ở gốc repo.

## Cách sửa báo cáo

`.docx` là tệp nhị phân nên Git không gộp được hai bản sửa cùng lúc. Quy ước:

1. Mỗi người đọc soát phần được giao trong TODO.md, ghi chỗ cần sửa bằng **Comment** hoặc
   **Track Changes** của Word trên bản của mình, rồi gửi cho Kiên.
2. Chỉ Kiên ráp các thay đổi vào `Bao_cao_PBL6.docx` và commit. Trước khi sửa, `git pull` để
   lấy bản mới nhất.
3. Sửa xong nội dung thì cập nhật lại mục lục: chuột phải vào mục lục → **Update Field** →
   **Update entire table**; làm tương tự với danh mục hình và danh mục bảng.

## Quy định trình bày (theo mẫu của Khoa)

- Khổ A4; lề trái 3 cm, lề phải, trên, dưới 2 cm.
- Nội dung: Times New Roman 13, giãn dòng 1,3, căn đều hai bên; dùng style `0-NDUNG`.
- Đề mục dùng style `Heading 1/2/3` (tự đánh số, mỗi chương sang trang mới).
- Chú thích hình dùng style `4-HINH` (đặt dưới hình), chú thích bảng dùng `6-BANG` (đặt trên bảng),
  gõ số theo chương, ví dụ "Hình 3.2. …", "Bảng 4.1. …".
- Số thập phân dùng dấu phẩy (0,75).

## Nguồn số liệu

Mọi con số trong báo cáo lấy từ code và kết quả đã chạy trong repo. Khi thay số, ghi rõ đo trên
kho nào (454 văn bản JSON v1/v2, hay 103 văn bản JSON v4 mà đồ thị và chatbot đang dùng) và
ngày đo. Nhãn đánh giá v4 và bộ chuẩn OCR 20 trang hiện do mô hình gán; khi viết phải ghi rõ.
