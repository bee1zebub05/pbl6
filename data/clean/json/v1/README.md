# JSON v1 — bản đầu tiên, sinh từ `data/clean/text_final`

454 file JSON theo `legal_knowledge_graph/schema/document.schema.json`, mỗi file
ứng với một văn bản trong `data/clean/text_final/`. Cấu trúc thư mục giữ nguyên
theo lĩnh vực, tên file giữ nguyên mã 4 chữ số ở đầu để đối chiếu hai chiều.

```
v1/
├── <lĩnh vực>/<mã>_….json     bản đã qua schema và các phép soi
└── _nghi_ngo/<lĩnh vực>/…     bản qua schema nhưng còn cảnh báo, xem bên dưới
```

## Sinh lại

```bash
python tools/gemini_api/chay_json.py              # gọi API, sinh file còn thiếu
python tools/gemini_api/chay_json.py --va-lai     # cắt lại Điều, KHÔNG gọi API
```

`--va-lai` dùng khi bộ cắt Điều được sửa: toàn văn mỗi Điều vốn cắt thẳng từ
`.txt` chứ không do model sinh, nên vá lại được mà không tốn hạn mức API.

## Toàn văn Điều đến từ đâu

Model chỉ sinh phần siêu dữ liệu — số hiệu, ngày, cơ quan, người ký, trích dẫn,
tiêu đề Điều. Còn `articles[].text` thì **cắt thẳng từ `.txt`** bằng
`tools/gemini_web/va_dieu_thieu.py`, vì model chép lại hay chuẩn hoá khoảng
trắng, nối dòng, đôi khi diễn đạt lại. Đo trên 0090: model chép thì 0/3 Điều
khớp nguyên văn.

Hiện `text` có bao gồm cả dòng tiêu đề `Điều N. Tên điều` ở đầu. Đây là quy ước
đã chốt; ví dụ trong `structured_form.md` thì không có, nhưng bỏ dòng đầu sẽ phá
dữ liệu ở hàng trăm Quyết định có thân điều nằm ngay trên dòng đó.

## Đã kiểm những gì

| | |
|---|---|
| Thân Điều khớp nguyên văn `.txt` | 99,87% |
| Trích dẫn có số hiệu kiểm chứng được từ dữ liệu gốc | 100% |
| Trượt schema | 0 |
| Thân Điều còn dính rác (Nơi nhận, chữ ký, phụ lục, tiêu đề chương) | 0 |
| File đọc tay đối chiếu với `.txt` | 53/454 |

Các bộ soi nằm ở `tools/kiem_tra/`:

```bash
python tools/kiem_tra/soi_trich_dan.py     # kiểm số hiệu đích của từng trích dẫn
python tools/gemini_web/tong_ket_json.py   # tổng kết toàn bộ
```

## `_nghi_ngo/` là gì

Bản qua được schema nhưng còn cảnh báo — thiếu người ký, không có căn cứ, hổ
nội dung giữa các Điều. Phần lớn là Công văn, Kế hoạch vốn không có mục *Căn
cứ*, nên cảnh báo chưa chắc là lỗi. Chưa đọc tay từng cái.

## Những chỗ đã biết là chưa đúng

- **0021** — bản gốc QĐ 1177 đánh số trùng, có hai `Điều 19`. Đã đối chiếu bản
  scan trang 8-10: bản gốc đúng là như vậy. Schema không cho trùng số Điều nên
  nội dung Điều 19 thứ hai nằm lồng trong thân Điều 19 thứ nhất — không mất chữ
  nào, nhưng đồ thị sẽ có 23 node cho 24 Điều.
- **26 trích dẫn đã bị gỡ** khỏi 11 file, vì nguồn chỉ ghi tên và ngày
  (`Căn cứ Luật Tổ chức Chính phủ ngày 19 tháng 6 năm 2015;`) mà schema lại bắt
  buộc `targetDocumentNumber`, nên model tự chế số hiệu. Trường `note` của từng
  file ghi rõ đã gỡ những gì; câu căn cứ vẫn nằm nguyên trong `.txt`.
- **0158 đã bị loại** khỏi bộ dữ liệu, xem `data/_loai_bo/VI_SAO_LOAI.md`.

## Vì sao đánh số phiên bản

`v1` sinh từ trạng thái hiện tại của `data/clean/text_final`. Nếu về sau sửa
`.txt` thì `v1` không còn khớp nguồn nữa — lúc đó sinh `v2` chứ đừng sửa đè lên
`v1`, để còn so được hai bản. Muốn biết `v1` ứng với bản `.txt` nào thì tra
commit tạo ra thư mục này trong git.
