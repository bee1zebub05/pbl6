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

- [x] (17/11) Kiên đã đọc: sửa 3.1.1, 2.2.2, 3.3.3, 3.4.6, 3.5.4 theo dữ liệu thật; báo cáo 43 trang
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
- [x] (17/11) Nhóm 4 (11–20 trang, 82 văn bản): đủ 82/82 JSON v4, Sonnet đối chiếu ảnh PDF, trọng
      tài duyệt; tập đánh giá lên 218 văn bản. Thêm "Chiến lược" vào loại nội dung kèm theo (0180).
- [x] (17/11) Bước luật `tools/kiem_tra/vet_quan_he.py` chạy sau `chay_json.py`: vét REPLACES/REPEALS
      model bỏ sót (REPEALS 45% → 99% trên 218 văn bản), báo chỗ model gán sai loại.
- [x] (17/11) Nhóm 5 (21–40 trang, 81 văn bản): đủ 81/81 JSON v4, Sonnet đối chiếu ảnh PDF, trọng
      tài duyệt; tập đánh giá lên 299 văn bản.
- [x] (17/11) Nhóm 6 (trên 40 trang; 50 văn bản, gồm 0245, 0246) và 0161, 0352 (bản gốc Word, chuyển
      sang PDF để đối chiếu; tệp 0161 trên web trường bị chèn 122 byte đường dẫn ở đầu, đã cắt và bù).
      v4 đủ 454/454; tập đánh giá 351 văn bản. `chay_json.py` bỏ Điều có nhãn bịa (0343).
- [x] (17/11) 5 văn bản vướng lược đồ (0023, 0084, 0110, 0193, 0488): nới lược đồ (số mục A–Z, loại
      "Quy chế"), sửa `chay_json.py`; đã trích xuất và đối chiếu PDF. Nhóm 1–3 đủ 136/136.
- [x] (17/11) 0149: bản trên web trường giống hệt bản trên máy (cùng SHA-256, 5 trang, thiếu trang 2).
      Lấy bản chính thức 6 trang trên datafiles.chinhphu.vn (lưu ở `data/raw/pdf_bo_sung/`), thêm 11
      quan hệ bãi bỏ (mục 3–13) vào JSON v4 và đồ thị.
- [x] (17/11) Sửa lỗi OCR theo ảnh PDF cho 26 văn bản có tỷ lệ âm tiết sai ≥ 1% (bộ đo mới
      `tools/kiem_tra/am_tiet.py`; 6 phụ lục scan vỡ cố ý bỏ qua): 3 agent Sonnet sửa 8 văn bản
      (0177, 0494, 0022, 0415, 0229, 0264, 0304, 0439), 18 văn bản còn lại chỉ bị đếm nhầm do từ
      nước ngoài, URL, ký hiệu. Cắt lại Điều vào JSON v4 bằng `tools/kiem_tra/cat_lai_dieu.py` (15 Điều
      đổi chữ), cập nhật text và embedding của 15 Điều đó trên Neo4j.
- [x] (17/11) Kiểm tra lược đồ cho toàn bộ 454 tệp: hợp lệ cả 454. Rà toàn kho: bỏ trích dẫn lấy
      ngày làm số hiệu, đổi 11 quan hệ "bãi bỏ/thay thế một phần" sang AMENDS, đưa 6 trạng thái
      model tự suy về null. Còn: soi trích dẫn (`tools/kiem_tra/soi_trich_dan.py`), đọc soát `_nghi_ngo/`.
- [x] (17/11) Suy hiệu lực trên toàn kho (`suy_hieu_luc.py --sua`): 26 văn bản sang HET_HIEU_LUC.
- [x] (17/11) Đối chiếu hiệu lực với web trường: 65 chỗ lệch. ~45 văn bản ta ghi hết hiệu lực vì có
      văn bản trong kho thay thế/bãi bỏ (web chậm cập nhật, như 1345, 905 đã kiểm PDF ngày 16/11);
      10 văn bản CHUA_HIEU_LUC đã qua ngày hiệu lực → CON_HIEU_LUC; 11 văn bản web ghi hết mà trong
      kho không có văn bản thay thế → giữ nguyên (xem "Việc khác" về 0151, 0011).
- [x] (17/11) Soi trích dẫn toàn kho (`soi_trich_dan.py` trên v4): 2.699/2.707 số hiệu có nguyên văn
      trong `.txt`; bỏ 1 số hiệu bịa (0093: "29/2015/QH13" ghép từ "Điều 29"). Soát 16 nhóm số hiệu
      trùng: đều là cùng văn bản; sửa ngày 0271, chức danh 0019/0054 theo PDF.
