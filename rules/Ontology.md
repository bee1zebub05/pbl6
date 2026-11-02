# Ontology v0.3 — KG Văn bản DUT (Mức 3 / Paper)

> Kế thừa v0.2 (neo vào dataset thật 475 VB từ `dut.udn.vn`). Bản này chốt cho **Mức 3 — paper nghiêm túc**: thêm 2 node (`NormativeContent`, `Article`) và đặc tả đầy đủ phần **evaluation** — thứ quyết định giá trị công bố.

---

## 1. Phạm vi

KG theo kịch bản **B**: Document gồm cả VB nội bộ DUT (ĐHBK 107, ĐHĐN 97) lẫn VB pháp luật ngoài (Bộ GD&ĐT 136, Quốc hội 55, Chính phủ 50…) đã có trong crawl. VB bị viện dẫn nhưng chưa crawl → tạo `Document`**stub** (chỉ số hiệu + tên), cùng class, làm giàu sau.

---

## 2. Node types (7)

### 2.1 `Document` — trung tâm


| Property                                 | Kiểu                                                  | Nguồn                                  |
| ---------------------------------------- | ------------------------------------------------------ | --------------------------------------- |
| `so_hieu`/`so_hieu_norm`(PK)             | string                                                 | metadata / derive                       |
| `title`                                  | text                                                   | metadata                                |
| `abstract`                               | text                                                   | PDF (tùy)                              |
| `documentType`                           | enum                                                   | metadata`loai`(đã tách §4.2 v0.2)   |
| `authority_level`                        | int                                                    | derive (§3)                            |
| `status`                                 | enum {CON\_HIEU\_LUC, HET\_HIEU\_LUC, CHUA\_HIEU\_LUC} | metadata                                |
| `issueDate`/`effectiveDate`/`expiryDate` | date                                                   | metadata (expiry parse từ`tinh_trang`) |
| `fileUrl`                                | url                                                    | metadata                                |
| `noi_dung_raw`                           | text                                                   | PDF + OCR                               |
| `is_stub`                                | bool                                                   | derive                                  |

### 2.2 `Organization`

`orgId`, `name`, `orgType` {quoc\_hoi, chinh\_phu, thu\_tuong, bo\_nganh, dai\_hoc\_vung, truong\_thanh\_vien, phong\_ban, don\_vi\_truc\_thuoc}, `parentOrg`.

### 2.3 `Person`

`personId`, `fullName`, `position`, `academicTitle`.

### 2.4 `Topic`

`topicId`, `name`, `description`. Vocabulary = 18 `linh_vuc` thật (§3.1 v0.2).

### 2.5 `TargetGroup`

`targetGroupId`, `name`, `description`, `level`.

### 2.6 `NormativeContent` — *(mới, Mức 3)*

Phần Quy định/Quy chế được một `Document` (thường là Quyết định) ban hành kèm. Giải quyết pattern **235/475 VB** dạng "Quyết định, Quy định". Props: `contentId`, `contentType` {Quy định, Quy chế}, `title`, `status`. Cho phép truy vấn: *"quy chế nào đang có hiệu lực về học vụ"* — hỏi vào nội dung, không hỏi vào cái quyết định bọc ngoài.

### 2.7 `Article` — *(mới, Mức 3)*

Điều/Khoản trong `NormativeContent`. Props: `articleId`, `number` (vd "Điều 5"), `heading`, `text`. Cho phép: retrieval cấp điều khoản + `AMENDS` trỏ chính xác tới từng Điều.

---

## 3. `authority_level` (property, không phải node)


| documentType                   | level |
| ------------------------------ | ----- |
| Hiến pháp                    | 6     |
| Luật, Pháp lệnh             | 5     |
| Nghị định                   | 4     |
| Thông tư / Quyết định-TTg | 3     |
| VB Đại học Đà Nẵng       | 2     |
| VB Trường ĐHBK              | 1     |

Dùng: `MATCH (d)-[:BASED_ON*1..3]->(b) RETURN b ORDER BY b.authority_level DESC` → ra văn bản gốc thẩm quyền cao nhất.

---

## 4. Relations (bản chốt)


| Relation                 | Domain → Range              | Card.     | Nguồn                      | Độ khó |
| ------------------------ | ---------------------------- | --------- | --------------------------- | --------- |
| `ISSUED_BY`              | Document → Organization     | n→1      | số hiệu                   | dễ       |
| `SIGNED_BY`              | Document → Person           | n→1      | PDF/OCR                     | TB        |
| `HAS_TOPIC`              | Document → Topic            | n→m      | metadata + NLP              | dễ       |
| `APPLIES_TO`             | Document → TargetGroup      | n→m      | NLP                         | khó      |
| `BASED_ON`               | Document → Document         | n→m      | PDF "Căn cứ" + regex      | TB        |
| `REFERENCES`             | Document → Document         | n→m      | số hiệu trong thân       | TB        |
| `REPLACES`/`REPLACED_BY` | Document ↔ Document         | n→m      | PDF điều khoản thi hành | khó      |
| `AMENDS`/`AMENDED_BY`    | Document ↔**Document        | Article** | n→m                        | PDF + NLP |
| `REPEALS`/`REPEALED_BY`  | Document ↔ Document         | n→m      | PDF                         | khó      |
| `PROMULGATES`            | Document → NormativeContent | 1→1      | metadata + PDF              | dễ       |
| `HAS_ARTICLE`            | NormativeContent → Article  | 1→n      | PDF parse                   | TB        |
| `PART_OF`                | Organization → Organization | n→1      | derive                      | dễ       |

