# Ví dụ câu hỏi & Cypher

20 câu hỏi mẫu theo góc nhìn người dùng thật (giảng viên, sinh viên, phụ
huynh) — không phải câu hỏi kỹ thuật. Mỗi câu gồm Cypher và kết quả **thật**,
chạy trực tiếp trên graph hiện có (418 văn bản thật, data
`data/clean/json/v2/`). Không có bước nào bịa số liệu.

Muốn chạy lại: mở Neo4j Browser (`http://localhost:7475`) rồi dán Cypher,
hoặc `python run.py lkg ask --template TPL_XXX --param k=v` với template
tương ứng (ghi ở cuối mỗi câu).

**2 phần khác nhau ở Neo4j Browser sẽ hiển thị:**
- **Phần 1 (câu 1-10)**: `RETURN` property (chuỗi, số) — Browser chỉ hiện
  **Table**. Phù hợp khi cần con số/danh sách rõ ràng (đếm, xếp hạng, phân
  bố) — những câu này vốn không có "hình graph" để vẽ.
- **Phần 2 (câu 11-20)**: `RETURN` thẳng node/relationship/path — Browser
  tự vẽ **Graph**, trực quan hơn nhiều khi trình bày cho người không rành
  kỹ thuật.

ĐẶC BIỆT: CALL db.schema.visualization()

---

# Phần 1 — Trả về Table

## 1. Giảng viên — "Trường Đại học Bách khoa còn văn bản nào hiệu lực?"

```cypher
MATCH (d:Document)-[:ISSUED_BY]->(:Organization {orgId: 'truong_dai_hoc_bach_khoa'})
WHERE d.status = 'CON_HIEU_LUC'
RETURN d.documentNumber AS documentNumber, d.title AS title
ORDER BY d.issueDate DESC
LIMIT 5
```

**Kết quả** (62 văn bản, 5 mới nhất):

| documentNumber | title |
|---|---|
| 107/QĐ-ĐHBK | Sửa đổi, bổ sung Quy định Quản lý hoạt động khoa học và công nghệ |
| 5247/QĐ-ĐHBK | Ban hành Chiến lược phát triển Trường ĐHBK giai đoạn 2025-2030 |
| 4532/QĐ-ĐHBK | Ban hành chính sách miễn học phí đào tạo thạc sĩ từ khoá tuyển sinh 50 |
| 3868/QĐ-ĐHBK | Quy định hồ sơ, thủ tục mua sắm, sửa chữa thường xuyên dưới 500 triệu đồng |
| 3707/QĐ-ĐHBK | Sửa đổi, bổ sung "Quy định về liêm chính học thuật" |

*Template: `TPL_DOCS_BY_ORG_STATUS`*

---

## 2. Sinh viên — "Văn bản nào áp dụng cho người học (sinh viên)?"

```cypher
MATCH (d:Document)-[:APPLIES_TO]->(:TargetGroup {targetGroupId: 'nguoi_hoc'})
RETURN d.documentNumber AS documentNumber, d.title AS title
LIMIT 5
```

**Kết quả** (51 văn bản, 5 đầu):

| documentNumber | title |
|---|---|
| 11/2020/TT-BGDĐT | Hướng dẫn thực hiện dân chủ trong hoạt động của cơ sở giáo dục công lập |
| 10/2016/TT-BGDĐT | Ban hành Quy chế công tác sinh viên đối với đào tạo đại học hệ chính quy |
| 2347/QĐ-ĐHBK | Quy định tổ chức hoạt động trang thông tin điện tử, thư điện tử |
| 1899/QĐ-ĐHĐN | Quy định về công tác quản lý hoạt động hợp tác quốc tế |
| 2352/QĐ-ĐHBK | Quy chế hoạt động truyền thông của Trường ĐHBK |

*Template: `TPL_DOCS_BY_TARGET_GROUP`*

---

## 3. Phụ huynh — "Trường có văn bản nào về tuyển sinh không?"

```cypher
MATCH (d:Document)-[:HAS_TOPIC]->(:Topic {name: 'Tuyển sinh'})
RETURN d.documentNumber AS documentNumber, d.title AS title
LIMIT 5
```

**Kết quả** (16 văn bản, 5 đầu):

| documentNumber | title |
|---|---|
| 18/2017/QĐ-TTg | Quy định về liên thông giữa trung cấp, cao đẳng với đại học |
| 4757/QĐ-ĐHĐN | Sửa đổi, bổ sung Quy chế tuyển sinh đại học vừa làm vừa học |
| 2414/QĐ-ĐHĐN | Quy chế tuyển sinh đào tạo trình độ đại học hình thức thường xuyên |
| 03/2022/TT-BGDĐT | Quy định xác định chỉ tiêu tuyển sinh đại học, thạc sĩ, tiến sĩ |
| 07/2020/TT-BGDĐT | Sửa đổi, bổ sung quy định về chỉ tiêu tuyển sinh |

