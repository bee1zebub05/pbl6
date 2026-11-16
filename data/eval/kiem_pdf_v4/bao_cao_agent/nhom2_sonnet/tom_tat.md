# Nhóm 2 (sonnet) - 15 mã còn lại, kiểm theo ảnh PDF

## Trích xuất (gemini-3.1-flash-lite, 4 lượt)
- Xong (10): 0025, 0056, 0059, 0143, 0149, 0328, 0355, 0431, 0433, 0445. Nghi ngờ: 0.
- Hỏng (5), không lách schema:
  - 0023, 0084: số Điều là chữ "A".
  - 0193: articles rỗng.
  - 0110: topics "Cán bộ, giảng viên, viên chức, người lao động" không thuộc danh mục.
  - 0488: documentType "Quy chế" không hợp lệ.
- Kiểm bằng ảnh PDF 100 DPI (không dùng .txt, metadata). Các trang phụ lục/phiếu chuyển chưa đọc: 0025 tr.2-5, 0431 tr.3-4, 0328 tr.2-4, 0143 tr.5-10, 0355 tr.2, 0445 tr.5.

## Đã sửa (bản gốc ở data/eval/kiem_pdf_v4/goc/<mã>.json, đều validate OK)
- 0025: documentNumber 441/QĐ-ĐHBK -> 447/QĐ-ĐHBK (tr.1, số viết tay phóng 300 DPI).
- 0431: effectiveDate 10/04/2025 -> 01/03/2025 (tr.2); context AMENDS 36/QĐ-ĐHĐN đổi sang câu Điều 1 (tr.1).
- 0328: citation 25/2019/TT-BGDĐT AMENDS -> REFERENCES (tr.1).
- 0445: signer Hiệu trưởng -> Giám đốc (tr.4); thêm 9 BASED_ON (tr.1-2).
- 0059: thêm 9 BASED_ON (tr.1).
- 0056: signer Hiệu trưởng -> Chủ tịch Hội đồng trường (tr.5); thêm 4 BASED_ON (tr.1).
- 0355: thêm BASED_ON 505-TB/BCSD (tr.1).
- 0149: thêm 33 REPEALS (tr.1-5).
- 0143: thêm 24 REPEALS (tr.1-4); context dài hơn 400 ký tự bị cắt kèm "…".
- 0433: không cần sửa.

## Chưa sửa / cần người quyết
- 5 văn bản hỏng schema: 0023, 0084, 0193, 0110, 0488.
- 0149: PDF thiếu trang in số 2 (Điều 1 mục 3-13), chưa thêm 11 REPEALS tương ứng.
- Căn cứ là Luật không ghi số hiệu (0328, 0445, 0433) không thêm.
- 0056: căn cứ ghi "08/QĐ-HĐĐH" (lỗi văn bản gốc), giữ 08/NQ-HĐĐH.
- 0433: status CHUA_HIEU_LUC trong khi văn bản ghi hiệu lực 14/01/2025, chưa đổi.
- 0431: articles trong JSON chỉ 1 mục "I" trong khi văn bản có 4 Điều (ngoài phạm vi trường được sửa); 0328, 0059, 0056, 0355, 0149, 0433 có articles trống/khác (chưa xác minh, ngoài phạm vi).
