# legal_knowledge_graph

Module gán tay văn bản pháp quy → JSON → Neo4j, dùng để bù đắp điểm yếu
recall của pipeline trích xuất tự động (`src/vanban/kg/`, dựa trên
regex/NLP) ở nhóm quan hệ hiệu lực (`REPLACES`, `AMENDS`, `REPEALS`). Một
người đọc trực tiếp câu "Căn cứ...", "thay thế...", "sửa đổi, bổ sung...",
"bãi bỏ..." trong văn bản và gán quan hệ bằng mắt đáng tin hơn nhiều so với
luật regex.

Quy trình đầy đủ: PDF/scan → OCR (thuộc `src/vanban/`, chạy trước, ra
`data/clean/text_final/*.txt`) → **người đọc `.txt` rồi gõ tay thành JSON**
(bước "gán tay" duy nhất) → **`core/build.py` tự động nạp JSON vào Neo4j**
(code, không có bước tay nào ở đây). Chỉ bước giữa là thủ công.

**Tách biệt hoàn toàn với phần còn lại của repo:** không import code từ
`src/vanban/`, không đọc `.env` gốc, không dùng chung Neo4j instance với
graph chính (10.978 node/14.120 cạnh đã nạp). Mọi thay đổi trong thư mục
này không ảnh hưởng tới pipeline tự động và ngược lại.

## Mục lục

