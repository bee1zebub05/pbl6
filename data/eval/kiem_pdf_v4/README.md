# Tập đánh giá: JSON v4 đối chiếu PDF gốc

Tập này đo độ sai lệch của dữ liệu do model trả về (trích xuất JSON v4 từ `text_final`)
so với nội dung thật trên ảnh PDF gốc, và gom các lỗi OCR phát hiện được trong lúc đối chiếu.
Dựng ngày 16–17/11/2026 khi chuyển văn bản sang JSON v4 theo nhóm số trang PDF: nhóm 1–3
(1–2, 3–5, 6–10 trang; 136 văn bản) và nhóm 4 (11–20 trang; 82 văn bản). Cả 218 văn bản có JSON
hợp lệ và được chấm.

## Cách làm

1. Trích xuất: `tools/gemini_api/chay_json.py --model gemini-3.1-flash-lite` (model
   `gemini-3.5-flash-lite` dùng cho 103 văn bản trước đó bị quá tải 503 hôm chạy). Trường
   `mappedBy` của các tệp này ghi `gemini-api:gemini-3.1-flash-lite`.
2. Bản model trả về được chụp vào `goc/<mã>.json` **trước khi** có bất kỳ chỉnh sửa nào.
3. Agent đọc ảnh PDF gốc và sửa JSON trong `data/clean/json/v4`, mỗi chỗ sửa ghi vào `note` kèm
   trang PDF. Nhóm 1 và khoảng một nửa nhóm 2, 3 do agent Claude Opus kiểm; phần còn lại do agent
   Claude Sonnet kiểm; nhóm 4 do Sonnet kiểm có chọn lọc (trang đầu, căn cứ, hiệu lực, chữ ký, trang
   có thay thế/bãi bỏ — văn bản 11–20 trang không mở hết). Từ lượt Sonnet, **nguồn đối chiếu duy nhất là ảnh PNG render từ PDF gốc**:
   không dùng `.txt` hay metadata web, vì JSON sinh ra từ chính `.txt` nên có thể sai giống nhau.
4. Trọng tài (Claude, phiên chính) tự xem ảnh PDF cho mọi chỗ sửa có rủi ro cao (số hiệu, ngày
   viết tay, chức vụ người ký, loại quan hệ, trạng thái) và sửa hoặc hoàn tác khi cần. Quyết định
   của trọng tài ghi trong `nhat_ky_sua.csv`.

Nguyên tắc: chỉ ghi điều văn bản ghi, không suy luận. Văn bản không ghi thì để null.

**Giới hạn:**
- Đáp án do mô hình AI đối chiếu ảnh PDF, chưa có người kiểm. Khi viết vào báo cáo phải ghi rõ.
- Nhóm đối tượng và lĩnh vực không được đối chiếu, nên điểm 1,00 của hai trường này không có
  nghĩa. Thân các Điều cắt nguyên văn từ `.txt` nên không thuộc phạm vi chấm.
- `chuan/` chỉ phản ánh điều chính văn bản ghi. Trạng thái hết hiệu lực suy từ văn bản khác
  (`tools/kiem_tra/suy_hieu_luc.py`) được áp vào dữ liệu nhưng không đưa vào `chuan/`, vì model
  chỉ thấy một văn bản khi trích xuất.
- 0042 và 0214 là cùng một tệp PDF (trùng md5) đăng ở hai lĩnh vực; 0130 và 0331 cùng là Luật
  39/2013/QH13; 0086 và 0349 cùng là Luật 52/2019/QH14 (tên tệp 0086 ghi nhầm 51_2019).
- 0168 (Nghị quyết 08/NQ-HĐĐH ngày 28/01/2022) có căn cứ Nghị quyết 08/NQ-HĐĐH ngày 12/7/2021 —
  trùng số hiệu khác ngày, lược đồ chặn tự trích dẫn nên chưa ghi được quan hệ này.

## Kết quả (218 văn bản nhóm 1–4, 17/11/2026)

| Trường | Tỷ lệ đúng |
|---|---|
| Số hiệu | 97,7% |
| Loại văn bản | 100% |
| Cơ quan ban hành | 99,1% |
| Ngày ban hành | 95,4% |
| Ngày hiệu lực | 89,0% |
| Trạng thái | 98,6% |
| Số Điều | 99,5% |

