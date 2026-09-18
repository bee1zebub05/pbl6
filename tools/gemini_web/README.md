# `gemini_web/` — hiệu đính OCR hàng loạt qua giao diện web Gemini

Đẩy 387 file `.txt` chưa được đọc lên Gemini, lấy bản đã sửa chính tả về.
Gồm hai mảnh chạy cùng lúc:

| Mảnh | Là gì |
|---|---|
| `gemini_web/cau_sua_txt.py` | máy chủ hàng chờ chạy trên máy bạn, cổng `8779` |
| `gemini_web/extension/` | extension Chrome lái 10 tab Gemini |

---

## Chạy

**1. Bật cầu** (mở một cửa sổ terminal, để yên đó):

```bash
python tools/gemini_web/cau_sua_txt.py
```

Mở `http://127.0.0.1:8779` xem tiến độ. Muốn làm trước mấy file tệ nhất:

```bash
python tools/gemini_web/cau_sua_txt.py --tu-loi-cao 2.0        # chỉ file ≥ 2% lỗi (15 file)
python tools/gemini_web/cau_sua_txt.py --chi 0114,0439,0403    # chỉ mấy mã này
```

**2. Nạp extension** — `chrome://extensions` → bật *Chế độ nhà phát triển* →
*Tải tiện ích đã giải nén* → trỏ vào `<repo>/tools/gemini_web/extension`.

**3. Đăng nhập Gemini** một lần bằng tay ở `https://gemini.google.com/u/1/app`.

**4. Bấm biểu tượng extension** → chọn số luồng (mặc định 10) → **▶ Bật**.

Nó sẽ tự mở 10 tab `gemini.google.com/u/1/app?pageId=none`, mỗi tab một luồng.

---

## Một lượt chạy ra sao

Với mỗi file, máy trên trang làm đúng các bước bạn làm tay:

1. Bấm **Cuộc trò chuyện mới**
2. Đính file `.txt` (qua `input[type=file]`, không được thì thả vào vùng drop)
3. Gõ câu lệnh vào ô nhập
4. Bấm **Gửi tin nhắn**
5. Chờ — trong lúc Gemini còn đang viết thì **chưa có nút Sao chép mã**, đúng như
   bản DOM bạn gửi. Máy nhận biết đã xong khi hội đủ ba điều: mất nút
   *Ngừng tạo câu trả lời*, `div.markdown` có `aria-busy="false"`, và khối mã
   đứng yên 3 giây liền.
6. Bấm nút **Sao chép mã** (`[data-test-id="gem-copy-button"]`)
7. Lấy nội dung khối `code[data-test-id="code-content"]` rồi nộp về cầu

> Nút *Sao chép mã* vẫn được bấm thật nên nội dung có vào clipboard. Nhưng giá trị
> nộp về lấy từ `textContent` của chính khối mã, vì đọc clipboard chỉ chạy được khi
> tab đang focus — mà ta chạy 10 tab, phần lớn thời gian chúng ở nền. Hai nguồn là
> cùng một chuỗi; clipboard chỉ dùng để đối chiếu khi đọc được.

---

## Vụ tab nền không render

Chrome bóp tab nền, Gemini không vẽ câu trả lời ra DOM, máy đọc không thấy → treo.
Xử lý bằng hai lớp chồng nhau:

- `extension/che_an_tab.js` chạy ở `document_start`, ép `document.hidden = false`,
  `visibilityState = "visible"`, `hasFocus() = true`, và nuốt sự kiện
  `visibilitychange`/`blur`.
- **Vòng xoay focus** trong `extension/background.js`: cứ 3,5 giây lại `chrome.tabs.update`
  cho một tab khác thành tab đang mở, quay vòng đủ 10 tab.

Hệ quả bạn sẽ thấy: cửa sổ Chrome tự nhảy tab liên tục khi đang chạy. Đó là cố ý.
Nên để riêng một cửa sổ Chrome cho việc này, đừng dùng cửa sổ đó làm việc khác.

---

## Tắt máy giữa chừng

Được. Tiến độ ghi xuống `trang_thai_sua_txt.json` **ngay sau mỗi file xong**.

- Bật lại cầu → nó đọc lại file trạng thái, file nào xong rồi thì bỏ qua.
- File đang làm dở lúc tắt máy: cầu không thấy ai nộp nên tự trả về hàng chờ.
- Muốn làm lại từ đầu: xoá `trang_thai_sua_txt.json`.

---

## Kết quả đi đâu

```
data/interim/text_gemini_sach/<lĩnh vực>/<tên file>.txt     ← nhận được
data/interim/text_gemini_sach/_nghi_ngo/<lĩnh vực>/...      ← cần bạn xem lại
```

**Không ghi đè `text_final`.** Đây là bản Gemini trả về, chưa ai duyệt — bạn đọc
xong ưng thì mới copy đè sang, giống quy trình bạn vẫn làm.

Cầu tự đẩy file vào `_nghi_ngo` khi:

- bản trả về ngắn hơn 80% bản gốc → Gemini đã cắt bớt nội dung
- số mốc `[Trang N]` không khớp bản gốc → mất hoặc thêm trang

Bản dưới 200 ký tự bị từ chối thẳng, file được xếp lại hàng chờ.

---

## Khi hỏng

| Hiện tượng | Xử lý |
|---|---|
| Panel báo `⚠ chưa thấy cầu` | chưa chạy `gemini_web/cau_sua_txt.py`, hoặc sai cổng |
| Một luồng treo mãi | cầu thu hồi việc sau 180 phút không ai nộp, xếp lại hàng chờ |
| Không chèn được câu lệnh vào ô nhập | cửa sổ Chrome đang mất focus — đừng để DevTools ở cửa sổ riêng giành focus |
| Nhiều file `⏳` liên tiếp | Gemini đang giới hạn lượt — tắt bớt luồng xuống 3–4 |
| Gemini đổi giao diện | sửa các neo trong `extension/may_gemini.js`, phần `const O = {...}` |
| Muốn làm lại các file hỏng | bấm **Đẩy lại file hỏng** trong panel |

Nhật ký chạy nằm trong panel (300 dòng gần nhất) và ở Console của service worker
(`chrome://extensions` → *Trang web của worker dịch vụ*).

---

## Một điều nên cân nhắc

Cách này lái giao diện web Gemini bằng script, không phải dùng API chính thức —
điều khoản sử dụng của Google không cho phép truy cập dịch vụ bằng phương tiện tự
động. Tài khoản có thể bị hạn chế. Dự án đã có sẵn đường chính thống dùng API với
17 key trong `.env` (`src/vanban/clean/gemini_fix.py`); chạy qua đó thì
không vướng gì, đổi lại Gemma hay bị `RECITATION` với trang dày chữ.
