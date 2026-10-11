# PBL6 — Đồ thị tri thức văn bản pháp quy Trường ĐH Bách khoa, Đại học Đà Nẵng

Tài liệu này mô tả mục tiêu, cấu trúc và tình trạng hiện hành của dự án.
Số liệu cập nhật ngày **09/10/2026**. Diễn biến theo thời gian và các tồn đọng
xem [docs/TIEN_DO.md](docs/TIEN_DO.md).

## 1. Mục tiêu

Xây dựng đồ thị tri thức (knowledge graph) từ văn bản pháp quy công bố tại
`dut.udn.vn/VanBanPhapQuy` để hỗ trợ tra cứu trong quản trị đại học, đặc biệt
các câu hỏi mà tìm kiếm từ khoá không trả lời được: chuỗi căn cứ pháp lý,
văn bản thay thế / sửa đổi / bãi bỏ, hiệu lực của một văn bản. Đặc tả ontology
nằm ở [rules/Ontology.md](rules/Ontology.md).

## 2. Hai pipeline xây graph

Dự án có hai pipeline dùng chung một kho văn bản đầu vào (`data/clean/text_final`)
nhưng khác nhau ở cách trích xuất quan hệ.

| | Pipeline tự động | Pipeline gán tay |
|---|---|---|
| Mã nguồn | `src/vanban/` | `src/legal_knowledge_graph/` |
| Cách trích xuất | Quy tắc (regex), cắt vùng cấu trúc, phân loại quan hệ theo vùng và từ khoá | Mô hình ngôn ngữ sinh JSON theo schema, kiểm tra bằng schema và các bộ soi, một phần đọc tay |
| Đầu ra trung gian | `data/kg/*.jsonl` | `data/clean/json/v1/`, `data/clean/json/v2/` |
| Neo4j | `bolt://localhost:7687` | `bolt://localhost:7688` (`docker-compose.yml`) |
| Lớp ứng dụng | Khối đánh giá §6 (`src/vanban/eval/`) | Chatbot tra cứu (LangChain + LangGraph), API FastAPI, giao diện chat React |
| Tình trạng | Hoàn chỉnh đến Bước 5, không còn phát triển; dữ liệu graph dựng trên bản text cũ | Đang phát triển; là hướng chính hiện nay |
| Tài liệu | [docs/PIPELINE_TU_DONG.md](docs/PIPELINE_TU_DONG.md) | [src/legal_knowledge_graph/README.md](src/legal_knowledge_graph/README.md), [GRAPHREPORT.md](src/legal_knowledge_graph/docs/GRAPHREPORT.md) |

Lý do có pipeline gán tay: bộ trích xuất quy tắc thiên về precision và có recall
thấp ở nhóm quan hệ hiệu lực (kho có 1.922 lần xuất hiện cụm "sửa đổi, bổ sung"
nhưng chỉ 118 cạnh `AMENDS`). Pipeline gán tay thay thế khâu trích xuất này; việc
kiểm chứng mức cải thiện bằng số đo vẫn chưa thực hiện được (xem mục 5).

## 3. Luồng dữ liệu và tình trạng từng bước

```
Crawl PDF ──► OCR ──► Chuẩn hoá ──► Hiệu đính ──► text_final ─┬─► Pipeline tự động ──► Neo4j :7687 ──► Đánh giá §6
 (501 file)  (501)    (501)         (460)          (454)      │
                                                              └─► JSON gán tay ──► Neo4j :7688 ──► Chatbot ──► API + giao diện chat
                                                                  (v1, v2: 454)
```

