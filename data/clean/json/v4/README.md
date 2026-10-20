# v4 — 103 văn bản liên quan người học

Trích từ `data/clean/sinh_vien_103/text/` bằng `tools/gemini_web/cau_json.py`
(đường trình duyệt) và `tools/gemini_api/chay_json.py` (đường API). Hai đường
dùng chung `cau_json.PROMPT` nên không lệch bản.

```
file               103      schema hỏng        0
Điều/mục         2.281      bản kèm theo      75
nguyên văn so txt  93,0%    organization     103/103 trong seed
targetGroups     103/103    người ký         102/103
```

## Khác v1/v2 ở đâu

`targetGroups` lần đầu được điền — v1 và v2 chưa có trường này. 103/103 file có,
mọi giá trị khớp `reference/target_groups_seed.json`.

`organization.name` dùng tên chuẩn trong seed cho cả 103 file. Trước đây ĐHBK
từng bị tách làm 4 node chỉ vì khác cách viết.

`normativeContents` nhận thêm bản kèm theo **không đánh số bằng Điều**. Đo trên
kho: 26/149 bản kèm theo (17%) không có Điều nào — Quy trình 7, Kế hoạch 7,
Chương trình 6. `$defs.article.number` nay nhận `1`, `2.1`, và số La Mã
`I`..`XXXIX` (64 file trong kho dùng La Mã, nhiều hơn cả số Ả Rập là 44).

`contentType` thêm `Phụ lục`. 96/454 văn bản có phần kèm theo là Phụ lục mà
enum cũ không có, nên model buộc phải khai thành `Quy định` hoặc `Hướng dẫn`.

## Đọc cảnh báo thế nào

Thư mục `_nghi_ngo/` là **hàng đợi soi tay**, không phải kết luận file sai.
Cảnh báo `ho noi dung giua <khối>` đo độ phủ của thân Điều trong `.txt`, đo
riêng từng khối (các Điều của văn bản, rồi từng bản kèm theo) vì chúng nằm
rời nhau trong `.txt`.

Ba loại báo oan đã biết, đều đã soi tay và xác nhận là model làm đúng:

**Bảng biểu.** Phụ lục dạng bảng phải dàn thành văn xuôi (luật 3a) nên không
thể trùng khít `.txt`. Gặp ở 0013, 0017, 0449, 0462, 0226.

**Biểu mẫu điền tay.** 0156 có `....(1).... cấp TÊN VĂN BẰNG (BẢN SAO) ...
Cho: ....(4)....` nằm giữa các mục — không phải văn bản quy phạm, model bỏ đúng.

**Phụ lục là danh mục.** 0004 có 81 KB txt mà 78 KB là danh sách tên 3.434 xã;
model lấy 5 Điều và không tạo `normativeContents`. Đúng.

## Hai điểm cần quyết

**`Hội Sinh viên` và `Hội Sinh viên Việt Nam` chưa gộp.** 0074 viết "Đoàn Thanh
niên - Hội Sinh viên **Trường**" (cấp trường), 0012 viết "Hội Sinh viên Việt
Nam" (trung ương). Không chứng minh được là một tổ chức nên để riêng.

**11 node tổ chức chưa có `orgType`**: Hội Sinh viên, Hội Sinh viên Việt Nam,
Kho bạc Nhà nước, Kiểm toán nhà nước, Bảo hiểm xã hội Việt Nam, Công an nhân
dân, Công an phường (xã), Quân đội nhân dân Việt Nam, Đại học Quốc gia, Trung
tâm Thông tin học liệu và Truyền thông, Đoàn TNCS Hồ Chí Minh. Gán kiểu cho
chúng phải suy từ kiến thức ngoài văn bản nên để trống, chờ người quyết.

## Gộp tên cơ quan mà không sửa data

`graph_model._load_seed` map `slug(name) -> orgId`. Hai **dòng** seed khác
`name` mà cùng `orgId` thì hai cách viết về cùng một node, không phải sửa một
chữ nào trong JSON. Đang dùng cho `Đoàn TNCS Hồ Chí Minh` và `Đoàn Thanh niên
Cộng sản Hồ Chí Minh`.

Dòng sau ghi đè tên hiển thị, nên **tên đầy đủ phải đặt sau** — đừng đổi thứ
tự hai dòng đó trong `organizations_seed.json`.
