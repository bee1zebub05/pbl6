# Tiến độ — KG Văn bản pháp quy DUT/ĐHĐN

> Cập nhật: **27/08/2026**
> Đặc tả đích: [rules/Ontology.md](../rules/Ontology.md) — Mức 3 (paper)
> Hướng dẫn chạy: [README.md](../README.md)

---

## 1. Đang ở đâu

Pipeline dữ liệu (crawl → OCR → hiệu đính) **đã xong**. Phần xây graph mới đi
được **Bước 0/5**: bảng `Document` đã chốt, chưa có quan hệ nào giữa các văn bản.

| Giai đoạn (§8 Ontology) | Việc | Trạng thái |
|---|---|---|
| P1 — Mức 1 | Crawl → metadata → node cơ bản | ✅ dữ liệu xong, **chưa nạp Neo4j** |
| P2 | OCR + regex → `BASED_ON` / `REFERENCES` + stub | ⬜ chưa bắt đầu |
| P3 | Quan hệ hiệu lực + `NormativeContent` / `Article` | ⬜ chưa bắt đầu |
| P4 — Mức 2 | BM25 baseline + query set + gold set | ⬜ chưa bắt đầu |
| P5 — Mức 3 | Hybrid + metrics + ablation + error analysis | ⬜ chưa bắt đầu |

Chia nhỏ phần xây graph thành 6 bước thi công:

| Bước | Việc | Trạng thái |
|---|---|---|
| **0** | **Bảng `Document` — gộp trùng, bậc thẩm quyền, hiệu lực** | ✅ **xong 27/08/2026** |
| 1 | Cắt vùng: header / Căn cứ / thân Điều-Khoản / điều khoản thi hành | ⬜ |
| 2 | Trích + resolve số hiệu → `BASED_ON` / `REFERENCES` + stub | ⬜ |
| 3 | Phân loại `REPLACES` / `AMENDS` / `REPEALS` theo vùng + trigger | ⬜ |
| 4 | `NormativeContent` + `Article` (§2.6, §2.7) | ⬜ |
| 5 | Nạp Neo4j + bộ Cypher mẫu | ⬜ |

---

## 2. Dữ liệu hiện có

### Kho văn bản

| Chỉ số | Con số |
|---|---|
| PDF đã crawl | 501 file / 11.420 trang |
| Đã OCR | 501/501 (EasyOCR tại máy) |
| Đã chuẩn hoá số hiệu/ngày (`normalize`) | 501/501 |
| Đã hiệu đính bằng Gemma | **460**, thiếu 2 văn bản (xem §4) |
| Tổng ký tự sau hiệu đính | 20,2 triệu (~43.800 ký tự/văn bản) |
| Vị trí | `data/clean/text_clean_gemma/<lĩnh vực>/*.txt` |

> ⚠️ `data/raw/pdf/` và `data/raw/metadata.csv` **đã bị xoá khỏi máy**. Nguồn
> metadata duy nhất còn lại là `data/manifest.jsonl` (xuất 17/08). Đừng xoá file
> đó — ngày ban hành, cơ quan ban hành, tình trạng hiệu lực chỉ còn nằm ở đấy.

### Node đã dựng (Bước 0)

`data/kg/documents.jsonl` · `organizations.jsonl` · `topics.jsonl`

| Node | Số lượng |
|---|---|
| `Document` | **450** (từ 501 dòng manifest + 460 file text) |
| `Organization` | 14 (kèm cây `PART_OF`) |
| `Topic` | 18 |

Bậc thẩm quyền (§3) phủ 100%:

| Bậc | | Số VB |
|---|---|---|
| 6 | Hiến pháp | 1 |
| 5 | Luật / Pháp lệnh | 50 |
| 4 | Nghị định | 49 |
| 3 | Thông tư / Thủ tướng / bộ ngành | 158 |
| 2 | Đại học Đà Nẵng | 94 |
| 1 | Trường ĐHBK | 98 |

Hiệu lực: **430** còn hiệu lực · **15** hết hiệu lực (đã tách được `expiryDate`)
· **5** chưa rõ.

### Nguyên liệu cho Bước 1–4 (đã đo trên kho sạch)

