# legal_knowledge_graph

Đồ thị tri thức văn bản pháp quy trong Neo4j, xây bằng cách gán tay
(JSON → graph) thay vì trích xuất tự động. Bù lại điểm yếu recall của
pipeline regex/NLP ở `src/vanban/kg/` cho nhóm quan hệ hiệu lực
(`REPLACES`, `AMENDS`, `REPEALS`) — những câu như "thay thế...", "sửa đổi,
bổ sung...", "bãi bỏ..." người đọc trực tiếp gán đúng hơn luật regex.

Package độc lập trong `src/`, ngang hàng `src/vanban/`: không import code
của `src/vanban/`, dùng Neo4j instance riêng. Hạ tầng (`.env`,
`requirements.txt`, `docker-compose.yml`, `run.py`) dùng chung với gốc
repo, namespace biến môi trường tách riêng bằng tiền tố `LKG_`.

Trên nền graph này có thêm một lớp truy vấn ngôn ngữ tự nhiên (`core/nlq/`)
và một chat UI (`core/api/` + `frontend/`).

## Cấu trúc

```
src/legal_knowledge_graph/
├── schema/document.schema.json     JSON Schema cho file gán tay
├── reference/                      topics_seed / target_groups_seed / organizations_seed
├── samples/                        17 văn bản mẫu, dùng cho regression test
├── core/
│   ├── config.py                     Cấu hình, đọc .env gốc repo
│   ├── normalize.py                  Chuẩn hoá khoá (normalizedNumber, orgId, slug...)
│   ├── validate.py                   Validate JSON theo schema + kiểm tra chéo
│   ├── collision_check.py            Báo cáo normalizedNumber bị trùng
│   ├── graph_model.py                Dựng đồ thị trong bộ nhớ từ JSON
│   ├── graph_loader.py               Ghi đồ thị vào Neo4j
│   ├── build.py                      CLI build (validate + nạp)
│   ├── build_pipeline.py             CLI all (collision-check → validate → build → sanity)
│   ├── query/                        Cypher viết tay — catalog.py (regression) + benchmark_catalog.py
│   ├── nlq/                          Câu hỏi tự nhiên → Cypher
│   └── api/                          FastAPI cho chat UI
├── frontend/                       Chat UI (React + Vite)
└── run.py                          Điểm vào CLI, gọi qua `python run.py lkg <lệnh>`
```

## Cài đặt

```powershell
pip install -r requirements.txt
docker compose up -d
Copy-Item .env.example .env
```

Neo4j riêng cho module này: Browser `http://localhost:7475`, Bolt
`bolt://localhost:7688`, user/pass `neo4j`/`lkg12345678` — khác cổng với
instance chính (`7474`/`7687`) của pipeline tự động.

| Biến | Mặc định | Dùng cho |
|---|---|---|
| `LKG_NEO4J_URI` / `_USER` / `_PASSWORD` / `_DATABASE` | xem trên | Kết nối Neo4j |
| `LKG_GEMINI_API_KEY_0` | (rỗng) | Gọi Gemini cho NLQ (`ask`, `nlq-eval`, chat UI) |
| `LKG_GEMINI_MODEL` | `gemini-3.6-flash` | Model Gemini dùng cho NLQ |
| `LKG_NLQ_TEMPLATE_CONFIDENCE_MIN` | `0.6` | Ngưỡng nhận 1 template match |
| `LKG_NLQ_ROW_CAP` | `200` | Số dòng tối đa mỗi truy vấn NLQ |
| `LKG_NLQ_QUERY_TIMEOUT_SECONDS` | `10` | Timeout Cypher phía server |

## Quy trình dữ liệu

```
data/clean/text_final/*.txt (OCR, thuộc src/vanban/)
        ↓  gán tay theo schema/document.schema.json
data/clean/json/<version>/*.json
        ↓  validate → build
Neo4j
```

Một file JSON = một văn bản. Chi tiết field: `schema/document.schema.json`,
bản diễn giải: `STRUCTUREDFORM.md`. Vài quy tắc chính:

- Chép nguyên văn những gì in trên văn bản, không tự tính khoá chuẩn hoá
  (`core/normalize.py` tự suy).
- `topics[]` khớp `reference/topics_seed.json`, `targetGroups[]` khớp
  `reference/target_groups_seed.json` — một văn bản có thể thuộc nhiều
  nhóm.
