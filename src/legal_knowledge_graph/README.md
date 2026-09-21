# legal_knowledge_graph

Module gán tay văn bản pháp quy → JSON → Neo4j, bù đắp điểm yếu recall của
pipeline trích xuất tự động (`src/vanban/kg/`, dựa trên regex/NLP) ở nhóm
quan hệ hiệu lực (`REPLACES`, `AMENDS`, `REPEALS`). Người đọc trực tiếp câu
"Căn cứ...", "thay thế...", "sửa đổi, bổ sung...", "bãi bỏ..." trong văn
bản và gán quan hệ bằng mắt cho độ chính xác cao hơn luật regex.

Quy trình đầy đủ: PDF/scan → OCR (`src/vanban/`, ra
`data/clean/text_final/*.txt`) → gán tay/AI-hỗ trợ thành JSON (bước thủ
công duy nhất) → `core/build.py` nạp JSON vào Neo4j (tự động).

**Tách biệt về logic** với phần còn lại của repo: đứng trong `src/` như
một package riêng, ngang hàng `src/vanban/`, không import code từ
`src/vanban/`, không dùng chung Neo4j instance với graph chính (10.978
node/14.120 cạnh). Hạ tầng (`.env`, `requirements.txt`,
`docker-compose.yml`, `run.py`) dùng chung ở gốc repo cho tiện cài đặt,
nhưng namespace biến môi trường tách biệt hoàn toàn (tiền tố `LKG_`) — xem
§2. Thay đổi trong thư mục này không ảnh hưởng pipeline tự động và ngược
lại.

## Mục lục

