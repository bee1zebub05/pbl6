# Gemini OCR Batch — PDF ➜ text, giữ nguyên cây thư mục

Đẩy PDF trong `data/raw/**` lên **chat Gemini** (dùng tài khoản đang đăng nhập trên Chrome, không cần API key),
lấy text OCR về, ghi sang `data/clean_data/**` **giữ nguyên cây thư mục**.

```
data/raw/pdf/Đào tạo/0159_....pdf   ──►   data/clean_data/pdf/Đào tạo/0159_....txt
data/raw/doc_new/Pháp chế/0352.doc  ──►   data/clean_data/doc_new/Pháp chế/0352.txt
```

## Vì sao có `bridge.py`

Chrome extension **không** đọc/ghi được ổ đĩa tuỳ ý. `bridge.py` (chỉ dùng thư viện chuẩn Python)
đứng giữa: quét `raw`, phát job cho extension, nhận text về và ghi đúng đường dẫn trong `clean_data`.
Nó cũng nhớ trạng thái ⇒ tắt máy bật lại vẫn **chạy tiếp**, không làm lại file đã xong.

## Cài đặt

1. Chrome ➜ `chrome://extensions` ➜ bật **Developer mode** ➜ **Load unpacked** ➜ chọn thư mục
   `project/gemini_ocr/extension`.
2. Đăng nhập `gemini.google.com` trên chính Chrome đó.
3. Bấm icon extension ➜ mở **bảng điều khiển**.

## Bước 1 — Test 1 file (làm trước)

Tab **1️⃣ Test 1 file**: kéo thả 1 PDF ➜ **▶ Chạy thử file này**.

Extension sẽ: mở tab Gemini mới ➜ đính file ➜ gõ prompt ➜ gửi ➜ chờ trả lời xong ➜ móc text về panel.
Xem kết quả, bấm **⬇ Tải .txt về** nếu ưng. Chưa ghi gì vào `clean_data` ở bước này.

> Mẹo khi soi lỗi: tab **⚙️ Cấu hình** ➜ bỏ tick *"Đóng tab Gemini sau khi xong"* để xem tab Gemini
> đang làm gì. Lỗi kèm nhật ký engine hiện ngay trong ô kết quả.

## Bước 2 — Chạy batch

```powershell
cd f:\DUT4\PBL6\project\gemini_ocr
python bridge.py
```

Rồi ở panel ➜ tab **📦 Chạy batch** ➜ **🔌 Kiểm tra bridge** ➜ **▶ Bắt đầu batch**.

Tuỳ chọn hay dùng:

| Lệnh | Ý nghĩa |
|---|---|
| `python bridge.py --flatten-top` | Bỏ cấp `pdf/` ⇒ `clean_data/Đào tạo/x.txt` |
| `python bridge.py --src <dir> --out <dir>` | Đổi thư mục nguồn/đích |
| `curl http://127.0.0.1:8777/api/stats` | Xem tiến độ |
| `curl -X POST http://127.0.0.1:8777/api/requeue` | Cho các file lỗi chạy lại |

**Số tab song song**: để `1` lúc đầu. Gemini web có giới hạn dùng — chạy 3–4 tab một lúc dễ bị chặn
tạm thời. Tăng dần khi thấy ổn.

## Text được lấy từ đâu

Với prompt OCR, Gemini thường trả lời một lượt gồm **hai** code block: khối `Python`
(mã nó chạy để ghi file) và khối `Plaintext` (nguyên văn nội dung) — kèm một thẻ file `.txt`
có nút **"Đang mở"**. Khối Python chứa cả nội dung trong chuỗi ba nháy nên **dài hơn** khối
Plaintext ⇒ **không được chọn theo độ dài**, phải xét **nhãn** trước:

1. Code block có nhãn `plaintext` / `text` / `markdown` → lấy thẳng. ✅ đường đi thường gặp
2. Code block không nhãn mà nội dung không có mùi mã nguồn.
3. Chỉ còn khối mã → **bóc chuỗi ba nháy** bên trong ra.
4. Thẻ file artifact: bấm **"Đang mở"** (`button[data-test-id="open-button"]`) rồi quét **mọi
   frame** (trình xem Drive nằm trong iframe). Dùng khi chat chỉ có mã, hoặc bản này dài hơn.
5. Cùng lắm: cả câu trả lời, đã cắt câu dẫn *"Dưới đây là toàn bộ nội dung…"*.

> Hai nút dễ nhầm — extension **không** đụng vào nút thứ hai:
> - `button[data-test-id="open-button"]` chữ "Đang mở" → thẻ **file artifact** (cái ta bấm).
> - `aria-label="Tải mã xuống"`, icon `arrow_circle_down` → nút tải của **code block**.

Không cần tải file về: text đã nằm sẵn trong DOM, lấy thẳng rồi đưa bridge ghi đúng đường dẫn —
chắc ăn hơn đi dò file trong thư mục Downloads.

### Kiểm thử phần chọn nội dung

```bash
node test_pick_block.js      # 17 ca, dùng đúng dữ liệu Gemini trả về (Python + Plaintext)
```

Chạy được không cần Chrome: test nạp `engine_gemini_pdf.js` với DOM giả rồi gọi hàm thuần
`pickBlockText`. Sửa logic chọn khối thì chạy lại test này trước khi thử trên Chrome.

## Khi Gemini đổi giao diện

Sửa các **selector chain** đầu file `extension/engine_gemini_pdf.js` (biến `SEL`) — mỗi chain thử
lần lượt từ trên xuống, thêm selector mới vào đầu là xong. Cách đính file có 4 phương án chạy nối
tiếp (input có sẵn ➜ menu "+" ➜ paste ➜ kéo-thả), hỏng cách này tự nhảy cách khác.


