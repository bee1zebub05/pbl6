# Quy ước gộp / tách thực thể (Organization, Person)

Cập nhật: **20/10/2026**. Trạng thái: **bản đề xuất, chờ nhóm và thầy hướng dẫn chốt** (mục 8).
Phạm vi: tập 103 văn bản liên quan đến sinh viên (`data/clean/sinh_vien_103/`).
Thay đổi ontology đi kèm: [rules/Ontology.md](../rules/Ontology.md) §10 (v0.4).

## 1. Vấn đề

Graph gán tay sinh khoá thực thể bằng cách bỏ dấu và viết thường tên gốc
(`slug()` trong `src/legal_knowledge_graph/core/normalize.py`): `orgId = slug(name)`,
`personId = slug(fullName)`. Vì vậy:

- **Tách nhầm (alias):** cùng một thực thể nhưng viết khác nhau thành nhiều node.
  Ví dụ "Trường Đại học Bách khoa" / "Trường Đại học Bách khoa, Đại học Đà Nẵng" là 2 node;
  "Đoàn TNCS Hồ Chí Minh" / "Đoàn Thanh niên Cộng sản Hồ Chí Minh" là 2 node.
- **Gộp nhầm:** cùng tên nhưng là các thực thể khác nhau, lại thành một node.
  Ví dụ "Phòng Đào tạo" của mọi trường dồn vào một node `phong_dao_tao`; alias "Bách khoa"
  trong `aliases_seed.json` trỏ về ĐHBK Đà Nẵng, trong khi kho có cả "Trường ĐHBK Hà Nội".

Quy mô trên 103 văn bản: 9 tên cơ quan ban hành, **266 chuỗi `mentions`** khác nhau
(827 lần xuất hiện), 29 người ký. Người ký tương đối sạch; vấn đề tập trung ở tổ chức.

## 2. Ba trục phải tách bạch

Mỗi cặp tên nghi trùng được xét theo đúng một trục. Không dùng thời gian để giải vấn đề
danh tính, không dùng gộp để giải vấn đề thời gian.

| Trục | Câu hỏi | Biểu diễn trong graph |
|---|---|---|
| **Danh tính** | Hai tên có chỉ *cùng một* thực thể ở *cùng một* thời điểm không? | Một node, tên phụ vào `aliases[]` |
| **Phân cấp** | Đơn vị này thuộc cơ quan nào? | Cạnh `PART_OF` |
| **Thời gian** | Đơn vị này có kế thừa từ đơn vị khác (đổi tên, sáp nhập, chia tách) không? | Hai node riêng + cạnh `SUCCEEDED_BY` |

## 3. Nhãn cho một chuỗi tên (mention)

Mỗi chuỗi tên, **xét trong ngữ cảnh văn bản chứa nó**, nhận đúng một nhãn:

| Nhãn | Nghĩa | Xử lý |
|---|---|---|
| `CUNG` | Là một cách viết khác của một tổ chức đã có | Ánh xạ về `orgId` chuẩn |
| `MOI` | Tổ chức cụ thể chưa có trong danh mục | Tạo `orgId` chuẩn mới |
| `CHUC_DANH` | Là chức danh, không phải tổ chức ("Bộ trưởng Bộ Giáo dục và Đào tạo") | Ánh xạ về tổ chức chứa chức danh đó (Bộ GD&ĐT); không tạo node riêng |
| `CHUNG` | Tên một *loại* đơn vị, không chỉ đơn vị cụ thể nào ("Hội sinh viên" trong Thông tư của Bộ, "Ban chức năng", "Khoa") | Không tạo cạnh `MENTIONS` tới tổ chức cụ thể (xem câu hỏi Q3) |
| `GHEP` | Một chuỗi chứa nhiều tổ chức ("Đoàn thanh niên, Hội sinh viên") | Tách thành từng chuỗi rồi gán nhãn lại |
| `LOAI` | Không phải tổ chức, hoặc rác do OCR / trích xuất | Bỏ |

Với một cặp tên đã cùng là tổ chức cụ thể, quan hệ giữa hai tên nhận một trong:
`TRUNG` (cùng thực thể), `KHAC` (khác thực thể), `KE_THUA` (đổi tên / sáp nhập / tách,
xem mục 5), `CHUA_RO`.