| Tín hiệu | Số đo | Dùng cho |
|---|---|---|
| File có `Căn cứ` | 439/460 (95%) | cắt vùng → `BASED_ON` |
| File có `Điều N.` | 426/460 (93%), 403 bắt đầu đúng Điều 1 | cắt vùng → `Article` |
| Heading `Điều N` | 10.858 | node `Article` (§2.7) |
| Trích dẫn số hiệu | **9.025 lần**, 2.136 số hiệu phân biệt | `BASED_ON` / `REFERENCES` |
| — nối được vào 450 VB | **428** | cạnh thật |
| — phải tạo stub | 1.708 (661 xuất hiện ≥2 lần, 1.047 chỉ 1 lần) | §1 Ontology |
| Trigger `sửa đổi, bổ sung` | 1.922 | `AMENDS` |
| Trigger `thay thế` | 521 | `REPLACES` |
| Trigger `bãi bỏ` | 325 | `REPEALS` |
| Trigger `hướng dẫn thi hành` | 270 | quan hệ hướng dẫn |
| Header tin được | 386/448 (86%) | mọi bước sau |

---

## 3. Đã làm gì

### Pipeline dữ liệu (xong trước 26/08)

- Crawler `dut.udn.vn` → 501 PDF + metadata.
- OCR bằng EasyOCR tại máy (chính xác **hơn** API OCR, lại miễn phí — README §5).
- `normalize`: tiêm số hiệu/ngày từ metadata (phần **viết tay** trên biểu mẫu,
  OCR đọc sai 77% — README §6b) + bỏ phiếu chéo sửa trích dẫn hỏng.
- Hiệu đính bằng Gemma qua Gemini API, xoay tua nhiều key.

### Bước 0 — bảng `Document` (27/08/2026)

Code: `src/vanban/kg/{norm,session,documents}.py` · lệnh `python run.py kg docs`

Ba việc:

1. **Neo vào kho text có thật.** Manifest ghi `fix_status: pending` cho 498/501
   và `text_clean: null` trong khi 460 văn bản đã hiệu đính xong ở một đường dẫn
   khác. Nay text lấy từ đĩa, manifest chỉ còn là nguồn metadata.
2. **Gộp trùng theo số hiệu.** 501 dòng → 445 số hiệu phân biệt: 55 nhóm trùng,
   11 nhóm được crawler cấp **hai `doc_id`** cho cùng một văn bản. §2.1 lấy
   `so_hieu_norm` làm khoá chính — không gộp thì `MERGE` trong Neo4j sẽ vỡ.
   4 nhóm nằm ở hai lĩnh vực → hợp nhất `topics` (đúng bản chất `HAS_TOPIC` n→m).
3. **Suy thuộc tính ontology**: `authority_level` (§3), `status` + `expiryDate`
   tách từ chuỗi `"Hết hiệu lực 01/01/2024"`, `documentType` tách khỏi
   `"Quyết định, Quy định"` (§2.6), `orgId`/`orgType`/`parentOrg` (§2.2).

Ba quyết định thiết kế đã chốt (chi tiết trong README §10):

- **Bậc thẩm quyền xét theo CƠ QUAN, không theo LOẠI.** Bảng §3 trộn hai tiêu
  chí; đi theo loại thì 252 văn bản `"Quyết định, Quy định"` — do đủ mọi cấp ban
  hành — rơi chung một bậc. Mỗi node mang thêm `level_note` phân biệt bậc tra
  thẳng từ ontology với bậc suy rộng.
- **`"Luật, Pháp lệnh"` là tên NHÓM, không phải loại văn bản.** Tách theo dấu
  phẩy như `"Quyết định, Quy định"` là sai với cả 50 văn bản luật.
- **Khoá chính = số hiệu bỏ dấu** (`so_hieu_key`). Nhờ chuẩn hoá này, số trích
  dẫn nối được vào văn bản thật tăng **365 → 428 (+17%)** so với so khớp thô.

Kèm theo: phép **đối chiếu header** — mở text, so số hiệu in ở đầu trang 1 với
metadata. Đây là thước đo văn bản nào có header đáng tin, mà Bước 1–2 dựa hết
vào đó.

---

## 4. Tồn đọng cần xử lý

Xếp theo mức độ chặn công việc sau.

### 4.1 Cần làm trước Bước 1 — 34 văn bản header lệch

`python run.py kg review --grep header-lech`

Không phải nhiễu — đây là **lỗi metadata và lỗi OCR thật**:

```
1/2024/TT-NBV     header ghi TT-BNV      <- metadata gõ nhầm BNV -> NBV
2453/QĐ-ĐHBK      header ghi QĐ-ĐHĐN     <- đúng cảnh báo normalize.py từng nêu
53/2022/NĐ-VP     header ghi NĐ-CP       <- metadata sai hậu tố
17/2021/TT-BGDĐT  header ghi 7/2021      <- OCR nuốt mất chữ số đầu
```