- Mỗi câu "Căn cứ/thay thế/sửa đổi/bãi bỏ/nhắc tới" trong văn bản ứng với
  một entry `citations[]` (`BASED_ON`/`REPLACES`/`AMENDS`/`REPEALS`/
  `REFERENCES`). Văn bản đích chưa có JSON riêng thì hệ thống tự tạo
  Document stub.
- Field không chắc thì để `null`/`[]` kèm lý do trong `note`, không đoán.

## CLI

```powershell
python run.py lkg validate [--dir DIR]
python run.py lkg check-collisions [--dir DIR]
python run.py lkg build [--dir DIR] [--wipe]
python run.py lkg all [--dir DIR] [--no-wipe]
python run.py lkg query [--source samples|benchmark] [--verbose]
python run.py lkg ask "<câu hỏi tự nhiên>" [--verbose]
python run.py lkg ask --template TPL_XXX --param k=v
python run.py lkg nlq-eval [--verbose]
python run.py lkg serve-api [--host HOST] [--port PORT] [--reload]
```

| Lệnh | Việc làm |
|---|---|
| `validate` | JSON Schema + kiểm tra chéo, đệ quy, bỏ qua thư mục `_...` |
| `check-collisions` | Báo cáo `normalizedNumber` bị ≥2 file trùng |
| `build` | Validate rồi nạp vào Neo4j (`--wipe` để nạp lại từ đầu) |
| `all` | 1 lệnh: check-collisions → validate → build → sanity |
| `query` | Chạy bộ Cypher (`samples` = regression có assertion, `benchmark` = đo trên data thật) |
| `ask` | Câu hỏi tự nhiên → Cypher → kết quả thô |
| `nlq-eval` | Chạy bộ câu hỏi gold cho NLQ |
| `serve-api` | Chạy FastAPI cho chat UI |

## Đồ thị

7 loại node (`Document`, `Organization`, `Person`, `Topic`, `TargetGroup`,
`NormativeContent`, `Article`), quan hệ chính: `ISSUED_BY`, `SIGNED_BY`,
`HAS_TOPIC`, `APPLIES_TO`, `MENTIONS`, `PROMULGATES`, `HAS_ARTICLE`, và
nhóm hiệu lực/trích dẫn `BASED_ON`/`REFERENCES`/`REPLACES`/`AMENDS`/
`REPEALS`. 3 full-text index (`doc_text`, `article_text`, `content_text`).
Nạp bằng `MERGE` nên `build` chạy lại nhiều lần không nhân đôi dữ liệu.

Số liệu graph hiện tại, các vấn đề dữ liệu đã biết, benchmark hiệu năng:
xem `GRAPHREPORT.md`.

## NLQ — câu hỏi tự nhiên → Cypher

`core/nlq/` dịch câu hỏi tiếng Việt sang Cypher rồi thực thi, trả về kết
quả thô (chưa tổng hợp câu trả lời văn xuôi).

```
Câu hỏi → Stage A: Gemini chọn 1/14 template + trích tham số
             │ khớp → resolve tham số (không LLM) → chạy template đã vetted
             │ không khớp
             ▼
          Stage B: Gemini tự sinh Cypher → guard.py (blocklist, whitelist
                    schema, EXPLAIN dry-run, ép LIMIT) → chạy
```

4 loại kết quả (`pipeline.NlqResult.kind`): `template_result`,
`freeform_result` (Cypher tự sinh, độ tin cậy thấp hơn),
`resolution_failed` (thực thể không tồn tại/mơ hồ — không chạy Cypher),
`unsupported` (ngoài phạm vi hoặc bị guard chặn — không chạy Cypher).

## Chat UI

FastAPI (`core/api/app.py`, `POST /api/chat`) gọi thẳng `core/nlq/
pipeline.ask()`; frontend React (Vite) hiển thị kết quả theo `kind` ở
trên.

```powershell
python run.py lkg serve-api          # http://localhost:8000

cd src/legal_knowledge_graph/frontend
npm install && npm run dev            # http://localhost:5173
```

## Tài liệu liên quan

- `GRAPHREPORT.md` — schema, số liệu graph, benchmark, vấn đề dữ liệu đã biết.
- `STRUCTUREDFORM.md` — diễn giải đầy đủ `document.schema.json`.
