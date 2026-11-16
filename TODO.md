# TODO — việc còn lại trước khi nộp PBL6

Cập nhật 16/11/2026. Làm xong việc nào thì đổi `[ ]` thành `[x]`, ghi ngày, commit kèm việc đó.
Việc nào bị kẹt thì ghi một dòng lý do ngay dưới nó.

Báo cáo: `bao_cao/Bao_cao_PBL6.docx` (đọc `bao_cao/README.md` trước khi sửa: chỉ Kiên ráp bản
chính, mọi người gửi Comment/Track Changes).

## Đã xong (để biết, không cần làm)

- Báo cáo đầy đủ 42 trang theo mẫu Khoa, có mục lục, danh mục hình, bảng, hình minh hoạ.
- Sửa số hiệu 0465 (1077/QĐ-ĐHBK), 0489 (1841/QĐ-ĐHĐN), 0051 (905/QĐ-ĐHBK) và hiệu lực 0461,
  0051 theo PDF gốc; dựng lại đồ thị v4 (2.890 đỉnh, 4.496 quan hệ), embed đủ 2.281 Điều.
- Cập nhật đáp án benchmark theo số hiệu mới (`src/cypher_benchmark/catalogs/`).
- Merge `ocr-improvement` vào `main`; 274/274 test đạt với Neo4j thật.
- Lưu mã xử lý dữ liệu cũ vào `tools/lich_su_xu_ly/`.

## Kiên

- [ ] Tra văn bản đã thay thế 09/2020/TT-BGDĐT (0151) và 09/2016/TTLT-BGDĐT-BTC-BLĐTBXH (0011);
      web trường ghi hết hiệu lực nhưng kho chưa có văn bản thay thế. Đọc điều khoản trong văn bản
      thay thế rồi mới sửa `status` + `note` trong JSON v1, v2, v4.
- [ ] Sửa tiếp lỗi OCR theo `F:\DUT4\PBL6\TIEN_DO_SUA_OCR.md` (54 văn bản lỗi ≥ 1%, `0440` mới
      đến trang 19). Chỉ sửa chỗ OCR sai, không chèn ghi chú vào `.txt`.
- [ ] Sửa `107/QĐ-ĐHBK` thành `1077/QĐ-ĐHBK` trong `data/clean/text_final/` của 0465 (lỗi OCR
      còn sót ở bản `.txt`).
- [ ] Cập nhật `docs/TIEN_DO.md` và `README.md` theo số liệu tháng 11 (đồ thị v4, benchmark,
      các mục đã xong ở trên).
- [ ] Ráp các góp ý của nhóm vào báo cáo, cập nhật mục lục, rà toàn bộ lần cuối.

## Đức

- [ ] Chatbot đôi khi đưa văn bản không liên quan vào phần Nguồn và không nhắc văn bản đã bị thay
      thế. Tái hiện: hỏi "Văn bản nào của ĐHBK về yêu cầu ngoại ngữ còn hiệu lực?" vài lần trên
      giao diện; có lần Nguồn kèm 1077/QĐ-ĐHBK và không nhắc 1345/QĐ-ĐHBK bị 4511 thay thế.
- [ ] Sắp các Điều trong phần Nguồn theo thứ tự số (đang ra "Điều 4, Điều 6, Điều 10, Điều 1").
- [ ] Đưa hướng dẫn dựng lại đồ thị vào README chính (`data/neo4j_dump/README.md` bị xoá khỏi
      `main` ở commit `f4892b9`). Lưu ý: phải gom phẳng cả 103 tệp JSON v4, kể cả `_nghi_ngo/`,
      và đặt `LKG_PAGE_PROVENANCE=data/clean/nguon_trang/dieu_v4.json`.
- [ ] Đọc soát báo cáo mục 3.5, 3.6, 4.1, 4.4, 4.5.1; gửi góp ý cho Kiên.

## Nguyên

- [ ] Merge nhánh `eval/danh-gia-v4` vào `main` (rebase theo `main` mới trước; đáp án benchmark
      đã đổi ở commit `bbf0ac3`).
- [ ] Chạy lại `python run.py bench --compare-bm25` và `python run.py lkg chat-eval` trên đồ thị đã
      dựng lại; commit báo cáo kết quả trong `src/cypher_benchmark/reports/`.
- [ ] Gửi Kiên số mới để thay vào báo cáo mục 4.5.4, 4.5.5, Bảng 4.7 và Hình 4.4 (biểu đồ vẽ từ
      các số F1, nDCG@10 của 7 cách tìm).
- [ ] Đọc soát báo cáo mục 4.5.2–4.5.6; gửi góp ý cho Kiên.

## Tùng

- [ ] Làm người gán thứ hai cho bộ chuẩn OCR 20 trang: so từng tệp trong
      `data/eval/ocr_gold/chuan/` với ảnh trang PDF gốc, sửa chỗ sai, ghi lại số chỗ đã sửa.
      Đọc `data/eval/ocr_gold/README.md` trước. PDF gốc nhờ Kiên gửi (không nằm trong git).
- [ ] Dựng dự án trên một máy sạch theo Phụ lục C của báo cáo; ghi lại bước nào lỗi hoặc thiếu
      để sửa hướng dẫn.
- [ ] Bổ sung phần việc của mình vào Bảng 1.1 của báo cáo (dòng của Tùng đang có chỗ trống).
- [ ] Đọc soát báo cáo phần Mở đầu, chương 1, 2, 5 và Tài liệu tham khảo (đổi sang thứ tự xuất
      hiện trong bài nếu thầy yêu cầu kiểu IEEE); gửi góp ý cho Kiên.

## Cả nhóm

- [ ] Thống nhất tên đề tài trên bìa với tên đã đăng ký.
- [ ] Điền ngày nộp trên bìa (đang ghi "Đà Nẵng, 12/2026") và số nhóm nếu thầy yêu cầu.
- [ ] Chuẩn bị slide và kịch bản demo (chạy chatbot trực tiếp, mở Neo4j Browser).
