# Văn bản bị loại khỏi bộ dữ liệu

## 0158 — Thông tư 12/2017/TT-BGDĐT (Quy định về kiểm định chất lượng cơ sở giáo dục đại học)

**Loại ngày 20/09/2026. Lý do: bản gốc hỏng, không dựng lại được.**

Nguồn của văn bản này không phải bản scan mà là một file Word
(`data/raw/doc_new/.../0158_....doc`), và container OLE của nó **bị cụt**.
Đã thử ba đường, đều không mở được:

| công cụ | kết quả |
|---|---|
| `antiword` | `0158.doc is not a Word Document` |
| Microsoft Word (COM) | `Word was unable to read this document. It may be corrupt.` |
| thư viện `olefile` | `OleFileError: incomplete OLE sector` |

Không có bản nào khác trong `data/raw` (không có PDF, không có bản scan).

Hậu quả trên bản `.txt` đã trích xuất: toàn bộ `Điều 1.` đến `Điều 30.` của
bản Quy định ban hành kèm theo bị biến thành dấu đầu dòng `·`, ví dụ:

```
· Phạm vi điều chỉnh và đối tượng áp dụng
· Văn bản này quy định về kiểm định chất lượng cơ sở giáo dục...
```

Lượt OCR còn lại trong `data/processed` cũng hỏng y như vậy. Bản `.txt` vì thế
chỉ còn 29/59 Điều (Điều 1-3 của Thông tư và Điều 31-56 của Quy định). Không
có cách nào phân biệt dòng `·` nào là tiêu đề Điều, dòng nào là khoản — đoán
thì thành bịa dữ liệu.

**Muốn khôi phục:** xin lại file gốc chưa hỏng, đặt vào `data/raw`, rồi chạy
lại pipeline cho riêng mã 0158. Bản `.txt` cũ giữ ở thư mục này để đối chiếu,
và toàn bộ lịch sử vẫn nằm trong git.
