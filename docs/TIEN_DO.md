# Báo cáo tiến độ — Đồ thị tri thức văn bản pháp quy DUT/ĐHĐN

Cập nhật: **18/11/2026**. Tổng quan dự án: [README.md](../README.md).
Đặc tả đích: [rules/Ontology.md](../rules/Ontology.md) (Mức 3).

## 1. Tóm tắt

Dự án có hai pipeline xây đồ thị tri thức trên cùng kho văn bản `data/clean/text_final`
(454 văn bản). Pipeline tự động (`src/vanban/`) hoàn chỉnh đến bước nạp Neo4j và không
còn phát triển. Pipeline gán tay (`src/legal_knowledge_graph/`) dựng graph từ **JSON v4 đủ 454/454 văn bản**
(18/11/2026), có chatbot tra cứu xây bằng LangChain + LangGraph, API và giao diện chat; đây là
hướng chính từ 19/09/2026.

Độ chính xác trích xuất đã có số: tập đánh giá `data/eval/kiem_pdf_v4/` gồm 351 văn bản, so JSON
model trả về với bản đã đối chiếu ảnh PDF gốc. Tồn đọng chính: đáp án benchmark truy hồi
(`gold_v4.json`) vẫn gán trên mẫu 103 văn bản, phải gán lại cho kho 454 văn bản.

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
| JSON v4 (toàn kho) | Hoàn thành 18/11 | 454/454 file hợp lệ; Gemini API (`gemini-3.1-flash-lite`) trích xuất, thân Điều cắt nguyên văn từ `.txt`, luật `vet_quan_he.py` bù quan hệ hiệu lực, agent Claude Sonnet đối chiếu ảnh PDF gốc, trọng tài duyệt; `suy_hieu_luc.py` suy trạng thái trên toàn kho |
| Nạp Neo4j (v4) | Hoàn thành 18/11 | 454 file → 437 `Document` thật sau gộp 16 nhóm trùng (cùng văn bản đăng ở hai lĩnh vực), 1.362 `Document` kể cả stub, 12.281 `Article` có embedding; 14.346 node, 19.959 cạnh; `REPLACES` 158, `REPEALS` 239, `AMENDS` 106 |
| Chatbot (LangGraph) | Hoạt động | Node intent (smalltalk / ngoài phạm vi / yêu cầu ghi-xoá, prompt injection); router trích action + slot (schema phẳng, bù số hiệu bằng regex), chọn 1 trong 68 template (mức 1–5, kiểm chạy thật trên graph), thừa điều kiện thì chuyển agent; agent ReAct với 3 tool (template, Cypher qua guard, GraphRAG); GraphRAG local search (hạt giống vector + BM25 gộp RRF, mở rộng theo quan hệ thay thế / sửa đổi / căn cứ, hiệu lực thực tế tính theo quan hệ); câu trả lời văn xuôi chỉ từ bằng chứng, có nguồn; hội thoại nhiều lượt bằng checkpointer; log JSON + LangSmith tracing (mặc định tắt); 165 kiểm thử đạt (offline + Neo4j thật) |
| API và giao diện chat | Hoạt động | FastAPI (`thread_id`), React/Vite |
| Bộ truy vấn | Hoàn thành | 17 truy vấn benchmark (đều dưới 30 ms trên graph 11.227 node), 20 kịch bản Cypher, 17 văn bản mẫu cho kiểm thử hồi quy |

Số node/cạnh chi tiết theo loại xem [GRAPHREPORT.md](../src/legal_knowledge_graph/docs/GRAPHREPORT.md).

### 2.4 Đánh giá

