# §6.3–6.5 — So sánh BM25 / KG / Hybrid

Bộ câu hỏi: **45** câu, **14** câu đã có đáp án.

> ⚠️ 31 câu chưa có đáp án nên bị bỏ qua. Điền cột `DAP_AN` trong `queries.csv` rồi chạy lại.

## Tổng thể

| Hệ | P@1 | P@5 | R@5 | R@10 | MRR | nDCG@10 |
|---|---|---|---|---|---|---|
| **BM25** | 0.571 | 0.586 | 0.087 | 0.162 | 0.729 | 0.659 |
| **KG** | 1.000 | 1.000 | 0.147 | 0.294 | 1.000 | 1.000 |
| **HYBRID** | 1.000 | 0.943 | 0.136 | 0.254 | 1.000 | 0.926 |

## Theo nhóm câu hỏi

§6.5 yêu cầu tách riêng nhóm **multi-hop** — đây là chỗ KG/Hybrid phải
thắng BM25 rõ rệt; nếu không thì phải giải thích tại sao.

| Nhóm | Hệ | P@1 | P@5 | R@5 | R@10 | MRR | nDCG@10 |
|---|---|---|---|---|---|---|---|
| single-hop | bm25 | 0.571 | 0.586 | 0.087 | 0.162 | 0.729 | 0.659 |
| single-hop | hybrid | 1.000 | 0.943 | 0.136 | 0.254 | 1.000 | 0.926 |
| single-hop | kg | 1.000 | 1.000 | 0.147 | 0.294 | 1.000 | 1.000 |

> ⬜ Chưa có câu nào được chấm ở nhóm: **multi-hop**, **hieu-luc**. Hai nhóm `multi-hop` và `hieu-luc` **không tự sinh đáp án được** — suy đáp án từ chính graph rồi đem chấm graph là lập luận vòng tròn. Phải người đọc văn bản rồi điền cột `DAP_AN`.
