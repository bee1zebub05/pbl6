# Báo cáo tiến độ — Đồ thị tri thức văn bản pháp quy DUT/ĐHĐN

Cập nhật: **11/10/2026**. Tổng quan dự án: [README.md](../README.md).
Đặc tả đích: [rules/Ontology.md](../rules/Ontology.md) (Mức 3).

## 1. Tóm tắt

Dự án có hai pipeline xây đồ thị tri thức trên cùng kho văn bản `data/clean/text_final`
(454 văn bản). Pipeline tự động (`src/vanban/`) hoàn chỉnh đến bước nạp Neo4j và không
còn phát triển. Pipeline gán tay (`src/legal_knowledge_graph/`) đã nạp 418/454 văn bản
vào một graph riêng, có chatbot tra cứu xây bằng LangChain + LangGraph, API và giao diện chat; đây là
hướng chính từ 19/09/2026.

Tồn đọng chính: **chưa có số đo độ chính xác** của việc trích xuất quan hệ do gold set
chưa được gán, và đánh giá retrieval mới có số cho nhóm câu hỏi đơn giản nhất.

## 2. Tình trạng theo giai đoạn

### 2.1 Chuẩn bị dữ liệu (dùng chung)

| Bước | Tình trạng | Kết quả |
|---|---|---|
| Crawl `dut.udn.vn` | Hoàn thành | Mục lục 475, tải được 460, 15 văn bản lỗi 404 |
| OCR EasyOCR cục bộ | Hoàn thành | 501/501 file, 11.420 trang |
| Chuẩn hoá số hiệu, ngày ban hành | Hoàn thành | Số hiệu đúng 25,5% → 94,6%; ngày ban hành đúng 40,7% → 82,0% |
| Hiệu đính bằng Gemma | Hoàn thành | 460/501 file; OCR lại các file kém, chọn bản tốt hơn cho từng văn bản |
| Dựng `text_final` | Hoàn thành | 454 văn bản; loại 5 bản website gắn nhầm file và `0158` |
| Sửa lỗi OCR mức ký tự | Một phần | 294/455 văn bản; 75 văn bản đọc tay; lỗi trung vị 0,13%, còn 54 văn bản ≥ 1% và 9 văn bản ≥ 3% |

Chất lượng `text_final`: ngày ban hành đọc được 100%; người ký 99% (4 văn bản còn lại là
biểu mẫu để trống chỗ ký); mục Căn cứ 93%; cấu trúc Điều 91%.

### 2.2 Pipeline tự động (`src/vanban/`)

| Bước | Nội dung | Tình trạng |
|---|---|---|
| 0 | Bảng `Document`: gộp trùng, bậc thẩm quyền, hiệu lực | Hoàn thành |
| 1 | Cắt vùng cấu trúc (header, Căn cứ, thân, điều khoản thi hành) | Hoàn thành |
| 2 | Trích số hiệu, nối `Document`, tạo stub | Hoàn thành |
| 3 | Phân loại `REPLACES` / `AMENDS` / `REPEALS` | Hoàn thành |
| 4 | `NormativeContent`, `Article` | Hoàn thành |
| 5 | Nạp Neo4j, bộ Cypher mẫu | Hoàn thành |
| Chạy lại trên `text_final` | `python run.py kg docs` và các bước sau | **Chưa thực hiện** |

Graph hiện có (đo ngày 03/09/2026, dựng từ `text_clean_gemma`): 10.978 node, 14.120 cạnh;
`Document` 1.244 (450 thật, 794 stub); `Article` 9.518; `BASED_ON` 1.853, `REFERENCES` 1.194,
`REPLACES` 88, `AMENDS` 56, `REPEALS` 23.

Chất lượng các bước: header khớp metadata 86% (386/448); tìm được vùng Căn cứ 95%
(427/448); trích dẫn nối được vào `Document` 88% (5.371/6.090).

