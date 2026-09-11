# RECITATION — vì sao một số văn bản không bao giờ OCR/hiệu đính được

## Triệu chứng

Một số file hỏng **giống hệt nhau qua mọi lần chạy lại**. Không phải lỗi mạng,
không phải hết quota: chạy lại ba lượt, cả ba đều trả về đúng **52 ký tự**.

Đo trên hai file:

| File | Kích thước | Trang | Text layer |
|---|---|---|---|
| `0124_05_2022_QĐ-TTg` | 0,8 MB | 3 | không có (scan thuần) |
| `0328_14_2021_TT-BGD&ĐT` | 4,7 MB | 5 | có, nhưng **là rác** — tỷ lệ dấu 7,7% |

Text layer của `0328` đọc ra `"BQ GIAO DUC vA BAO TJO"` thay vì
`"BỘ GIÁO DỤC VÀ ĐÀO TẠO"`, nên không dùng thay OCR được.

## Nguyên nhân

Gọi API trực tiếp và in `finish_reason` thì rõ ngay:

```
0124 — gửi trang 1   ->  1618 ký tự,  finish_reason = STOP
0328 — gửi trang 1   ->     0 ký tự,  finish_reason = RECITATION
```

`RECITATION` = model **chặn** đầu ra vì nhận ra nội dung trùng dữ liệu huấn
luyện. Văn bản quy phạm pháp luật công khai thì rất dễ trùng, nên trên kho này
gặp thường xuyên chứ không phải ca hiếm.

Đây là **từ chối cứng**, không phải lỗi tạm thời. Thử lại y hệt là vô ích — đó
chính là lý do ba lần chạy lại cho kết quả giống hệt nhau.

## Cách thoát

Thử đủ 4 model × 2 cách chia trên `0328`:

| Cách gửi | Kết quả |
|---|---|
| Cả file — cả 4 model | RECITATION hết |
| Từng trang — `gemini-3.5-flash-lite` | vẫn RECITATION cả 5 trang |
| Từng trang — `gemini-3.1-flash-lite` | vẫn RECITATION cả 5 trang |
| Từng trang — `gemma-4-31b-it` | 2/5 (3 trang lỗi 500) |
| Từng trang — `gemma-4-26b-a4b-it` | **5/5 đạt** |

Phải thoả **đồng thời hai điều kiện**:

1. **Chia nhỏ** — một đoạn ngắn ít giống "văn bản model đã thuộc" hơn cả khối lớn
2. **Đổi họ model** — bộ lọc recitation của Gemma khác Gemini

Điều kiện (1) là điều kiện quan trọng hơn: đổi model mà vẫn gửi cả file thì
vẫn bị chặn.

Kết quả sau khi cứu:

| | ký tự | tỷ lệ dấu | người ký |
|---|---|---|---|
| `0124` | 4.357 | 28,4% | Lê Minh Khái — Phó thủ tướng |
| `0328` | 11.274 | 30,7% | Phạm Ngọc Thưởng — Thứ trưởng |

## Đã sửa gì trong code

`src/vanban/gemini_fix.py`:

1. Thêm `RecitationError(GeminiError)` và `_la_recitation(response)`.

2. Trong `_call`, tách RECITATION ra **trước** nhánh hạ cấu hình. Trước đây mọi
   response rỗng đều bị quy cho "thinking tiêu hết token" rồi gọi `_downgrade`.
   Với RECITATION thì hạ cấu hình **không gỡ được lệnh chặn**, mà `_variant` lại
   là biến dùng chung cho mọi khối về sau — nên hạ một lần là hỏng oan cả phần
   còn lại của kho.

3. Trong `fix_chunk`, bắt `RecitationError` rồi gọi `_chia_nho_khi_bi_chan`:
   cắt đôi ở ranh giới đoạn gần giữa nhất rồi hiệu đính từng nửa, đệ quy cho tới
   ngưỡng 400 ký tự. Chỉ cần **một** nửa qua được đã hơn hẳn cách cũ là bỏ nguyên
   khối.

Không cắt giữa câu: cắt ẩu thì mỗi nửa mất đầu hoặc mất đuôi câu, model hiệu
đính sẽ "chữa" nó thành một câu khác.

## Còn thiếu

Phần **đổi họ model** khi bị chặn chưa đưa vào `GeminiCorrector` vì lớp này
hiện gắn với một model duy nhất. Nếu sau này gặp đoạn mà chia nhỏ tới ngưỡng
vẫn bị chặn thì đó là việc cần làm tiếp.