*Template: `TPL_DOCS_BY_TOPIC`*

---

## 4. Phụ huynh — "Học phí năm nay quy định ở văn bản nào?"

```cypher
CALL db.index.fulltext.queryNodes('doc_text', '"học phí"') YIELD node, score
RETURN node.documentNumber AS documentNumber, node.title AS title, score
ORDER BY score DESC
LIMIT 5
```

**Kết quả** (tìm đúng theo nội dung, không chỉ tiêu đề):

| documentNumber | title |
|---|---|
| 81/2021/NĐ-CP | Cơ chế thu, quản lý học phí; chính sách miễn, giảm học phí |
| 3443/ĐHĐN-KHTC | Mức thu học phí năm học 2024-2025 |
| 09/2016/TTLT-BGDĐT-BTC-BLĐTBXH | Hướng dẫn thực hiện quy định về học phí 2015-2021 |
| 97/2023/NĐ-CP | Sửa đổi, bổ sung Nghị định 81/2021/NĐ-CP về học phí |
| 4532/QĐ-ĐHBK | Chính sách miễn học phí đào tạo thạc sĩ từ khoá tuyển sinh 50 |

*Template: `TPL_DOCUMENT_FULLTEXT_SEARCH`*

---

## 5. Giảng viên — "Những Quy chế nào đang còn hiệu lực?"

```cypher
MATCH (:Document)-[:PROMULGATES]->(c:NormativeContent)
WHERE c.contentType = 'Quy chế' AND c.status = 'CON_HIEU_LUC'
RETURN c.title AS title
LIMIT 5
```

**Kết quả** (57 Quy chế còn hiệu lực, 5 đầu):

| title |
|---|
| Quy chế công tác sinh viên đối với đào tạo đại học hệ chính quy |
| Quy chế đánh giá kết quả rèn luyện của người học trình độ đại học hệ chính quy |
| Quy chế Công tác sinh viên Đại học Đà Nẵng hệ chính quy |
| Quy chế Công tác sinh viên Trường ĐHBK hệ chính quy |
| Quy chế ngoại trú của học sinh, sinh viên hệ chính quy |

*Template: `TPL_NORMATIVE_CONTENT_BY_TYPE`*

---

## 6. Sinh viên — "Quy chế công tác sinh viên cũ (42/2007/QĐ-BGDĐT) đã bị thay bằng văn bản nào?"

```cypher
MATCH (new:Document)-[:REPLACES]->(:Document {normalizedNumber: '42/2007/QD-BGDDT'})
RETURN new.documentNumber AS van_ban_thay_the, new.title AS title
```

**Kết quả**:

| van_ban_thay_the | title |
|---|---|
| 10/2016/TT-BGDĐT | Ban hành Quy chế công tác sinh viên đối với đào tạo đại học hệ chính quy |

*Template: `TPL_REPLACED_BY`*

---

## 7. Giảng viên — "Văn bản 3868/QĐ-ĐHBK đã trải qua bao nhiêu lần sửa đổi/thay thế?"

```cypher
MATCH path = (d:Document {normalizedNumber: '3868/QD-DHBK'})-[:AMENDS|REPLACES*1..5]->(b:Document)
RETURN [n IN nodes(path) | n.documentNumber] AS chuoi, length(path) AS so_buoc
ORDER BY so_buoc DESC
LIMIT 1
```

**Kết quả** — chuỗi hiệu lực dài nhất từ văn bản này, 3 bước:

```
3868/QĐ-ĐHBK → 760/QĐ-ĐHBK → 2652/QĐ-ĐHBK → 2929/QĐ-ĐHBK
```

Đây là loại truy vấn thể hiện rõ nhất giá trị của việc gán tay — truy vết
chuỗi văn bản thay thế nhau qua nhiều đời, việc pipeline tự động (regex)
làm không đáng tin.

*Template: `TPL_AMEND_REPLACE_CHAIN`*

---

## 8. Phụ huynh — "Cơ quan nào ban hành nhiều văn bản nhất?"

```cypher
MATCH (d:Document)-[:ISSUED_BY]->(o:Organization)
RETURN o.name AS organization, count(d) AS total
ORDER BY total DESC
LIMIT 5
```

**Kết quả**:

| organization | total |
|---|---|
| Bộ Giáo dục và Đào tạo | 115 |
| Đại học Đà Nẵng | 85 |
| Trường Đại học Bách khoa | 67 |
| Chính phủ | 40 |
| Quốc hội | 35 |

