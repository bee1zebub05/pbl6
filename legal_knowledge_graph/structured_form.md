# Cấu trúc JSON chuẩn cho gán tay (legal_knowledge_graph)

Tài liệu này liệt kê **đầy đủ field, kiểu dữ liệu, bắt buộc/tuỳ chọn và ý
nghĩa** của một file JSON gán tay. Nguồn sự thật duy nhất về format vẫn là
[`schema/document.schema.json`](schema/document.schema.json) (JSON Schema
draft 2020-12, có `additionalProperties: false` ở mọi object — gõ sai tên
field sẽ bị `validate.py` báo lỗi ngay); file này là bản diễn giải dễ đọc
của schema đó, kèm ví dụ đầy đủ.

**Quy ước đọc bảng:** cột *Bắt buộc* = `✓` nghĩa là field phải có mặt trong
JSON (có thể là `null` nếu type cho phép); ô trống nghĩa là tuỳ chọn, có thể
bỏ hẳn field đó.

---

## 0. Một file JSON = một văn bản

Cấu trúc gốc (top-level) của mỗi file:

| Field | Type | Bắt buộc | Ý nghĩa |
|---|---|:-:|---|
| `schemaVersion` | `"1.0"` (hằng số) | ✓ | Phiên bản schema, luôn ghi đúng `"1.0"`. |
| `sourceFile` | `string \| null` | | Tên/đường dẫn file `.txt` gốc trong `data/clean/text_final/`, để truy vết. |
| `mappedBy` | `string \| null` | | Tên hoặc email người gán, ghi chú tự do. |
| `note` | `string \| null` | | Ghi chú tự do (chỗ không chắc, chỗ đã sửa lỗi OCR...). **Không nạp vào Neo4j**, chỉ để người đọc sau này hiểu quyết định gán. |
| `document` | object | ✓ | Thông tin văn bản — xem [§1](#1-document-bắt-buộc). |
| `organization` | object | ✓ | Cơ quan ban hành — xem [§2](#2-organization-bắt-buộc). |
| `signers` | array of object | | Người ký — xem [§3](#3-signers-mảng). |
| `citations` | array of object | | Văn bản được viện dẫn — xem [§4](#4-citations-mảng). |
| `mentions` | array of `string` | | Tên tổ chức được **nhắc tới** trong thân văn bản (không phải cơ quan ban hành/ký). Không cần đếm số lần xuất hiện. |
| `normativeContents` | array of object | | Nội dung kèm theo (Quy định/Quy chế/...) — xem [§5](#5-normativecontents-mảng). |
| `articles` | array of object | | Điều nằm **trực tiếp** dưới văn bản — xem [§6](#6-article-dùng-chung-cho-articles-và-normativecontentsarticles). |

---

## 1. `document` (bắt buộc)

| Field | Type | Bắt buộc | Ý nghĩa |
|---|---|:-:|---|
| `documentNumber` | `string` | ✓ | Số hiệu chép nguyên văn như in trên văn bản, VD `"2852/QĐ-ĐHĐN"`. Văn bản không có số hiệu thật thì tự đặt nhãn dạng `"VB-<mô tả ngắn>"` và bắt buộc điền `idOverride` trùng giá trị này. |
| `title` | `string` | ✓ | Tiêu đề đầy đủ của văn bản. |
| `documentType` | `enum` | ✓ | Một trong 14 giá trị: `Luật`, `Pháp lệnh`, `Nghị định`, `Thông tư`, `Thông tư liên tịch`, `Quyết định`, `Nghị quyết`, `Chỉ thị`, `Hướng dẫn`, `Kế hoạch`, `Văn bản hợp nhất`, `Lệnh`, `Công văn`, `Hiến pháp`. |
| `status` | `enum \| null` | | `CON_HIEU_LUC` / `HET_HIEU_LUC` / `CHUA_HIEU_LUC` / `null` (không rõ). |
| `issueDate` | `string \| null` (`dd/mm/yyyy`) | | Ngày ban hành, đúng như trên văn bản — **không phải ISO**, loader tự đổi. |
| `effectiveDate` | `string \| null` (`dd/mm/yyyy`) | | Ngày có hiệu lực. |
| `expiryDate` | `string \| null` (`dd/mm/yyyy`) | | Ngày hết hiệu lực (nếu có). |
| `fileUrl` | `string \| null` (URI) | | Đường dẫn tới file gốc, nếu có sẵn URL công khai. |
| `topics` | array of `string` | | Tên lĩnh vực — **phải khớp** (không phân biệt hoa/thường, có/không dấu) một mục trong [`reference/topics_seed.json`](reference/topics_seed.json) (18 lĩnh vực, xem [§7](#7-danh-mục-tham-chiếu)). Kiểm tra ở `validate.py`, không phải ở JSON Schema. |
| `summary` | `string \| null` (≤600 ký tự) | | 1-3 câu tóm tắt do người gán viết. **Không** chép lại toàn văn — toàn văn thuộc về `articles[].text`. |
| `idOverride` | `string \| null` | | Ép `normalizedNumber` về đúng giá trị này thay vì để loader tự suy. Chỉ dùng khi cần (đụng hàng, văn bản không có số hiệu chuẩn). |

## 2. `organization` (bắt buộc)

Cơ quan **ban hành** văn bản (đơn vị đứng tên ký, không phải nơi soạn thảo).

| Field | Type | Bắt buộc | Ý nghĩa |
|---|---|:-:|---|
| `name` | `string` | ✓ | Tên tổ chức chép nguyên văn. Nếu trùng một tên trong [`reference/organizations_seed.json`](reference/organizations_seed.json), loader tự khớp — để `orgType`/`parentOrg` là `null`. |
| `orgType` | `enum \| null` | | **Bắt buộc điền** nếu `name` không có trong seed. Một trong: `quoc_hoi`, `chinh_phu`, `thu_tuong`, `bo_nganh`, `dai_hoc_vung`, `truong_thanh_vien`, `don_vi_truc_thuoc`, `phong_ban`. |
| `parentOrg` | `string \| null` | | Tên cơ quan cấp trên trực tiếp (raw), dùng dựng quan hệ `PART_OF`. Bỏ trống nếu là cơ quan gốc hoặc đã có sẵn trong seed (loader tự lấy `parentOrg` từ seed). |
| `idOverride` | `string \| null` | | Ép `orgId` về giá trị chỉ định. |

## 3. `signers[]` (mảng)

Mỗi phần tử là một người ký văn bản.

| Field | Type | Bắt buộc | Ý nghĩa |
|---|---|:-:|---|
| `fullName` | `string` | ✓ | Họ tên đầy đủ. |
| `academicTitle` | `string \| null` | | Học hàm/học vị, VD `"PGS.TS"`. |
| `position` | array of `string` (≥1 phần tử) | ✓ | Chức danh ghi trên chữ ký của **văn bản này**. Có thể có nhiều hơn 1 nếu văn bản ghi kiêm nhiệm (VD `["Bí thư Đảng uỷ", "Hiệu trưởng"]`). |
| `idOverride` | `string \| null` | | Ép `personId` về giá trị chỉ định — dùng khi hai người trùng tên. |

## 4. `citations[]` (mảng)

Mỗi phần tử là **một** văn bản được viện dẫn (mỗi câu "Căn cứ...",
"thay thế...", "sửa đổi, bổ sung...", "bãi bỏ..." → một entry).

| Field | Type | Bắt buộc | Ý nghĩa |
|---|---|:-:|---|
| `targetDocumentNumber` | `string` | ✓ | Số hiệu văn bản được trích dẫn, chép nguyên văn. Không cần văn bản đích đã được gán thành file JSON hay chưa — nếu chưa có, loader tự tạo một Document "stub" (`isStub: true`). |
| `relationType` | `enum` | ✓ | Một trong 5 giá trị — xem bảng quy tắc bên dưới. |
| `targetArticle` | `string \| null` (mẫu `"Điều N"`) | | Chỉ dùng cho `AMENDS` khi biết rõ Điều nào của văn bản đích bị sửa. Lưu như thuộc tính mô tả trên cạnh, không resolve thành cạnh riêng tới node Article cụ thể (cắt phạm vi có chủ đích ở v1). |
| `context` | `string \| null` (≤400 ký tự) | | Trích đoạn câu làm bằng chứng — không bắt buộc nhưng nên điền để dễ kiểm tra sau này. |

Quy tắc chọn `relationType`:

| Trong văn bản | `relationType` |
|---|---|
| Nằm trong khối "Căn cứ..." ở đầu văn bản | `BASED_ON` |
| "...thay thế Quyết định số..." | `REPLACES` |
| "...sửa đổi, bổ sung...Điều...của..." | `AMENDS` |
| "...bãi bỏ.../huỷ bỏ..." | `REPEALS` |
| Nhắc tới nhưng không thuộc 4 loại trên | `REFERENCES` |

## 5. `normativeContents[]` (mảng)

Nội dung **kèm theo** văn bản (VD một Quyết định "ban hành kèm theo" một
Quy định/Quy chế). Bỏ trống nếu văn bản không ban hành nội dung kèm theo nào
(VD Công văn thuần), hoặc nếu nội dung kèm theo không khớp `contentType` nào
đã biết (xem ví dụ thực tế ở cuối tài liệu).

| Field | Type | Bắt buộc | Ý nghĩa |
|---|---|:-:|---|
| `title` | `string` | ✓ | Tên nội dung kèm theo, VD `"Quy định về việc biên soạn, lựa chọn giáo trình..."`. |
| `contentType` | `enum` | ✓ | Một trong 9 giá trị: `Quy định`, `Quy chế`, `Điều lệ`, `Quy trình`, `Nội quy`, `Đề án`, `Kế hoạch`, `Hướng dẫn`, `Chương trình`. |
| `status` | `enum \| null` | | `CON_HIEU_LUC` / `HET_HIEU_LUC` / `CHUA_HIEU_LUC` / `null`. Để `null` thì loader lấy theo `status` của Document cha (nội dung kèm theo hết hiệu lực cùng lúc với quyết định ban hành nó). |
| `idOverride` | `string \| null` | | Ép `contentId` về giá trị chỉ định. |
| `articles` | array of `article` (≥1 phần tử) | ✓ | Các Điều bên trong nội dung này — dùng chung định dạng `article` ở [§6](#6-article-dùng-chung-cho-articles-và-normativecontentsarticles). |

## 6. `article` (dùng chung cho `articles[]` và `normativeContents[].articles[]`)

| Field | Type | Bắt buộc | Ý nghĩa |
|---|---|:-:|---|
| `number` | `string` (mẫu `"Điều N"` hoặc `"Điều Na"`) | ✓ | VD `"Điều 1"`, `"Điều 12"`, `"Điều 5a"`. |
| `heading` | `string \| null` | | Tên Điều, nếu văn bản có đặt tên (VD `"Phạm vi điều chỉnh"`). |
| `text` | `string` | ✓ | Toàn văn nội dung Điều, chép/gõ lại từ file `.txt`. |
| `isImplementationClause` | `boolean` (mặc định `false`) | | `true` nếu đây là Điều thuộc phần "Điều khoản thi hành" (nơi thường chứa các câu `REPLACES`/`AMENDS`/`REPEALS`). |

**Điều "vỏ bọc" (`articles` cấp Document) so với Điều bên trong nội dung
kèm theo (`normativeContents[].articles`):** nếu văn bản là một Quyết định
"ban hành kèm theo" một Quy định/Quy chế —

- Điều vỏ bọc của Quyết định (thường chỉ Điều 1 "Ban hành kèm theo...",
  Điều 2 "Hiệu lực thi hành...", Điều 3 "Trách nhiệm thi hành...") →
  `articles` cấp Document.
- Điều bên trong Quy định/Quy chế kèm theo → `normativeContents[].articles`.
- **Hai nhóm này có thể cùng tồn tại trong một file** — đây là trường hợp
  phổ biến, không phải ngoại lệ (xem ví dụ đầy đủ bên dưới).

## 7. Danh mục tham chiếu

Hai file dùng để tra cứu giá trị hợp lệ khi điền `topics`/`organization`,
**không được tự bịa giá trị ngoài danh sách** cho `topics`:

- [`reference/topics_seed.json`](reference/topics_seed.json) — 18 lĩnh vực
  hợp lệ cho `document.topics[]` (VD `"Đào tạo"`, `"Tuyển sinh"`, `"Khảo
  thí"`, `"Thi đua, khen thưởng"`...).
- [`reference/organizations_seed.json`](reference/organizations_seed.json)
  — tổ chức đã biết trước, kèm `orgType`/`parentOrg` đã chuẩn hoá sẵn (VD
  `"Đại học Đà Nẵng"`, `"Trường Đại học Bách khoa"`, `"Bộ Giáo dục và Đào
  tạo"`...). Tổ chức **không** có trong danh sách này thì `organization`
  (hoặc phần tử trong `citations`/`mentions` nếu liên quan) phải tự điền
  `orgType` thủ công.

## 8. Những gì KHÔNG được tự điền

Các giá trị sau đều do `core/normalize.py` tự suy khi nạp vào Neo4j —
người gán **không bao giờ** tự tính:

- `normalizedNumber`, `orgId`, `personId`, `topicId`, `contentId`, `articleId`
- `authorityLevel` (bậc thẩm quyền)
- `isStub` (đánh dấu node tự sinh từ citation chưa được gán thành file
  riêng)

Muốn ép một trong các khoá trên về giá trị cụ thể (do đụng hàng hoặc văn
bản đặc biệt), dùng field `idOverride` sẵn có ở `document`, `organization`,
từng phần tử `signers[]`, và từng phần tử `normativeContents[]`.

---

## Ví dụ đầy đủ

File thật [`samples/010_2852-QD-DHDN.json`](samples/010_2852-QD-DHDN.json),
rút gọn từ văn bản thật trong `data/clean/text_final/`. Minh hoạ **đồng
thời**: nhiều `topics`, nhiều `citations` (toàn bộ đều `BASED_ON`), một
`normativeContents` có 3 Điều bên trong, **và** `articles` vỏ bọc cấp
Document cùng lúc — trường hợp phổ biến nhất trong kho dữ liệu thật.

```json
{
  "schemaVersion": "1.0",
  "sourceFile": "Đào tạo/0227_2852_QĐ-ĐHĐN_Quy định về việc biên soạn, lựa chọn giáo trình giáo dục đại học dùng chung trong.txt",
  "mappedBy": "mock",
  "note": "Văn bản thật (14KB, 7 Điều trong nội dung kèm theo) — chỉ chép Điều 1, 2, 7; bỏ Điều 3-6 (kinh phí, quy trình 4 bước, hồ sơ) và 3 Phụ lục biểu mẫu trống.",
  "document": {
    "documentNumber": "2852/QĐ-ĐHĐN",
    "title": "Ban hành Quy định về việc biên soạn, lựa chọn giáo trình giáo dục đại học dùng chung trong Đại học Đà Nẵng",
    "documentType": "Quyết định",
    "status": "CON_HIEU_LUC",
    "issueDate": "05/07/2023",
    "effectiveDate": "05/07/2023",
    "expiryDate": null,
    "fileUrl": null,
    "topics": ["Đào tạo", "Học liệu, truyền thông"],
    "summary": "Quy định việc biên soạn và lựa chọn giáo trình dùng chung (GTDC) cho các môn học chung (lý luận chính trị, khoa học cơ bản, ngoại ngữ...) sử dụng từ 2 đơn vị đào tạo trở lên trong ĐHĐN.",
    "idOverride": null
  },
  "organization": {
    "name": "Đại học Đà Nẵng",
    "orgType": null,
    "parentOrg": null,
    "idOverride": null
  },
  "signers": [
    {
      "fullName": "Lê Thành Bắc",
      "academicTitle": "PGS.TS",
      "position": ["Phó Giám đốc"],
      "idOverride": null
    }
  ],
  "citations": [
    {
      "targetDocumentNumber": "32/CP",
      "relationType": "BASED_ON",
      "targetArticle": null,
      "context": "Căn cứ Nghị định số 32/CP ngày 04/4/1994 của Chính phủ về việc thành lập Đại học Đà Nẵng."
    },
    {
      "targetDocumentNumber": "10/2020/TT-BGDĐT",
      "relationType": "BASED_ON",
      "targetArticle": null,
      "context": "Căn cứ Thông tư số 10/2020/TT-BGDĐT ngày 14/5/2020 của Bộ trưởng Bộ Giáo dục và Đào tạo ban hành Quy chế tổ chức và hoạt động của đại học vùng và các cơ sở giáo dục đại học thành viên."
    },
    {
      "targetDocumentNumber": "35/2021/TT-BGDĐT",
      "relationType": "BASED_ON",
      "targetArticle": null,
      "context": "Căn cứ Thông tư số 35/2021/TT-BGDĐT ngày 06/12/2021 của Bộ trưởng Bộ Giáo dục và Đào tạo quy định việc biên soạn, lựa chọn, thẩm định, duyệt và sử dụng tài liệu giảng dạy, giáo trình giáo dục đại học."
    },
    {
      "targetDocumentNumber": "08/NQ-HĐĐH",
      "relationType": "BASED_ON",
      "targetArticle": null,
      "context": "Căn cứ Nghị quyết số 08/NQ-HĐĐH ngày 12/7/2021 của Hội đồng Đại học Đà Nẵng về việc ban hành Quy chế tổ chức và hoạt động của Đại học Đà Nẵng."
    }
  ],
  "mentions": ["Ban Đào tạo"],
  "normativeContents": [
    {
      "title": "Quy định về việc biên soạn, lựa chọn giáo trình giáo dục đại học dùng chung trong Đại học Đà Nẵng",
      "contentType": "Quy định",
      "status": null,
      "idOverride": null,
      "articles": [
        {
          "number": "Điều 1",
          "heading": "Phạm vi điều chỉnh và đối tượng áp dụng",
          "text": "1. Văn bản này quy định về việc biên soạn, lựa chọn giáo trình giáo dục đại học dùng chung trong toàn ĐHĐN, bao gồm: phạm vi điều chỉnh, đối tượng áp dụng; kinh phí thực hiện; biên soạn giáo trình dùng chung; lựa chọn giáo trình dùng chung; tổ chức thực hiện. 2. Áp dụng đối với các trường đại học thành viên, khoa, viện, phân hiệu, trung tâm trực thuộc, đối với tất cả các hình thức đào tạo, trình độ đào tạo. 3. Không áp dụng đối với giáo trình các môn lý luận chính trị và quốc phòng - an ninh do Bộ GD&ĐT tổ chức biên soạn.",
          "isImplementationClause": false
        },
        {
          "number": "Điều 2",
          "heading": "Giải thích từ ngữ",
          "text": "1. Môn chung là những môn học trang bị kiến thức, kỹ năng thuộc kiến thức giáo dục đại cương, khoa học cơ bản như: Triết học, Kinh tế chính trị, Chủ nghĩa xã hội khoa học, Lịch sử Đảng, Tư tưởng Hồ Chí Minh, Pháp luật đại cương, Tâm lý, Xác suất thống kê, Ngoại ngữ cơ bản, Giáo dục thể chất, Toán, Vật lí, Hóa học. 2. Giáo trình dùng chung (GTDC) là tài liệu giảng dạy, học tập, nghiên cứu chính của các môn chung được sử dụng từ 02 đơn vị trở lên.",
          "isImplementationClause": false
        },
        {
          "number": "Điều 7",
          "heading": "Tổ chức thực hiện",
          "text": "1. Thủ trưởng đơn vị đào tạo phụ trách giảng dạy môn chung tổ chức rà soát những GTDC hiện đang sử dụng và thực hiện theo Quy định này. 3. Trường hợp các văn bản quy phạm pháp luật được dẫn chiếu để áp dụng tại Quy định này được sửa đổi, bổ sung, thay thế thì sẽ áp dụng theo các văn bản sửa đổi, bổ sung, thay thế đó.",
          "isImplementationClause": true
        }
      ]
    }
  ],
  "articles": [
    {
      "number": "Điều 1",
      "heading": "Ban hành kèm theo",
      "text": "Ban hành kèm theo Quyết định này Quy định về việc biên soạn, lựa chọn giáo trình giáo dục đại học dùng chung trong Đại học Đà Nẵng.",
      "isImplementationClause": false
    },
    {
      "number": "Điều 2",
      "heading": "Hiệu lực thi hành",
      "text": "Quyết định này có hiệu lực kể từ ngày ký.",
      "isImplementationClause": true
    },
    {
      "number": "Điều 3",
      "heading": "Trách nhiệm thi hành",
      "text": "Chánh Văn phòng, Trưởng các ban hữu quan, Hiệu trưởng các trường đại học thành viên, Thủ trưởng các đơn vị đào tạo thuộc và trực thuộc chịu trách nhiệm thi hành Quyết định này.",
      "isImplementationClause": false
    }
  ]
}
```

Sau khi viết xong một file, kiểm tra ngay:

```powershell
python legal_knowledge_graph/run.py validate --dir duong/dan/toi/thu/muc
```