| Trường tập hợp | P | R | F1 |
|---|---|---|---|
| Người ký (họ tên + chức vụ) | 0,89 | 0,89 | 0,89 |
| Trích dẫn (đích + loại quan hệ) | 0,88 | 0,80 | 0,84 |
| — BASED_ON | 0,86 | 0,85 | 0,86 |
| — REFERENCES | 1,00 | 0,76 | 0,86 |
| — REPLACES | 1,00 | 0,85 | 0,92 |
| — AMENDS | 0,86 | 0,86 | 0,86 |
| — REPEALS | 0,91 | 0,45 | 0,60 |

Đây là điểm của riêng model. Thêm bước luật `tools/kiem_tra/vet_quan_he.py` (chỉ thêm
REPLACES/REPEALS còn thiếu), độ phủ REPEALS tăng từ 45% lên 99% (128/129), REPLACES từ 85% lên
87%; luật không ra quan hệ sai nào (46/46 REPLACES, 93/93 REPEALS). Luật được chỉnh trên nhóm 1–3;
trên nhóm 4 (chưa dùng để chỉnh) luật vẫn đúng 29/29 REPLACES, 2/2 REPEALS.

Lỗi điển hình của model: bỏ sót danh sách dài văn bản bị bãi bỏ (0149, 0143, 0284); chép
nguyên ngày viết tay bị OCR đọc sai; gán chức vụ "Hiệu trưởng" mặc định cho người ký của Đại học
Đà Nẵng; lấy ngày tháng làm số hiệu cho Luật không ghi số (trái quy tắc 7d của prompt; agent nhóm 4
cũng mắc, trọng tài bỏ cả 104 trích dẫn kiểu này trong v4); nhầm căn cứ với dẫn chiếu; ghi
REPEALS khi văn bản viết "thay thế" (0432).

## Năm văn bản phải sửa lược đồ hoặc code mới trích xuất được

| Mã | Vướng | Cách xử lý (17/11/2026) |
|---|---|---|
| 0023, 0084 | Mục đánh số bằng chữ cái (A, B…) | Lược đồ cho phép số mục là một chữ cái in hoa |
| 0488 | Loại văn bản "Quy chế" đứng độc lập | Thêm "Quy chế" vào danh sách loại văn bản (lược đồ và chatbot) |
| 0193 | Bản kèm theo không có Điều | Sửa thứ tự trong `chay_json.py`: bỏ bản kèm theo rỗng sau khi xoá Điều do model tự đặt |
| 0110 | Model xếp nhóm đối tượng vào ô lĩnh vực | `chay_json.py` bỏ lĩnh vực ngoài danh mục chuẩn |

0149: bản PDF scan thiếu trang in số 2, nên 11 quan hệ bãi bỏ ở trang đó chưa thêm được.

## Tệp

| Tệp | Nội dung |
|---|---|
| `goc/<mã>.json` | JSON model trả về, chưa sửa. Không bao giờ sửa tệp trong này |
| `chuan/<mã>.json` | JSON sau đối chiếu PDF và trọng tài, dùng làm đáp án |
| `nhat_ky_sua.csv` | Các quyết định của trọng tài: mã, trường, cũ, mới, trang PDF, ai phát hiện, kết luận |
| `bao_cao_agent/` | Báo cáo gốc của từng agent (Opus, Sonnet) theo nhóm |
| `loi_ocr.csv` | Lỗi OCR trong `text_final` phát hiện khi đối chiếu PDF |
| `trong_tai.py` | Áp quyết định trọng tài: sửa JSON, ghi note, validate, ghi nhật ký |
| `tinh_sai_lech.py` | Chấm `goc` so với `chuan`, ghi `ket_qua.md` và `ket_qua.json` |

## Chấm

```
python data/eval/kiem_pdf_v4/tinh_sai_lech.py
```

Trường đơn chấm tỷ lệ đúng sau chuẩn hoá. Trường tập hợp chấm Precision, Recall, F1 gộp vi mô;
trích dẫn chấm thêm theo từng loại quan hệ. Áp dụng tiếp cho nhóm 5–6 bằng cách thêm bản gốc
và bản chuẩn vào hai thư mục.