*Template: `TPL_TOP_ORGS_BY_DOC_COUNT`*

---

## 9. Giảng viên — "Bao nhiêu văn bản còn hiệu lực, bao nhiêu hết hiệu lực?"

```cypher
MATCH (d:Document) WHERE d.isStub = false
RETURN d.status AS status, count(d) AS total
ORDER BY total DESC
```

**Kết quả**:

| status | total |
|---|---|
| CON_HIEU_LUC | 381 |
| (chưa gán) | 21 |
| HET_HIEU_LUC | 1 |

*Template: `TPL_DOC_DISTRIBUTION_BY_STATUS`*

---

## 10. Giảng viên — "Những văn bản gốc thẩm quyền cao nào liên quan tới Đại học Đà Nẵng?"

```cypher
CALL db.index.fulltext.queryNodes('doc_text', '"Đại học Đà Nẵng"') YIELD node, score
WITH node, score ORDER BY score DESC LIMIT 5
MATCH (node)-[:BASED_ON|REFERENCES*0..2]->(expanded:Document)
RETURN DISTINCT expanded.documentNumber AS documentNumber
LIMIT 5
```

**Kết quả** — tìm theo nội dung trước, rồi mở rộng theo quan hệ "căn cứ
vào" để lần ra văn bản gốc (phần lớn là Nghị định/Thông tư cấp trên, hiện
là Document stub vì chưa được gán tay đầy đủ):

```
86/2015/NĐ-CP, 55/2015/TTLT-BTC-BKHCN, 191/2013/NĐ-CP,
1219/QĐ-ĐHĐN, 58/2016/TT-BTC
```

Câu này kết hợp cả 2 khả năng: tìm theo nội dung (full-text) và truy vết
quan hệ (multi-hop) trong cùng một câu hỏi.

*Template: `TPL_HYBRID_FULLTEXT_EXPAND`*

---

# Phần 2 — Trả về Graph

Cùng loại câu hỏi như Phần 1, nhưng đổi `RETURN` sang node/relationship/
path thay vì property — dán vào Neo4j Browser sẽ tự vẽ thành đồ thị thay
vì bảng.

## 11. Giảng viên — "Trường ĐHBK còn văn bản nào hiệu lực?" (dạng graph)

```cypher
MATCH (d:Document)-[r:ISSUED_BY]->(o:Organization {orgId: 'truong_dai_hoc_bach_khoa'})
WHERE d.status = 'CON_HIEU_LUC'
RETURN d, r, o
ORDER BY d.issueDate DESC
LIMIT 5
```

**Graph hiện ra**: 1 node `Organization` (Trường ĐHBK) ở giữa, 5 node
`Document` toả ra xung quanh, mỗi node nối bằng 1 cạnh `ISSUED_BY` — hình
"ngôi sao" (5 văn bản mới nhất trong 62 văn bản còn hiệu lực của ĐHBK):
107/QĐ-ĐHBK, 5247/QĐ-ĐHBK, 4532/QĐ-ĐHBK, 3868/QĐ-ĐHBK, 3707/QĐ-ĐHBK.

---

## 12. Sinh viên — "Văn bản nào áp dụng cho người học?" (dạng graph)

```cypher
MATCH (d:Document)-[r:APPLIES_TO]->(tg:TargetGroup {targetGroupId: 'nguoi_hoc'})
RETURN d, r, tg
LIMIT 5
```

**Graph hiện ra**: 1 node `TargetGroup` ("Người học") ở giữa, 5 node
`Document` nối vào bằng cạnh `APPLIES_TO` — cùng hình "ngôi sao", nhưng
tâm là một nhóm đối tượng thay vì một tổ chức.

---

## 13. Phụ huynh — "Văn bản nào về tuyển sinh?" (dạng graph)

```cypher
MATCH (d:Document)-[r:HAS_TOPIC]->(t:Topic {name: 'Tuyển sinh'})
RETURN d, r, t
LIMIT 5
```

**Graph hiện ra**: node `Topic` "Tuyển sinh" ở giữa, 5 `Document` nối
bằng `HAS_TOPIC` — cùng dạng ngôi sao, đổi trục sang lĩnh vực.

---

## 14. Giảng viên — "Quy chế nào còn hiệu lực, do văn bản nào ban hành?" (dạng graph)

```cypher
MATCH (d:Document)-[r:PROMULGATES]->(c:NormativeContent)
WHERE c.contentType = 'Quy chế' AND c.status = 'CON_HIEU_LUC'
RETURN d, r, c
LIMIT 5
```

