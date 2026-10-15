# Trang gán nhãn văn bản sinh viên

Trang web để nhóm 4 người gán tay 103 văn bản trong `data/clean/sinh_vien_103/`: bôi đen một đoạn,
chọn loại node/quan hệ của knowledge graph, rồi xuất JSON đúng `src/legal_knowledge_graph/schema/document.schema.json`.

Bản đang chạy (chia sẻ qua menu Share, quyền Contributor): https://claude.ai/artifact/HsHAhg16vzYdS4ZqRqucgE

| File | Nội dung |
|---|---|
| `index.html` | Mã nguồn trang. Nhãn lưu trong cơ sở dữ liệu dùng chung của artifact (capability `db`), không lưu trong repo |
| `build_data.py` | Dựng `data/` (text, bản nháp v2, chỉ mục, người phụ trách) từ `data/clean/sinh_vien_103/` |

```powershell
python tools/labeler/build_data.py
```

## Loại highlight và node tương ứng

| Phím | Highlight | Ghi vào JSON |
|---|---|---|
| 1 | Cơ quan ban hành | `organization` → `ISSUED_BY` |
| 2 | Người ký | `signers[]` → `SIGNED_BY` |
| 3 | Đối tượng áp dụng | `document.targetGroups` → `APPLIES_TO` |
| 4 | Trích dẫn văn bản | `citations[]` (BASED_ON / REFERENCES / REPLACES / AMENDS / REPEALS) |
| 5 | Tổ chức được nhắc | `mentions[]` |
| 6 | Nội dung quy phạm | `normativeContents[]` → `PROMULGATES` |
| 7 | Điều | `articles[]` → `HAS_ARTICLE`, gắn vào nội dung quy phạm gần nhất phía trên |

Thông tin văn bản (số hiệu, loại, ngày, lĩnh vực, tóm tắt) điền ở cột phải, không cần highlight.

## Phân công

Cố định theo cột `nguoi_gan` của `danh_sach.csv`: Nguyên 28, Đức 25, Tùng 25, Kiên 25. Chia riêng mức A và B,
trong mỗi mức cân theo tổng số ký tự để khối lượng gần bằng nhau.
