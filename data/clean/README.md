# Kho văn bản đã OCR

## Dùng cái nào

**`text_final/` — 455 văn bản. Đây là kho chuẩn, dùng cái này.**

`text_clean_gemma/` là bản cũ, giữ lại vì `data/kg/documents.jsonl` và
`src/vanban/config.py` còn trỏ vào nó. Khi chuyển sang `text_final` thì sửa
`config.py` và chạy lại `python run.py kg docs`.

| | `text_clean_gemma` | **`text_final`** |
|---|---|---|
| Số văn bản | 460 | **455** |
| Đọc được người ký | ~50% | **99%** |
| Đọc được ngày ban hành | ~89% | **100%** |
| Watermark quảng cáo | còn | **đã dọn** |
| Bản bị website gắn nhầm | còn | **đã loại** |

## `text_final` được dựng thế nào

Với **từng văn bản**, chọn bản OCR tốt hơn giữa bản cũ và bản OCR lại bằng Gemma,
qua cổng lọc năm điều kiện:

1. không còn dấu `[[KHÔNG OCR ĐƯỢC]]`
2. tỷ lệ dấu tiếng Việt ≥ 12% (thật thường 18–23%; dưới 12% là bản hỏng)
3. giữ được ≥ 85% số chữ cái của bản cũ
4. **không mất người ký** mà bản cũ đọc được
5. **phải thêm được thông tin** — người ký, ngày, quan hệ, hoặc sửa ngày sai

Điều 4 và 5 là phần quan trọng. Đã đo được trường hợp bản mới **dài hơn** bản cũ
nhưng lại **mất người ký** (`0255`, vì thiếu 4 khúc chứa khối ký). Gộp theo độ dài
là gộp nhầm.

Kết quả: lấy bản Gemma cho **196** văn bản, giữ bản cũ cho phần còn lại.

## Chất lượng đo được

| | |
|---|---|
| Ngày ban hành | **455 / 455 (100%)** — 0 ngày không hợp lệ |
| Người ký | **451 / 455 (99%)** |
| Căn cứ pháp lý | 424 / 455 (93%) — 2.089 căn cứ |
| Quan hệ hiệu lực | 233 (51%) |
| Cấu trúc Điều | 412 (91%) — 9.734 Điều / 33.956 Khoản |
| Đủ cả ngày + người ký + căn cứ | **422 / 455 (93%)** |
| Thiếu cả ba | **0** |
| Tỷ lệ dấu < 12% (bản hỏng) | **0** |
| Rác | **0** |

## Bốn văn bản còn thiếu người ký

`0304`, `0460`, `0494` là **biểu mẫu phụ lục** — chỗ ký ghi
`(Ký, ghi rõ họ tên và đóng dấu)`, tức chỗ trống để người dùng điền. Không có người
ký là **đúng**, không phải lỗi OCR.

## Năm văn bản đã loại — website nguồn gắn nhầm file

Xem `data/../processed/_cach_ly_ban_sai/` ở bản local. Đã đối chiếu md5 toàn bộ PDF
rồi **mở từng file đọc tận mắt**:

| id | Mục lục ghi | PDF thật là | Trùng với |
|---|---|---|---|
| `0326` | 51/2012/TT-**TTCP** | 51/2012/TT-**BGDĐT** | `0296` |
| `0327` | 39/2013/TT-**TTCP** | 39/2013/TT-**BGDĐT** | `0297` |
| `0329` | 23/2016/TT-BGD**&**ĐT | 23/2016/TT-BGDĐT | `0165` |
| `0198` | 21/2020/TT-BGDĐT | **12/2019/TT-BNV** (Bộ Nội vụ) | `0197` |
| `0282` | 10/2022/QH15 | **43/2019/QH14** (Luật Giáo dục) | `0089` |

Đã thử tải lại cả ba URL — **md5 giống hệt**, tức lỗi nằm ở chính `dut.udn.vn` chứ
không phải ở khâu crawl. `file_url` trong `metadata.csv` nói thẳng ra điều đó: mục
"Luật thực hiện dân chủ ở cơ sở" trỏ tới `.../4. Luat so 43_2019_QH14. luat giao duc
2019.pdf`.

Giữ lại thì mỗi văn bản sinh một node mang số hiệu riêng nhưng **nội dung trùng**
node khác. Cạnh `BASED_ON` / `AMENDS` của văn bản thật bị nhân đôi sang node giả,
làm lệch PageRank, bậc vào/ra, và cả bộ đánh giá retrieval.
`neo4j_load` gộp theo **số hiệu** nên không bắt được — chúng khác số hiệu.

## Mười lăm văn bản không có trong kho

Mục lục website liệt kê **475**, tải về được **460**. Mười lăm cái còn lại **không có
file nào** — đã thử tải lại, cả 15 đều trả **404**. File chưa từng được đăng hoặc đã
bị gỡ khỏi máy chủ.

Đáng tiếc nhất: `41/2024/QH15` (Luật Bảo hiểm xã hội 2024), `36/2024/QH15` (Luật
Trật tự an toàn giao thông đường bộ 2024), `115/2020/NĐ-CP`, `75/2012/NĐ-CP`.

Chúng vẫn xuất hiện trong graph dưới dạng `Document` **stub** khi bị văn bản khác
viện dẫn — đúng như Ontology §1.

## Ba thứ trông như rác nhưng là nội dung thật, đừng dọn

1. **Dấu chấm dẫn** trong Mục lục (`Điều 1 ......... 5`) và chỗ trống biểu mẫu —
   136 file, 7.011 lần. Đây là cách trình bày thật của văn bản hành chính.
2. **Chữ Cyrillic** trong 4 file: `ТРКИ Тест по русскому языку` — tên kỳ thi tiếng
   Nga, được liệt kê trong quy định chứng chỉ ngoại ngữ.
3. **Khối `[Khối ký — ...]`** ở cuối một số file — khối ký được OCR lại riêng rồi
   chèn thêm vào, vì bản OCR gốc không bắt được (con dấu đè lên chữ, bố cục hai cột
   bị xáo). Có dán nhãn rõ để phân biệt với phần OCR gốc.

## Mốc trang

Mốc `----- [Trang N] -----`. Một điểm cần biết: các văn bản lấy từ bản OCR lượt hai
được gửi theo **khúc 5 trang**, nên mốc của chúng đánh theo trang đầu mỗi khúc
(`1, 6, 11, 16…`) chứ không phải từng trang. Định vị được trong khoảng 5 trang, đủ
cho đồ thị tri thức nhưng chưa đủ nếu cần trích dẫn chính xác số trang.