| # | Bước | Tình trạng | Số liệu |
|---|---|---|---|
| 1 | Crawl `dut.udn.vn` | Hoàn thành | Mục lục 475; tải được 460 (15 văn bản trả 404); PDF gốc 501 file / 11.420 trang theo manifest. Thư mục `data/raw/pdf/` hiện rỗng trên máy này |
| 2 | OCR (EasyOCR cục bộ) | Hoàn thành | 501/501 file |
| 3 | Chuẩn hoá số hiệu, ngày ban hành | Hoàn thành | Số hiệu đúng tăng từ 25,5% lên 94,6%; 137 file bị gắn cờ cần soi tay |
| 4 | Hiệu đính bằng Gemma, dựng `text_final` | Hoàn thành | 454 văn bản. Đã loại 5 bản website gắn nhầm file và `0158` (bản gốc hỏng) |
| 5 | Sửa lỗi OCR mức ký tự | Hoàn thành một phần | 294/455 văn bản đã sửa, 75 văn bản đọc tay từng trang; còn 54 văn bản lỗi ≥ 1% và 9 văn bản ≥ 3% |
| 6 | Graph tự động (`kg`, Bước 0–5) | Hoàn thành, dữ liệu cũ | 10.978 node, 14.120 cạnh. `data/kg/` dựng ngày 04/09 từ `text_clean_gemma`, chưa dựng lại từ `text_final` |
| 7 | Đánh giá §6 (gold set, κ, P/R/F1) | Chưa thực hiện được | Có 175 phiếu gán trong `data/eval/goldset/phieu_gan/`; hai thư mục `nguoi_gan_1/` và `nguoi_gan_2/` đều trống |
| 8 | Đánh giá retrieval BM25 / KG / Hybrid | Một phần | Chỉ có số cho 14/45 câu single-hop; 31 câu còn lại chưa có đáp án |
| 9 | JSON gán tay | Hoàn thành | v1 và v2 đều 454 file; 36 file ở `_nghi_ngo/` còn cảnh báo, chưa nạp vào graph |
| 10 | Graph gán tay | Hoàn thành | 418/454 văn bản được nạp (403 `Document` duy nhất sau gộp trùng số hiệu); 11.227 node, 17.410 cạnh |
| 11 | Chatbot (LangGraph) | Hoạt động | Node intent lọc câu ngoài phạm vi; router trích action + slot rồi chọn 1 trong 68 template (6 nhóm, mức 1–5); agent ReAct cho câu ngoài các template; câu trả lời có dẫn nguồn; hội thoại nhiều lượt; log JSON + LangSmith. Bộ 17 truy vấn benchmark và 20 kịch bản Cypher |
| 12 | API và giao diện chat | Hoạt động | FastAPI `POST /api/chat` (`thread_id`), frontend React/Vite |

Số liệu graph ở các dòng 6 và 10 lấy từ báo cáo đã lưu trong repo
(`docs/PIPELINE_TU_DONG.md`, `GRAPHREPORT.md`), chưa được đo lại tại ngày cập nhật.
Kết quả của bộ `chat-eval` chưa được ghi lại trong tài liệu nào.

## 4. Cấu trúc thư mục

```
PBL6/
├── run.py                        Điểm vào duy nhất. `python run.py --help`; `python run.py lkg ...` chuyển sang pipeline gán tay
├── docker-compose.yml            Neo4j của pipeline gán tay (cổng 7475 / 7688)
├── requirements.txt, .env.example
│
├── src/
│   ├── vanban/                   Pipeline tự động
│   │   ├── core/                 Cấu hình, session SQLite, chuẩn hoá tên và văn bản
│   │   ├── clean/                PDF → OCR → chuẩn hoá → hiệu đính
│   │   ├── kg/                   Xây graph theo quy tắc (Bước 0–5)
│   │   ├── rag/                  Ba hệ truy hồi BM25 / KG / Hybrid
│   │   └── eval/                 Khối đánh giá §6
│   └── legal_knowledge_graph/    Pipeline gán tay
│       ├── schema/, reference/   JSON Schema và danh mục chuẩn (topic, nhóm đối tượng, cơ quan, alias)
│       ├── samples/              17 văn bản mẫu cho kiểm thử hồi quy
│       ├── core/                 ingest (validate, build), benchmark, graph_query, chat (LangGraph), api
│       ├── frontend/             Giao diện chat (React + Vite)
│       └── tests/                Kiểm thử offline của chatbot (pytest)
│
├── tools/                        Công cụ chạy theo đợt, ngoài luồng `run.py`
│   ├── gemini_web/               Hiệu đính hàng loạt qua giao diện web Gemini; dựng và đối chiếu JSON
│   ├── gemini_api/               Sinh JSON và đọc lại PDF bằng API Gemini
│   └── kiem_tra/                 Bộ đo và soi chất lượng `text_final`, soi trích dẫn, sửa số hiệu OCR
│
├── scripts/                      Crawler gốc, vẽ ontology, các script xuất phụ trợ
├── rules/Ontology.md             Đặc tả ontology v0.3
├── docs/                         Tài liệu tiến độ, ghi chú kỹ thuật, sơ đồ
└── data/                         Xem mục 6 và data/README.md
```

## 5. Hạn chế và việc còn tồn đọng

1. **Chưa có số đo độ chính xác của bộ trích xuất quan hệ.** Gold set chưa được hai
   người gán, nên chưa tính được Cohen's κ và P/R/F1 theo từng loại quan hệ.
   Kết luận pipeline gán tay tốt hơn pipeline tự động hiện chỉ dựa trên so sánh số
   cạnh (ví dụ `REPEALS`: 185 so với 23; `REPLACES`: 187 so với 88), chưa có đối chiếu
   với nhãn chuẩn.
2. **Đánh giá retrieval chưa đủ.** Chỉ nhóm single-hop có đáp án (tự sinh từ metadata);
   kết quả KG vượt BM25 ở nhóm này là hệ quả của cách đặt câu hỏi. Nhóm multi-hop và
   nhóm hiệu lực cần người điền đáp án.
3. **Graph tự động dựng trên bản text cũ.** `config.py` đã trỏ tới `text_final` nhưng
   chưa chạy lại `python run.py kg docs`.