## 4. Quy tắc danh tính (khi nào là `TRUNG`)

**R1. Khác biệt hình thức thì gộp.** Hoa/thường, dấu nối (`-`, `–`), `&` / `và`,
viết tắt chuẩn, lỗi OCR một ký tự.

| Gộp | Lý do |
|---|---|
| "Phòng Công tác Sinh viên" = "Phòng Công tác sinh viên" = "Phòng Công tác SV" | Hoa/thường, viết tắt |
| "Phòng Tổ chức - Hành chính" = "Phòng Tổ chức – Hành chính" = "Phòng Tổ chức Hành chính" | Dấu nối |
| "Đoàn TNCS Hồ Chí Minh" = "Đoàn Thanh niên Cộng sản Hồ Chí Minh" | Viết tắt chuẩn |
| "Phan hiệu ĐHĐN tại Kon Tum" = "Phân hiệu ĐHĐN tại Kon Tum" | Lỗi OCR |

**R2. Hậu tố chỉ cơ quan chủ quản thì gộp, nếu đúng là cơ quan chủ quản thật.**
"Trường Đại học Bách khoa" = "Trường Đại học Bách khoa, Đại học Đà Nẵng" =
"Trường Đại học Bách khoa - Đại học Đà Nẵng".

**R3. Tên chung chung được hiểu theo cơ quan ban hành văn bản chứa nó.** "Phòng Đào tạo"
trong một Quyết định của ĐHBK là Phòng Đào tạo *của ĐHBK*. Khoá ánh xạ vì vậy là cặp
**(chuỗi tên, cơ quan ban hành)**, không phải chuỗi tên đơn thuần.
Nếu văn bản là của cấp Bộ / Chính phủ / Quốc hội thì tên chung chung là `CHUNG` (mục 3).

**R4. Cùng tên nhưng khác cấp thì tách.** "Đoàn Thanh niên ĐHĐN" ≠ Đoàn Thanh niên của
Trường ĐHBK; "Hội Sinh viên ĐHĐN" ≠ Hội Sinh viên Trường. Hai node, nối bằng `PART_OF`
nếu có quan hệ trực thuộc.

**R5. Cùng tên nhưng khác đơn vị chủ quản thì tách.** "Trường ĐHBK Hà Nội",
"Trường ĐHBK (ĐHQG TP Hồ Chí Minh)" ≠ ĐHBK Đà Nẵng. Alias "Bách khoa" / "ĐHBK" chỉ được
trỏ về ĐHBK Đà Nẵng khi không có tên địa danh khác đi kèm.

**R6. Chức danh không phải tổ chức.** "Bộ trưởng Bộ Y tế" nhận nhãn `CHUC_DANH`, ánh xạ về
"Bộ Y tế". Riêng cơ quan ban hành dạng "Trường Đại học Bách khoa, Hội đồng trường" là
**Hội đồng trường** (cơ quan ban hành thật), không phải Trường.

**R7. Nghi ngờ thì không gộp.** Tách nhầm chỉ làm câu trả lời thiếu; gộp nhầm làm câu
trả lời sai. Cặp nào chưa chắc thì gán `CHUA_RO` và giữ hai node.

## 5. Quy tắc thời gian: đổi tên, sáp nhập, chia tách

**T1. Kế thừa thì tách node, nối bằng cạnh.** Đơn vị trước và sau khi đổi tên là hai node.
Văn bản ban hành trước ngày đổi tên thuộc node cũ, sau thuộc node mới. Gộp lại sẽ làm sai
lịch sử; chọn một tên thì mất văn bản của tên kia.

```
(cũ:Organization)-[:SUCCEEDED_BY {type, date, basisDoc, status}]->(mới:Organization)
```

| Thuộc tính | Giá trị |
|---|---|
| `type` | `doi_ten` (1→1), `sap_nhap` (n→1, mỗi đơn vị cũ một cạnh), `chia_tach` (1→n) |
| `date` | Ngày có hiệu lực của việc thay đổi, nếu biết |
| `basisDoc` | Số hiệu văn bản quyết định thay đổi, nếu biết |
| `status` | `nghi_ngo` (chỉ suy từ dữ liệu) hoặc `xac_nhan` (có văn bản căn cứ hoặc người xác nhận) |