Sửa tay 34 cái này → tỷ lệ header tin được lên ~94% trước khi vào Bước 1.
Ngoài ra còn **28 văn bản header không đọc ra số hiệu nào** — cần xem lại thủ
công xem bản scan có thật sự thiếu hay chỉ do vùng header bị cắt sai.

### 4.2 Nên làm sớm — 2 văn bản chưa hiệu đính

| doc_id | Số hiệu | Ghi chú |
|---|---|---|
| 0166 | `115/2020/NĐ-CP` | **bị trích dẫn 115 lần** trong kho — đáng chạy lại nhất |
| 0307 | `14/2021/TT-BGDDT` | metadata ghi `BGDDT` (thiếu `Đ`) |

Chạy lại: `python run.py fix` rồi copy kết quả vào `data/clean/text_clean_gemma/`.

### 4.3 Ghi nhận, chưa cần xử lý

- **5 file không có trong manifest** (0148, 0151, 0158, 0161, 0352) — metadata
  đang lấy từ tên file nên thiếu ngày ban hành và tình trạng hiệu lực. Bổ sung
  tay 5 dòng vào manifest là xong.
- **`normativeType` mới bắt được 224/450.** Ví dụ `10/2016/TT-BGDĐT` rõ ràng ban
  hành một *Quy chế* nhưng metadata chỉ ghi `loai = "Thông tư"`. Phần còn lại
  nằm trong tiêu đề và thân văn bản → để Bước 4 moi ra.
- **1.708 stub sẽ áp đảo graph 3,8:1** nếu tạo hết. Cần chốt ngưỡng ở Bước 2
  (xem §5).

---

## 5. Việc tiếp theo

### Bước 1 — cắt vùng (ưu tiên 1)

Chia mỗi văn bản thành 4 vùng: header / phần `Căn cứ` / thân Điều-Khoản / điều
khoản thi hành. **Không phải bước phụ**: vùng chính là tín hiệu phân loại quan
hệ theo §5.4 — cùng một số hiệu, nằm trong `Căn cứ` thì là `BASED_ON`, nằm ở
điều khoản thi hành cạnh chữ "thay thế" thì là `REPLACES`.

Dữ liệu ủng hộ: 439/460 file có `Căn cứ`, 426/460 có `Điều N.`

### Bước 2 — trích + resolve số hiệu (ưu tiên 2)

Tái dùng `_CITE` và `CitationIndex` có sẵn trong `src/vanban/normalize.py` —
logic chuẩn hoá đã viết rồi, đừng viết lại. Resolve qua `norm.so_hieu_key`.

**Quyết định cần chốt trước khi code:** tạo stub cho tất cả 1.708 số hiệu lạ,
hay chỉ cho 661 cái xuất hiện ≥2 lần? Đề xuất: chỉ ≥2 lần (hoặc nằm trong vùng
`Căn cứ`), phần còn lại giữ dạng thuộc tính text để graph khỏi loãng.

### Chạy song song — gold set (§6.1)

Ontology ghi rõ "làm sớm, gán song song". Đây là thứ **duy nhất bị ràng buộc bởi
lịch người thật** (50–100 văn bản, 2 người gán độc lập, đo Cohen's κ), mà toàn
bộ phần đánh giá của paper treo vào nó. Không nên đợi extractor xong mới bắt đầu.

Việc cụ thể: chọn 50–100 văn bản đa dạng loại/cơ quan/thời kỳ → viết guideline
gán → 2 người gán độc lập các quan hệ `BASED_ON` / `REFERENCES` / `REPLACES` /
`AMENDS` / `REPEALS`, `SIGNED_BY`, `APPLIES_TO`.

---

## 6. Nhật ký

| Ngày | Việc |
|---|---|
| 27/08/2026 | **Bước 0 xong** — 450 `Document` + 14 `Organization` + 18 `Topic` ra `data/kg/*.jsonl`. Thêm gói `src/vanban/kg/`, nhóm lệnh `python run.py kg`, session `kg.db` riêng. Phát hiện 34 header lệch (có lỗi metadata thật) |
| 26/08/2026 | Hiệu đính Gemma xong 460/501, kết quả về `data/clean/text_clean_gemma/` |
| 25/08/2026 | Chốt `rules/Ontology.md` v0.3 (Mức 3); vẽ `docs/kg_ontology.png`, `docs/kg_instance.png` |
| 21/08/2026 | `normalize` xong 501/501 |
| 17/08/2026 | Xuất `data/manifest.jsonl` (501 dòng) |
| — | OCR 501/501 bằng EasyOCR tại máy; crawl 501 PDF từ `dut.udn.vn` |