**Ba quan hệ hiệu lực tách bạch:**`REPLACES` (thay thế → B hết hiệu lực) ≠ `AMENDS` (sửa đổi/bổ sung → B vẫn hiệu lực) ≠ `REPEALS` (bãi bỏ → B hết hiệu lực, không có VB thay). Trigger: "thay thế…" / "sửa đổi, bổ sung một số điều…" / "bãi bỏ…".

---

## 5. Pipeline trích xuất

1. **OCR** (Tesseract `vie` / VietOCR) — bắt buộc, vì text layer nhiều PDF hỏng ("Căn cứ"→"Can cir").
2. **Regex số hiệu**`\d+/[\w\-/ĐĐ.]+` — sống sót qua OCR lỗi → bắt VB được nhắc.
3. **Resolve** số hiệu → node qua `so_hieu_norm`; miss → tạo stub.
4. **Phân loại quan hệ** (BASED\_ON vs REPLACES vs AMENDS vs REPEALS) — rule-based theo trigger + vị trí (phần "Căn cứ" đầu VB = BASED\_ON; "Điều khoản thi hành" cuối VB = REPLACES/REPEALS). Nâng cấp: fine-tune classifier nếu rule chưa đủ.
5. **Parse Điều/Khoản** → `Article`.

---

## 6. EVALUATION DESIGN (lõi của Mức 3)

### 6.1 Gold set (làm sớm, gán song song lúc crawl)