Hai đánh đổi thiết kế đã chốt: (a) tạo stub khi số hiệu được viện dẫn ≥ 2 lần hoặc nằm
trong vùng Căn cứ; (b) quan hệ hiệu lực ưu tiên precision, nên recall thấp
(1.922 lần xuất hiện cụm "sửa đổi, bổ sung" nhưng chỉ 118 cạnh `AMENDS`).

### 2.3 Pipeline gán tay (`src/legal_knowledge_graph/`)

| Hạng mục | Tình trạng | Kết quả |
|---|---|---|
| JSON v1 (sinh từ `text_final`) | Hoàn thành | 454 file; thân Điều khớp nguyên văn `.txt` 99,87%; trích dẫn có số hiệu kiểm chứng được 100%; 0 file trượt schema; 53 file đối chiếu tay |
| JSON v2 (bổ sung `targetGroups`) | Hoàn thành | 454 file |
| Nạp Neo4j | Hoàn thành | 418/454 văn bản (403 `Document` thật sau gộp trùng), 11.227 node, 17.410 cạnh |
| Chatbot (LangGraph) | Hoạt động | Node intent (smalltalk / ngoài phạm vi / yêu cầu ghi-xoá, prompt injection); router trích action + slot (schema phẳng, bù số hiệu bằng regex), chọn 1 trong 68 template (mức 1–5, kiểm chạy thật trên graph), thừa điều kiện thì chuyển agent; agent ReAct với 3 tool (template, Cypher qua guard, GraphRAG); GraphRAG local search (hạt giống vector + BM25 gộp RRF, mở rộng theo quan hệ thay thế / sửa đổi / căn cứ, hiệu lực thực tế tính theo quan hệ); câu trả lời văn xuôi chỉ từ bằng chứng, có nguồn; hội thoại nhiều lượt bằng checkpointer; log JSON + LangSmith tracing (mặc định tắt); 165 kiểm thử đạt (offline + Neo4j thật) |
| API và giao diện chat | Hoạt động | FastAPI (`thread_id`), React/Vite |
| Bộ truy vấn | Hoàn thành | 17 truy vấn benchmark (đều dưới 30 ms trên graph 11.227 node), 20 kịch bản Cypher, 17 văn bản mẫu cho kiểm thử hồi quy |

Số node/cạnh chi tiết theo loại xem [GRAPHREPORT.md](../src/legal_knowledge_graph/docs/GRAPHREPORT.md).

### 2.4 Đánh giá

| Mục §6 | Tình trạng | Ghi chú |
|---|---|---|
| 6.1 Gold set, Cohen's κ | **Chưa thực hiện** | 175 phiếu gán trong `data/eval/goldset/phieu_gan/`; `nguoi_gan_1/` và `nguoi_gan_2/` trống. Tài liệu ngày 03/09 ghi 131 phiếu; thư mục hiện có 175, chưa xác định nguyên nhân chênh lệch |
| 6.2 P/R/F1 theo quan hệ | Chưa thực hiện | Phụ thuộc gold set |
| 6.3–6.4 BM25 / KG / Hybrid | Một phần | 14/45 câu single-hop có đáp án (tự sinh từ metadata) |
| 6.5 Nhóm multi-hop | Chưa thực hiện | 31 câu cần người điền đáp án |
| 6.6 Ablation | Có số | Bỏ cắt vùng mất 62,9% cạnh; bỏ stub mất 68,6%. Hạng mục `-OCR` không đo được vì PDF gốc không còn |
| 6.7 Phân tích lỗi | Có số | 342/354 văn bản (96,6%) có ít nhất một nhánh `BASED_ON` kết thúc ở stub |
| Chatbot (`chat-eval`) | Chưa ghi kết quả | Bộ gold câu hỏi và lệnh chạy đã có; chưa có báo cáo số đo |

Kết quả §6.4 trên 14 câu single-hop (ngày 03/09/2026):

