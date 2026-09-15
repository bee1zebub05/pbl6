# Dữ liệu — từ PDF trên website tới knowledge graph

Đọc file này để biết **dữ liệu đi qua những đâu, còn lại bao nhiêu, và hiện đang ở
trạng thái nào**. Chi tiết cách chạy từng bước xem [README gốc](../README.md).

---

## ⚠ Có HAI cây `data/` song song

Đây là thứ gây nhầm nhiều nhất, đọc kỹ trước khi làm gì.

| | Đường dẫn | Có gì | Trong git? |
|---|---|---|---|
| **Bản làm việc** | `F:\DUT4\PBL6\data\` | `raw/` 2,3 GB PDF · `processed/` 2.186 file | **KHÔNG** |
| **Bản trong repo** | `F:\DUT4\PBL6\pbl6\data\` | `clean/` · `kg/` · `eval/` | có |

Repo **chỉ chứa đầu ra đã chốt**, không chứa PDF gốc (2,3 GB) và không chứa các bản
OCR trung gian. Vì vậy khi clone repo về, `data/raw/` và `data/processed/` sẽ **rỗng** —
đó là bình thường, không phải thiếu file.

**Hai bản không tự đồng bộ.** Sửa ở bản làm việc xong phải copy đè sang repo:

```bash
cp -r ../data/processed/text_final/. data/clean/text_final/
```

---

## 1. Dữ liệu rụng dần qua từng bước

| Bước | Còn lại | Mất bao nhiêu, vì sao |
|---|---|---|
| Mục lục website `dut.udn.vn` | **475** | — |
| Tải về được | **460** | −15: máy chủ trả **404**, file chưa từng đăng hoặc đã gỡ |
| Sau khi loại bản gắn nhầm | **455** | −5: website gắn **sai file** cho mục lục (xem §4) |
| Kho chuẩn `text_final` | **455** | không mất thêm |

15 văn bản 404 vẫn xuất hiện trong graph dưới dạng `Document` **stub** khi bị văn bản
khác viện dẫn — đúng như Ontology §1. Đáng tiếc nhất: `41/2024/QH15` (Luật Bảo hiểm
xã hội 2024), `36/2024/QH15` (Luật Trật tự an toàn giao thông đường bộ 2024),
`115/2020/NĐ-CP`, `75/2012/NĐ-CP`.

---

## 2. `raw/` là gì

Nằm ở **bản làm việc**, không commit vì 2,3 GB.

```
data/raw/
├── metadata.csv        ← 475 dòng: mục lục cào từ website
│                         (tên, số hiệu, lĩnh vực, ngày, file_url)
├── metadata.csv.bak
├── pdf/<lĩnh vực>/     ← 455 PDF — nguồn gốc của mọi thứ
├── pdf_fixed/          ← 1 file tải lại vì bản đầu hỏng
├── pdf_new/            ← rỗng
└── doc_new/            ← 6 file .doc, một số văn bản website đăng dạng Word
```

**PDF là ảnh scan thuần, không có lớp text.** Đã kiểm: `get_text()` trả về 0 ký tự.
Nên bắt buộc phải OCR, không trích text trực tiếp được.

Cũng vì vậy mà muốn đối chiếu bản OCR với trang giấy thì phải render ra ảnh:

```python
import pymupdf
d = pymupdf.open(duong_dan_pdf)
d[so_trang - 1].get_pixmap(dpi=150).save("xem.png")
```

`pdftoppm` **không có** trên máy này, nên đọc thẳng PDF sẽ báo lỗi.

---

## 3. `processed/` — các bản OCR trung gian

Nằm ở **bản làm việc**, không commit. Giữ lại để đối chiếu khi nghi ngờ.

| Thư mục | File | Là gì |
|---|---|---|
| `text_raw/` | 690 | OCR **thô**, chưa hiệu đính |
| `text_clean_gemma/` | 460 | Bản hiệu đính lượt một |
| `text_gemma_moi/` | 287 | OCR **lại** bằng Gemma cho những file lượt một đọc kém |
| `text_gemma_trang/` | 283 | OCR lại theo **từng trang** cho file vẫn còn hỏng |
| `text_gemma_vet/` | 4 | Vét nốt 4 file cứng đầu |
| `_cach_ly_ban_sai/` | 6 | 5 bản website gắn nhầm, tách ra để không lọt vào kho |
| **`text_final/`** | **455** | **Kho chuẩn** — nguồn của `clean/text_final` trong repo |

Ngoài ra `data/_ban_luu_truoc_khi_sua/` (210 file) là **bản lưu trước đợt sửa lỗi OCR
mức ký tự**, giữ để hoàn tác nếu cần.

---

## 4. `clean/` — data thật trong repo

```
data/clean/
├── README.md                 ← chi tiết kho text_final, ĐỌC FILE ĐÓ
├── text_final/       455 file ← KHO CHUẨN, dùng cái này
└── text_clean_gemma/ 464 file ← bản cũ, giữ vì config.py còn trỏ vào
```

Kho `text_final` được dựng bằng cách **chọn bản OCR tốt hơn cho từng văn bản** giữa
bản cũ và bản OCR lại, qua cổng lọc năm điều kiện — trong đó hai điều kiện quan trọng
nhất là **không được mất người ký** và **phải thêm được thông tin**. Đã đo được trường
hợp bản mới dài hơn nhưng lại mất người ký (`0255`), nên gộp theo độ dài là gộp nhầm.

Sau đó kho đi qua **đợt sửa lỗi OCR mức ký tự** (commit `ad3e512`) — 294/455 văn bản,
trong đó 75 văn bản được mở ra đọc từng trang.

👉 Toàn bộ chi tiết ở **[`clean/README.md`](clean/README.md)**: cách dựng kho, chất
lượng đo được, 5 bản gắn nhầm, 15 bản 404, những thứ trông như rác nhưng là nội dung
thật, quy ước mốc trang, và danh sách chỗ cần rà lại.

### Chất lượng hiện tại

| | |
|---|---|
| Ngày ban hành đọc được | **455 / 455 (100%)** |
| Người ký đọc được | **451 / 455 (99%)** — 4 bản còn lại là biểu mẫu, chỗ ký để trống |
| Căn cứ pháp lý | 424 / 455 (93%) — 2.089 căn cứ |
| Cấu trúc Điều | 412 / 455 (91%) — 9.734 Điều / 33.956 Khoản |
| Watermark quảng cáo | **0** |
| Tỷ lệ lỗi ký tự — trung vị | **0,13%** |
| Văn bản còn ≥ 1% lỗi | **54** |
| Văn bản còn ≥ 3% lỗi | **9** |

Con số lỗi ký tự **không tuyệt đối chính xác**: bộ đo dựa trên cấu trúc âm tiết tiếng
Việt nên tính nhầm `TTg` `logo` `km` `Internet` `Excel` `Covid` là "âm tiết sai". Phải
mở file ra xem, đừng xếp hạng chỉ theo số.

---

## 5. `kg/` — đầu ra knowledge graph

```
data/kg/
├── documents.jsonl           1.248 dòng   node Document (gồm cả stub)
├── articles.jsonl            9.546 dòng   node Article
├── relations.jsonl           3.231 dòng   quan hệ giữa các văn bản
├── mentions.jsonl            1.014 dòng   trích dẫn bắt được
├── segments.jsonl              450 dòng   vùng cấu trúc đã cắt
├── signed_by.jsonl             227 dòng   quan hệ ký
├── normative_contents.jsonl    178 dòng   NormativeContent
├── persons.jsonl                49 dòng   node Person
├── organizations.jsonl          18 dòng   node Organization
├── topics.jsonl                 18 dòng   node Topic
├── nguoi_ky.json                           bảng tra người ký
├── schema.cypher                           ràng buộc + index Neo4j
└── queries.cypher                          bộ Cypher mẫu
```

Nạp vào Neo4j (`bolt://localhost:7687`) ra **10.978 node · 14.120 cạnh**.

