# Báo cáo đánh giá — KG Văn bản pháp quy DUT/ĐHĐN

> Sinh tự động lúc 03/09/2026 11:40 bởi `python run.py eval all`
> Đặc tả: [rules/Ontology.md](../../rules/Ontology.md) §6

## Tình trạng từng phần

| Phần §6 | Trạng thái |
|---|---|
| 6.1 Gold set + κ | ⬜ chờ hai người gán xong |
| 6.2 P/R/F1 extraction | ⬜ chờ gold set |
| 6.3–6.4 BM25/KG/Hybrid | ✅ có số |
| 6.5 Multi-hop tách riêng | ⬜ chờ đáp án nhóm multi-hop (người điền) |
| 6.6 Ablation | ✅ có số |
| 6.7 Error analysis | ✅ có số |

## §6.4 — Ba hệ tìm kiếm

| Hệ | P@5 | R@10 | MRR | nDCG@10 |
|---|---|---|---|---|
| **BM25** | 0.586 | 0.162 | 0.729 | 0.659 |
| **KG** | 1.000 | 0.294 | 1.000 | 1.000 |
| **HYBRID** | 0.943 | 0.254 | 1.000 | 0.926 |

### §6.5 — Riêng nhóm multi-hop

> ⬜ **Chưa chấm được câu nào.** Nhóm multi-hop không tự sinh
> đáp án được — lấy đáp án từ chính graph rồi đem chấm graph là
> lập luận vòng tròn. Phải người đọc văn bản rồi điền cột
> `DAP_AN` trong `queries.csv`.
>
> Đây là nhóm **quan trọng nhất** của cả §6: chỗ KG/Hybrid phải
> thắng BM25 rõ rệt, nếu không thì phải giải thích tại sao.

## §6.6 — Ablation

Graph đầy đủ 3,231 cạnh. Bỏ cắt vùng mất **62.9%**, bỏ stub mất **68.6%**.

## File chi tiết

| File | Nội dung |
|---|---|
| `extraction.md` | §6.1–6.2 đầy đủ, kèm bảng bất đồng giữa hai người gán |
| `retrieval.md` | §6.3–6.5 đầy đủ, tách theo nhóm câu hỏi |
| `ablation_va_loi.md` | §6.6–6.7 |
| `retrieval_runs.jsonl` | kết quả thô từng câu × từng hệ, để soi lỗi |
| `goldset/` | phiếu gán, hướng dẫn, phân tầng |
| `*.json` | cùng số liệu ở dạng máy đọc được |