| Hệ | P@5 | R@10 | MRR | nDCG@10 |
|---|---|---|---|---|
| BM25 | 0,586 | 0,162 | 0,729 | 0,659 |
| KG | 1,000 | 0,294 | 1,000 | 1,000 |
| Hybrid | 0,943 | 0,254 | 1,000 | 0,926 |

KG đạt điểm tối đa vì các câu này tra trực tiếp thuộc tính metadata (cơ quan, lĩnh vực,
hiệu lực); kết quả không phản ánh năng lực ở nhóm multi-hop.

## 3. Tồn đọng

| # | Vấn đề | Ảnh hưởng | Hướng xử lý |
|---|---|---|---|
| 1 | Gold set chưa được gán | Không có P/R/F1 và κ; không kết luận được pipeline gán tay vượt pipeline tự động | Hai người gán độc lập theo `goldset/huong_dan_gan.md`; thử 20 văn bản đầu, tính κ, chỉnh hướng dẫn, gán tiếp |
| 2 | 31/45 câu hỏi retrieval chưa có đáp án | Chưa đánh giá được multi-hop và hiệu lực | Người đọc văn bản và điền cột `DAP_AN` trong `queries.csv` |
| 3 | Graph tự động dựng trên `text_clean_gemma` | Số liệu graph tự động không khớp `text_final` | Chạy lại `kg all` và `kg load --wipe` |
| 4 | 36 file JSON ở `_nghi_ngo/` chưa nạp | Graph gán tay phủ 418/454 văn bản | Đọc soát từng file; phần lớn là Công văn, Kế hoạch không có mục Căn cứ nên có thể hợp lệ |
| 5 | 14 nhóm số hiệu trùng (29 file) | `MERGE` gộp thành một `Document`, thuộc tính phẳng bị ghi đè | Đã soi 2 nhóm (`05/NQ-HĐT`, `771/QĐ-ĐHBK`, vô hại); 12 nhóm còn lại chưa soi; dùng `idOverride` nếu hai văn bản khác nhau |
| 6 | File `0049` sai nội dung | Thiếu văn bản "Quy chế làm việc của Phòng Thí nghiệm và Xưởng thực hành" | Cần thu thập lại từ nguồn |
| 7 | 34 văn bản header lệch số hiệu, 28 văn bản không đọc ra số hiệu | Một phần là lỗi metadata gốc (ví dụ `1/2024/TT-NBV` thực là `TT-BNV`) | Người xác nhận rồi sửa; đổi số hiệu là đổi khoá chính |
| 8 | 15 văn bản 404 | Luật BHXH 2024, `36/2024/QH15`, `115/2020/NĐ-CP`, `75/2012/NĐ-CP` chỉ là stub | Tìm nguồn khác |
| 9 | 54 văn bản lỗi OCR ≥ 1%; `0440` mới sửa đến trang 19/~60; 7 chỗ cần đối chiếu ảnh | Lỗi chính tả dạng `é` thay `ế/ề/ể/ệ` không sửa máy móc được | Đọc tay; cần PDF gốc (không còn trên máy) |
| 10 | `targetGroups`: 186 file rỗng; 16 văn bản nhãn "Khác"; 7 văn bản có cách diễn đạt đối tượng khác thường | `APPLIES_TO` phủ 268/454 văn bản | Rà tay 23 văn bản nêu trên (danh sách ở GRAPHREPORT §5) |
| 11 | `targetArticle` của `AMENDS` chỉ là thuộc tính chuỗi | Không truy vấn được "Điều nào bị sửa" ở mức node | Giới hạn phạm vi có chủ đích |
| 12 | Router chatbot: 4/20 câu hỏi định tuyến nhận slot rỗng (nhóm cơ quan, lĩnh vực, `content_type`, cụm từ) | Không chọn đúng template cho các câu này (đúng 16/20) | Đã sửa: nguyên nhân là slot là key tuỳ chọn nên Gemini bỏ hẳn key; nay bắt buộc mọi key. Chờ quota để đo lại trọn bộ 20 câu |

