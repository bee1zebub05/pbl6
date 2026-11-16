# Báo cáo PBL6

Thư mục này chứa mẫu báo cáo của Khoa và bảng đối chiếu giữa mẫu với nội dung
nhóm đã viết, để mỗi người biết phần mình viết nằm ở đâu trong bản nộp.

- `Mau_bao_cao_PBL6_KhoaCNTT.docx`: mẫu gốc của Khoa CNTT, chưa sửa. Khi viết bản nộp,
  sao ra file mới rồi điền vào; giữ nguyên style có sẵn (Heading1–3, `0-NDUNG`,
  mục lục tự động) để mục lục và danh mục hình tự cập nhật.
- Bản nháp nội dung hiện viết trên Google Doc "BÁO CÁO PBL6", gồm 4 tab:
  Cơ sở lý thuyết, Xử lý dữ liệu, Đánh giá, Chatbot.

## Quy định định dạng của mẫu

- Nội dung: Times New Roman, cỡ 13, giãn dòng 1,3, căn đều hai bên.
- Tiêu đề chương: Times New Roman, đậm, cỡ 14, căn giữa. Trước nội dung để 2 dòng trống.
- Trang bìa: tên đề tài đậm, cỡ 20–30 tuỳ độ dài; ghi người hướng dẫn, tên sinh viên,
  lớp, nhóm; dòng "Đà Nẵng, <tháng>/<năm>" (mẫu đang ghi 9/2022, phải sửa).
- Mục "Mở đầu" phải nêu: mục đích, mục tiêu, phạm vi và đối tượng nghiên cứu,
  phương pháp nghiên cứu, cấu trúc của báo cáo.

## Đối chiếu mẫu với nội dung đã có

| Mục của mẫu | Nội dung đã có | Còn thiếu |
|---|---|---|
| Mở đầu | Chưa có | Viết toàn bộ |
| 1. Tổng quan đề tài | Tab Cơ sở lý thuyết, mục I (2 đoạn) | Hiện trạng tra cứu trên dut.udn.vn, các hệ thống và công trình liên quan, mục tiêu, phạm vi kho dữ liệu |
| 2.1. Ý tưởng | Rải rác ở các tab | Ý tưởng tổng thể (đồ thị tri thức + chatbot), hình kiến trúc toàn hệ |
| 2.2. Cơ sở lý thuyết | Tab Cơ sở lý thuyết, mục 1–7 (OCR, trích xuất bằng LLM, đồ thị tri thức, truy hồi, RAG/GraphRAG, chatbot, phương pháp đánh giá) | Công thức (CER, RRF, nDCG, κ) phải chèn lại bằng Equation; trích dẫn tài liệu tham khảo |
| 3.1. Phát biểu bài toán | Tab Chatbot (đầu vào và đầu ra của chatbot) | Phát biểu cho toàn hệ: đầu vào là kho PDF và metadata, đầu ra là đồ thị tri thức và câu trả lời có dẫn nguồn |
| 3.2. Thuật toán: xử lý dữ liệu | Tab Xử lý dữ liệu, mục 1–10 | Thêm 9.5–9.7 (bộ chuẩn OCR theo trang, truy nguồn Điều về trang PDF, rerank); bản nháp ở `docs/BAN_GIAO_OCR_IMPROVEMENT.md` trên nhánh `ocr-improvement` |
| 3.2. Thuật toán: xây dựng đồ thị | Chưa có tab nào | Ontology, schema node/cạnh, nạp Neo4j, suy hiệu lực, chỉ mục toàn văn và vector. Nguồn: `rules/Ontology.md`, `src/legal_knowledge_graph/docs/GRAPHREPORT.md`, `docs/Xay dung graph db.md` |
| 3.2. Thuật toán: chatbot | Tab Chatbot (dạng gạch đầu dòng) | Viết thành văn; mục "GraphRAG và suy hiệu lực văn bản" còn trống |
| 4.1. Tổ chức chương trình | `README.md` §4 | Sơ đồ module, các lệnh `run.py` |
| 4.2. Ứng dụng học máy | Rải rác | Gom lại: EasyOCR, Gemma/Gemini (OCR lượt hai, hiệu đính, trích xuất JSON), gemini-embedding-001, bge-reranker-v2-m3, LLM trong router và agent |
| 4.3. Ứng dụng kiểm thử | Chưa có | pytest của chatbot, bộ đo `src/cypher_benchmark` (regression, hiệu năng, kịch bản), `chat-eval`; chạy lại và ghi số |
| 4.4. Ngôn ngữ cài đặt | Chưa có | Python, Cypher, JavaScript (React + Vite), FastAPI, LangChain/LangGraph, Neo4j trên Docker |
| 4.5.1. Giao diện chính | Tab Chatbot (mới có tên mục) | Ảnh chụp giao diện chat mới, ảnh đồ thị trên Neo4j Browser |
| 4.5.2. Kết quả thực thi | Tab Đánh giá mục 2–4; tab Xử lý dữ liệu 1.2 và 10.6 | Số liệu graph đang chạy, ví dụ hội thoại thật |
| 4.5.3. Nhận xét đánh giá | Tab Đánh giá mục 5–6; tab Chatbot "Nhận xét đánh giá" | Gộp thành một mục, thống nhất số liệu |
| 5. Kết luận và hướng phát triển | Rải rác cuối mỗi tab | Viết thống nhất cho toàn đề tài |
| Tài liệu tham khảo | Chưa có | Toàn bộ |
| Phụ lục | Chưa có | Gợi ý: ontology đầy đủ, danh sách 68 template, prompt trích xuất, bảng benchmark theo từng câu |
| Danh mục hình vẽ | Chưa có | Đặt caption cho mọi hình để Word tự sinh |

## Lưu ý khi viết

- Số liệu phải lấy từ code và kết quả đã chạy trong repo, không tự đặt số.
- Thống nhất phạm vi dữ liệu: kho 454 văn bản (JSON v1, v2) và kho 103 văn bản liên
  quan người học (JSON v4, graph mà chatbot đang dùng). Mỗi bảng số liệu phải ghi rõ
  là đo trên kho nào.
- Nhãn đánh giá v4 và bộ chuẩn OCR 20 trang là do AI gán. Khi đưa vào báo cáo phải
  ghi rõ điều này, kèm phần người đã kiểm lại.