**T2. Mô hình chỉ được đề xuất, không được tạo cạnh `xac_nhan`.** Gemini đánh dấu cặp
"có thể kế thừa"; người kiểm tra và điền `basisDoc`. Cạnh `nghi_ngo` vẫn được nạp nhưng
chatbot phải nói rõ là chưa xác nhận.

**T3. Phân biệt khoảng quan sát và khoảng hiệu lực.** Văn bản hầu như không ghi
"đơn vị X tồn tại từ năm A đến năm B"; thứ có được là ngày ban hành của các văn bản nhắc tới X.

| Thuộc tính | Nguồn | Luôn có? |
|---|---|---|
| `observedFrom`, `observedTo` | Ngày ban hành sớm nhất / muộn nhất trong các văn bản nhắc tới hoặc do đơn vị ban hành. Tính tự động | Có |
| `validFrom`, `validTo` | Chỉ điền khi có văn bản căn cứ (quyết định thành lập, đổi tên, giải thể); kèm `validSource` | Không |

Không được dùng `observedFrom` như ngày thành lập: văn bản cũ nhất trong kho là năm 2016
không có nghĩa đơn vị được lập năm 2016.

**Các trường hợp nghi kế thừa trong 103 văn bản** (năm = năm ban hành của văn bản nhắc tới;
tất cả đều `nghi_ngo`, chưa có văn bản căn cứ):

| Tên cũ (năm thấy) | Tên mới (năm thấy) | Cấp | Loại đoán |
|---|---|---|---|
| Phòng Khoa học Công nghệ và Hợp tác Quốc tế (2018–2021) | Phòng Khoa học Công nghệ và Đối ngoại (2026) | ĐHBK | `doi_ten` |
| Ban Đào tạo (2020–2023) | Ban Đào tạo và Đảm bảo chất lượng giáo dục (2024–2026) | ĐHĐN | `sap_nhap` hoặc `doi_ten` |
| Ban Công tác học sinh, sinh viên (2018–2021) | Ban Công tác sinh viên, Quan hệ doanh nghiệp và Truyền thông (2025) | ĐHĐN | `sap_nhap` hoặc `doi_ten` |
| Vụ Công tác học sinh, sinh viên (2011–2016) | Vụ Giáo dục Chính trị và Công tác học sinh, sinh viên (2022) | Bộ GD&ĐT | `sap_nhap` |
| Ban Tuyên giáo Trung ương (2009–2023) | Ban Tuyên giáo và Dân vận Trung ương (2026) | Trung ương | `sap_nhap` |

Ví dụ truy vấn được nhờ cạnh này: "mọi văn bản liên quan Phòng KHCN qua các thời kỳ":

```cypher
MATCH (o:Organization {orgId: $orgId})-[:SUCCEEDED_BY*0..]-(x:Organization)
MATCH (d:Document)-[:MENTIONS|ISSUED_BY]->(x)
RETURN x.name, d.documentNumber, d.issueDate ORDER BY d.issueDate
```

## 6. Người ký

**P1. Họ tên là danh tính; học hàm, học vị, chức vụ là thuộc tính tại thời điểm ký.**
`academicTitle` và `position` chuyển từ node `Person` lên cạnh `SIGNED_BY`. Node `Person`
chỉ giữ `fullName` và `aliases[]`. Ví dụ "Lê Kim Hùng" ký với học hàm PGS.TS ở một văn bản và
GS.TS ở văn bản khác; hiện code giữ giá trị gặp đầu tiên nên một trong hai bị sai.

**P2. Bỏ học hàm, học vị khỏi `fullName` trước khi so sánh.** "TS Trương Ngọc Châu" →
"Trương Ngọc Châu", học vị đưa sang `SIGNED_BY.academicTitle`.