* Chọn **50–100 Document** đa dạng loại/cơ quan/thời kỳ.
* Gán tay: tất cả quan hệ `BASED_ON / REFERENCES / REPLACES / AMENDS / REPEALS`, `SIGNED_BY`, `APPLIES_TO`.
* 2 người gán độc lập → đo **inter-annotator agreement** (Cohen's κ) → tài liệu hóa guideline gán.

### 6.2 Đánh giá extraction (per-relation)

* **Precision / Recall / F1** cho *từng loại* quan hệ (đừng gộp — REPLACES khó hơn BASED\_ON nhiều).
* Tách 2 tầng lỗi: (a) *detection* (có bắt được quan hệ không) và (b) *resolution* (nối đúng node đích không).

### 6.3 Retrieval — bộ câu hỏi

Xây **query set** \~30–50 câu, chia nhóm:

* *single-hop* ("VB nào do Phòng Đào tạo ban hành, còn hiệu lực")
* *multi-hop* ("QĐ 1425 dựa trên những Luật/Nghị định gốc nào")
* *hiệu lực* ("QĐ nào đang thay thế QĐ 6950") Mỗi câu có **gold answer set**.

### 6.4 So sánh 3 hệ: BM25 vs KG vs Hybrid

* **BM25**: baseline tìm kiếm text thuần.
* **KG**: trả lời bằng truy vấn Cypher trên đồ thị.
* **Hybrid**: BM25 lọc ứng viên + KG mở rộng theo quan hệ (hoặc re-rank).
* Metrics: **P@k, R@k, MRR, nDCG**.

### 6.5 Multi-hop (đánh giá riêng)

Tách riêng nhóm câu multi-hop và báo cáo riêng — đây là nơi KG/Hybrid phải thắng BM25 rõ rệt; nếu không, phải giải thích tại sao.

### 6.6 Ablation

Bỏ từng thành phần, đo mức tụt: (–OCR) / (–quan hệ hiệu lực) / (–authority\_level) / (–NormativedContent+Article) / (–Hybrid, chỉ KG). Chứng minh từng phần *thật sự* đóng góp.

### 6.7 Error analysis

Phân loại lỗi điển hình: OCR nuốt số hiệu, nhầm REPLACES↔AMENDS, resolve sai văn bản trùng số khác năm, stub không bao giờ được nối… → gợi ý hướng cải thiện.

---

## 7. Cấu trúc paper gợi ý

1. Introduction (bài toán tra cứu VB pháp quy nội bộ + liên thông pháp luật)
2. Related work (legal KG, document retrieval, Vietnamese legal NLP)
3. Dataset (475+ VB, thống kê, đặc thù OCR)
4. Ontology & KG construction (bản này)
5. Extraction method + evaluation (§6.1–6.2)
6. Retrieval: BM25 / KG / Hybrid (§6.3–6.5)
7. Ablation & error analysis (§6.6–6.7)
8. Conclusion

---

## 8. Lộ trình triển khai từng bước (đích Mức 3)


| Giai đoạn | Việc                                             | Ra được               |
| ----------- | ------------------------------------------------- | ------------------------ |
| P1 (Mức 1) | Crawl → metadata → Neo4j (node + quan hệ dễ)  | KG chạy, tra cơ bản   |
| P2          | OCR + regex →`BASED_ON`/`REFERENCES`+ stub       | multi-hop căn cứ chạy |
| P3          | Quan hệ hiệu lực +`NormativeContent`/`Article` | ontology đầy đủ      |
| P4 (Mức 2) | BM25 baseline + query set + gold set              | có đối chứng         |
| P5 (Mức 3) | Hybrid + đủ metrics + ablation + error analysis | paper                    |

## 9. Không đưa vào ontology

Node cho: trạng thái hiệu lực (→ property), người ký (→ Person), thời gian (→ property Document), nơi nhận/phụ lục (giá trị thấp). Không tách class riêng cho VB pháp luật ngoài (dùng chung `Document`).

---

## 10. Thay đổi v0.4 — danh tính và thời gian của thực thể *(đề xuất, 20/10/2026)*

> Lý do: khoá `orgId`/`personId` sinh từ tên gốc (`slug(name)`) làm một thực thể thành nhiều node (alias) và nhiều thực thể cùng tên thành một node. Quy ước gộp/tách chi tiết: [docs/QUY_UOC_THUC_THE.md](../docs/QUY_UOC_THUC_THE.md). Các mục §2.2, §2.3, §4 ở trên vẫn là v0.3; bảng dưới là phần bổ sung/thay thế.

### 10.1 `Organization`

| Property | Kiểu | Thay đổi | Nguồn |
| --- | --- | --- | --- |
| `orgId` (PK) | string | **Đổi nghĩa:** khoá chuẩn từ bảng ánh xạ `reference/entity_canonical.json`, không còn là `slug(name)` | bảng ánh xạ (người duyệt) |
| `name` | string | Tên chuẩn hiển thị | bảng ánh xạ |
| `aliases` | string[] | **Mới** — mọi cách viết đã gặp trong kho | bảng ánh xạ |
| `observedFrom` / `observedTo` | date | **Mới** — ngày ban hành sớm nhất / muộn nhất của văn bản nhắc tới hoặc do đơn vị ban hành | derive |
| `validFrom` / `validTo` / `validSource` | date / date / string | **Mới, tuỳ chọn** — chỉ điền khi có văn bản căn cứ (thành lập, đổi tên, giải thể) | người điền |

### 10.2 `Person`

`personId`, `fullName`, `aliases[]`. **Bỏ** `position`, `academicTitle` khỏi node (chuyển lên `SIGNED_BY`, §10.3), vì học hàm và chức vụ thay đổi theo thời gian.

### 10.3 Quan hệ

| Relation | Domain → Range | Card. | Thuộc tính | Thay đổi |
| --- | --- | --- | --- | --- |
| `SIGNED_BY` | Document → Person | n→m | `academicTitle`, `position[]` (tại thời điểm ký) | **Thêm thuộc tính** |
| `MENTIONS` | Document → Organization | n→m | `surface` (chuỗi gốc trong văn bản) | **Thêm thuộc tính** |
| `SUCCEEDED_BY` | Organization → Organization | n→m | `type` {doi\_ten, sap\_nhap, chia\_tach}, `date`, `basisDoc`, `status` {nghi\_ngo, xac\_nhan} | **Mới** |
| `PART_OF` | Organization → Organization | n→1 | — | Không đổi; dùng để tách đơn vị cùng tên khác cấp (Đoàn TN ĐHĐN ≠ Đoàn TN Trường) |

Ba trục tách bạch: **danh tính** (gộp về một node + `aliases`), **phân cấp** (`PART_OF`), **thời gian** (`SUCCEEDED_BY` giữa hai node riêng). Đơn vị đổi tên **không** được gộp làm một node.

### 10.4 Truy vấn mới cho phép

* "Văn bản liên quan tới đơn vị X qua mọi lần đổi tên": `MATCH (o {orgId:$id})-[:SUCCEEDED_BY*0..]-(x) MATCH (d:Document)-[:MENTIONS|ISSUED_BY]->(x) …`
* "Tên của đơn vị X vào năm Y": node trong chuỗi `SUCCEEDED_BY` có `observedFrom ≤ Y ≤ observedTo` (hoặc `validFrom/validTo` nếu có).
* "Ông/bà X ký văn bản với chức vụ gì, năm nào": đọc thuộc tính trên `SIGNED_BY`.

### 10.5 Đánh giá (bổ sung §6)

**6.8 Entity resolution** — trên 103 văn bản: người gán tay toàn bộ chuỗi tên (κ trên phần gán chung), so với nhãn Gemini; báo P/R/F1 gộp theo cặp, B-cubed theo cụm, **tỉ lệ gộp nhầm** riêng, và độ chính xác phát hiện `SUCCEEDED_BY`.