| Mục §6 | Tình trạng | Ghi chú |
|---|---|---|
| Độ chính xác trích xuất JSON v4 | **Có số (18/11)** | 351 văn bản, `data/eval/kiem_pdf_v4/`: số hiệu 98,0%, ngày ban hành 95,7%, người ký F1 0,91, trích dẫn F1 0,82; REPEALS model 52%, model + luật 96%. Đáp án do AI đối chiếu ảnh PDF, chưa có người kiểm |
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
| 4 | ~~36 file JSON ở `_nghi_ngo/` chưa nạp~~ | Đã xử lý 18/11: graph v4 nạp cả `_nghi_ngo/`, đủ 454/454 | — |
| 5 | ~~Nhóm số hiệu trùng~~ | Đã soi đủ 16 nhóm (18/11): đều là cùng một văn bản (trùng số hiệu, ngày, tên; 5 nhóm trùng cả SHA-256 PDF); đã thống nhất chỗ lệch giữa các bản (0271 ngày ban hành, 0019/0054 chức danh) | — |
| 6 | File `0049` sai nội dung | Thiếu văn bản "Quy chế làm việc của Phòng Thí nghiệm và Xưởng thực hành" | Cần thu thập lại từ nguồn |
| 7 | 34 văn bản header lệch số hiệu, 28 văn bản không đọc ra số hiệu | Một phần là lỗi metadata gốc (ví dụ `1/2024/TT-NBV` thực là `TT-BNV`) | Người xác nhận rồi sửa; đổi số hiệu là đổi khoá chính |
| 8 | 15 văn bản 404 | Luật BHXH 2024, `36/2024/QH15`, `115/2020/NĐ-CP`, `75/2012/NĐ-CP` chỉ là stub | Tìm nguồn khác |
| 9 | 54 văn bản lỗi OCR ≥ 1%; `0440` mới sửa đến trang 19/~60; 7 chỗ cần đối chiếu ảnh | Lỗi chính tả dạng `é` thay `ế/ề/ể/ệ` không sửa máy móc được; thân Điều v4 cắt từ `.txt` nên mang theo lỗi này | Đọc tay đối chiếu PDF gốc (đã có lại trên máy Kiên, `data/raw/pdf/`) |
| 13 | 0149: bản PDF thiếu trang 2 | 11 quan hệ bãi bỏ ở trang đó chưa thêm | Tìm bản PDF đủ trang |
| 14 | Trạng thái hiệu lực chỉ đúng "trong phạm vi kho" | Văn bản bị thay bởi văn bản ngoài kho vẫn ghi còn hiệu lực (vd 0151, 0011 web trường ghi đã hết) | Tra văn bản thay thế từ nguồn chính thức rồi mới sửa |
| 10 | `targetGroups`: 186 file rỗng; 16 văn bản nhãn "Khác"; 7 văn bản có cách diễn đạt đối tượng khác thường | `APPLIES_TO` phủ 268/454 văn bản | Rà tay 23 văn bản nêu trên (danh sách ở GRAPHREPORT §5) |
| 11 | `targetArticle` của `AMENDS` chỉ là thuộc tính chuỗi | Không truy vấn được "Điều nào bị sửa" ở mức node | Giới hạn phạm vi có chủ đích |
| 12 | Router chatbot: 4/20 câu hỏi định tuyến nhận slot rỗng (nhóm cơ quan, lĩnh vực, `content_type`, cụm từ) | Không chọn đúng template cho các câu này (đúng 16/20) | Đã sửa: nguyên nhân là slot là key tuỳ chọn nên Gemini bỏ hẳn key; nay bắt buộc mọi key. Chờ quota để đo lại trọn bộ 20 câu |

## 4. Nhật ký

| Ngày | Công việc |
|---|---|
| 18/11/2026 | JSON v4 đủ 454 văn bản (nhóm 6, 0161, 0352 bản gốc Word); rà toàn kho: 11 quan hệ "bãi bỏ một phần" đổi sang `AMENDS`, bỏ trích dẫn lấy ngày/năm làm số hiệu và số hiệu bịa, trạng thái model tự suy đưa về null; `suy_hieu_luc.py`: 26 văn bản sang hết hiệu lực; dựng bảng Điều → trang (12.281 Điều) và graph v4, embed đủ 12.281 Điều; 274/274 kiểm thử đạt với Neo4j thật |
| 17/11/2026 | JSON v4 nhóm 1–5 (299 văn bản) theo số trang PDF; tập đánh giá `data/eval/kiem_pdf_v4/`; luật `tools/kiem_tra/vet_quan_he.py` vét quan hệ hiệu lực (REPEALS 29% → 99% trên nhóm 1–3, không ra quan hệ sai) |
| 16/11/2026 | Đối chiếu PDF gốc: sửa số hiệu 0465, 0489, 0051 và hiệu lực 0461, 0051; dựng lại graph v4 103 văn bản; cập nhật đáp án benchmark; merge `ocr-improvement` vào `main` |
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