1. [Cấu trúc thư mục](#1-cấu-trúc-thư-mục)
2. [Cài đặt](#2-cài-đặt)
3. [Quy trình làm việc](#3-quy-trình-làm-việc)
4. [Gán tay: quy tắc điền JSON](#4-gán-tay-quy-tắc-điền-json)
5. [Lệnh CLI](#5-lệnh-cli)
6. [Logic nạp vào Neo4j](#6-logic-nạp-vào-neo4j)
7. [So với `rules/Ontology.md`](#7-so-với-rulesontologymd)
8. [Bộ Cypher: regression vs benchmark](#8-bộ-cypher-regression-vs-benchmark)
9. [Kiểm chứng module](#9-kiểm-chứng-module)
10. [Data thật đã nạp](#10-data-thật-đã-nạp)
11. [NLQ: câu hỏi tự nhiên → Cypher](#11-nlq-câu-hỏi-tự-nhiên--cypher)
12. [Chat UI: FastAPI + React](#12-chat-ui-fastapi--react)

## 1. Cấu trúc thư mục

```
src/legal_knowledge_graph/
├── schema/document.schema.json     JSON Schema (draft 2020-12) — nguồn sự thật duy nhất về format
├── reference/
│   ├── topics_seed.json            18 lĩnh vực hợp lệ cho document.topics[]
│   ├── target_groups_seed.json     8 nhóm đối tượng áp dụng hợp lệ cho document.targetGroups[]
│   └── organizations_seed.json     Tổ chức đã biết trước (orgId, name, orgType, parentOrg)
├── samples/                        17 văn bản mẫu thật (rút gọn) — dùng làm regression test cho cơ chế
├── core/                           Package Python — mỗi file một trách nhiệm
│   ├── config.py                     Đọc .env gốc repo (biến tiền tố LKG_ riêng, xem §2)
│   ├── normalize.py                  normalize_document_number, slug, authority_level...
│   ├── validate.py                   JSON Schema + kiểm tra chéo, quét đệ quy, bỏ qua thư mục `_...`
│   ├── collision_check.py            CLI `check-collisions` — báo cáo normalizedNumber bị >=2 file trùng
│   ├── graph_model.py                Dựng đồ thị trong bộ nhớ từ JSON đã validate — không đụng Neo4j
│   ├── graph_loader.py               Ghi GraphModel vào Neo4j: schema DDL, batch MERGE, wipe
│   ├── build.py                      CLI `build` — nối graph_model + graph_loader, in báo cáo
│   ├── pipeline.py                   CLI `all` — chạy trọn collision-check → validate → build → sanity
│   ├── query/                        Subpackage Cypher — xem §8
│   │   ├── catalog.py                  16 câu regression, tuned cho samples/ (assert đúng số dòng)
│   │   ├── benchmark_catalog.py        17 câu minh hoạ hiệu năng trên data thật (không assert số dòng)
│   │   └── runner.py                   CLI `query` — chạy 1 trong 2 bộ trên, đo thời gian + đọc PROFILE
│   ├── nlq/                          Subpackage NLQ (câu hỏi tự nhiên → Cypher) — xem §11
│   │   ├── templates.py                14 template Cypher tham số hoá, lấy từ core/query/ đã test
│   │   ├── resolve.py                  Resolve thực thể thô → giá trị thật (không LLM)
│   │   ├── gemini_client.py            Wrapper Gemini mỏng, key/model riêng (LKG_GEMINI_*)
│   │   ├── match_template.py           Stage A — Gemini chọn template + trích tham số thô
│   │   ├── freeform.py                 Stage B — Gemini tự sinh Cypher khi Stage A miss
│   │   ├── guard.py                    An toàn cho Stage B: blocklist, whitelist schema, EXPLAIN, LIMIT
│   │   ├── schema_context.py           Mô tả schema tĩnh dùng cho prompt Stage B + whitelist guard.py
│   │   ├── execute.py                  Thực thi Cypher có timeout thật (Session.begin_transaction)
│   │   ├── pipeline.py                 CLI `ask` — điểm vào, orchestrate 2 giai đoạn
│   │   └── eval_gold.py                CLI `nlq-eval` — bộ câu hỏi gold, chạy thật qua Gemini + Neo4j
│   └── api/                          Subpackage FastAPI (chat UI) — xem §12
│       └── app.py                      POST /api/chat, GET /api/health — gọi thẳng core/nlq/pipeline.ask()
├── frontend/                       React (Vite) — chat UI cho core/api/ — xem §12
│   └── src/App.jsx, api.js, ErrorBoundary.jsx, ...
└── run.py                          CLI: validate | check-collisions | build | query | all | ask
                                    | nlq-eval | serve-api
                                    (gọi qua `python run.py lkg <lệnh>` ở gốc repo — xem §2)
```

`.env`/`.env.example`, `requirements.txt`, `docker-compose.yml` dùng chung
với gốc repo — không có bản riêng trong thư mục này.

`core/graph_model.py` không import `neo4j` — dựng đồ thị trong bộ nhớ là
logic Python thuần, tách khỏi việc ghi DB (`graph_loader.py`). Có thể gọi
`graph_model.collect(dir)` để kiểm tra dữ liệu mà không cần Neo4j đang
chạy.

## 2. Cài đặt

Hạ tầng dùng chung với gốc repo — một lần cài đặt cho cả pipeline tự động
lẫn module này:

```powershell
pip install -r requirements.txt              # đã gộp neo4j/jsonschema/python-dotenv/google-genai/fastapi/uvicorn
docker compose up -d                          # instance Neo4j riêng cho module này (neo4j-lkg)
Copy-Item .env.example .env                   # nếu chưa có .env — điền LKG_GEMINI_API_KEY_0
```

Container tên `neo4j-pbl6-lkg` — Browser tại `http://localhost:7475`, Bolt
tại `bolt://localhost:7688`, mật khẩu `lkg12345678`. Không trùng
cổng/mật khẩu với container `neo4j-pbl6` (7474/7687) của pipeline chính
(khởi động bằng `docker run` thủ công, không qua compose — xem README
gốc).

Namespace biến môi trường tách biệt dù `.env` vật lý dùng chung: mọi biến
của module này có tiền tố `LKG_`, không đụng `NEO4J_*`/`GEMINI_*` của
pipeline tự động (`core/config.py` chỉ đọc biến `LKG_*`).

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `LKG_NEO4J_URI` | `bolt://localhost:7688` | Địa chỉ Bolt của instance riêng |
| `LKG_NEO4J_USER` | `neo4j` | User |
| `LKG_NEO4J_PASSWORD` | `lkg12345678` | Mật khẩu |
| `LKG_NEO4J_DATABASE` | `neo4j` | Tên database |
| `LKG_GEMINI_API_KEY_0` | (rỗng) | Key Gemini riêng cho `ask`/`nlq-eval`, không dùng chung `GEMINI_*` ở `.env` gốc — xem §11 |
| `LKG_GEMINI_MODEL` | `gemini-3.6-flash` | Model dùng cho Stage A/B — xem note ở §11 |
| `LKG_NLQ_TEMPLATE_CONFIDENCE_MIN` | `0.6` | Ngưỡng tin cậy tối thiểu để chấp nhận 1 template match |
| `LKG_NLQ_ROW_CAP` | `200` | Số dòng tối đa mọi truy vấn NLQ (template lẫn freeform) |
| `LKG_NLQ_QUERY_TIMEOUT_SECONDS` | `10` | Timeout Cypher phía server cho NLQ |

## 3. Quy trình làm việc

```
văn bản .txt (data/clean/text_final/)
        │  người gán tay đọc + điền JSON theo schema (hoặc AI hỗ trợ, xem §10)
        ▼
   *.json  ──validate──▶  OK / lỗi field cụ thể
        │  build (tự validate lại trước khi nạp)
        ▼
   Neo4j (instance riêng, cổng 7688)
        │  query --source samples   (regression, assert số dòng)
        │  query --source benchmark (minh hoạ hiệu năng trên data thật)
        ▼
   báo cáo PASS/FAIL + rows + elapsed_ms + index_used
```

## 4. Gán tay: quy tắc điền JSON

Một file JSON = một văn bản. Cấu trúc đầy đủ và mô tả từng field nằm ở
[`schema/document.schema.json`](schema/document.schema.json) (bản diễn
giải dễ đọc hơn: [`structured_form.md`](structured_form.md)) — dưới đây là
tóm tắt các quy tắc quan trọng nhất.

**Nguyên tắc chung**

- Chỉ chép nguyên văn những gì in trên văn bản. Không tự tính
  `normalizedNumber`, `orgId`, `personId`... — `core/normalize.py` tự suy
  khi nạp.
- Ngày ghi dạng `dd/mm/yyyy` như trên văn bản, không phải ISO.
- Không chắc một field thì để `null` (hoặc `[]`) và ghi lý do vào `note` ở
  đầu file, không đoán.
- Gặp lỗi rõ ràng của chính văn bản/OCR (số hiệu gõ sai kiểu, thiếu
  chữ...) thì sửa lại cho đúng và ghi chú trong `note`.

**`document.topics[]`** — phải khớp một mục trong
[`reference/topics_seed.json`](reference/topics_seed.json) (không phân
biệt hoa/thường, có/không dấu).

**`document.targetGroups[]`** — đối tượng áp dụng (Điều 1/2 "Phạm vi điều
chỉnh và đối tượng áp dụng"), phải khớp một mục trong
[`reference/target_groups_seed.json`](reference/target_groups_seed.json)
(8 nhóm). Một văn bản thường áp dụng cho nhiều nhóm cùng lúc — điền hết,
không chọn 1. Không rõ thuộc nhóm nào thì dùng `"Khác"`.

**`organization`** — nếu `name` trùng một tổ chức trong
[`reference/organizations_seed.json`](reference/organizations_seed.json)
thì để `orgType`/`parentOrg` là `null`, máy tự khớp. Tổ chức mới (chưa có
trong seed, ví dụ một Khoa/Phòng cụ thể) bắt buộc tự điền `orgType` (enum
trong schema) và `parentOrg`.

**`citations[]`** — mỗi câu "Căn cứ...", "thay thế...", "sửa đổi, bổ
sung...", "bãi bỏ..." ứng với một entry:

| Trong văn bản | `relationType` |
|---|---|
| Nằm trong khối "Căn cứ..." ở đầu văn bản | `BASED_ON` |
| "...thay thế Quyết định số..." | `REPLACES` |
| "...sửa đổi, bổ sung...Điều...của..." | `AMENDS` (điền thêm `targetArticle` nếu biết rõ Điều nào) |
| "...bãi bỏ.../huỷ bỏ..." | `REPEALS` |
| Nhắc tới nhưng không thuộc 4 loại trên | `REFERENCES` |

Không cần văn bản đích đã có file JSON riêng hay chưa — nếu chưa, hệ thống
tự tạo một Document "stub" (`isStub: true`) cho số hiệu đó khi nạp.

**`articles[]` vs `normativeContents[].articles[]`** — nếu văn bản là một
Quyết định "ban hành kèm theo" một Quy định/Quy chế:

- Điều "vỏ bọc" của Quyết định (thường chỉ Điều 1 "Ban hành kèm theo...",
  Điều 2 "Hiệu lực thi hành...") → `articles` cấp Document.
- Điều bên trong Quy định/Quy chế kèm theo → `normativeContents[].articles`.
- Cả hai có thể cùng tồn tại trong một file — xem
  [`samples/010_2852-QD-DHDN.json`](samples/010_2852-QD-DHDN.json).

**Ví dụ tham khảo** — [`samples/`](samples/) chứa 17 file dựa trên văn bản
thật (rút gọn, xem `note` đầu mỗi file). Copy file gần giống văn bản đang
gán rồi sửa lại là cách nhanh nhất để bắt đầu.

**Kiểm tra file vừa viết**

```powershell
python run.py lkg validate --dir duong/dan/toi/thu/muc
```

Báo lỗi theo từng file: thiếu field bắt buộc, sai kiểu/enum, số Điều trùng
trong cùng một văn bản, tự trích dẫn chính mình, topic/tổ chức không khớp
danh sách seed. Quét đệ quy (chịu được thư mục lồng theo lĩnh vực) và tự
bỏ qua mọi file nằm dưới thư mục con tên bắt đầu bằng `_` (quy ước "gác
lại, chưa xử lý xong" — xem §10).

## 5. Lệnh CLI

Chạy qua entry point chung ở gốc repo, namespace `lkg`:

```powershell
python run.py lkg validate [--dir DIR]      # mặc định: src/legal_knowledge_graph/samples
python run.py lkg check-collisions [--dir DIR]
python run.py lkg build [--dir DIR] [--wipe]
python run.py lkg query [--source samples|benchmark] [--verbose]
python run.py lkg all [--dir DIR] [--no-wipe]
python run.py lkg ask "<câu hỏi tự nhiên>" [--verbose]
python run.py lkg ask --template TPL_XXX --param k=v [--verbose]
python run.py lkg nlq-eval [--verbose]
python run.py lkg serve-api [--host HOST] [--port PORT] [--reload]
```

Chạy trực tiếp `python src/legal_knowledge_graph/run.py <lệnh>` vẫn hoạt
động — `run.py` ở gốc chỉ là lớp chuyển tiếp mỏng.

| Lệnh | Module đứng sau | Việc làm |
|---|---|---|
| `validate` | `core/validate.py` | JSON Schema + kiểm tra chéo trên toàn bộ `*.json` trong `--dir` (đệ quy, bỏ qua thư mục `_...`). Không đụng Neo4j. |
| `check-collisions` | `core/collision_check.py` | Gom file theo `normalizedNumber`, báo cáo mọi khoá bị >=2 file trùng (không tự sửa — xem §10). Thoát mã khác 0 nếu có trùng. |
| `build` | `core/build.py` (`graph_model.py` + `graph_loader.py`) | Validate lại rồi nạp vào Neo4j riêng. `--wipe` xoá sạch graph trong instance này trước khi nạp. |
| `query` | `core/query/runner.py` | `--source samples` (mặc định): 16 câu regression, assert đúng số dòng. `--source benchmark`: 17 câu minh hoạ hiệu năng trên data thật, không assert số dòng. |
| `all` | `core/pipeline.py` | 1 lệnh chạy trọn `check-collisions` (chỉ cảnh báo) → validate → `build --wipe` (mặc định; `--no-wipe` để tắt) → sanity. Dùng khi nạp version dữ liệu mới — xem §10. |
| `ask` | `core/nlq/pipeline.py` | Câu hỏi tự nhiên → Cypher → kết quả thô, xem §11. `--template` bỏ qua Gemini, chạy thủ công 1 template. |
| `nlq-eval` | `core/nlq/eval_gold.py` | Chạy ~18 câu hỏi gold thật qua Gemini + Neo4j, assert đúng loại kết quả — xem §11. |
| `serve-api` | `core/api/app.py` | Chạy FastAPI cho chat UI (`frontend/`) — xem §12. |

## 6. Logic nạp vào Neo4j

`core/graph_model.py` dựng một `GraphModel` trong bộ nhớ (validate trước,
đăng ký Topic/Organization/Person, gộp Điều theo Document/NormativeContent),
sau đó `core/graph_loader.push()` ghi model vào Neo4j theo thứ tự sau —
mọi bước dùng `MERGE` (idempotent: chạy `build` nhiều lần không nhân đôi
node/cạnh, chỉ cập nhật property):

1. Constraint + index, gồm 3 full-text index: `doc_text`, `article_text`,
   `content_text`.
2. Toàn bộ `Topic` + `TargetGroup` + `Organization` từ `reference/` (kể cả
   node chưa được văn bản nào dùng tới).
3. `Document` thật (`isStub: false`) cho mọi file trong `--dir`.
4. `ISSUED_BY`, `HAS_TOPIC`, `APPLIES_TO`, `MENTIONS`, `Person` +
   `SIGNED_BY`, `NormativeContent` + `PROMULGATES`, `Article` +
   `HAS_ARTICLE`.
5. Cuối cùng: `citations[]` trên toàn bộ file — với số hiệu đích chưa có
   Document thật, tạo Document stub (`ON CREATE SET isStub: true`, chỉ có
   `documentNumber`/`normalizedNumber`) rồi tạo cạnh
   `BASED_ON`/`REFERENCES`/`REPLACES`/`AMENDS`/`REPEALS` (5 câu Cypher
   riêng — loại quan hệ không tham số hoá được).

Thứ tự bước 3 trước bước 5 đảm bảo một Document thật không bao giờ bị hạ
xuống thành stub, bất kể thứ tự đọc file.

**Chuẩn hoá** (`core/normalize.py`, không import `src/vanban/kg/norm.py`):
`normalize_document_number()` (bỏ tiền tố "Số:", chuẩn hoá biến thể gạch
ngang, bỏ số 0 đầu, deaccent+uppercase) → property `normalizedNumber`;
`org_id`/`person_id`/`topic_id` (slug); `content_id` =
`"{normalizedNumber}#nd{index}"`; `article_id` = `"{parent_key}#{number}"`;
`authority_level()` suy theo bảng org-type rồi tới doc-type (org-type ưu
tiên hơn), với `Organization` không có sẵn bậc thì đi ngược `parentOrg`
tới khi gặp tổ chức có bậc trong seed.

## 7. So với `rules/Ontology.md`

`rules/Ontology.md` (7 loại node, 12 quan hệ) là nền cho cả pipeline tự
động lẫn schema gán tay này. 4 điểm khác biệt so với tài liệu gốc khi
chuyển sang bản cho người gán tay (không sửa `rules/Ontology.md` hay code
cũ), mỗi điểm đối chiếu với data thật (`data/kg/*.jsonl` của pipeline tự
động — 1248 Document, `data/clean/text_final/` — 454 văn bản gốc):

1. **`TargetGroup`/`APPLIES_TO` — giữ lại, thu hẹp phạm vi.**
   `rules/Ontology.md` §2.5 định nghĩa `TargetGroup` tự do (`name` bất kỳ,
   không có vocabulary chuẩn) và xếp `APPLIES_TO` ở mức độ khó trích xuất
   "khó" (§6.1). Trong `data/kg/*.jsonl` và toàn bộ `src/vanban/`, trường
   này chưa từng được cài đặt (0 tham chiếu). Đọc 268 đoạn "Đối tượng áp
   dụng" thật (267/454 = 59% văn bản có cụm này), nội dung lặp lại theo
   mẫu cố định — gom thành 8 nhóm (`reference/target_groups_seed.json`:
   Người học; Cán bộ/giảng viên/viên chức/NLĐ; Đơn vị trực thuộc; Cơ sở
   giáo dục/trường thành viên; Cơ quan-tổ chức-cá nhân liên quan; Hội
   đồng; Doanh nghiệp/đối tác nước ngoài; Khác), phủ 263/268 đoạn (98%).
   Field `document.targetGroups[]` + node `TargetGroup` + quan hệ
   `APPLIES_TO` theo đúng khuôn `topics`/`HAS_TOPIC`, so khớp bằng
   `validate.py` (không phải enum JSON Schema, vì cần xử lý có/không
   dấu). Khác với `Topic` (18 lĩnh vực copy nguyên từ
   `src/vanban/config.py::CATEGORIES`), vocabulary này tự thiết kế nên có
   thể còn thiếu trường hợp hiếm — dùng `"Khác"` khi gặp. Việc gán
   `targetGroups` cho 418 file thật ở `data/clean/json/v1/` là backfill
   riêng, chưa thực hiện trong module này — hạ tầng đã sẵn sàng.
2. **Bỏ `noi_dung_raw`**, thay bằng `document.summary` (1-3 câu tự viết)
   để tránh trùng lặp với `Article.text` (đã có toàn văn), đồng thời cho
   `Công văn` (không có cấu trúc Điều) một chỗ mô tả nội dung. Trong
   `documents.jsonl`, `noi_dung_raw` là `null` ở 100% (1248/1248) Document
   — field không được dùng trong pipeline tự động. `summary` ở 418 file
   thật của module này có giá trị ở 100% (418/418), dài 106-513 ký tự
   (trung bình 260).
3. **Bỏ `Document.normativeType`** khỏi input — là bản sao của
   `normativeContents[0].contentType`; `core/graph_model.py` tự suy khi
   cần, không cần giữ đồng bộ hai chỗ. Cùng `documents.jsonl`:
   `normativeType` là `null` ở 100% (1248/1248) — cũng không được dùng
   trong pipeline tự động.
4. **Giữ `MENTIONS` nhưng bỏ đếm số lần** — chỉ giữ danh sách tên tổ chức
   được nhắc tới. Pipeline tự động có ghi số lần (`so_lan` trên cạnh
   MENTIONS, `src/vanban/kg/neo4j_load.py`, 1014 giá trị trong
   `mentions.jsonl`), nhưng không có nơi nào đọc lại trường này
   (`src/vanban/rag/`, `src/vanban/eval/retrieval.py`,
   `data/kg/queries.cypher` — 0 kết quả). Schema hiện tại
   (`mentions: string[]`) cũng không có chỗ chứa số đếm; khôi phục sẽ cần
   đổi cấu trúc field và yêu cầu người gán tự đếm tay, không phục vụ nhu
   cầu nào đang có.

`authorityLevel`, `isStub`, và mọi khoá chuẩn hoá (`normalizedNumber`,
`orgId`, `contentId`, `articleId`, `personId`) không do người gán điền —
`core/normalize.py` tự suy 100%.

**Escape hatch `idOverride`** — khi khoá tự suy bị đụng hàng (hai người
trùng tên, một tổ chức có cách viết tắt gây trùng slug...), điền
`idOverride` ở đúng entity đó (`document`, `organization`, `signers[]`,
`normativeContents[]`) để ép khoá về giá trị mong muốn.

## 8. Bộ Cypher: regression vs benchmark

Hai bộ câu Cypher tách biệt, mục đích khác nhau, dùng chung một
`core/query/runner.py`:

**[`core/query/catalog.py`](core/query/catalog.py)** — 16 câu, mỗi câu có
số dòng kỳ vọng đo trên `samples/` (17 văn bản cố định). Dùng để kiểm tra
cơ chế (validate/build/query) không bị hỏng sau khi sửa code — `query
--source samples` thoát mã khác 0 nếu có câu sai số dòng.

| Nhóm | Câu | Kiểm tra |
|---|---|---|
| Lookup | Q1, Q2, Q4–Q7, Q12, Q14, Q15 | Truy vấn 1 bước theo tổ chức/topic/nhóm đối tượng/quan hệ, đếm gộp |
| Multi-hop | Q3 | Chuỗi `AMENDS\|REPLACES*1..3` |
| Full-text | Q8, Q9 | Tìm cụm từ chính xác trong `article_text`/`doc_text` |
| Hybrid | Q10 | Full-text lọc ứng viên rồi mở rộng theo quan hệ |
| Sanity | Q11, Q13a, Q13b | Đếm node stub, đếm theo nhãn, đếm theo loại quan hệ |

**[`core/query/benchmark_catalog.py`](core/query/benchmark_catalog.py)** —
17 câu, chạy trên data thật (`data/clean/json/v1/`, xem §10), không
assert số dòng cố định (`expected_rows=None` ở mọi câu). Đây là bộ câu hỏi
tự chọn để minh hoạ nhiều góc độ khác nhau — số đo (elapsed_ms, index_used)
là thật, nhưng bộ câu hỏi chưa được nhóm thẩm định là đại diện đúng nhu
cầu truy vấn thật. Khi nhóm có bộ câu hỏi chính thức (vd theo §6.3
Ontology: single-hop/multi-hop/hiệu lực với gold answer set) thì thay thế
bộ này.

| Nhóm | Câu | Góc độ |
|---|---|---|
| Phân bố node | B1–B4 | Document theo status/type/authorityLevel, NormativeContent theo contentType |
| Xếp hạng quan hệ | B5–B7 | Top 10 Organization/Person/Topic theo số Document |
| Quan hệ hiệu lực riêng lẻ | B8–B9 | Đếm tách bạch 5 loại quan hệ; độ đầy đủ `targetArticle` của AMENDS |
| Multi-hop | B10 | Phân bố độ sâu chuỗi `AMENDS\|REPLACES*1..5` (không chỉ đếm gộp) |
| Full-text, cả 3 index | B11–B13 | `doc_text`, `article_text`, `content_text` |
| Hybrid, 2 hướng | B14–B15 | Full-text rồi mở rộng xuôi (dựa trên gì) và ngược (ai trích dẫn tới) |
| Bất thường/chất lượng | B16–B17 | Top stub bị trích dẫn nhiều nhất; văn bản thật thiếu trích dẫn hoàn toàn |

`runner.py` chạy mỗi câu 2 lần: một lần đo thời gian thật
(`time.perf_counter`), một lần `PROFILE` để đọc plan (`NodeIndexSeek`/
fulltext hay quét toàn bộ). Với `expected_rows=None` (toàn bộ
`benchmark_catalog.py`, và 3 câu trong `catalog.py`) không có assertion —
0 dòng có thể là kết quả đúng (vd B17: 0 nghĩa là không có văn bản nào
thiếu trích dẫn).

## 9. Kiểm chứng module

```powershell
python run.py lkg validate            # kỳ vọng: 17/17 PASS (samples/)
python run.py lkg build --wipe         # nạp samples/ vào Neo4j riêng
python run.py lkg query                # kỳ vọng: 16/16 PASS
python run.py lkg build                # chạy lại không --wipe: nodes_created ~ 0 (idempotent)
```

Đối chiếu Neo4j chính không đổi: mở Neo4j Browser của instance gốc
(`http://localhost:7474`, cổng khác), chạy `MATCH (n) RETURN count(n)`
trước/sau khi chạy các lệnh trên — số node phải giữ nguyên.

## 10. Data thật đã nạp

Từ 19/9, một thành viên khác trong nhóm đã độc lập sinh 454 file JSON thật
tại `data/clean/json/v1/<lĩnh vực>/<mã>.json` (map theo
`schema/document.schema.json`, dùng Gemini API cho phần siêu dữ liệu +
`va_dieu_thieu.py` cắt toàn văn Điều thẳng từ `.txt`, không để model chép
lại — xem `data/clean/json/v1/README.md`), cộng 36 file trong
`_nghi_ngo/<lĩnh vực>/` (qua schema nhưng còn cảnh báo thiếu người ký/
không có Căn cứ — chưa build, chờ đọc tay).

Nạp lại (hoặc nạp version mới v2, v3...) chỉ cần 1 lệnh:

```powershell
python run.py lkg all --dir data/clean/json/v1
python run.py lkg query --source benchmark
```

`all` tự chạy `check-collisions` trước. Data thật hiện có 14
`normalizedNumber` bị >=2 file trùng (29 file). 2 nhóm đã soi tận gốc
(đọc thẳng `.txt` nguồn): `05/NQ-HĐT` (3 file) và `771/QĐ-ĐHBK` (2 file) —
cả hai là cùng một văn bản bị crawl/OCR nhiều lần, gộp là đúng (cộng dồn
trích dẫn, không mất/lẫn nội dung). 12 nhóm còn lại chưa soi từng nhóm,
giả định trùng thật theo cùng khuôn mẫu nhưng chưa xác nhận riêng lẻ.

**Vấn đề dữ liệu đã biết** — file `.txt` của `771/QĐ-ĐHBK` mang tên "Quy
chế làm việc của Phòng Thí nghiệm và Xưởng thực hành..." nhưng nội dung
bên trong là bản sao của văn bản "Quy trình xây dựng kế hoạch và dự toán
kinh phí hoạt động" (cũng 771/QĐ-ĐHBK). Nội dung thật về "Phòng Thí nghiệm
và Xưởng thực hành" không có trong toàn bộ 454 file `.txt` — văn bản đó đã
mất khỏi kho crawl (`data/clean/text_final/`), không phải bị gộp nhầm ở
bước gán JSON. Đây là lỗi ở khâu thu thập dữ liệu gốc (crawl/OCR); JSON
hiện tại phản ánh đúng những gì có trong file `.txt` nhận được.

**Số liệu đã build**: 403 Document thật (418 file dồn về do một số file
trùng `normalizedNumber`), 778 Organization, 60 Person, 150
NormativeContent, 8814 Article, 996 Document stub, 2865 cạnh trích dẫn
(2009 BASED_ON, 346 REFERENCES, 187 REPLACES, 63 AMENDS, 185 REPEALS). 8
node `TargetGroup` được tạo từ seed nhưng 0 cạnh `APPLIES_TO` — field
`targetGroups` chưa backfill vào 418 file thật (§7 mục 1), chỉ có ở
`samples/`. `query --source benchmark`: 17/17, toàn bộ dưới 350ms kể cả
câu chậm nhất (GROUP BY toàn bảng Document theo status); 3 index full-text
đều dùng được (`index_used = Y`); chuỗi hiệu lực dài nhất 3 bước; B17 xác
nhận 0 văn bản thật thiếu trích dẫn hoàn toàn.

Sau khi build data thật, Neo4j instance chứa data thật chứ không còn 17
samples — quay lại kiểm regression (`query --source samples`) cần chạy lại
`build --dir src/legal_knowledge_graph/samples --wipe` trước.

## 11. NLQ: câu hỏi tự nhiên → Cypher

`core/nlq/` dịch câu hỏi tiếng Việt tự nhiên thành Cypher rồi thực thi,
dừng ở kết quả thô (rows từ Neo4j) — chưa có bước tổng hợp câu trả lời tự
nhiên từ kết quả.

**Luồng 2 giai đoạn** (Stage A luôn chạy, Stage B chỉ chạy khi Stage A
trượt):

```
Câu hỏi
  │
  ▼
Stage A (match_template.py) ── Gemini chọn 1 trong 14 template + trích
  │                             tham số thô (không tự suy ra ID)
  │
  ├─ khớp (confidence đủ) ──▶ resolve.py (không LLM) ──▶ execute template
  │                            đã hand-vetted sẵn (templates.py)
  │
  └─ không khớp ──▶ Stage B (freeform.py) ── Gemini tự viết Cypher,
                     giới hạn bởi schema_context.py
                        │
                        ▼
                     guard.py: blocklist ghi/xoá → chặn label/property
                     giả (lỗ hổng EXPLAIN không bắt được) → EXPLAIN dry-run
                     → ép LIMIT → mới cho chạy thật
```

**4 loại kết quả, không trộn lẫn** (`pipeline.NlqResult.kind`):

| Loại | Khi nào |
|---|---|
| `template_result` | Khớp template, tham số resolve thành công, Cypher (đã vetted) chạy xong — kể cả 0 dòng vẫn là câu trả lời hợp lệ |
| `freeform_result` | Stage A trượt, Cypher do Gemini tự sinh qua hết `guard.py` — gắn cảnh báo "độ tin cậy thấp hơn template, nên soát lại Cypher" |
| `resolution_failed` | Khớp template nhưng 1 thực thể (tên tổ chức/số hiệu văn bản...) không tồn tại/mơ hồ trong graph thật — không chạy Cypher |
| `unsupported` | Ngoài schema, hoặc yêu cầu ghi/xoá, hoặc bị `guard.py` chặn — không chạy Cypher |

**Vì sao tách 2 giai đoạn thay vì 1 lệnh gọi LLM duy nhất**: chính sách
"thử template an toàn trước" nằm ở tầng code, không phải để model tự quyết
định; schema JSON đơn giản hơn cho độ tin cậy cao hơn; đa số câu hỏi khớp
template nên không tốn prompt lớn của Stage B mỗi lần.

**Vì sao template không để Gemini tự viết Cypher**: 14 template trong
`templates.py` là Cypher đã hand-vetted, lấy từ `core/query/catalog.py`/
`benchmark_catalog.py` (đã test trên data thật), chỉ thay literal bằng
`$param`. Gemini chỉ chọn tên template + trích chuỗi thô cho tham số —
`resolve.py` (thuần Python, không LLM) biến chuỗi thô đó thành
`orgId`/`normalizedNumber`/... thật, đối chiếu trực tiếp với graph sống
(778 `Organization` thật, seed `organizations_seed.json` chỉ có 21, chỉ là
fast-path) bằng so khớp token phân biệt sau khi bỏ tiền tố chung ("Trường
Đại học..."). So khớp ký tự thô (`SequenceMatcher` toàn chuỗi) cho kết quả
sai vì mọi tên trường đều chung tiền tố này.

**Vì sao vẫn cần `guard.py` dù đã có schema-grounding trong prompt Stage
B**: prompt chỉ là lớp phòng vệ mềm. `guard.py` là lớp cứng bắt buộc:

1. Chặn nhiều statement / từ khoá ghi-xoá-admin
   (`CREATE/MERGE/SET/DELETE/DROP/CALL apoc.*`...).
2. Chặn label/relationship-type/property không có thật — lỗ hổng `EXPLAIN`
   không bắt được (Neo4j không báo lỗi khi truy cập property sai tên, chỉ
   âm thầm trả `null`).
3. `EXPLAIN <cypher>` dry-run trước khi chạy thật.
4. Ép `LIMIT <= LKG_NLQ_ROW_CAP`.

Neo4j Community Edition (`docker-compose.yml` dùng `neo4j:5`, không phải
`-enterprise`, không cài APOC) không có RBAC, nên an toàn phải làm 100% ở
code, không dựa được vào DB tạo user chỉ-đọc riêng.

**Timeout** — driver cài là `neo4j==6.3.1`. `session.run(query,
timeout=N)` không hoạt động như timeout (bị driver coi là 1 Cypher
parameter `$timeout` vô nghĩa). `core/nlq/execute.py` dùng đúng API:
`Session.begin_transaction(timeout=N)` — khác với `core/query/runner.py`.

**Các vấn đề đã xử lý trong quá trình phát triển**: tên tổ chức hoàn toàn
khác nhau bị coi "mơ hồ" do chung tiền tố "Trường Đại học" (sửa bằng so
khớp token); `additionalProperties` trong JSON schema không được Gemini
Developer API hỗ trợ, chỉ Vertex/Enterprise (đổi `params` từ object tự do
sang mảng `{key,value}`); tham số `limit` bị giữ dạng chuỗi thay vì `int`
gây `CypherSyntaxError`; `Topic`/`TargetGroup` là từ vựng đóng nhỏ nhưng
thiếu chỉ dẫn cho Gemini map trực tiếp như `status` (khiến "sinh viên"
không khớp "Người học"); mô tả 2 template REPLACES mơ hồ chiều quan hệ
khiến Gemini chọn nhầm.

**Giới hạn vận hành**: free-tier Gemini API key có quota thấp (vd 5
request/phút, 20 request/ngày) — `nlq-eval` chạy ~18-36 lệnh gọi Gemini
liên tiếp nên dễ chạm quota giữa chừng dù `gemini_client.py` đã có
retry/backoff cho lỗi tạm thời (429/503).

**Model deprecation**: `gemini-2.5-flash` (giá trị mặc định ban đầu) bị
Google ngừng cấp cho API key mới — gọi `generate_content` trả `404
NOT_FOUND` dù model vẫn xuất hiện trong `client.models.list()`. Mặc định
đã đổi sang `gemini-3.6-flash` (model Google đề xuất thay thế trong thông
báo lỗi, đã xác nhận gọi được với key hiện tại). Nếu gặp `404` tương tự
sau này, kiểm tra `client.models.list()` để tìm model còn dùng được rồi
đổi `LKG_GEMINI_MODEL` trong `.env`.

## 12. Chat UI: FastAPI + React

Lớp trình bày cho `core/nlq/pipeline.ask()` — cùng logic, cùng độ tin cậy
với CLI `ask`, chỉ khác giao diện. Không có tính năng nghiệp vụ mới: không
auth, không lưu lịch sử hội thoại qua lần reload, không gửi ngữ cảnh nhiều
lượt lên backend (mỗi câu hỏi độc lập, giống CLI).

```
core/api/app.py     FastAPI: POST /api/chat, GET /api/health
frontend/            React (Vite) — 1 trang chat duy nhất
```

**Chạy** (2 tiến trình riêng):

```powershell
pip install -r requirements.txt
python run.py lkg serve-api                 # BE tại http://localhost:8000

cd src/legal_knowledge_graph/frontend
npm install
npm run dev                                  # FE tại http://localhost:5173
```

`serve-api` nhận `--host`/`--port`/`--reload` (dev). Frontend đọc backend
URL qua `VITE_API_BASE_URL` (`.env.example` trong `frontend/`, mặc định
`http://localhost:8000`).

**`POST /api/chat`** — request `{"question": "..."}`, response đúng shape
`NlqResult` (`core/nlq/pipeline.py`):

```json
{"kind": "template_result", "template": "...", "cypher": "...",
 "params": {...}, "rows": [...], "elapsed_ms": 64.8, "reason": null,
 "confidence": 0.98}
```

`kind` là 1 trong 4 loại đã thiết kế ở §11 — `resolution_failed`/
`unsupported` không phải lỗi HTTP, vẫn trả `200` kèm `reason`: bot giải
thích không trả lời được, khác lỗi hệ thống.

**Xử lý lỗi**: `pipeline.ask()` chỉ tự bọc 3 loại lỗi đã biết trước
(`GeminiCallError`, `ResolutionFailed`, `TemplateParamError`) thành
`NlqResult` — lỗi hạ tầng ngoài dự kiến (Neo4j mất kết nối, timeout
mạng...) ném ra ngoài `ask()`. `/api/chat` bọc `try/except Exception`
quanh lời gọi `ask()`, cộng 1 `exception_handler` toàn cục cho phần còn
lại — luôn trả JSON `{"error": "..."}` (HTTP 500), không lộ traceback
thô. Đã kiểm chứng bằng cách tắt container Neo4j trong lúc backend đang
chạy: nhận HTTP 500 kèm lý do rõ ràng, server không sập; bật lại Neo4j thì
request tiếp theo chạy đúng ngay, không cần khởi động lại backend.

Phía frontend, `api.js` bọc mọi lỗi gọi API (mạng chết, backend 500, JSON
không parse được) thành 1 `Error` có message rõ; `App.jsx` `try/catch`
quanh mỗi lần gửi, lỗi hiện thành 1 bong bóng chat riêng, không chặn việc
gõ câu hỏi tiếp theo. `ErrorBoundary.jsx` bắt thêm lỗi render bất ngờ
(khác lỗi gọi API), tránh trắng trang khi component crash.

**Giới hạn đã biết**: mỗi request tự mở/đóng 1 driver Neo4j riêng, không
pool connection giữa các request (xem `core/nlq/execute.py`) — chấp nhận
được ở quy mô demo/prototype, cần đổi nếu phục vụ nhiều người dùng đồng
thời. CORS ở `app.py` chỉ mở cho `localhost:5173`/`127.0.0.1:5173` (Vite
dev server) — cần sửa nếu deploy ở domain khác.