## Đường lui: Gemma 31B qua API

File nào Gemini web thử 3 lượt vẫn hỏng thì bridge tự gọi **`gemma-4-31b-it`**. Luồng nền
trong bridge lo việc này, không cần bấm gì.

Vì sao Gemma chứ không phải Gemini API: `gemini-3.5-flash-lite` trả `finish_reason=RECITATION`
với **mọi** văn bản pháp quy — chặn sạch, output rỗng, thử bao nhiêu key cũng vậy. Gemma
không bị bộ lọc đó, và vẫn nhận thẳng file PDF.

Hai bước, giữ đúng nguyên tắc gửi PDF chứ không render ảnh:

1. Gửi **nguyên cả file PDF**.
2. Hỏng → **cắt thành PDF nhỏ 5 trang/khúc** → OCR từng khúc → **ghép lại**.
   Khúc nào hỏng thì chèn `[[TRANG x-y KHÔNG OCR ĐƯỢC: lý do]]` — thiếu chỗ nào phải thấy
   được chỗ đó, không im lặng nuốt mất.

```powershell
python gemma_ocr.py "file.pdf"              # chạy tay 1 file
python gemma_ocr.py "file.pdf" --out a.txt
python gemma_ocr.py --kiem-key              # kiểm tra sức khoẻ key
python bridge.py --khong-gemma              # tắt đường lui
python bridge.py --gemma-moi-khuc 3         # cắt 3 trang/khúc thay vì 5
```

### Quản lý key

`.env` có 21 key `GEMMA_API_KEY*`. **Đừng lọc theo hình dạng key** — key dạng `AQ.Ab8…` gọi
API bình thường y như `AIza…`; lọc "chỉ nhận AIza" là mất 15/21 key (đã mắc lỗi này một lần).

Kiểm tra hai tầng, cả hai chạy song song 10 luồng:

| Tầng | Cách | Bắt được gì |
|---|---|---|
| Nhanh — liệt kê model | 21/21 qua | key sai, key thu hồi |
| Sâu — gọi thật 1 request tí hon | **17/21** qua | dự án bị khoá quyền (`403 PERMISSION_DENIED`) |

Tầng nhanh **không** thấy được key bị khoá quyền; phải gọi thật mới lộ. Lúc chạy thì xoay vòng
tròn: `429` → hoãn key đó 90 giây; `403` → đánh chết. Mỗi lần OCR thử tối đa 3 key khác nhau.

### File nào đã phải fallback

Ghi vào `state.json`: `nguon`, `gemma_che_do`, `gemma_khuc_hong`.

```powershell
python bao_cao_loi.py                    # có mục "FILE ĐÃ FALLBACK SANG GEMMA"
curl http://127.0.0.1:8777/api/gemma
```

CSV xuất ra có thêm cột `nguon`, `gemma_che_do`.

## Làm sạch trước khi ghi

Cùng một prompt, Gemini trả về **ba kiểu khác nhau**: văn bản thuần, markdown có rào ```` ``` ````,
hoặc code Python `text_content = """…"""`. `sach_hoa.py` gỡ hết trước khi ghi — đặt ở bridge chứ
không ở extension, vì sửa bridge có hiệu lực ngay còn extension phải tải lại mới ăn.

`kiem_dinh()` chặn không cho ghi khi: dưới 200 ký tự, vẫn là mã nguồn, còn dấu rào ở đầu, hoặc
tài liệu ≥5 trang mà dưới 400 chữ/trang (dấu hiệu bị cắt giữa chừng). Không đạt thì đánh hỏng
để thử lại, chứ không ghi rác ra `clean_data`.

## Theo dõi và sửa chữa

```powershell
python bao_cao_loi.py                    # bảng theo thư mục + xuất CSV/MD
python bao_cao_loi.py --requeue          # xoá đánh dấu hỏng, cho chạy lại
python danh_gia_clean.py                 # chấm chất lượng file đã ghi
python don_dep_clean.py --apply          # dọn file đã ghi từ trước khi có sach_hoa.py
```

## Kiểm thử

```bash
node test_pick_block.js     # 17 ca — chọn nội dung trong DOM Gemini
python test_sach_hoa.py     # 21 ca — làm sạch + kiểm định
```

Sửa logic chọn/làm sạch thì chạy hai bộ này trước khi thử trên Chrome.

## Cấu trúc

```
project/gemini_ocr/
├── bridge.py                    # server job local + luồng nền gọi Gemma
├── sach_hoa.py                  # làm sạch + kiểm định text trước khi ghi
├── gemma_ocr.py                 # đường lui: Gemma 31B, xoay key, cắt PDF thành khúc
├── bao_cao_loi.py               # liệt kê file hỏng theo thư mục, xuất CSV/MD
├── danh_gia_clean.py            # chấm chất lượng kết quả
├── don_dep_clean.py             # dọn file đã ghi từ trước
├── test_pick_block.js           # test chọn nội dung (17 ca)
├── test_sach_hoa.py             # test làm sạch (21 ca)
├── state.json                   # tiến độ, tự sinh
└── extension/
    ├── manifest.json
    ├── background.js            # điều phối: mở tab, inject, poll, ghi kết quả
    ├── engine_gemini_pdf.js     # inject vào gemini.google.com: đính file, gửi, móc text
    ├── frame_grabber.js         # lấy text trong iframe trình xem Drive
    ├── visibility_spoof.js      # ép Gemini vẫn render khi tab ở nền
    └── panel.html / panel.js    # bảng điều khiển
```
