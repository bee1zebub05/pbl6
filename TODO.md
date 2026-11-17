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

## Mỗi người đọc lại và kiểm tra phần báo cáo của mình

Bản nháp báo cáo được viết từ Google Doc của nhóm và từ repo, **chưa ai trong nhóm đọc duyệt**.
Mỗi người đọc kỹ phần ứng với việc mình đã làm trong `bao_cao/Bao_cao_PBL6.docx` (cùng nội dung với
`F:\DUT4\PBL6\Bao_cao_PBL6.docx` trên máy Kiên; `git pull` để lấy bản mới nhất).

| Người | Phần trong báo cáo |
|---|---|
| Kiên | 2.2.1–2.2.2; 3.1; 3.3 (định dạng văn bản, text_final, JSON); 3.4 (xử lý dữ liệu); 3.5.3–3.5.4; 4.5.3 phần đối chiếu bản gốc và Bảng 4.6 |
| Đức | 2.2.3–2.2.6; 3.2; 3.5.1–3.5.2, 3.5.5–3.5.6 (ontology, quan hệ, đồ thị con); 3.6 (chatbot); 4.1–4.4; 4.5.1–4.5.2 |
| Nguyên | 2.2.7; 4.5.3 phần độ chính xác trích xuất (Bảng 4.5); 4.5.4–4.5.6 (đánh giá truy hồi, chatbot, nhận xét) |
| Tùng | Trang bìa, Mở đầu, chương 1 (cả Bảng 1.1), 2.1, chương 5, Tài liệu tham khảo, Phụ lục; định dạng chung (mục lục, danh mục hình, bảng, từ viết tắt) |

Khi đọc, kiểm tra:

- Mỗi câu mô tả đúng cái nhóm đã làm và đúng với code; không có chi tiết nào bịa hay hiểu sai.
- Mọi con số, tên tệp, tên lệnh, số hiệu văn bản khớp với kết quả thật trong repo.
- Hình và bảng đúng nội dung, chú thích đúng, được nhắc tới trong đoạn văn.
- Văn phong, chính tả, thuật ngữ thống nhất giữa các chương.

Góp ý bằng Comment hoặc Track Changes của Word rồi gửi cho Kiên; không tự commit đè tệp `.docx`.

- [ ] Kiên đã đọc và gửi góp ý
- [ ] Đức đã đọc và gửi góp ý
- [ ] Nguyên đã đọc và gửi góp ý
- [ ] Tùng đã đọc và gửi góp ý

## Kiên

### Chuyển toàn bộ kho sang JSON v4 (454 văn bản thay cho mẫu 103)

Hiện đồ thị, chatbot và mọi số đo chạy trên 103 văn bản liên quan người học. Kiên làm nốt 351
văn bản còn lại để hệ thống chạy trên toàn kho. Làm theo thứ tự:

- [x] (17/11) Nhóm 1–3 theo số trang PDF (1–10 trang, 136 văn bản): 131 văn bản có JSON v4, đã
      đối chiếu ảnh PDF gốc và sửa; tập đánh giá độ sai lệch ở `data/eval/kiem_pdf_v4/`. Model
      `gemini-3.1-flash-lite` (3.5-flash-lite bị quá tải 503).
- [ ] Nhóm 4–6 (11–20, 21–40, trên 40 trang; 213 văn bản) và 0161, 0352 (bản gốc .doc): làm theo
      đúng quy trình trong `data/eval/kiem_pdf_v4/README.md` (chụp bản gốc → đối chiếu ảnh PDF →
      trọng tài → chấm). Hai văn bản lớn 0245, 0246 (730–810 KB) chạy riêng sau cùng.
- [x] (17/11) 5 văn bản vướng lược đồ (0023, 0084, 0110, 0193, 0488): nới lược đồ (số mục A–Z, loại
      "Quy chế"), sửa `chay_json.py`; đã trích xuất và đối chiếu PDF. Nhóm 1–3 đủ 136/136.