## 4. Nhật ký

| Ngày | Công việc |
|---|---|
| 11/10/2026 | Chatbot đổi được nhà cung cấp LLM và embedding bằng cấu hình (`LKG_LLM_PROVIDER`, `LKG_EMBED_PROVIDER`): Gemini hoặc mọi server chuẩn OpenAI API (tự host vLLM/Ollama hoặc dịch vụ); `embed-articles --reset` dựng lại vector index khi đổi model embedding; chia lại `core/chat/` theo bước pipeline (`understanding/`, `retrieval/`, `answering/`, `adapters/`, `workflow/`, `models/`), gộp kết nối Neo4j vào `core/db.py` |
| 11/10/2026 | Chatbot: router dùng schema phẳng (đúng template 11/20 → 16/20) và bù `doc_number` bằng regex nhận diện số hiệu (nhận 1.394/1.399 số hiệu trong graph); tìm cụm ≥ 3 âm tiết khớp cả các âm tiết đảo thứ tự; GraphRAG ưu tiên văn bản được câu hỏi nêu tên; kiểm thử không còn gửi trace LangSmith, tracing mặc định tắt. Kiểm chứng đầu-cuối với Gemini + Neo4j thật trên 2 câu hỏi về `2673/QĐ-ĐHBK` (đúng template, cảnh báo đã bị `1092/QĐ-ĐHBK` thay thế, 3 lượt LLM); 165 kiểm thử đạt |
| 09/10/2026 | GraphRAG cho chatbot: ngữ cảnh Điều + quan hệ thay bước tìm Điều chỉ bằng vector; phát hiện 44 văn bản đã bị thay thế nhưng `status` vẫn ghi còn hiệu lực, chatbot cảnh báo theo quan hệ |
| 09/10/2026 | Dựng lại chatbot bằng LangChain + LangGraph (`core/chat/`): node intent, router khung action + slot, agent ReAct, câu trả lời có dẫn nguồn, hội thoại nhiều lượt, LangSmith + log JSON; xoá `pipeline.py`, `match_template.py`, `freeform.py`; ghim phiên bản thư viện |
| 30/09/2026 | Dọn mã chết trong `core/`; thêm 20 kịch bản Cypher; `evaluate` dùng lại được cho BM25 |
| 29/09/2026 | Dọn mã theo hướng sẵn sàng vận hành, loại trùng lặp trong `core/` |
| 28/09/2026 | NLQ: alias, hỏi lại, tự sửa Cypher; retrieval ngữ nghĩa chạy song song Cypher |
| 22/09/2026 | Bù `targetGroups` thành kho v2; bể khoá cho NLQ; đo benchmark; viết lại tài liệu |
| 21/09/2026 | Dựng ứng dụng: frontend, API, Cypher cơ bản |
| 20/09/2026 | Loại `0158` khỏi bộ dữ liệu (file Word gốc hỏng, không dựng lại được); kho còn 454 văn bản |
| 19/09/2026 | Hoàn tất JSON v1 (454 file); sửa lỗi hệ thống do các lượt đọc tay phát hiện; gỡ 26 trích dẫn có số hiệu không có căn cứ; đọc lại `0196` từ bản scan (53 → 105 Điều) |
| 18/09/2026 | Tách văn bản lồng nhau vào `normativeContents`; vá 111 Điều bị bỏ sót |
| 03/09/2026 | Có mã khối đánh giá §6 (`src/vanban/eval/`); sinh gold set phân tầng và bộ 45 câu hỏi; chạy BM25/KG/Hybrid, ablation, phân tích lỗi |
| 27/08/2026 | Hoàn thành Bước 0–5 của pipeline tự động; nạp Neo4j |
| 26/08/2026 | Hiệu đính Gemma xong 460/501 |
| 25/08/2026 | Chốt ontology v0.3 |
| 21/08/2026 | Chuẩn hoá 501/501 |
| 17/08/2026 | Xuất `data/manifest.jsonl` |