**P3. Tên viết tắt ("TN Châu") chỉ gộp khi có bằng chứng ngữ cảnh:** cùng đơn vị, cùng chức
vụ, cùng giai đoạn và chỉ có đúng một ứng viên khớp. Thiếu một điều kiện thì `CHUA_RO` (R7).

**P4. Lỗi OCR một ký tự được gộp** ("Phạm Ngọc Thưởng" / "Phạm Ngọc Thường") theo quy tắc
sẵn có của `tools/kiem_tra/chuan_ten_ky.py`. Tên đúng lấy theo bản đối chiếu tay
(`data/clean/README.md`).

**P5. Trùng họ tên nhưng khác người** (cùng tên, khác đơn vị, khác thời kỳ) thì tách.

## 7. Quy trình

1. **Gom tên.** Lấy mọi chuỗi tên từ `organization`, `signers`, `mentions` của 103 JSON. Mỗi
   chuỗi kèm: cơ quan ban hành, năm ban hành, số hiệu văn bản, câu ngữ cảnh (tìm lại trong
   `.txt`, vì `mentions` không lưu vị trí).
2. **Chia cụm.** Theo cấp: Trung ương, Bộ (Vụ, Cục), ĐHĐN (Ban), Trường (Phòng, Khoa, Trung tâm),
   đoàn thể. Trong mỗi cụm, sinh cặp ứng viên bằng độ tương đồng chuỗi và cosine embedding.
   Độ tương đồng chỉ dùng để **lọc ứng viên**, không dùng để quyết định ("Khoa Điện" và
   "Khoa Điện tử – Viễn thông" rất giống nhau nhưng khác nhau).
3. **Gemini gán nhãn** theo mục 3–6, trả JSON: nhãn, `orgId` đích, lý do, độ tin cậy. Prompt chứa
   nguyên văn các quy tắc R1–R7, T1–T3, P1–P5.
4. **Người gán tay toàn bộ** (không lấy mẫu; khoảng 300 chuỗi, chia 4 người), độc lập với kết quả
   Gemini. Hai người gán chung khoảng 50 chuỗi để tính Cohen's κ.
5. **Đánh giá.** So nhãn Gemini với nhãn người: precision / recall của việc gộp theo cặp và
   B-cubed theo cụm; báo riêng **tỉ lệ gộp nhầm** và độ chính xác phát hiện kế thừa.
6. **Xuất bảng ánh xạ** `src/legal_knowledge_graph/reference/entity_canonical.json` (từ nhãn người,
   không từ nhãn Gemini). Bước nạp graph tra bảng này trước khi rơi về `slug()`.

Thứ tự: nhóm đang gán lại 103 văn bản bằng `tools/labeler`, và việc này làm thay đổi chuỗi tên.
Bước 1–3 có thể chạy thử trên bản nháp `json_v2` để chỉnh prompt; bước 4–6 chạy trên kết quả
gán lại cuối cùng.

## 8. Câu hỏi cần chốt

| # | Câu hỏi | Đề xuất |
|---|---|---|
| Q1 | Đơn vị đổi tên: tách hay gộp? | **Đã chốt (nhóm, 20/10):** tách, nối bằng `SUCCEEDED_BY` (T1) |
| Q2 | Chuỗi chức danh ("Bộ trưởng Bộ X") | Ánh xạ về tổ chức X (R6) |
| Q3 | Tên loại đơn vị trong văn bản cấp Bộ ("Hội sinh viên", "Phòng Đào tạo" trong Thông tư) | Nhãn `CHUNG`, không nối tới tổ chức cụ thể. Phương án khác: nối tới `TargetGroup` |
| Q4 | Cạnh `SUCCEEDED_BY` chưa có văn bản căn cứ có nạp vào graph không? | Có, với `status: nghi_ngo`; chatbot nói rõ chưa xác nhận |
| Q5 | Có cần node sự kiện `OrgChange` (để nối tới văn bản quyết định đổi tên như một `Document`) không? | Chưa; dùng thuộc tính `basisDoc`. Nâng lên node khi văn bản quyết định có trong kho |
| Q6 | Phạm vi: chỉ 103 văn bản hay cả kho 454? | 103 văn bản theo hướng dẫn của thầy; bảng ánh xạ dùng lại được khi mở rộng |
