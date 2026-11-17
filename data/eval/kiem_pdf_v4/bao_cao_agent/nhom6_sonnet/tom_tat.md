# Tóm tắt kiểm v4 nhóm 6 (lượt Sonnet) — 50/50 mã

Đã kiểm 50, chưa trích xuất 0, không có PDF 0 (0161 và 0352 dùng PDF chuyển từ Word). Mọi file sửa đều validate OK; bản gốc nằm ở data/eval/kiem_pdf_v4/goc/. Chi tiết từng trường: ket_qua.csv, loi_ocr.csv.

## Đã sửa (mã, trường, cũ -> mới, trang PDF)
Bỏ trích dẫn có số hiệu là ngày/năm/tên chung (PDF chỉ ghi tên + ngày):
- 0382 (4 dòng, tr.1), 0247 REPLACES "2001" (tr.45), 0325 (5), 0308 (5), 0291 (2), 0153 (1), 0164 (2), 0133 (7), 0097 "Hiến pháp", 0305 "Luật Thanh tra", 0191, 0428, 0199, 0169, 0114, 0161, 0118, 0269 "18/6/2012", 0287, 0411 (3), 0112 (5, gồm số hiệu luật PDF không ghi), 0132 (4 gồm 3 BASED_ON có số hiệu mà PDF không ghi), 0293 (2 BASED_ON có số hiệu mà PDF không ghi)

Chức vụ người ký:
- 0277: Hiệu trưởng -> Giám đốc (tr.1); 0169: Hiệu trưởng -> Giám đốc (tr.2); 0280: Hiệu trưởng -> Chủ tịch Quốc hội (tr.82)

Ngày hiệu lực:
- 0380: 05/04/2025 -> 05/01/2025 (chữ viết tay, tr.17), sửa cả context REPLACES
- 0352: 24/07/2014 -> null (công văn không ghi, tr.1-2)
- 0337: 11/05/2022 -> null (công văn không ghi, tr.8)
- 0343: 05/03/2011 -> null (văn bản chỉ ghi "có hiệu lực sau 45 ngày, kể từ ngày ký", tr.18)

Loại quan hệ hiệu lực:
- 0117: 133/2008/NĐ-CP REPEALS -> REPLACES (tr.34); bỏ 103/2011, 120/2014 (chuỗi sửa đổi)
- 0486: 106/2020/NĐ-CP REPEALS -> AMENDS (tr.12); 0132: 16/2015/NĐ-CP REPEALS -> AMENDS (tr.14)
- 0476: 159/QĐ, 2108/QĐ, 3277/QĐ-BGDĐT REPEALS -> AMENDS (tr.2)
- 0343: 55/2005/TTLT-BNV-VPCP REPEALS -> AMENDS (chỉ quy định trái, tr.19)
- 0096: 71/2006/QH11 REPLACES -> REPEALS (văn bản ghi "hết hiệu lực", tr.51)
- 0087: 92/2015/QH13 targetArticle null -> Điều 32 (tr.82)

Thêm trích dẫn thiếu:
- 0291 +9 REPEALS (tr.47); 0401 +3 AMENDS (tr.68); 0305 +4 REPEALS (tr.29); 0201 +4 BASED_ON (tr.1)
- 0440 +2 BASED_ON (124-QĐ/TW, 25-HD/BTCTW); 0485 +4 REPEALS (tr.57); 0269 +1 BASED_ON, +2 REPLACES (04/QĐ-ĐHBK, 374/QĐ-ĐHBK)
- 0411 +6 (5 REPLACES, 1 AMENDS, tr.33); 0112 +13 REPEALS (tr.87-88); 0391 +2 BASED_ON; 0423 +3 BASED_ON; 0425 +3 BASED_ON; 0373 +1 BASED_ON
- 0118 +REPLACES 42/2010/NĐ-CP (tr.61); 0287 +REPEALS 85/2014/NĐ-CP, 51/2010/QĐ-TTg, +AMENDS 145/2013/NĐ-CP (tr.74)

## Bổ sung 0245 và 0246 (tổng 52 mã)
- 0245: không sai (số hiệu, ngày, hiệu lực 01/07/2016, Nguyễn Sinh Hùng, 2 REPEALS khớp, tr.304-305).
- 0246 (văn bản hợp nhất 01/VBHN-VPQH, xác thực 10/07/2017, Chủ nhiệm Nguyễn Hạnh Phúc, hiệu lực 01/01/2018): thêm REPEALS 15/1999/QH10 và 37/2009/QH12 theo Điều 426 (tr.312). NGHI_NGO: dòng AMENDS 12/2017/QH14 giữ nguyên, chiều quan hệ mơ hồ vì chính 12/2017 sửa Bộ luật 100/2015.

## Chưa sửa / cần người quyết
- 0277: issueDate 22/01/2024 viết tay, chữ số tháng khó đọc chắc, NGHI_NGO.
- 0280 và 0094: status HET_HIEU_LUC không do văn bản tự ghi, giữ nguyên (không suy luận).
- 0352 và 0337: documentType "Hướng dẫn" nhưng văn bản không có tiêu đề loại, có "V/v" (công văn); cân nhắc đổi thành Công văn.
- 0287: 101/2018/NĐ-CP (sửa đổi 85/2014) không ghi trích dẫn vì thuộc chuỗi sửa đổi; 0112: tương tự 148/2018 và 121/2018 đã ghi vì PDF liệt kê là nghị định riêng hết hiệu lực (có thể người quyết xem lại).
- Mốc trang trong .txt lệch khỏi trang PDF thực ở một số văn bản (0114, 0343): chỉ dùng để định vị.