Đặc tả 7 loại node và 12 quan hệ ở [`rules/Ontology.md`](../rules/Ontology.md).

**Lưu ý:** `documents.jsonl` và `src/vanban/config.py` hiện còn trỏ vào
`text_clean_gemma` chứ chưa phải `text_final`. Muốn chuyển thì sửa `config.py` rồi
chạy lại `python run.py kg docs`.

---

## 6. `eval/` — đánh giá

190 file. Kết quả gom ở [`eval/BAO_CAO.md`](eval/BAO_CAO.md), chi tiết tách theo mục
của Ontology §6:

| File | Nội dung |
|---|---|
| `extraction.md` · `extraction_metrics.json` | §6.1–6.2 — Cohen's κ, P/R/F1 từng loại quan hệ |
| `retrieval.md` | §6.3–6.5 — bộ câu hỏi, so BM25 / KG / Hybrid |
| `ablation_va_loi.md` · `ablation.json` · `error_analysis.json` | §6.6–6.7 — ablation và phân tích lỗi |
| `goldset/` | gold set phân tầng + phiếu gán tay |
| `agreement.json` · `queries.csv` | dữ liệu thô |

---

## 7. `manifest.jsonl`

501 dòng, mỗi dòng một JSON gộp toàn bộ metadata của một văn bản qua các bước. Có ở
**cả hai cây** `data/`.

Số 501 lớn hơn 455 vì manifest giữ lại cả những bản đã bị loại và những mục lục không
tải được — để truy vết, không phải để dùng làm kho.

---

## 8. Còn dở việc gì

| Việc | Trạng thái |
|---|---|
| Sửa lỗi OCR ký tự | 294/455 văn bản; **54 văn bản còn ≥1% lỗi** |
| Đọc tay từng trang | 75/455 văn bản |
| `0440` | mới sửa tới trang 19/~60 |
| 7 chỗ cần đối chiếu ảnh gốc | chưa làm — xem `clean/README.md` |
| Chuyển KG sang `text_final` | chưa — `config.py` còn trỏ `text_clean_gemma` |

Ghi chép chi tiết để chạy tiếp nằm ở `TIEN_DO_SUA_OCR.md` (bản local, ngoài repo).
