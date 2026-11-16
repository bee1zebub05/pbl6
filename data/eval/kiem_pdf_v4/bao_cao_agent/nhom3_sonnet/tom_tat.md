# Nhóm 3 (sonnet) - tóm tắt

Cách kiểm: nguồn đối chiếu là ảnh PDF render (trang đầu, trang chữ ký, trang có câu thay thế/bãi bỏ). Ban đầu sàng lọc theo .txt/metadata cho một số mã (0381, 0370, 0383, 0344, 0384, 0256, 0232, 0197, 0122, 0107, 0306, 0301, 0303, 0163, 0060, 0487); sau chỉ thị đổi cách kiểm đã xem lại ảnh trang đầu và trang chữ ký của các mã này. Chưa render hết mọi trang của từng văn bản (chỉ trang căn cứ, trang ký, trang có quan hệ thay thế/bãi bỏ). cach_kiem trong ket_qua.csv ghi ANH_PDF.

## Kết quả trích xuất (gemini-3.1-flash-lite, 4 lượt do 429)
- Đủ 37/37 mã đã có JSON v4 (lượt cuối 0271, 0195, 0173, 0263 xong). 0487 có sẵn JSON. Không file nào "sai schema"; 0301 từng cảnh báo trùng số hiệu 15/11/2010 (do ngày Luật, đã bỏ khi sửa).
- Không còn mã thiếu.

## Ca 0042 và 0214 (cùng số 1394/QĐ-ĐHBK)
Hai file PDF trong manifest giống hệt nhau từng byte (md5 857cd798f0177537ddf4233d4c5edda3, 2.039.473 byte). Là CÙNG MỘT văn bản (QĐ 1394/QĐ-ĐHBK, ngày viết tay 11/5/2021) lưu ở hai lĩnh vực. Không đổi số hiệu. 0042 JSON ngày 11/05/2021 đúng; 0214 JSON ghi 14/05/2021 là sai (đã sửa thành 11/05/2021).

## Đã sửa (trang PDF)
- 0381: thêm căn cứ TT 10/2020/TT-BGDĐT, NĐ 32/CP (tr.1)
- 0370: thêm KL 69-KL/TW, KL 91-KL/TW, CV 575-TB/BCSĐ (tr.1-2)
- 0384: thêm 6 BASED_ON (32/CP, 99/2019/NĐ-CP, 10/2020 và 20/2020/TT-BGDĐT, 08 và 13/NQ-HĐĐH) và AMENDS 3237/QĐ-ĐHĐN (Điều 2 bãi bỏ mục 8,9 Bảng 3) (tr.1-2)
- 0163: thêm 2762/QĐ-HĐĐH, 996 và 998/QĐ-BGDĐT, 04/NQ-HĐĐH (tr.1)
- 0487: thêm Luật 123/2025/QH15 (tr.1)
- 0388: chức vụ Hiệu trưởng -> Giám đốc (tr.1)
- 0424: chức vụ Hiệu trưởng -> Phó Hiệu trưởng (KT. Hiệu trưởng) (tr.2); thêm CT 27-CT/TW (tr.1)
- 0227: chức vụ Hiệu trưởng -> Phó Giám đốc (KT. Giám đốc) (tr.1)
- 0060: issueDate null -> 23/12/2015, effectiveDate null -> 23/12/2015, chức vụ Hiệu trưởng -> Chủ tịch Hội đồng trường (tr.1)
- 0451: issueDate 26/11/2025 -> 26/12/2025 (tr.1, phóng 300 DPI)
- 0214: issueDate và effectiveDate 14/05/2021 -> 11/05/2021 (tr.1, phóng 300 DPI)
- 0144: thêm căn cứ NĐ 69/2017/NĐ-CP (tr.1)
- 0313: thêm căn cứ NĐ 86/2022/NĐ-CP (tr.1)
- 0491: thêm 6 Luật sửa đổi (123/2025, 36/2009, 42/2019, 07/2022, 93/2025, 131/2025) (tr.1)
- 0263: thêm CV 1448-CV/ĐU và 181/CĐĐHĐN-VP (tr.1)
- Bỏ trích dẫn có số hiệu là ngày/năm (Luật không ghi số hiệu): 0344, 0256, 0232, 0122, 0107, 0306, 0301, 0430, 0125, 0357, 0203, 0216, 0297, 0271
- Bỏ trích dẫn Luật có số QH do model thêm mà PDF không ghi: 0303 (3), 0195 (3)

Bản gốc trước sửa nằm ở data/eval/kiem_pdf_v4/goc/<mã>.json. Mọi sửa đã qua validate OK.

## Chưa sửa / cần người quyết
- 0271: ngày ban hành 29/11/2023 - tháng viết tay bị gạch/đè, không đọc chắc; ngày hiệu lực 13/02/2024 viết tay chữ số khó đọc.
- 0313: ngày hiệu lực 01/11/2024 - chữ số ngày viết tay không chắc.
- 0227: ngày ban hành 05/07/2023 bị dấu đến che một phần.
- 0297: status HET_HIEU_LUC không có trong văn bản (không sửa vì cấm suy luận).
- 0471 (REPEALS 40/2020/TT-BGDĐT, 04/2022/TT-BGDĐT) và 0487 (REPEALS 61/2006/NĐ-CP, 113/2015/NĐ-CP): văn bản chỉ bãi bỏ một phần điều khoản, có thể nên là AMENDS; giữ nguyên.
- 0256: metadata web ghi cơ quan "Chính phủ", PDF là Bộ Giáo dục và Đào tạo (JSON đúng).
- 0370: câu căn cứ NĐ 86/2022 trong PDF in "ngày 24/1/2022"? khó đọc ở 100 DPI; chỉ ảnh hưởng context, không sửa.
- Lưu ý: ảnh trang đầu của 0344, 0197, 0122, 0107, 0301 đã xem, không thấy lệch ngoài các mục đã sửa; chưa soát toàn bộ các trang giữa.

Tệp: ket_qua.csv, loi_ocr.csv, tom_tat.md cùng thư mục.