4. **36 văn bản chưa nạp vào graph gán tay** (thư mục `_nghi_ngo/`), chưa đọc soát từng file.
5. **Dữ liệu đầu vào còn khiếm khuyết:**
   - 15 văn bản không tải được (404), trong đó có Luật Bảo hiểm xã hội 2024 và
     `115/2020/NĐ-CP`; chúng chỉ xuất hiện dưới dạng `Document` stub.
   - File `0049` mang tên "Quy chế làm việc của Phòng Thí nghiệm và Xưởng thực hành"
     nhưng nội dung là bản sao của văn bản khác; văn bản đúng chưa có trong kho.
   - 14 nhóm số hiệu trùng giữa các file; mới đối chiếu 2 nhóm.
   - 34 văn bản có số hiệu trong header lệch với metadata (một phần là lỗi metadata gốc).
   - Bản PDF gốc không còn trên máy, nên các chỗ OCR nghi ngờ chưa thể đối chiếu ảnh.

## 6. Dữ liệu

| Thư mục | Nội dung |
|---|---|
| `data/clean/text_final/` | Kho văn bản chuẩn, 454 file `.txt` theo lĩnh vực. Nguồn duy nhất của cả hai pipeline |
| `data/clean/json/v1/`, `v2/` | JSON gán tay, 454 file mỗi bản (v2 bổ sung nhóm đối tượng áp dụng) |
| `data/kg/` | Đầu ra `.jsonl` của pipeline tự động |
| `data/eval/` | Kết quả và phiếu gán của khối đánh giá §6 |
| `data/kiem_tra/` | Báo cáo chất lượng `text_final` |
| `data/_loai_bo/` | Văn bản đã loại khỏi bộ dữ liệu, kèm lý do |
| `data/manifest.jsonl` | Metadata 501 mục từ bước crawl (nguồn metadata duy nhất còn lại) |
| `data/raw/`, `data/processed/` | Gần như rỗng trong repo; PDF gốc và các bản OCR trung gian không được lưu |

Chi tiết xem [data/README.md](data/README.md) và [data/clean/README.md](data/clean/README.md).

## 7. Vận hành

Cài đặt:

```powershell
pip install -r requirements.txt
Copy-Item .env.example .env        # điền khoá Gemini (GEMINI_API_KEY_0, _1, ...)
docker compose up -d               # Neo4j của pipeline gán tay
```

Pipeline gán tay:

```powershell
python run.py lkg all              # kiểm tra trùng → validate → nạp Neo4j → kiểm tra nhanh
python run.py lkg query --source benchmark
python run.py lkg ask "<câu hỏi>"
python run.py lkg chat              # hội thoại nhiều lượt trong terminal
python run.py lkg chat-eval
python run.py lkg serve-api        # API tại http://localhost:8000
# giao diện: cd src/legal_knowledge_graph/frontend; npm install; npm run dev
```

Pipeline tự động:

```powershell
python run.py scan ; python run.py ocr ; python run.py normalize ; python run.py fix ; python run.py export
python run.py kg all               # Bước 0–4
python run.py kg load --wipe       # Bước 5: nạp Neo4j cổng 7687
python run.py eval all             # tổng hợp data/eval/BAO_CAO.md
```

Mọi bước của pipeline tự động lưu tiến độ trong `sessions/<tên>/`, có thể ngắt
và chạy lại từ vị trí dở. Tham số, giá trị đã đo và lý do chọn xem
[docs/PIPELINE_TU_DONG.md](docs/PIPELINE_TU_DONG.md).

## 8. Tài liệu liên quan

| Tài liệu | Nội dung |
|---|---|
| [docs/TIEN_DO.md](docs/TIEN_DO.md) | Tiến độ, tồn đọng, nhật ký |
| [docs/PIPELINE_TU_DONG.md](docs/PIPELINE_TU_DONG.md) | Ghi chép kỹ thuật pipeline tự động: OCR, hiệu đính, graph theo quy tắc, đánh giá §6 |
| [rules/Ontology.md](rules/Ontology.md) | Đặc tả ontology |
| [src/legal_knowledge_graph/README.md](src/legal_knowledge_graph/README.md) | Pipeline gán tay, chatbot, API, quan sát |
| [src/legal_knowledge_graph/docs/GRAPHREPORT.md](src/legal_knowledge_graph/docs/GRAPHREPORT.md) | Schema, số liệu và benchmark của graph gán tay |
| [src/legal_knowledge_graph/docs/STRUCTUREDFORM.md](src/legal_knowledge_graph/docs/STRUCTUREDFORM.md) | Diễn giải schema JSON |
| [src/legal_knowledge_graph/docs/EXAMPLE.md](src/legal_knowledge_graph/docs/EXAMPLE.md) | 20 câu hỏi mẫu kèm Cypher |
| [tools/README.md](tools/README.md) | Các công cụ chạy tay |