**Graph hiện ra**: 5 cặp `Document`→`NormativeContent` tách rời nhau
(mỗi Quyết định ban hành đúng 1 Quy chế kèm theo) — khác hình "ngôi sao"
ở trên, đây là nhiều cặp độc lập, cho thấy quan hệ 1-1 giữa văn bản và
nội dung quy phạm nó ban hành.

---

## 15. Sinh viên — "1 văn bản có bao nhiêu Điều, nội dung ra sao?" (dạng graph)

```cypher
MATCH (d:Document {normalizedNumber: '1559/QD-BGDDT'})-[r:HAS_ARTICLE]->(a:Article)
RETURN d, r, a
```

**Graph hiện ra**: 1 node `Document` (1559/QĐ-BGĐT) ở giữa, 7 node
`Article` toả ra — bấm vào từng node `Article` xem được toàn văn Điều đó.
Ngôi sao 7 cánh, trực quan hơn nhiều so với đọc file `.txt` tuần tự.

---

## 16. Phụ huynh — "Văn bản này nhắc tới những đơn vị nào?" (dạng graph)

```cypher
MATCH (d:Document {normalizedNumber: '4757/QD-DHDN'})-[r:MENTIONS]->(o:Organization)
RETURN d, r, o
```

**Graph hiện ra**: 1 `Document` (4757/QĐ-ĐHĐN — sửa đổi Quy chế tuyển
sinh) nối tới 6 `Organization` được nhắc tới trong "Trách nhiệm thi
hành" (Bộ GD&ĐT, Trường ĐHBK, và 4 đơn vị khác) — cho thấy 1 văn bản
"lan toả" tới những đơn vị nào phải thực hiện.

---

## 17. Sinh viên — "Quy chế sinh viên cũ đã bị thay bằng văn bản nào?" (dạng graph)

```cypher
MATCH path = (new:Document)-[:REPLACES]->(:Document {normalizedNumber: '42/2007/QD-BGDDT'})
RETURN path
```

**Graph hiện ra**: 2 node `Document` nối bằng 1 cạnh `REPLACES` —
10/2016/TT-BGDĐT → 42/2007/QĐ-BGDĐT (node thứ 2 là stub, viền nhạt hơn
vì chưa được gán tay đầy đủ, chỉ biết số hiệu).

---

## 18. Giảng viên — "Văn bản 3868/QĐ-ĐHBK đã qua bao nhiêu đời sửa đổi?" (dạng graph)

```cypher
MATCH path = (d:Document {normalizedNumber: '3868/QD-DHBK'})-[:AMENDS|REPLACES*1..5]->(b:Document)
RETURN path
ORDER BY length(path) DESC
LIMIT 1
```

**Graph hiện ra**: chuỗi 4 node `Document` nối tiếp nhau bằng 3 cạnh
`REPLACES` — 3868 → 760 → 2652 → 2929/QĐ-ĐHBK (node cuối là stub). Đây là
câu trực quan nhất trong cả 20 câu: nhìn 1 đường thẳng nối 4 văn bản dễ
hiểu "qua bao nhiêu đời" hơn hẳn đọc mảng số hiệu.

---

## 19. Phụ huynh — "Cơ quan nào ban hành nhiều văn bản, những văn bản đó là gì?" (dạng graph)

```cypher
MATCH (d:Document)-[r:ISSUED_BY]->(o:Organization {orgId: 'bo_giao_duc_va_dao_tao'})
RETURN d, r, o
LIMIT 8
```

**Graph hiện ra**: node `Organization` (Bộ Giáo dục và Đào tạo) ở giữa,
8 node `Document` toả ra — cùng dạng ngôi sao như câu 11, nhưng đây là cơ
quan đứng đầu bảng xếp hạng ở câu 8 (115 văn bản), nhìn trực quan vì sao
số lượng lớn nhất.

---

## 20. Giảng viên — "Điều gì liên quan tới Đại học Đà Nẵng, kể cả văn bản gốc cấp trên?" (dạng graph)

```cypher
CALL db.index.fulltext.queryNodes('doc_text', '"Đại học Đà Nẵng"') YIELD node, score
WITH node, score ORDER BY score DESC LIMIT 3
MATCH path = (node)-[:BASED_ON|REFERENCES*0..2]->(expanded:Document)
RETURN path
LIMIT 5
```

**Graph hiện ra**: vài `Document` gốc (tìm được nhờ full-text) toả nhánh
`BASED_ON`/`REFERENCES` tới các Nghị định/Thông tư cấp trên (phần lớn là
stub) — hình cây nhiều tầng, câu phức tạp nhất trong 20 câu, phù hợp làm
điểm kết khi trình bày.
