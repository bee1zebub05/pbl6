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

## Đợt sửa lỗi OCR mức ký tự (commit `ad3e512`)

Sau khi dựng xong kho, kho vẫn còn lỗi **mức ký tự** mà cổng lọc năm điều kiện ở trên
không bắt được — vì nó chỉ đo tỷ lệ dấu, độ dài và sự hiện diện của người ký, không
đo **chữ có đúng không**.

Đã sửa **294 / 455 văn bản**. Trong đó **75 văn bản được mở ra đọc từng trang**, phần
còn lại đi qua các lượt sửa theo lớp:

| Việc | Phạm vi |
|---|---|
| Gỡ LaTeX + kẻ bảng markdown do model OCR tự thêm | 163 file |
| Watermark ThuVienPhapLuat/LuatVietnam | sạch tuyệt đối 455/455 |
| Chuẩn hoá mốc trang | 64 + 34 file |
| Bỏ dấu văn thư "đến" chèn giữa câu | 8 chỗ |
| `BÁOISố` → `BÁO/Số` | 714 chỗ |
| `I` hoa đứng thay `l` thường ở đầu từ | 1.612 chỗ |
| Vần `ươ` sai chỗ dấu móc (`truờng` `chưong` `luợng`) | 4.211 chỗ |

Ba lớp cuối là lỗi đặc trưng của OCR sinh bằng VLM: `l`/`I`/`/` gần như trùng glyph ở
độ phân giải scan, còn dấu móc của `ươ` là nét ~2 pixel nên model gắn sai vị trí.

Với lớp `ươ` **chỉ nhận cặp mà bản in đã có sẵn dấu móc** (ư hoặc ơ), tức chính trang
giấy đã chứng minh vần là `ươ`. Đã loại hết dạng `uo` không dấu (`chuong` `luong`
`thuong`) vì nó lẫn giữa `ương` và `uông` — không có căn cứ để chọn.

**Nguyên tắc áp dụng xuyên suốt:** không chèn ghi chú vào file dữ liệu · không dựng
lại bố cục bảng theo suy đoán · không xoá nội dung OCR gốc · không sửa số liệu và số
hiệu văn bản. Phụ lục scan vỡ hoàn toàn của `0132` `0004` `0414` `0413` `0420` `0152`
**cố ý giữ nguyên**.

### Còn lại bao nhiêu

Đo bằng bộ kiểm âm tiết tiếng Việt (phụ âm đầu + bảng vần hữu hạn + đúng một dấu
thanh mỗi âm tiết), bỏ qua từ viết hoa toàn bộ:

| | Trước | Sau |
|---|---|---|
| Trung vị | 0,21% | **0,13%** |
| Trung bình | 0,87% | **0,45%** |
| Văn bản ≥ 3% lỗi | 40 | **9** |
| Văn bản ≥ 1% lỗi | 112 | **54** |
| Văn bản dưới 0,5% | 291 | **356** |

Con số tuyệt đối **không đáng tin hoàn toàn**: bộ đo tính nhầm `TTg` `logo` `km`
`Internet` `Excel` `iBT` `Covid` là "âm tiết sai". Phải mở file ra xem, đừng xếp hạng
theo số.

### Lớp lỗi lớn nhất còn lại

`é` đứng thay `ế/ề/ể/ệ` — `tiét`→`tiết`, `diéu`→`điều`, `hién`→`hiện`,
`quyén`→`quyền`, `Quyét`→`Quyết`, `Viét`→`Việt`, `Gido`→`Giáo`.

Khi nguyên âm mang hai dấu chồng nhau (mũ + thanh), model chỉ "thấy" một khối mực ở
trên và sinh ra **một** dấu duy nhất. Dấu sắc trong `é` chỉ là dạng rơi mặc định,
**không mang thông tin về thanh điệu thật**. Vì vậy lớp này **không thay máy móc
được** — phải đọc ngữ cảnh hoặc đối chiếu ảnh gốc.

### Đối chiếu ảnh gốc

`data/raw/pdf/` (bản local, không nằm trong repo) có đủ 457 PDF gốc. PDF là ảnh scan
thuần, không có lớp text, nhưng render ra ảnh rồi đọc thì rõ hoàn toàn:

```python
import pymupdf
d = pymupdf.open(duong_dan_pdf)
d[so_trang - 1].get_pixmap(dpi=150).save("xem.png")
```

Đã kiểm thử trên `0297`: ảnh gốc ghi `Nguyễn Vinh Hiển`, khớp với bản đã sửa; toàn bộ
trang 9 so từng chữ **khớp 100%**. Măng-sét thật là
`CÔNG BÁO/Số 913 + 914/Ngày 20-12-2013` — xác nhận quy tắc `BÁOISố` → `BÁO/Số`.

### Chỗ cần rà lại

Những chỗ phải suy ra từ ngoài trang giấy đã ghi trong `TIEN_DO_SUA_OCR.md` (bản
local). Đáng chú ý: `0254` ngày ban hành mâu thuẫn ngay trong văn bản (trang 17 ghi
`21/8/2023`, trang 3 và 16 ghi `24`) · `0193` số hiệu lệch giữa trang 1 (`150`) và
phụ lục (`450`) · `0060` `01/NQ-PHBK` có thể là `NQ-ĐHBK` hoặc `NQ-HĐT` · `0320`
URL chú thích dựng lại từ chuỗi vỡ · `0463` còn 2 dòng rác chưa đọc được.

### Sửa tiếp ở đâu

Bản trong repo này được sinh từ `data/processed/text_final` ở **bản local, ngoài
repo**. Hai bản **không tự đồng bộ**. Sửa tiếp thì sửa ở bản local rồi copy đè:

```
cp -r data/processed/text_final/. pbl6/data/clean/text_final/
```

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
3. **Khối ký nằm cuối file, tách khỏi trang của nó** ở một số văn bản — khối ký được
   OCR lại riêng rồi chèn thêm vào, vì bản OCR gốc không bắt được (con dấu đè lên
   chữ, bố cục hai cột bị xáo).

   Trước đây các khối này có dán nhãn `----- [Khối ký — OCR lại trang N] -----`.
   **Nhãn đó đã bị gỡ hết** (16 file) vì file dữ liệu không được chứa ghi chú của
   công cụ. Sáu trường hợp đã đưa khối ký về đúng cuối trang của nó
   (`0105` `0229` `0160` `0414` `0413` `0152`); số còn lại khối ký vẫn nằm cuối file.

## Mốc trang

Mốc `----- [Trang N] -----`. Một điểm cần biết: **38 văn bản** lấy từ bản OCR lượt
hai được gửi theo **khúc 5 trang**, nên mốc của chúng đánh theo trang đầu mỗi khúc
(`1, 6, 11, 16…`) chứ không phải từng trang. Định vị được trong khoảng 5 trang, đủ
cho đồ thị tri thức nhưng chưa đủ nếu cần trích dẫn chính xác số trang.

`0184` và `0233` vốn cũng thuộc nhóm này nhưng mốc bị **reset về 1 ở mỗi khúc**,
đã đánh lại liên tục (1–48 và 1–33).

Còn **8 file** mang mốc dạng mơ hồ, cố ý giữ nguyên vì quy đổi sang số trang đơn sẽ
mất thông tin: `[TRANG 3, 4, 5 - PHỤ LỤC]` · `[TRANG PHỤ LỤC VI - 1]` ·
`TRANG 2 (Trang 18)`.
