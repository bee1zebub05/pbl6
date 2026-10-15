# Tập 103 văn bản liên quan đến sinh viên

Tập con của `data/clean/text_final/` (454 file, 439 số hiệu riêng biệt), chỉ gồm các văn bản liên quan
đến người học (sinh viên, học viên cao học, nghiên cứu sinh, thí sinh) theo yêu cầu của thầy hướng dẫn.
Các file là **bản sao**; kho gốc không bị thay đổi.

| Thư mục / file | Nội dung |
|---|---|
| `text/<lĩnh vực>/` | 103 file `.txt` chép từ `text_final` |
| `json_v2/<lĩnh vực>/` | 103 file JSON v2 tương ứng, dùng làm bản nháp để gán lại bằng tay |
| `danh_sach.csv` | Danh sách 103 văn bản, mở bằng Excel. Có cột đối tượng, điều liên quan, lý do, câu hỏi ví dụ, và cột trống `nguoi_gan`, `trang_thai`, `ghi_chu` để chia việc |
| `phan_loai_toan_bo_454.csv` | Kết quả phân loại cả 454 file, để tra vì sao một văn bản bị loại |

## Cách chọn

1. Với mỗi file trong `text_final`, trích ba phần: đầu văn bản, mục "Phạm vi điều chỉnh / Đối tượng áp dụng"
   (hoặc Điều 1), và danh sách tiêu đề Chương/Điều.
2. Chia 454 file cho 10 agent (mô hình ngôn ngữ) đọc song song. Mỗi agent xếp từng văn bản vào một mức
   (A, B, C, KHONG) kèm lý do. Khi phần trích không đủ, agent đọc thêm phần đầu file gốc.
3. Gộp các bản trùng số hiệu, giữ bản có mức cao nhất. Lấy mức A và B: **103 văn bản**.
4. Thống nhất mức giữa các agent: mọi quy chế/quy định đào tạo (kể cả sau đại học, liên thông) và văn bằng
   xếp A; tuyển sinh xếp B.

| Mức | Số văn bản | Ý nghĩa |
|---|---|---|
| A | 53 | Quy định trực tiếp quyền, nghĩa vụ, thủ tục, chế độ của người học: công tác sinh viên, rèn luyện, học bổng, học phí, khen thưởng, quy chế đào tạo, đánh giá, đồ án, ngoại ngữ, văn bằng, KTX, thư viện |
| B | 50 | Người học là một đối tượng rõ ràng nhưng không phải trọng tâm, hoặc văn bản tuyển sinh, liên kết đào tạo, đào tạo trực tuyến, hợp tác quốc tế, luật khung có chương về người học |

Mức C (110 văn bản, chỉ nhắc người học gián tiếp) và KHONG (226) không được đưa vào.

## Lưu ý khi gán

- Phân loại dựa trên phần phạm vi và mục lục, chưa đọc toàn văn. Khi gán, văn bản nào thấy không liên quan
  thì ghi vào `ghi_chu`.
- 7 văn bản có JSON v2 nằm trong `_nghi_ngo/` (cột `json_nghi_ngo`), cần soi kỹ.
- Có thể đã hết hiệu lực: TTLT 09/2016 (học phí, áp dụng đến năm học 2020-2021); HD 1606/HD-ĐHBK
  (bảo vệ trực tuyến, đến 31/12/2021).
- Lỗi dữ liệu ngoài tập này: `text_final/.../0049_...` mang tên "Quy chế Phòng Thí nghiệm" nhưng nội dung là
  QĐ 771 về dự toán kinh phí; `1280/QĐ-ĐHĐN` thiếu phần quy định đính kèm.
