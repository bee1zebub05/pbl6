# `kiem_tra/` — đo chất lượng kho `text_final`

Đọc toàn bộ `data/clean/text_final` rồi kiểm từng trường mà knowledge graph cần, mỗi
nhóm có **ngưỡng báo động riêng** chứ không chỉ đếm.

```bash
python tools/kiem_tra/kiem_ban_cuoi.py
```

Ra `data/kiem_tra/bao_cao_ban_cuoi.csv` — mỗi văn bản một dòng, kèm bản tóm tắt in ra
màn hình.

## Sáu nhóm kiểm

| Nhóm | Kiểm gì |
|---|---|
| 1 | Sức khoẻ văn bản — độ dài, tỷ lệ dấu tiếng Việt, rác còn sót |
| 2 | Ngày ban hành — có đọc được không, và có **hợp lệ** không (không phải 32/13) |
| 3 | Người ký — họ tên, chức danh, học hàm |
| 4 | Căn cứ pháp lý — `Căn cứ <loại> số <X>` |
| 5 | Quan hệ hiệu lực — `REPLACES` / `AMENDS` / `REPEALS` và ba chiều ngược |
| 6 | Cấu trúc Điều / Khoản |

Văn bản **không có người ký chưa chắc là lỗi**: công văn, thông báo, bản sao y đều có
thể không có khối ký. Nên báo cáo tách theo loại văn bản để biết chỗ nào đáng lo thật.

## Các file

| File | Vai trò |
|---|---|
| `kiem_ban_cuoi.py` | Điểm vào, gom sáu nhóm và xuất CSV |
| `trich_do_thi.py` | Số hiệu, ngày, người ký, căn cứ; tách metadata từ tên file |
| `trich_dieu_khoan.py` | Cắt Điều / Khoản thành node `Article` |
| `quan_he_hieu_luc.py` | Phân loại quan hệ hiệu lực giữa các văn bản |
| `trich_don_vi.py` | Nhận diện đơn vị, tổ chức |
| `chuan_ten_ky.py` | Chuẩn hoá tên người ký |

Chỉ sáu file này là đủ để dựng lại báo cáo — đã kiểm bằng cách lần theo đồ thị import.

## So với bản gốc và truy nguồn trang

Hai công cụ dưới đây cần PDF gốc trong `data/raw/pdf/` (ngoài git, 2,3 GB).

| File | Vai trò |
|---|---|
| `ocr_gold.py` | Bộ chuẩn OCR theo trang: chọn trang, xuất ảnh, chấm `text_final` bằng CER, từ thiếu/thừa và token chứa chữ số. Xem `data/eval/ocr_gold/README.md` |
| `nguon_trang.py` | `data/clean/nguon_trang/`: manifest PDF có SHA-256, và bảng Điều -> trang PDF kèm độ tin cậy, dùng cho `LKG_PAGE_PROVENANCE` khi build graph |

Mốc `[Trang N]` của `text_final` chỉ khớp đủ 1..N với PDF ở 285/450 văn bản; 82 văn
bản tăng dần nhưng thiếu trang, 83 văn bản lộn xộn hoặc chia theo khúc 5 trang. Vì vậy
bảng Điều -> trang ghi độ tin cậy, và chatbot chỉ dẫn số trang khi độ tin cậy là `cao`
(đối chiếu với bộ chuẩn: 21/22 Điều mức `cao` đúng trang).

## Ba chỗ dễ đọc sai, đã xử lý

**Tiêu đề Điều dài hơn một dòng.** Trong quyết định, Điều 1/2/3 thường là cả đoạn nằm
trọn trên một dòng (đo được 148–392 ký tự). Mẫu nhận diện **không được chặn độ dài**,
nếu không sẽ trượt sạch cả văn bản — từng làm 15 văn bản ra 0 Điều dù có đủ.

**Công văn không có mã loại.** Số hiệu công văn là `<số>/<cơ quan>-<đơn vị soạn>`
(`4079/ĐHĐN-TCCB`), vế trái là **cơ quan** chứ không phải loại văn bản. Rơi ra ngoài
bảng mã loại hợp lệ thì xếp là `CV`.

**Ngày ban hành của Luật nằm ở cuối.** Luật không ghi ngày ở đầu như quyết định, mà ở
câu `"Luật này đã được Quốc hội … thông qua ngày X tháng Y năm Z"`. Cột `ngay` giữ
nguyên chuỗi khớp để còn đối chiếu, cột `ngay_iso` mới là dạng `YYYY-MM-DD` để nạp.
