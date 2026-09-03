# §6.6–6.7 — Ablation và phân tích lỗi

## Ablation

Graph đầy đủ: **3,231 cạnh** (1,862 `BASED_ON`, 169 quan hệ hiệu lực).

| Bỏ thành phần | Hậu quả | Mất |
|---|---|---|
| Cắt vùng (Bước 1) | Không có Bước 1 thì BASED_ON và ba quan hệ hiệu lực đều không phân biệt được — sụp hết về REFERENCES. | **2,031 cạnh (62.9%)** |
| Quan hệ hiệu lực | Mất khả năng trả lời 'văn bản nào đang còn hiệu lực' và 'cái gì thay thế cái gì'. | 169 cạnh |
| Stub (§1) | Chuỗi BASED_ON đứt ở mọi văn bản chưa crawl — đúng chỗ §3 cần để truy lên văn bản gốc thẩm quyền cao nhất. | 2,216 cạnh (68.6%) |
| `authority_level` (§3) | Truy vấn §3 `ORDER BY authority_level DESC` không còn sắp được thứ tự văn bản gốc. | 107 node |

**Chưa đo được:**

- `-OCR` — Cần OCR lại toàn kho bằng lớp text gốc của PDF, mà data/raw/pdf/ đã bị xoá khỏi máy.
- `-NormativeContent+Article` — Phải đo qua retrieval cấp điều khoản; xem retrieval.md khi có gold answer.

---

## Phân tích lỗi

### Resolve — trích dẫn không nối được vào node nào

**717** lượt / 717 số hiệu phân biệt (11.7% tổng số trích dẫn), trong đó **151** là số hiệu **cụt đuôi** (mất phần `-CP`, `-BGDĐT`… do OCR hoặc xuống dòng).

> Toàn bộ nhóm này gần như đều chỉ xuất hiện **đúng một lần** — đó là
> hệ quả tất yếu của ngưỡng tạo stub (≥2 lần **hoặc** nằm trong vùng
> Căn cứ): mọi số hiệu lặp lại đã được vét lên thành node rồi. Nên đây
> là phần đuôi dài của nhiễu OCR, không phải chỗ sửa tay có lợi.

### Chuỗi `BASED_ON` chết ở stub

**344/356** văn bản (96.6%) có ít nhất một nhánh căn cứ dừng lại ở một stub — tức truy ngược lên văn bản gốc thẩm quyền cao nhất (§3) bị đứt giữa chừng.

Crawl bổ sung 15 văn bản dưới đây sẽ nối lại nhiều nhánh nhất:

| Số hiệu | Loại | Số lần bị viện dẫn |
|---|---|---|
| `32/CP` | Nghị định | 172 |
| `13/NQ-HDDH` | Nghị quyết | 97 |
| `8/NQ-HDDH` | Nghị quyết | 76 |
| `91/2026/ND-CP` | Nghị định | 61 |
| `2009/VBQPPLIQ` | Công văn | 54 |
| `8/2014/TT-BGDDT` | Thông tư | 35 |
| `85/2025/ND-CP` | Nghị định | 32 |
| `37/2025/ND-CP` | Nghị định | 31 |
| `8/2023/TT-BGDDT` | Thông tư | 30 |
| `151/2017/ND-CP` | Nghị định | 29 |
| `85/2016/ND-CP` | Nghị định | 29 |
| `2/2022/TT-BGDDT` | Thông tư | 28 |
| `204/2004/ND-CP` | Nghị định | 28 |
| `86/2022/ND-CP` | Nghị định | 28 |
| `24/2024/ND-CP` | Nghị định | 26 |

### Header lệch kéo theo cạnh đáng ngờ

| Kết luận đối chiếu header | Số văn bản |
|---|---|
| `khop` | 381 |
| `lech` | 34 |
| `khong-thay` | 28 |
| `gan-khop` | 7 |
| `khong-co-file` | 2 |

**465 cạnh** xuất phát từ văn bản có header lệch metadata — mỗi cạnh đó mang sẵn cờ `source_header_check: "lech"` trong `relations.jsonl` để lọc ra.

### Cấu trúc

- 116 nhóm văn bản **trùng cả số lẫn cơ quan, chỉ khác năm** (`8/2014/TT-BGDĐT` vs `8/2020/TT-BGDĐT`) — đúng nguồn resolve sai mà §6.7 nêu đích danh. Trích dẫn nào mất phần năm do OCR là có nguy cơ nối nhầm sang đây.
- 33 văn bản không đọc ra `Điều` nào → Bước 4 không sinh được `Article`.