- [ ] 0149: tìm bản PDF đủ trang (bản hiện có thiếu trang 2), thêm 11 quan hệ bãi bỏ còn thiếu.
- [ ] Kiểm tra lược đồ cho toàn bộ 454 tệp (`python run.py lkg validate --dir data/clean/json/v4`)
      và soi trích dẫn (`tools/kiem_tra/soi_trich_dan.py`); đọc soát các tệp rơi vào `_nghi_ngo/`.
- [ ] Suy hiệu lực trên toàn kho: `python tools/kiem_tra/suy_hieu_luc.py --dir data/clean/json/v4`
      (xem trước), rồi thêm `--sua`.
- [ ] Đối chiếu hiệu lực với web trường và PDF gốc như đã làm cho 103 văn bản ngày 16/11: chỗ nào lệch
      thì mở PDF kiểm, sửa kèm `note` ghi căn cứ.
- [ ] Dựng lại bảng Điều → trang PDF: `python tools/kiem_tra/nguon_trang.py --json v4` (cần 455 PDF
      gốc ở `data/raw/pdf/`).
- [ ] Dựng lại đồ thị từ cả 454 tệp (gom phẳng cả `_nghi_ngo/`), đặt
      `LKG_PAGE_PROVENANCE=data/clean/nguon_trang/dieu_v4.json`, rồi `python run.py lkg embed-articles`.
      Ghi lại số đỉnh, số cạnh theo loại.
- [ ] Cập nhật báo cáo theo kho mới: phạm vi ở Mở đầu và mục 1.4, Bảng 3.1, Bảng 3.5, mục 4.5.2
      (Bảng 4.4), mục 4.5.3, Kết luận; báo Nguyên khi đồ thị mới đã sẵn sàng.

### Việc khác

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

## Nguyên

- [ ] Merge nhánh `eval/danh-gia-v4` vào `main` (rebase theo `main` mới trước; đáp án benchmark
      đã đổi ở commit `bbf0ac3`).
- [ ] Chạy lại `python run.py bench --compare-bm25` và `python run.py lkg chat-eval` trên đồ thị đã
      dựng lại; commit báo cáo kết quả trong `src/cypher_benchmark/reports/`.
      **Chờ Kiên làm xong JSON v4 toàn kho rồi mới chạy.** Đáp án trong
      `src/cypher_benchmark/catalogs/gold_v4.json` đang gán trên 103 văn bản; khi kho thành 454
      văn bản, đáp án các câu lọc danh sách (S01–S04, S19, S20…) sẽ đổi, phải chạy lại Cypher từng
      câu trên đồ thị mới và gán lại trước khi chấm. Nhãn đối chứng `data/eval/v4_gold/` cũng chỉ phủ
      103 văn bản: hoặc gán thêm, hoặc ghi rõ trong báo cáo là đo trên mẫu 103.
- [ ] Gửi Kiên số mới để thay vào báo cáo mục 4.5.4, 4.5.5, Bảng 4.7 và Hình 4.4 (biểu đồ vẽ từ
      các số F1, nDCG@10 của 7 cách tìm).

## Tùng

- [ ] Làm người gán thứ hai cho bộ chuẩn OCR 20 trang: so từng tệp trong
      `data/eval/ocr_gold/chuan/` với ảnh trang PDF gốc, sửa chỗ sai, ghi lại số chỗ đã sửa.
      Đọc `data/eval/ocr_gold/README.md` trước. PDF gốc nhờ Kiên gửi (không nằm trong git).
- [ ] Dựng dự án trên một máy sạch theo Phụ lục C của báo cáo; ghi lại bước nào lỗi hoặc thiếu
      để sửa hướng dẫn.
- [ ] Bổ sung phần việc của mình vào Bảng 1.1 của báo cáo (dòng của Tùng đang có chỗ trống).
- [ ] Đổi Tài liệu tham khảo sang thứ tự xuất hiện trong bài nếu thầy yêu cầu kiểu IEEE.

## Cả nhóm

- [ ] Thống nhất tên đề tài trên bìa với tên đã đăng ký.
- [ ] Điền ngày nộp trên bìa (đang ghi "Đà Nẵng, 12/2026") và số nhóm nếu thầy yêu cầu.
- [ ] Chuẩn bị slide và kịch bản demo (chạy chatbot trực tiếp, mở Neo4j Browser).
