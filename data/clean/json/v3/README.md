# JSON v3 — sửa 5 nhóm lỗi tìm được khi đọc tay 14 file cảnh báo

Sinh từ `v2`. Mọi thay đổi đều đối chiếu tận nguồn (`data/clean/text_final/`
hoặc bản scan trong `data/raw/`), không suy diễn.

| | v2 | v3 |
|---|---|---|
| Điều | 10.472 | 10.472 |
| Trích dẫn | 3.004 | **2.994** |
| Thân Điều khớp nguyên văn `.txt` | 99,89% | 99,89% |
| Trượt schema | 0 | 0 |
| File còn cảnh báo | 29 | **23** |
| Node `Organization` graph sẽ dựng | 19 | **18** |

## Năm thay đổi

**A. Gỡ 10 trích dẫn lấy NGÀY hoặc NĂM làm số hiệu.**
`0439` `0250` `0293` `0292` `0358`. Nguồn ghi căn cứ theo tên và ngày, không có
số hiệu — `Căn cứ Luật An ninh mạng ngày 12/6/2018;` — model nhét `2018` vào
`targetDocumentNumber`. Cùng bệnh với 26 chỗ đã gỡ ở v1, nhưng lọt bộ kiểm vì
phép kiểm cũ hỏi "số hiệu này có nằm nguyên văn trong `.txt` không", mà chuỗi
`2018` thì văn bản nào chẳng có. Đã siết `soi_trich_dan.py`: số hiệu thật luôn
có phần chữ (`QH13`, `NĐ-CP`, `NQ/TW`), không có chữ nào là hỏng.

**B. Sửa 1 cạnh `REPEALS` trỏ sai** — `0447`. Context nói *bãi bỏ Điều 165 của
Luật Xây dựng số 50/2014/QH13*, nhưng model lấy số hiệu **cuối cùng** trong
chuỗi sửa đổi dài (`…Luật số 45/2024/QH15, Luật số…`) làm đích. Đồ thị vì vậy
nói Luật Thanh tra bãi bỏ Luật Di sản văn hoá.

**C. Bù 2 người ký** — `0376` (PGS.TS. Nguyễn Mạnh Toàn, Phó Giám đốc) và
`0304` (Đoàn Hồng Phong, Tổng Thanh tra). Tên không có trong bất kỳ lượt OCR
nào; đọc thẳng từ bản scan bằng `tools/gemini_api/doc_pdf.py`.

**D. Gộp 33 văn bản về đúng node cơ quan.** `organization.name` lấy nguyên văn
theo tiêu ngữ từng văn bản, mà loader tính `orgId = slug(name)`, nên Trường
ĐHBK bị tách làm ba node:

```
Trường Đại học Bách khoa                    72 văn bản
Trường Đại học Bách khoa, Đại học Đà Nẵng   28      -> cùng một trường
Trường Đại học Bách khoa - Đại học Đà Nẵng   3
Trường Đại học Bách khoa, Hội đồng trường    2      -> Hội đồng trường, KHÁC
```

Cách sửa: **giữ nguyên `organization.name`**, chỉ điền `organization.idOverride`
trỏ về `orgId` chuẩn trong `reference/organizations_seed.json`. `graph_model.py`
đã có sẵn cơ chế này — `org_id = id_override or ...`. Nhờ vậy văn bản vẫn ghi
đúng những gì bản gốc in, mà graph vẫn gom về một node.

Sau khi gộp: `truong_dai_hoc_bach_khoa` có **103 văn bản** thay vì 72. Bảng
alias tay trong `reference/aliases_seed.json` (`_note`: *"tạm trỏ vào biến thể
tên có nhiều ISSUED_BY nhất trong 3 node ĐHBK chưa gộp"*) giờ không cần nữa.

**E. `CHÍNH PHỦ` không phải lỗi** — `slug()` bỏ dấu và hạ chữ thường nên nó và
`Chính phủ` vốn đã cùng ra `chinh_phu`.

## Bốn tên cơ quan sinh node riêng — ĐÚNG, đừng gộp

`Văn phòng Quốc hội`, `Ủy ban nhân dân thành phố Đà Nẵng`, `Cục Quản lý chất
lượng` là cơ quan riêng biệt thật, chỉ chưa có trong seed. `Bộ Giáo dục và Đào
tạo - Bộ Tài chính - Bộ Lao động - Thương binh và Xã hội` là văn bản liên tịch
ba bộ. Muốn sạch thì thêm ba cơ quan đầu vào `organizations_seed.json`.

## 23 file còn cảnh báo — đã đọc tay, phần lớn KHÔNG phải lỗi

| | |
|---|---|
| 11 | "không có căn cứ" nhưng nguồn **chỉ ghi tên + ngày, không số hiệu** — để trống là đúng, thà trống còn hơn bịa |
| 4 | nguồn **không có mục Căn cứ** (`0051` `0338` `0159` Công văn, `0105` Hiến pháp) |
| 4 | "thiếu Điều" — `0397` `0116` `0402` `0458` là luật/nghị định **sửa đổi**; các Điều "thiếu" (`37`, `43b`, `34`, `48`, `48b`, `66b`, `105`) là điều của luật BỊ SỬA, trích nguyên văn trong Điều 1 |
| 1 | `0136` viện dẫn Luật Xây dựng 10 lần ở 10 điều khác nhau — Neo4j `MERGE` gộp thành một cạnh, vô hại |
| 1 | `0494` — bản scan 26 trang chỉ có phần Quy chế, không có trang Quyết định ký |
| 1 | `0013` — khoảng hở giữa các Điều là `Nơi nhận` + chữ ký + tiêu đề văn bản kèm theo |
| 1 | `0021` — bản gốc QĐ 1177 có hai `Điều 19`, đã đối chiếu scan trang 8-10 |

Nghĩa là **22/23 file này nạp vào graph được ngay**, không cần sửa gì thêm.
Cộng với 7 file đã sạch từ v2, `_nghi_ngo/` chỉ còn đúng `0021` là trường hợp
thật sự chưa biểu diễn được.

## Sinh lại

```bash
python tools/kiem_tra/soi_trich_dan.py     # kiểm số hiệu đích từng trích dẫn
python tools/gemini_api/chay_json.py --va-lai   # cắt lại Điều, không gọi API
```
