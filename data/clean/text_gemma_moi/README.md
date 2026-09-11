# `text_gemma_moi` — lượt OCR thứ hai

287 văn bản được OCR lại lần hai. **Chưa thay thế `text_clean_gemma`** — để song
song để đối chiếu, gộp sau khi qua cổng lọc chất lượng.

## Vì sao phải OCR lại

Bản đầu đọc bằng Gemini qua giao diện web, và nó **xáo trộn khối ký hai cột**:
phần "Nơi nhận" bên trái với khối chữ ký bên phải bị trộn vào nhau, nên tên người
ký hoặc mất hẳn hoặc dính vào danh sách nơi nhận.

Đo trên cùng một bộ file:

| Nguồn OCR | Đọc được người ký |
|---|---|
| Gemini qua web (bản đầu) | 33% |
| Gemma qua API (bản này) | 91% |

Người ký là trường không suy ra được từ chỗ nào khác — không có trong tên file,
không có trong metadata crawl. Mất là mất hẳn.

## Trạng thái hiện tại

| | |
|---|---|
| Văn bản | 287 |
| Dung lượng | 12,5 MB |
| Còn khúc thiếu | **21 file / 36 khúc** |

Chỗ thiếu được đánh dấu thẳng trong văn bản:

```
[[KHÔNG OCR ĐƯỢC TRANG 36-40]]
```

36 khúc này **đang được vá tiếp**. Chúng sót lại vì dính `RECITATION` — model
chặn đầu ra khi nhận ra nội dung trùng dữ liệu huấn luyện. Xem `docs/recitation.md`
để biết cách thoát; tóm tắt: phải chia xuống **từng trang** *và* dùng **Gemma
26B**, thiếu một trong hai là vẫn bị chặn.

## So với bản cũ

Sau khi vá được 41/78 chỗ của hai đợt đầu:

| | |
|---|---|
| Tổng ký tự so với `text_clean_gemma` | **1,02x** |
| Số file dài hơn bản cũ | 166/287 |

Lúc chưa vá thì tỷ lệ này là 0,85x — tức **đọc con số trước khi vá xong sẽ ra
kết luận ngược**. Vá nốt 36 chỗ còn lại thì 1,02x sẽ còn tăng.

## Chưa nên gộp thẳng

Bản mới **dài hơn không có nghĩa là tốt hơn ở mọi file**. Đã đo trên 15 file của
đợt đầu: 7 file lấy lại được người ký, nhưng 1 file (`0255`) **mất** người ký so
với bản cũ vì thiếu mất 4 khúc chứa khối ký.

Nên gộp bằng cổng lọc nhiều điều kiện, không gộp bằng cách so độ dài:

1. không còn dấu `[[KHÔNG OCR ĐƯỢC]]`
2. tỷ lệ dấu tiếng Việt ≥ 12% (thật thường 18–23%; dưới 12% là bản hỏng)
3. giữ được ≥ 85% số chữ cái của bản cũ
4. **phải thêm được thông tin** — người ký, hoặc ngày ban hành, hoặc quan hệ

Điều kiện 4 là điều kiện quan trọng nhất: nó bảo đảm việc gộp luôn đổi lấy một
thứ cụ thể, chứ không chỉ đổi bản OCR này lấy bản OCR khác.

## Hai file phải cứu riêng

`0124` và `0328` hỏng toàn bộ qua **ba lượt chạy**, mỗi lượt đều trả về đúng
52 ký tự — dấu hiệu của từ chối cứng chứ không phải lỗi mạng. Cứu được bằng
cách gửi từng trang qua Gemma 26B:

| | ký tự | tỷ lệ dấu | người ký |
|---|---|---|---|
| `0124` | 4.357 | 28,4% | Lê Minh Khái — Phó thủ tướng |
| `0328` | 11.274 | 30,7% | Phạm Ngọc Thưởng — Thứ trưởng |

Riêng `0328` có sẵn text layer nhưng **không dùng được**: tỷ lệ dấu chỉ 7,7%,
đọc ra `"BQ GIAO DUC vA BAO TJO"` thay vì `"BỘ GIÁO DỤC VÀ ĐÀO TẠO"`.
