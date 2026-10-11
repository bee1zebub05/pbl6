# Dữ liệu — từ PDF trên website đến đồ thị tri thức

Cập nhật: **09/10/2026**. Cách chạy từng bước xem [README gốc](../README.md) và
[docs/PIPELINE_TU_DONG.md](../docs/PIPELINE_TU_DONG.md).

## 1. Phạm vi lưu trữ

Repo chỉ lưu **đầu ra đã chốt**. PDF gốc (khoảng 2,3 GB) và các bản OCR trung gian
không được đưa vào repo và hiện **không còn trên máy chứa repo này**: `data/raw/pdf/`
rỗng, `data/processed/` chỉ còn vài file đọc lại từ PDF (`_doc_lai_pdf/`). Hệ quả:

- không đối chiếu được ảnh gốc khi nghi ngờ lỗi OCR;
- không chạy lại được các bước crawl và OCR;
- `data/manifest.jsonl` là nguồn metadata duy nhất còn lại (ngày ban hành, cơ quan, hiệu lực).

Bản làm việc từng tồn tại ở một cây `data/` riêng ngoài repo và không tự đồng bộ với repo.
Mọi chỉnh sửa kho văn bản sau thời điểm đó phải được sao chép thủ công vào `data/clean/text_final/`.

## 2. Số lượng văn bản qua từng bước

| Bước | Còn lại | Hao hụt và lý do |
|---|---|---|
| Mục lục website `dut.udn.vn` | 475 | — |
| Tải về được | 460 | −15: máy chủ trả 404 |
| Loại bản website gắn nhầm file | 455 | −5: PDF không đúng với mục lục |
| Loại `0158` | **454** | −1: bản gốc hỏng, xem `_loai_bo/VI_SAO_LOAI.md` |
| Kho chuẩn `text_final` | **454** | — |

15 văn bản bị 404 vẫn xuất hiện trong graph dưới dạng `Document` stub khi bị văn bản khác
viện dẫn. Đáng kể nhất: `41/2024/QH15` (Luật Bảo hiểm xã hội 2024), `36/2024/QH15`
(Luật Trật tự, an toàn giao thông đường bộ 2024), `115/2020/NĐ-CP`, `75/2012/NĐ-CP`.

## 3. Cấu trúc thư mục

| Thư mục / file | Nội dung | Số lượng |
|---|---|---|
| `clean/text_final/` | Kho văn bản chuẩn, `.txt` theo lĩnh vực | 454 file |
| `clean/json/v1/` | JSON gán tay sinh từ `text_final`; thư mục con `_nghi_ngo/` chứa bản còn cảnh báo | 454 file (36 ở `_nghi_ngo/`) |
| `clean/json/v2/` | Như v1, bổ sung `targetGroups` | 454 file (36 ở `_nghi_ngo/`) |
| `kg/` | Đầu ra `.jsonl` và Cypher của pipeline tự động | 13 file |
| `eval/` | Kết quả và phiếu gán của khối đánh giá §6 | xem mục 6 |
| `kiem_tra/` | Báo cáo chất lượng bản cuối (`bao_cao_ban_cuoi.csv`) | 1 file |
| `_loai_bo/` | Văn bản loại khỏi bộ dữ liệu (hiện có `0158`) kèm lý do | 1 văn bản |
| `manifest.jsonl` | Metadata gộp qua các bước crawl, OCR, hiệu đính | 501 dòng |
| `raw/`, `interim/`, `processed/` | Gần như rỗng (xem mục 1) | — |

`manifest.jsonl` nhiều hơn kho chuẩn vì giữ cả các mục bị loại và các mục tải không được,
để truy vết; không dùng làm kho.

## 4. Nguồn gốc `text_final`

PDF của kho là ảnh scan, không có lớp text, nên toàn bộ văn bản đều qua OCR. Quy trình:
OCR bằng EasyOCR, chuẩn hoá số hiệu và ngày từ metadata, hiệu đính bằng Gemma, OCR lại
bằng Gemma các file kém, rồi chọn bản tốt hơn cho từng văn bản qua cổng lọc năm điều kiện
(trong đó có điều kiện không được mất người ký và phải bổ sung được thông tin). Sau đó
kho qua đợt sửa lỗi OCR mức ký tự (commit `ad3e512`). Chi tiết và lý do từng quy tắc xem
[clean/README.md](clean/README.md).

Chất lượng hiện tại:

| Chỉ số | Kết quả |
|---|---|
| Ngày ban hành đọc được | 100% |
| Người ký đọc được | 99% (4 văn bản là biểu mẫu để trống chỗ ký) |
| Căn cứ pháp lý | 93% (2.089 căn cứ) |
| Cấu trúc Điều | 91% (9.734 Điều, 33.956 Khoản) |
| Watermark quảng cáo | 0 |
| Tỷ lệ lỗi ký tự, trung vị | 0,13% |
| Văn bản còn ≥ 1% / ≥ 3% lỗi | 54 / 9 |

Bộ đo lỗi dựa trên cấu trúc âm tiết tiếng Việt nên tính nhầm các từ như `TTg`, `Internet`,
`Excel`, `Covid` là lỗi. Con số dùng để ước lượng, không dùng để xếp hạng từng văn bản.

## 5. Đầu ra graph

**Pipeline tự động** — `kg/`: `documents`, `articles`, `relations`, `mentions`, `segments`,
`signed_by`, `normative_contents`, `persons`, `organizations`, `topics` (`.jsonl`), cùng
`nguoi_ky.json`, `schema.cypher`, `queries.cypher`. Thời điểm dựng không đồng nhất:
`documents`, `articles`, `relations`, `segments`, `organizations`, `topics` ngày 04/09/2026
từ `text_clean_gemma`; `mentions`, `persons`, `signed_by`, `nguoi_ky` ngày 15/09;
`normative_contents` ngày 17/09. Cần chạy lại `python run.py kg all` để đồng bộ với `text_final`.

**Pipeline gán tay** — không ghi file trung gian ngoài JSON ở `clean/json/`; graph nằm trong
Neo4j cổng 7688 (xem [GRAPHREPORT.md](../src/legal_knowledge_graph/docs/GRAPHREPORT.md)).

## 6. Thư mục `eval/`

| File | Nội dung |
|---|---|
| `BAO_CAO.md` | Tổng hợp (sinh ngày 03/09/2026) |
| `extraction.md`, `extraction_metrics.json`, `agreement.json` | §6.1–6.2 (chưa có số: gold set chưa gán) |
| `retrieval.md`, `retrieval_metrics.json`, `retrieval_runs.jsonl`, `queries.csv` | §6.3–6.5 |
| `ablation_va_loi.md`, `ablation.json`, `error_analysis.json` | §6.6–6.7 |
| `goldset/` | 175 phiếu gán, hướng dẫn gán, danh sách và phân tầng; `nguoi_gan_1/`, `nguoi_gan_2/` trống |

## 7. Việc còn dở về dữ liệu

| Việc | Tình trạng |
|---|---|
| Sửa lỗi OCR ký tự | 294/455 văn bản; 54 văn bản còn ≥ 1% lỗi |
| Đọc tay từng trang | 75/455 văn bản |
| `0440` | Sửa đến trang 19/~60 |
| 7 chỗ cần đối chiếu ảnh gốc | Chưa làm; ảnh gốc không còn trên máy |
| Dựng lại graph tự động từ `text_final` | Chưa làm |
| 36 JSON ở `_nghi_ngo/` | Chưa đọc soát |
| Gán gold set | Chưa làm |