1. [Cấu trúc thư mục](#1-cấu-trúc-thư-mục)
2. [Cài đặt](#2-cài-đặt)
3. [Quy trình làm việc](#3-quy-trình-làm-việc)
4. [Gán tay: quy tắc điền JSON](#4-gán-tay-quy-tắc-điền-json)
5. [Lệnh CLI](#5-lệnh-cli)
6. [Logic nạp vào Neo4j](#6-logic-nạp-vào-neo4j)
7. [So với `rules/Ontology.md`](#7-so-với-rulesontologymd)
8. [Bộ Cypher test](#8-bộ-cypher-test)
9. [Kiểm chứng module](#9-kiểm-chứng-module)

## 1. Cấu trúc thư mục

```
legal_knowledge_graph/
├── schema/document.schema.json     JSON Schema (draft 2020-12) — nguồn sự thật duy nhất về format
├── reference/
│   ├── topics_seed.json            18 lĩnh vực hợp lệ cho document.topics[]
│   └── organizations_seed.json     Tổ chức đã biết trước (orgId, name, orgType, parentOrg)
├── samples/                        17 văn bản mẫu, map từ data/clean/text_final/ thật (rút gọn)
├── core/                           Package Python — mỗi file một trách nhiệm
│   ├── config.py                     Đọc legal_knowledge_graph/.env — không đụng .env gốc
│   ├── normalize.py                  normalizedNumber, slug, các khoá suy ra, authorityLevel
│   ├── validate.py                   JSON Schema + kiểm tra chéo (topic/org khớp seed, không tự trích dẫn...)
│   ├── graph_model.py                Dựng đồ thị TRONG BỘ NHỚ từ JSON đã validate — không đụng Neo4j
│   ├── graph_loader.py               Ghi GraphModel vào Neo4j: schema DDL, batch MERGE, wipe
│   ├── build.py                      CLI `build` — nối graph_model + graph_loader, in báo cáo
│   ├── query_catalog.py              14 câu Cypher test, kèm số dòng kỳ vọng (data thuần)
│   └── query_runner.py               CLI `query` — chạy query_catalog, đo thời gian + đọc PROFILE
├── run.py                          CLI gốc: validate | build | query
├── docker-compose.yml              Neo4j instance THỨ HAI (cổng riêng)
├── requirements.txt                neo4j, jsonschema, python-dotenv
├── .env.example / .env             Cấu hình kết nối Neo4j riêng của module
└── .gitignore                      Chỉ ignore .env
```

`core/graph_model.py` không import `neo4j` — dựng đồ thị trong bộ nhớ là
logic Python thuần, tách khỏi việc ghi DB (`graph_loader.py`). Nhờ vậy có
thể gọi `graph_model.collect(dir)` để kiểm tra dữ liệu mà không cần Neo4j
đang chạy.

## 2. Cài đặt

```powershell
pip install -r legal_knowledge_graph/requirements.txt
docker compose -f legal_knowledge_graph/docker-compose.yml up -d
Copy-Item legal_knowledge_graph/.env.example legal_knowledge_graph/.env
```

Container mới tên `neo4j-pbl6-lkg` — Browser tại `http://localhost:7475`,
Bolt tại `bolt://localhost:7688`, mật khẩu `lkg12345678`. Không trùng
cổng/mật khẩu với container `neo4j-pbl6` (7474/7687) của pipeline chính.
`.env.example` đã khớp sẵn với `docker-compose.yml`, dùng ngay được khi chạy
local.

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `LKG_NEO4J_URI` | `bolt://localhost:7688` | Địa chỉ Bolt của instance riêng |
| `LKG_NEO4J_USER` | `neo4j` | User |
| `LKG_NEO4J_PASSWORD` | `lkg12345678` | Mật khẩu |
| `LKG_NEO4J_DATABASE` | `neo4j` | Tên database |

## 3. Quy trình làm việc

```
văn bản .txt (data/clean/text_final/)
        │  người gán tay đọc + điền JSON theo schema
        ▼
   *.json  ──validate──▶  OK / lỗi field cụ thể
        │  build (tự validate lại trước khi nạp)
        ▼
   Neo4j (instance riêng, cổng 7688)
        │  query — 14 câu Cypher test
        ▼
   báo cáo PASS/FAIL + rows + elapsed_ms + index_used
```

## 4. Gán tay: quy tắc điền JSON

Một file JSON = một văn bản. Cấu trúc đầy đủ và mô tả từng field nằm ở
[`schema/document.schema.json`](schema/document.schema.json) (bản diễn giải
dễ đọc hơn: [`structured_form.md`](structured_form.md)) — đây là tóm tắt các
quy tắc quan trọng nhất.

**Nguyên tắc chung**

- Chỉ chép nguyên văn những gì in trên văn bản. Không tự tính `normalizedNumber`,
  `orgId`, `personId`... — `core/normalize.py` tự suy khi nạp.
- Ngày ghi dạng `dd/mm/yyyy` như trên văn bản, không phải ISO.
- Không chắc một field thì để `null` (hoặc `[]`) và ghi lý do vào `note` ở
  đầu file, đừng đoán.
- Gặp lỗi rõ ràng của chính văn bản/OCR (số hiệu gõ sai kiểu, thiếu chữ...)
  thì sửa lại cho đúng và ghi chú lại trong `note` — đây là giá trị con
  người mang lại so với pipeline regex. Ví dụ:
  [`samples/016_1605-QD-DHBK.json`](samples/016_1605-QD-DHBK.json) chuẩn
  hoá "32/NĐ-CP" (lỗi gõ trong bản gốc) thành "32/CP" cho khớp cách viết
  dùng thống nhất ở mọi văn bản khác, tránh tạo hai stub cho cùng một Nghị
  định.

**`document.topics[]`** — phải khớp một mục trong
[`reference/topics_seed.json`](reference/topics_seed.json) (không phân biệt
hoa/thường, có/không dấu).

**`organization`** — nếu `name` trùng một tổ chức trong
[`reference/organizations_seed.json`](reference/organizations_seed.json) thì
để `orgType`/`parentOrg` là `null`, máy tự khớp. Tổ chức mới (chưa có trong
seed, ví dụ một Khoa/Phòng cụ thể) bắt buộc tự điền `orgType` (enum trong
schema) và `parentOrg`.

**`citations[]`** — mỗi câu "Căn cứ...", "thay thế...", "sửa đổi, bổ
sung...", "bãi bỏ..." ứng với một entry:

| Trong văn bản | `relationType` |
|---|---|
| Nằm trong khối "Căn cứ..." ở đầu văn bản | `BASED_ON` |
| "...thay thế Quyết định số..." | `REPLACES` |
| "...sửa đổi, bổ sung...Điều...của..." | `AMENDS` (điền thêm `targetArticle` nếu biết rõ Điều nào) |
| "...bãi bỏ.../huỷ bỏ..." | `REPEALS` |
| Nhắc tới nhưng không thuộc 4 loại trên | `REFERENCES` |

Không cần văn bản đích đã có file JSON riêng hay chưa — nếu chưa, máy tự tạo
một Document "stub" (`isStub: true`) cho số hiệu đó khi nạp.

**`articles[]` vs `normativeContents[].articles[]`** — nếu văn bản là một
Quyết định "ban hành kèm theo" một Quy định/Quy chế:

- Điều "vỏ bọc" của Quyết định (thường chỉ Điều 1 "Ban hành kèm theo...",
  Điều 2 "Hiệu lực thi hành...") → `articles` cấp Document.
- Điều bên trong Quy định/Quy chế kèm theo → `normativeContents[].articles`.
- **Cả hai có thể cùng tồn tại** trong một file — trường hợp phổ biến, xem
  [`samples/010_2852-QD-DHDN.json`](samples/010_2852-QD-DHDN.json).

**Ví dụ tham khảo** — [`samples/`](samples/) chứa 17 file dựa trên văn bản
thật trong `data/clean/text_final/` (rút gọn, xem `note` đầu mỗi file để
biết đã bỏ bớt gì). Mỗi file minh hoạ một tình huống: đỉnh chuỗi thẩm quyền
(Luật, Quốc hội), `BASED_ON` nhiều bậc, hai cặp `AMENDS`/`REPLACES` thật với
cả hai phía đều là văn bản có thật (003↔004, 005↔006), `REPEALS` đơn và
hàng loạt, Quy định/Quy chế kèm theo, Công văn không có cấu trúc Điều, và
một trường hợp nội dung kèm theo không khớp enum `contentType` nào (017 —
"Chiến lược") nên cố tình để trống `normativeContents` thay vì ép sai loại.
Copy file gần giống văn bản đang gán rồi sửa lại là cách nhanh nhất để bắt
đầu.

**Kiểm tra file vừa viết**

```powershell
python legal_knowledge_graph/run.py validate --dir duong/dan/toi/thu/muc
```

Báo lỗi rõ theo từng file: thiếu field bắt buộc, sai kiểu/enum, số Điều
trùng trong cùng một văn bản, tự trích dẫn chính mình, topic/tổ chức không
khớp danh sách seed.

## 5. Lệnh CLI

```powershell
python legal_knowledge_graph/run.py validate [--dir DIR]      # mặc định: legal_knowledge_graph/samples
python legal_knowledge_graph/run.py build [--dir DIR] [--wipe]
python legal_knowledge_graph/run.py query [--verbose]
```

| Lệnh | Module đứng sau | Việc làm |
|---|---|---|
| `validate` | `core/validate.py` | Chạy JSON Schema + kiểm tra chéo trên toàn bộ `*.json` trong `--dir`. Không đụng Neo4j. |
| `build` | `core/build.py` (dùng `graph_model.py` + `graph_loader.py`) | Validate lại (luôn luôn, không thể bỏ qua) rồi nạp vào Neo4j riêng. `--wipe` xoá sạch graph trong instance này trước khi nạp — không đụng Neo4j chính. |
| `query` | `core/query_runner.py` (dữ liệu ở `query_catalog.py`) | Chạy 14 câu Cypher, in bảng `rows \| expected \| elapsed_ms \| index_used \| PASS/FAIL`. Thoát mã khác 0 nếu có câu sai số dòng. |

## 6. Logic nạp vào Neo4j

`core/graph_model.py` dựng một `GraphModel` trong bộ nhớ (validate trước,
đăng ký Topic/Organization/Person, gộp Điều theo Document/NormativeContent),
sau đó `core/graph_loader.push()` ghi model đó vào Neo4j theo đúng thứ tự
sau — mọi bước dùng `MERGE` (idempotent: chạy `build` nhiều lần không nhân
đôi node/cạnh, chỉ cập nhật property):

1. Constraint + index, gồm 3 full-text index: `doc_text`, `article_text`,
   `content_text`.
2. Toàn bộ `Topic` + `Organization` từ `reference/` (kể cả node chưa được
   văn bản nào dùng tới).
3. `Document` **thật** (`isStub: false`) cho mọi file trong `--dir`.
4. `ISSUED_BY`, `HAS_TOPIC`, `MENTIONS`, `Person` + `SIGNED_BY`,
   `NormativeContent` + `PROMULGATES`, `Article` + `HAS_ARTICLE`.
5. **Cuối cùng**: `citations[]` trên toàn bộ file — với số hiệu đích chưa có
   Document thật, tạo Document **stub** (`ON CREATE SET isStub: true`,
   chỉ có `documentNumber`/`normalizedNumber`) rồi mới tạo cạnh
   `BASED_ON`/`REFERENCES`/`REPLACES`/`AMENDS`/`REPEALS` (5 câu Cypher riêng
   — loại quan hệ không tham số hoá được).

Thứ tự bước 3 trước bước 5 đảm bảo một Document thật không bao giờ bị hạ
xuống thành stub, bất kể thứ tự đọc file.

**Chuẩn hoá** (`core/normalize.py`, viết mới, không import
`src/vanban/kg/norm.py`): `normalizedNumber` (bỏ tiền tố "Số:", chuẩn hoá biến
thể gạch ngang, bỏ số 0 đầu, deaccent+uppercase), `org_id`/`person_id`/
`topic_id` (slug), `content_id` = `"{normalizedNumber}#nd{index}"`, `article_id`
= `"{parent_key}#{number}"`, `authorityLevel` suy theo bảng org-type rồi
tới doc-type (org-type ưu tiên hơn), với `Organization` không có sẵn bậc thì
đi ngược `parentOrg` tới khi gặp tổ chức có bậc trong seed.

## 7. So với `rules/Ontology.md`

`rules/Ontology.md` (7 loại node, 12 quan hệ) là nền cho cả pipeline tự
động lẫn schema gán tay này. 4 điều chỉnh khi chuyển sang bản cho người gán
tay (không sửa `rules/Ontology.md` hay code cũ):

1. **Bỏ `TargetGroup`/`APPLIES_TO`** khỏi v1 — chưa có vocabulary chuẩn như
   Topic; giao cho người gán tự nghĩ nhãn sẽ tạo dữ liệu rác không nhất
   quán. Thêm được sau mà không phá cấu trúc cũ.
2. **Bỏ `noi_dung_raw`**, thay bằng `document.summary` (1-3 câu tự viết) —
   tránh trùng lặp với `Article.text` (đã có toàn văn), nhưng vẫn cho
   `Công văn` (không có cấu trúc Điều) một chỗ mô tả nội dung.
3. **Bỏ `Document.normativeType`** khỏi input — là bản sao của
   `normativeContents[0].contentType`; giữ đồng bộ hai chỗ là thừa,
   `core/graph_model.py` tự suy khi cần.
4. **Giữ `MENTIONS` nhưng bỏ đếm số lần** — chỉ cần danh sách tên tổ chức
   được nhắc tới, không cần đếm tay.

`authorityLevel`, `isStub`, và mọi khoá chuẩn hoá (`normalizedNumber`,
`orgId`, `contentId`, `articleId`, `personId`) không bao giờ do người gán tự
điền — `core/normalize.py` tự suy 100%.

**Escape hatch `idOverride`** — khi khoá tự suy bị đụng hàng (hai người
trùng tên, một tổ chức có cách viết tắt gây trùng slug...), điền
`idOverride` ở đúng entity đó (`document`, `organization`, `signers[]`,
`normativeContents[]`) để ép khoá về giá trị mong muốn.

## 8. Bộ Cypher test

[`core/query_catalog.py`](core/query_catalog.py) định nghĩa 14 câu Cypher
đặt tên, mỗi câu có số dòng kỳ vọng đã đo thật trên bộ `samples/` (không
phải suy đoán):

| Nhóm | Câu | Kiểm tra |
|---|---|---|
| Lookup | Q1, Q2, Q4–Q7, Q12 | Truy vấn 1 bước theo tổ chức/topic/quan hệ, đếm gộp |
| Multi-hop | Q3 | Chuỗi `AMENDS\|REPLACES*1..3` |
| Full-text | Q8, Q9 | Tìm cụm từ chính xác trong `article_text`/`doc_text` (baseline kiểu BM25) |
| Hybrid | Q10 | Full-text lọc ứng viên rồi mở rộng theo quan hệ (`expected_rows = None`, chỉ soi tay) |
| Sanity | Q11, Q13a, Q13b | Đếm node stub, đếm theo nhãn, đếm theo loại quan hệ |

[`core/query_runner.py`](core/query_runner.py) chạy mỗi câu 2 lần — một lần
đo thời gian thật (`time.perf_counter`), một lần `PROFILE` để đọc plan (có
dùng `NodeIndexSeek`/fulltext hay rơi về quét toàn bộ). In bảng kết quả và
thoát mã khác 0 nếu có câu fail — dùng lặp lại được như smoke test.

## 9. Kiểm chứng module

```powershell
python legal_knowledge_graph/run.py validate            # kỳ vọng: 17/17 PASS
python legal_knowledge_graph/run.py build --wipe         # nạp vào Neo4j riêng
python legal_knowledge_graph/run.py query                # kỳ vọng: 14/14 PASS
python legal_knowledge_graph/run.py build                # chạy lại không --wipe: nodes_created ~ 0 (idempotent)
```

Soi bằng mắt ở Neo4j Browser (`http://localhost:7475`): chuỗi hiệu lực thật
2 bước `4757/QĐ-ĐHĐN --AMENDS--> 4481/QĐ-ĐHĐN --REPLACES--> 1341/QĐ-ĐHĐN`
(stub) hiển thị đúng; node stub `32/CP` (Nghị định thành lập ĐHĐN, không có
trong kho thật — giống tình trạng ở graph chính) là node có nhiều cạnh trỏ
vào nhất trên bộ dữ liệu này (14 cạnh).

**Đối chiếu Neo4j chính không đổi** — mở Neo4j Browser của instance gốc
(`http://localhost:7474`, cổng khác hẳn), chạy `MATCH (n) RETURN count(n)`
trước/sau khi chạy các lệnh trên: số node phải giữ nguyên, chứng minh
`legal_knowledge_graph` không đụng vào graph 10.978 node đã có.