- [x] (17/11) Dựng lại bảng Điều → trang PDF: 12.281 Điều (7.523 độ tin cậy cao).
- [x] (17/11) Dựng lại đồ thị từ 454 tệp: 437 văn bản thật (1.362 `Document` kể cả stub), 12.281
      `Article`, 372 `NormativeContent`, 245 `Organization`, 61 `Person`; 14.346 đỉnh, 19.959 cạnh
      (`BASED_ON` 1.887, `REFERENCES` 230, `REPLACES` 158, `REPEALS` 239, `AMENDS` 106). Embed đủ
      12.281 Điều. 274/274 test đạt với Neo4j thật. Chatbot chưa thử được hôm 17/11 vì 18 key Gemini
      đang hết quota.
- [x] (17/11) Cập nhật báo cáo theo kho mới: phạm vi ở Mở đầu, Bảng 3.1, Bảng 3.5 và câu dẫn, mục
      4.5.2 (Bảng 4.4), thêm đoạn đối chiếu toàn kho sau Bảng 4.6 (4.5.3), hạn chế đánh giá, Kết luận,
      Phụ lục C; cập nhật mục lục. Mục 1.4 không cần sửa. Bảng 4.5 (phần Nguyên) và 4.5.4–4.5.5
      vẫn là số đo trên mẫu 103, chờ Nguyên chạy lại.
- [ ] Báo Nguyên: đồ thị 454 văn bản đã sẵn sàng (17/11), chạy lại benchmark và gán lại `gold_v4.json`.

### Việc khác

- [x] (17/11) 0151 (09/2020/TT-BGDĐT): Điều 2 Thông tư 08/2022/TT-BGDĐT (bản chính thức
      datafiles.chinhphu.vn/cpp/files/vbpq/2022/08/08-bgddt.signed.pdf) thay thế, hiệu lực 22/7/2022;
      đã sửa `status` + `note` trong v1, v2, v4 và đồ thị.
- [ ] 0011 (09/2016/TTLT-BGDĐT-BTC-BLĐTBXH): chưa tìm được văn bản chính thức tuyên bố thay thế.
      Nghị định 81/2021/NĐ-CP (0109, có trong kho) chỉ thay Nghị định 86/2015 mà TTLT này hướng dẫn,
      không nêu tên TTLT; web trường ghi "Hết hiệu lực 15/02/2022" không khớp điều khoản nào tìm
      được. Giữ CON_HIEU_LUC cho tới khi có văn bản tuyên bố.
- [x] (17/11) Sửa tiếp lỗi OCR (mức 1: các văn bản ≥ 1%, xem mục sửa OCR ở trên). Còn lại nếu
      muốn làm tiếp: lỗi `é` thay `ế/ề/ể/ệ` nằm trong từ vẫn hợp lệ (bộ đo không bắt được), và
      `0440` mới đọc tay đến trang 19.
- [x] (17/11) Sửa `107/QĐ-ĐHBK` thành `1077/QĐ-ĐHBK` trong `text_final` của 0465 (theo PDF gốc).
- [x] (17/11) Cập nhật `docs/TIEN_DO.md` và `README.md` theo số liệu tháng 11.
- [ ] Ráp các góp ý của nhóm vào báo cáo, cập nhật mục lục, rà toàn bộ lần cuối.

## Đức

- [ ] Chatbot đôi khi đưa văn bản không liên quan vào phần Nguồn và không nhắc văn bản đã bị thay
      thế. Tái hiện: hỏi "Văn bản nào của ĐHBK về yêu cầu ngoại ngữ còn hiệu lực?" vài lần trên
      giao diện; có lần Nguồn kèm 1077/QĐ-ĐHBK và không nhắc 1345/QĐ-ĐHBK bị 4511 thay thế.
- [ ] Sắp các Điều trong phần Nguồn theo thứ tự số (đang ra "Điều 4, Điều 6, Điều 10, Điều 1").
- [x] (17/11, Kiên làm) Đưa hướng dẫn dựng lại đồ thị vào README chính, mục 7: gom phẳng cả 454 tệp
      JSON v4, kể cả `_nghi_ngo/`, và đặt `LKG_PAGE_PROVENANCE=data/clean/nguon_trang/dieu_v4.json`.

## Nguyên

- [ ] Merge nhánh `eval/danh-gia-v4` vào `main` (rebase theo `main` mới trước; đáp án benchmark
      đã đổi ở commit `bbf0ac3`).
- [ ] Chạy lại `python run.py bench --compare-bm25` và `python run.py lkg chat-eval` trên đồ thị đã
      dựng lại; commit báo cáo kết quả trong `src/cypher_benchmark/reports/`.
      **JSON v4 toàn kho và đồ thị 454 văn bản đã xong ngày 17/11 — chạy được.** Đáp án trong
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
