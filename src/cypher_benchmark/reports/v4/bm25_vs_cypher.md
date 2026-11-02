# Benchmark các hệ truy hồi — 28 kịch bản

Chạy ngày 27/10/2026 trên graph `legal_knowledge_graph` (Neo4j `LKG_NEO4J_*`), kho v4 — gold theo `catalogs/gold_v4.json`. Sinh bởi `python run.py bench --compare-bm25`.

| Hệ | Cách trả lời |
|---|---|
| Cypher viết tay | Câu Cypher người viết cho từng case. Mức trần của graph: người viết đã biết câu hỏi |
| Chatbot | Chatbot LangGraph nhận câu tiếng Việt, tự chọn template hoặc tự viết Cypher. Số đo của hệ thống thật |
| BM25 (tiêu đề) | Từ khoá trên tiêu đề + tóm tắt (full-text Neo4j) |
| BM25 toàn văn | Từ khoá trên cả toàn văn các Điều, gộp lên văn bản |
| Vector | Embedding ngữ nghĩa (Gemini) trên các Điều, gộp lên văn bản |
| Hybrid | BM25 toàn văn + Vector, gộp thứ hạng (RRF) |
| Hybrid + KG | Hybrid chọn 5 văn bản hạt giống, KG mở rộng một bước theo căn cứ / sửa đổi / thay thế / bãi bỏ |

P/R/F1: Cypher và Chatbot chấm trên toàn bộ kết quả; các hệ tìm kiếm cắt tại k = số đáp án đúng (có lợi cho chúng). Ground truth S13–S17 và S21–S31 do Claude gán thay người — phiếu kiểm `reports/review_S13_S17.csv`; các case còn lại lấy từ graph đã kiểm.

## Tổng hợp

Trung bình macro trên 26 case có danh sách đáp án, cộng 2 câu đếm:

| Hệ | F1 | P@10 | nDCG@10 | MRR | Câu đếm đúng | Câu không trả lời được |
|---|---|---|---|---|---|---|
| Cypher viết tay | 0.71 | 0.48 | 0.84 | 0.87 | 2/2 | 0/28 |
| BM25 (tiêu đề) | 0.35 | 0.27 | 0.44 | 0.46 | 0/2 | 4/28 |
| BM25 toàn văn | 0.37 | 0.26 | 0.47 | 0.50 | 0/2 | 4/28 |
| Vector | 0.49 | 0.31 | 0.60 | 0.66 | 0/2 | 4/28 |
| Hybrid | 0.48 | 0.32 | 0.59 | 0.65 | 0/2 | 4/28 |
| Hybrid + KG | 0.44 | 0.29 | 0.58 | 0.66 | 0/2 | 4/28 |

## F1 theo mức độ

| Mức | Số case | Cypher viết tay | BM25 (tiêu đề) | BM25 toàn văn | Vector | Hybrid | Hybrid + KG |
|---|---|---|---|---|---|---|---|
| Mức 1 — 1-hop | 4 | 1.00 | 0.72 | 0.64 | 0.75 | 0.75 | 0.50 |
| Mức 2 — 1-hop nhiều quan hệ | 3 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.13 |
| Mức 3 — multi-hop | 2 | 1.00 | 0.00 | 0.50 | 0.50 | 0.50 | 0.50 |
| Mức 4 — fulltext/hybrid | 14 | 0.46 | 0.39 | 0.41 | 0.59 | 0.56 | 0.56 |
| Mức 5 — tổng hợp, đa điều kiện | 3 | 1.00 | 0.23 | 0.09 | 0.18 | 0.18 | 0.09 |

## Nhóm câu đi theo quan hệ (§6.5)

S08, S10, S11, S16, S20: câu trả lời nằm ở cạnh giữa các văn bản (căn cứ, sửa đổi, thay thế), không nằm trong chữ của văn bản. Đây là nhóm mà Ontology §6.5 yêu cầu KG phải thắng rõ.

| Hệ | F1 | nDCG@10 |
|---|---|---|
| Cypher viết tay | 0.91 | 0.96 |
| BM25 (tiêu đề) | 0.07 | 0.11 |
| BM25 toàn văn | 0.20 | 0.20 |
| Vector | 0.20 | 0.23 |
| Hybrid | 0.20 | 0.24 |
| Hybrid + KG | 0.28 | 0.36 |

## F1 từng case

| Case | Câu hỏi | Số đáp án | Cypher viết tay | BM25 (tiêu đề) | BM25 toàn văn | Vector | Hybrid | Hybrid + KG |
|---|---|---|---|---|---|---|---|---|
| S01 | Trường Đại học Bách khoa còn văn bản nào đang có hiệu lực? | 31 | 1.00 | 0.74 | 0.68 | 0.87 | 0.84 | 0.39 |
| S02 | Văn bản nào áp dụng cho người học (sinh viên)? | 99 | 1.00 | 0.96 | 0.98 | 0.92 | 0.98 | 0.79 |
| S03 | Trường có văn bản nào về tuyển sinh không? | 18 | 1.00 | 0.61 | 0.44 | 0.78 | 0.67 | 0.33 |
| S04 | Những Quy chế nào đang còn hiệu lực? | 18 | 1.00 | 0.56 | 0.44 | 0.44 | 0.50 | 0.50 |
| S05 | Văn bản 4511/QĐ-ĐHBK nói gì, ai ký, thuộc lĩnh vực nào? | 1 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| S07 | Văn bản 4757/QĐ-ĐHĐN nhắc tới những đơn vị nào? | 5 | 1.00 | – | – | – | – | – |
| S08 | Văn bản 4511/QĐ-ĐHBK dựa trên những căn cứ pháp lý nào? | 10 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.40 |
| S10 | Quy chế công tác sinh viên cũ (42/2007/QĐ-BGDĐT) đã bị thay bằng văn bản nào? | 1 | 1.00 | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| S11 | Những văn bản nào bị sửa đổi một phần nhưng tổng thể vẫn còn hiệu lực? | 7 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| S12 | Chuỗi văn bản thay thế nhau trong kho sâu tới mức nào? | (con số) | đúng | – | – | – | – | – |
| S13 | Học phí năm nay quy định ở văn bản nào? | 5 | 1.00 | 0.40 | 0.60 | 0.80 | 0.80 | 0.80 |
| S14 | Điều nào quy định trách nhiệm thi hành? | 149 | 0.75 | 0.22 | 0.22 | 0.74 | 0.56 | 0.56 |
| S16 | Những văn bản gốc thẩm quyền cao nào liên quan tới Đại học Đà Nẵng? | 5 | 0.53 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| S17 | Cơ quan nào ban hành nhiều văn bản nhất? | 7 | 1.00 | – | – | – | – | – |
| S18 | Bao nhiêu văn bản còn hiệu lực, bao nhiêu hết hiệu lực? | (con số) | đúng | – | – | – | – | – |
| S19 | Văn bản nào về Công tác sinh viên, áp dụng cho Người học, do chính Trường ĐHBK ban hành? | 11 | 1.00 | 0.36 | 0.27 | 0.55 | 0.55 | 0.27 |
| S20 | Trong số văn bản còn hiệu lực do Trường ĐHBK ban hành, văn bản nào từng sửa đổi văn bản khác? | 3 | 1.00 | 0.33 | 0.00 | 0.00 | 0.00 | 0.00 |
| S21 | Quy định tính điểm trung bình tích lũy và điểm trung bình học kỳ như thế nào? | 2 | 0.29 | 0.50 | 0.50 | 1.00 | 1.00 | 1.00 |
| S22 | Bao nhiêu điểm thì bị cảnh báo học tập hoặc buộc thôi học? | 4 | 0.57 | 0.25 | 0.25 | 0.75 | 0.50 | 0.50 |
| S23 | Nghỉ có lý do chính đáng thì làm thủ tục ở đâu? | 3 | 0.15 | 0.33 | 0.33 | 0.67 | 0.67 | 0.67 |
| S24 | Điều kiện để được xét công nhận tốt nghiệp là gì? | 3 | 0.31 | 0.67 | 0.67 | 0.67 | 0.67 | 0.67 |
| S25 | Xếp hạng tốt nghiệp loại giỏi, xuất sắc cần bao nhiêu điểm? | 4 | 0.50 | 0.25 | 0.25 | 0.00 | 0.25 | 0.25 |
| S26 | Chuẩn đầu ra ngoại ngữ của sinh viên là gì? | 1 | 0.18 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| S27 | Mỗi học kỳ được đăng ký tối thiểu và tối đa bao nhiêu tín chỉ? | 2 | 0.17 | 0.00 | 0.00 | 0.50 | 0.50 | 0.50 |
| S28 | Điều kiện để học cùng lúc hai chương trình là gì? | 3 | 0.67 | 0.67 | 0.67 | 1.00 | 0.67 | 0.67 |
| S29 | Sinh viên được xét học bổng khuyến khích học tập như thế nào? | 5 | 0.27 | 0.40 | 0.40 | 0.60 | 0.40 | 0.40 |
| S30 | Thi hộ hoặc nhờ người thi hộ bị xử lý kỷ luật thế nào? | 3 | 0.75 | 0.33 | 0.33 | 0.00 | 0.33 | 0.33 |
| S31 | Đối tượng nào được miễn, giảm học phí? | 2 | 0.33 | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 |

`–`: hệ không có cách trả lời loại đáp án này (không có index cho tổ chức, không đếm được).

## Top 5 từng hệ (để soi lỗi)

**S01_docs_by_org_active** — Trường Đại học Bách khoa còn văn bản nào đang có hiệu lực?

- Cypher viết tay: 107/QĐ-ĐHBK, 5543/QĐ-ĐHBK, 4532/QĐ-ĐHBK, 3707/QĐ-ĐHBK, 1214/QĐ-ĐHBK
- BM25 (tiêu đề): 2858/QĐ-ĐHĐN, 806/QĐ-ĐHBK, 1214/QĐ-ĐHBK, 1216/QĐ-ĐHBK, 4511/QĐ-ĐHBK
- BM25 toàn văn: 806/QĐ-ĐHBK, 3646/QĐ-ĐHBK, 2858/QĐ-ĐHĐN, 1214/QĐ-ĐHBK, 1404/QĐ-ĐHBK
- Vector: 1001/QĐ-ĐHBK, 3536/QĐ-ĐHBK, 1779/QĐ-ĐHBK, 3240/QĐ-ĐHBK, 806/QĐ-ĐHBK
- Hybrid: 806/QĐ-ĐHBK, 3646/QĐ-ĐHBK, 1214/QĐ-ĐHBK, 1001/QĐ-ĐHBK, 05/NQ-HĐT
- Hybrid + KG: 806/QĐ-ĐHBK, 3646/QĐ-ĐHBK, 1214/QĐ-ĐHBK, 1001/QĐ-ĐHBK, 05/NQ-HĐT

**S02_docs_by_target_group** — Văn bản nào áp dụng cho người học (sinh viên)?

- Cypher viết tay: 56/2026/TT-BGDĐT, 08/2021/TT-BGDĐT, 10/2016/TT-BGDĐT, 78/2020/NĐ-CP, 09/2016/TTLT-BGDĐT-BTC-BLĐTBXH
- BM25 (tiêu đề): 02/2025/TT-BGDĐT, 2858/QĐ-ĐHĐN, 2058/QĐ-ĐHĐN, 1414/QĐ-ĐHBK, 4420/QĐ-ĐHBK
- BM25 toàn văn: 2058/QĐ-ĐHĐN, 4420/QĐ-ĐHBK, 3226/QĐ-ĐHĐN, 3758/QĐ-ĐHĐN, 3646/QĐ-ĐHBK
- Vector: 10/2016/TT-BGDĐT, 08/2012/QH13, 81/2021/NĐ-CP, 4420/QĐ-ĐHBK, 05/NQ-HĐT
- Hybrid: 4420/QĐ-ĐHBK, 2058/QĐ-ĐHĐN, 3226/QĐ-ĐHĐN, 1980/QĐ-ĐHBK, 3758/QĐ-ĐHĐN
- Hybrid + KG: 4420/QĐ-ĐHBK, 2058/QĐ-ĐHĐN, 3226/QĐ-ĐHĐN, 1980/QĐ-ĐHBK, 3758/QĐ-ĐHĐN

**S03_docs_by_topic** — Trường có văn bản nào về tuyển sinh không?

- Cypher viết tay: 3183/QĐ-ĐHĐN, 3297/QĐ-ĐHĐN, 1340/QĐ-ĐHBK, 23/2021/TT-BGDĐT, 09/2020/TT-BGDĐT
- BM25 (tiêu đề): 2858/QĐ-ĐHĐN, 806/QĐ-ĐHBK, 4420/QĐ-ĐHBK, 28/VBHN-BGDĐT, 2058/QĐ-ĐHĐN
- BM25 toàn văn: 806/QĐ-ĐHBK, 4420/QĐ-ĐHBK, 09/2020/TT-BGDĐT, 06/2026/TT-BGDĐT, 3297/QĐ-ĐHĐN
- Vector: 1609/QĐ-ĐHBK, 06/2026/TT-BGDĐT, 2414/QĐ-ĐHĐN, 4481/QĐ-ĐHĐN, 1340/QĐ-ĐHBK
- Hybrid: 06/2026/TT-BGDĐT, 1609/QĐ-ĐHBK, 09/2020/TT-BGDĐT, 4481/QĐ-ĐHĐN, 4473/QĐ-ĐHĐN
- Hybrid + KG: 06/2026/TT-BGDĐT, 1609/QĐ-ĐHBK, 09/2020/TT-BGDĐT, 4481/QĐ-ĐHĐN, 4473/QĐ-ĐHĐN

**S04_normative_content_active** — Những Quy chế nào đang còn hiệu lực?

- Cypher viết tay: 10/2016/TT-BGDDT#nd1, 30/2018/TT-BGDDT#nd1, 16/2015/TT-BGDDT#nd1, 2721/QD-DHDN#nd1, 1001/QD-DHBK#nd1
- BM25 (tiêu đề): 4511/QD-DHBK#nd1, 56/2026/TT-BGDDT#nd1, 3297/QD-DHDN#nd1, 8/2021/TT-BGDDT#nd1, 4481/QD-DHDN#nd1
- BM25 toàn văn: 4511/QD-DHBK#nd1, 5/NQ-HDT#nd1, 3536/QD-DHBK#nd1, 10/2016/TT-BGDDT#nd1, 405/QD-DHBK#nd1
- Vector: 5/NQ-HDT#nd1, 905#nd1, 3536/QD-DHBK#nd1, 3107/QD-DHDN#nd1, 2533/QD-DHBK#nd1
- Hybrid: 5/NQ-HDT#nd1, 3536/QD-DHBK#nd1, 905#nd1, 56/2026/TT-BGDDT#nd1, 8/2021/TT-BGDDT#nd1
- Hybrid + KG: 5/NQ-HDT#nd1, 3536/QD-DHBK#nd1, 905#nd1, 56/2026/TT-BGDDT#nd1, 8/2021/TT-BGDDT#nd1

**S05_document_detail** — Văn bản 4511/QĐ-ĐHBK nói gì, ai ký, thuộc lĩnh vực nào?

- Cypher viết tay: 4511/QĐ-ĐHBK
- BM25 (tiêu đề): 618/QĐ-BGDĐT, 754/QĐ-BGDĐT, 2858/QĐ-ĐHĐN, 81/2021/NĐ-CP, 861/QĐ-TTg
- BM25 toàn văn: 754/QĐ-BGDĐT, 81/2021/NĐ-CP, 618/QĐ-BGDĐT, 1899/QĐ-ĐHĐN, 3646/QĐ-ĐHBK
- Vector: 3536/QĐ-ĐHBK, 1216/QĐ-ĐHBK, 4768/QĐ-ĐHĐN, 1404/QĐ-ĐHBK, 1214/QĐ-ĐHBK
- Hybrid: 3646/QĐ-ĐHBK, 3107/QĐ-ĐHĐN, 754/QĐ-BGDĐT, 1216/QĐ-ĐHBK, 107/QĐ-ĐHBK
- Hybrid + KG: 3646/QĐ-ĐHBK, 3107/QĐ-ĐHĐN, 754/QĐ-BGDĐT, 1216/QĐ-ĐHBK, 107/QĐ-ĐHBK

**S07_document_mentions** — Văn bản 4757/QĐ-ĐHĐN nhắc tới những đơn vị nào?

- Cypher viết tay: dai_hoc_da_nang, thu_tuong_chinh_phu, bo_giao_duc_va_dao_tao, hoi_dong_dai_hoc_da_nang, chinh_phu

**S08_document_based_on** — Văn bản 4511/QĐ-ĐHBK dựa trên những căn cứ pháp lý nào?

- Cypher viết tay: 13/NQ-HĐĐH, 788/ĐHĐN-ĐT, 08/NQ-HĐĐH, 32/CP, 99/2019/NĐ-CP
- BM25 (tiêu đề): 806/QĐ-ĐHBK, 2858/QĐ-ĐHĐN, 107/QĐ-ĐHBK, 1356/QĐ-ĐHĐN, 1899/QĐ-ĐHĐN
- BM25 toàn văn: 3646/QĐ-ĐHBK, 2858/QĐ-ĐHĐN, 806/QĐ-ĐHBK, 10/2026/TT-BGDĐT, 1489/QĐ-ĐHĐN
- Vector: 3536/QĐ-ĐHBK, 1216/QĐ-ĐHBK, 1214/QĐ-ĐHBK, 4768/QĐ-ĐHĐN, 1404/QĐ-ĐHBK
- Hybrid: 3646/QĐ-ĐHBK, 1214/QĐ-ĐHBK, 1404/QĐ-ĐHBK, 3107/QĐ-ĐHĐN, 4420/QĐ-ĐHBK
- Hybrid + KG: 3646/QĐ-ĐHBK, 1214/QĐ-ĐHBK, 1404/QĐ-ĐHBK, 3107/QĐ-ĐHĐN, 4420/QĐ-ĐHBK

**S10_replaced_by** — Quy chế công tác sinh viên cũ (42/2007/QĐ-BGDĐT) đã bị thay bằng văn bản nào?

- Cypher viết tay: 10/2016/TT-BGDĐT
- BM25 (tiêu đề): 05/2022/QĐ-TTg, 2858/QĐ-ĐHĐN, 1325/QĐ-BGDĐT, 10/2026/TT-BGDĐT, 3107/QĐ-ĐHĐN
- BM25 toàn văn: 10/2016/TT-BGDĐT, 10/2026/TT-BGDĐT, 3107/QĐ-ĐHĐN, 05/2022/QĐ-TTg, 2721/QĐ-ĐHĐN
- Vector: 10/2016/TT-BGDĐT, 973/QĐ-ĐHĐN, 27/2009/TT-BGDĐT, 1325/QĐ-BGDĐT, 1001/QĐ-ĐHBK
- Hybrid: 10/2016/TT-BGDĐT, 1001/QĐ-ĐHBK, 2721/QĐ-ĐHĐN, 27/2009/TT-BGDĐT, 1325/QĐ-BGDĐT
- Hybrid + KG: 10/2016/TT-BGDĐT, 1001/QĐ-ĐHBK, 2721/QĐ-ĐHĐN, 27/2009/TT-BGDĐT, 1325/QĐ-BGDĐT

**S11_amends_target_still_active** — Những văn bản nào bị sửa đổi một phần nhưng tổng thể vẫn còn hiệu lực?

- Cypher viết tay: 10/2016/TT-BGDĐT, 1404/QĐ-ĐHBK, 1899/QĐ-ĐHĐN, 2231/QĐ-ĐHBK, 2721/QĐ-ĐHĐN
- BM25 (tiêu đề): 754/QĐ-BGDĐT, 2858/QĐ-ĐHĐN, 51/2024/QH15, 107/QĐ-ĐHBK, 806/QĐ-ĐHBK
- BM25 toàn văn: 51/2024/QH15, 1274/QĐ-ĐHBK, 806/QĐ-ĐHBK, 10/2026/TT-BGDĐT, 4511/QĐ-ĐHBK
- Vector: 05/NQ-HĐT, 5543/QĐ-ĐHBK, 2533/QĐ-ĐHBK, 3828/QĐ-ĐHĐN, 1340/QĐ-ĐHBK
- Hybrid: 51/2024/QH15, 754/QĐ-BGDĐT, 10/2026/TT-BGDĐT, 3828/QĐ-ĐHĐN, 1489/QĐ-ĐHĐN
- Hybrid + KG: 51/2024/QH15, 754/QĐ-BGDĐT, 10/2026/TT-BGDĐT, 3828/QĐ-ĐHĐN, 1489/QĐ-ĐHĐN

**S13_fulltext_doc_content** — Học phí năm nay quy định ở văn bản nào?

- Cypher viết tay: 3443/ĐHĐN-KHTC, 81/2021/NĐ-CP, 09/2016/TTLT-BGDĐT-BTC-BLĐTBXH, 4532/QĐ-ĐHBK, 97/2023/NĐ-CP
- BM25 (tiêu đề): 2858/QĐ-ĐHĐN, 3443/ĐHĐN-KHTC, 1340/QĐ-ĐHBK, 09/2016/TTLT-BGDĐT-BTC-BLĐTBXH, 806/QĐ-ĐHBK
- BM25 toàn văn: 81/2021/NĐ-CP, 2858/QĐ-ĐHĐN, 09/2016/TTLT-BGDĐT-BTC-BLĐTBXH, 1356/QĐ-ĐHĐN, 97/2023/NĐ-CP
- Vector: 97/2023/NĐ-CP, 81/2021/NĐ-CP, 3443/ĐHĐN-KHTC, 09/2016/TTLT-BGDĐT-BTC-BLĐTBXH, 43/2019/QH14
- Hybrid: 81/2021/NĐ-CP, 97/2023/NĐ-CP, 09/2016/TTLT-BGDĐT-BTC-BLĐTBXH, 3443/ĐHĐN-KHTC, 1345/QĐ-ĐHBK
- Hybrid + KG: 81/2021/NĐ-CP, 97/2023/NĐ-CP, 09/2016/TTLT-BGDĐT-BTC-BLĐTBXH, 3443/ĐHĐN-KHTC, 1345/QĐ-ĐHBK

**S14_fulltext_article** — Điều nào quy định trách nhiệm thi hành?

- Cypher viết tay: 1489/QD-DHDN#nd1#Điều 36, 3226/QD-DHDN#nd1#Điều 25, 78/2020/ND-CP#Điều 27, 84/2020/ND-CP#Điều 12, 86/2021/ND-CP#Điều 30
- BM25 (tiêu đề): 3226/QD-DHDN#nd1#Điều 25, 1489/QD-DHDN#nd1#Điều 36, 78/2020/ND-CP#Điều 27, 84/2020/ND-CP#Điều 12, 86/2021/ND-CP#Điều 30
- BM25 toàn văn: 3226/QD-DHDN#nd1#Điều 25, 1489/QD-DHDN#nd1#Điều 36, 78/2020/ND-CP#Điều 27, 84/2020/ND-CP#Điều 12, 86/2021/ND-CP#Điều 30
- Vector: 84/2020/ND-CP#Điều 12, 2721/QD-DHDN#nd1#Điều 24, 1489/QD-DHDN#nd1#Điều 36, 78/2020/ND-CP#Điều 27, 86/2021/ND-CP#Điều 30
- Hybrid: 84/2020/ND-CP#Điều 12, 1489/QD-DHDN#nd1#Điều 36, 78/2020/ND-CP#Điều 27, 2721/QD-DHDN#nd1#Điều 24, 3226/QD-DHDN#nd1#Điều 25
- Hybrid + KG: 84/2020/ND-CP#Điều 12, 1489/QD-DHDN#nd1#Điều 36, 78/2020/ND-CP#Điều 27, 2721/QD-DHDN#nd1#Điều 24, 3226/QD-DHDN#nd1#Điều 25

**S16_hybrid_expand** — Những văn bản gốc thẩm quyền cao nào liên quan tới Đại học Đà Nẵng?

- Cypher viết tay: 32/CP, 10/2020/TT-BGDĐT, 08/2021/TT-BGDĐT, 08/2014/TT-BGDĐT, 08/2022/TT-BGDĐT
- BM25 (tiêu đề): 806/QĐ-ĐHBK, 3107/QĐ-ĐHĐN, 2858/QĐ-ĐHĐN, 18/2017/QĐ-TTg, 1779/QĐ-ĐHBK
- BM25 toàn văn: 806/QĐ-ĐHBK, 1356/QĐ-ĐHĐN, 2858/QĐ-ĐHĐN, 3107/QĐ-ĐHĐN, 3646/QĐ-ĐHBK
- Vector: 1356/QĐ-ĐHĐN, 2858/QĐ-ĐHĐN, 3107/QĐ-ĐHĐN, 806/QĐ-ĐHBK, 4473/QĐ-ĐHĐN
- Hybrid: 1356/QĐ-ĐHĐN, 806/QĐ-ĐHBK, 2858/QĐ-ĐHĐN, 3107/QĐ-ĐHĐN, 05/NQ-HĐT
- Hybrid + KG: 1356/QĐ-ĐHĐN, 806/QĐ-ĐHBK, 2858/QĐ-ĐHĐN, 3107/QĐ-ĐHĐN, 05/NQ-HĐT

**S17_top_organizations** — Cơ quan nào ban hành nhiều văn bản nhất?

- Cypher viết tay: Trường Đại học Bách khoa, Đại học Đà Nẵng, Bộ Giáo dục và Đào tạo, Chính phủ, Quốc hội

**S19_multi_facet_and** — Văn bản nào về Công tác sinh viên, áp dụng cho Người học, do chính Trường ĐHBK ban hành?

- Cypher viết tay: 29/QĐ-ĐHBK, 1001/QĐ-ĐHBK, 1216/QĐ-ĐHBK, 5543/QĐ-ĐHBK, 3337/QĐ-ĐHBK
- BM25 (tiêu đề): 1414/QĐ-ĐHBK, 2721/QĐ-ĐHĐN, 1001/QĐ-ĐHBK, 3646/QĐ-ĐHBK, 10/2016/TT-BGDĐT
- BM25 toàn văn: 3646/QĐ-ĐHBK, 2721/QĐ-ĐHĐN, 1216/QĐ-ĐHBK, 10/2016/TT-BGDĐT, 1001/QĐ-ĐHBK
- Vector: 1001/QĐ-ĐHBK, 1216/QĐ-ĐHBK, 1214/QĐ-ĐHBK, 2231/QĐ-ĐHBK, 4420/QĐ-ĐHBK
- Hybrid: 1216/QĐ-ĐHBK, 1001/QĐ-ĐHBK, 3646/QĐ-ĐHBK, 4420/QĐ-ĐHBK, 10/2016/TT-BGDĐT
- Hybrid + KG: 1216/QĐ-ĐHBK, 1001/QĐ-ĐHBK, 3646/QĐ-ĐHBK, 4420/QĐ-ĐHBK, 10/2016/TT-BGDĐT

**S20_active_org_docs_that_amend** — Trong số văn bản còn hiệu lực do Trường ĐHBK ban hành, văn bản nào từng sửa đổi văn bản khác?

- Cypher viết tay: 1088/QĐ-ĐHBK, 107/QĐ-ĐHBK, 3707/QĐ-ĐHBK
- BM25 (tiêu đề): 2858/QĐ-ĐHĐN, 806/QĐ-ĐHBK, 107/QĐ-ĐHBK, 10/2026/TT-BGDĐT, 4420/QĐ-ĐHBK
- BM25 toàn văn: 806/QĐ-ĐHBK, 10/2026/TT-BGDĐT, 3107/QĐ-ĐHĐN, 3646/QĐ-ĐHBK, 1899/QĐ-ĐHĐN
- Vector: 1214/QĐ-ĐHBK, 1404/QĐ-ĐHBK, 1779/QĐ-ĐHBK, 1216/QĐ-ĐHBK, 3240/QĐ-ĐHBK
- Hybrid: 806/QĐ-ĐHBK, 3646/QĐ-ĐHBK, 1214/QĐ-ĐHBK, 107/QĐ-ĐHBK, 10/2026/TT-BGDĐT
- Hybrid + KG: 806/QĐ-ĐHBK, 3646/QĐ-ĐHBK, 1214/QĐ-ĐHBK, 107/QĐ-ĐHBK, 10/2026/TT-BGDĐT

**S21_gpa_rule** — Quy định tính điểm trung bình tích lũy và điểm trung bình học kỳ như thế nào?

- Cypher viết tay: 2231/QD-DHBK#nd1#Điều 4, 56/2026/TT-BGDDT#nd1#Điều 14, 2244/QD-DHBK#nd1#Điều 12, 2244/QD-DHBK#nd1#Điều 11, 2244/QD-DHBK#nd1#Điều 10
- BM25 (tiêu đề): 2244/QD-DHBK#nd1#Điều 9, 56/2026/TT-BGDDT#nd1#Điều 13, 8/2021/TT-BGDDT#nd1#Điều 10, 2244/QD-DHBK#nd1#Điều 10, 2244/QD-DHBK#nd1#Điều 11
- BM25 toàn văn: 2244/QD-DHBK#nd1#Điều 9, 56/2026/TT-BGDDT#nd1#Điều 13, 8/2021/TT-BGDDT#nd1#Điều 10, 2244/QD-DHBK#nd1#Điều 10, 2244/QD-DHBK#nd1#Điều 11
- Vector: 2244/QD-DHBK#nd1#Điều 11, 56/2026/TT-BGDDT#nd1#Điều 13, 8/2021/TT-BGDDT#nd1#Điều 10, 2367/QD-DHDN#nd1#Điều 4, 1779/QD-DHBK#nd1#Điều 6
- Hybrid: 56/2026/TT-BGDDT#nd1#Điều 13, 2244/QD-DHBK#nd1#Điều 11, 8/2021/TT-BGDDT#nd1#Điều 10, 2244/QD-DHBK#nd1#Điều 9, 1779/QD-DHBK#nd1#Điều 6
- Hybrid + KG: 56/2026/TT-BGDDT#nd1#Điều 13, 2244/QD-DHBK#nd1#Điều 11, 8/2021/TT-BGDDT#nd1#Điều 10, 2244/QD-DHBK#nd1#Điều 9, 1779/QD-DHBK#nd1#Điều 6

**S22_academic_warning** — Bao nhiêu điểm thì bị cảnh báo học tập hoặc buộc thôi học?

- Cypher viết tay: 2244/QD-DHBK#nd1#Điều 12, 56/2026/TT-BGDDT#nd1#Điều 14, 56/2026/TT-BGDDT#nd1#Điều 15, 2347/QD-DHBK#nd1#Điều 17, 1001/QD-DHBK#nd2#25
- BM25 (tiêu đề): 1779/QD-DHBK#nd1#Điều 7, 3875/QD-DHBK#nd1#Điều 29, 2244/QD-DHBK#nd1#Điều 12, 8/2021/TT-BGDDT#nd1#Điều 11, 56/2026/TT-BGDDT#nd1#Điều 14
- BM25 toàn văn: 1779/QD-DHBK#nd1#Điều 7, 3875/QD-DHBK#nd1#Điều 29, 2244/QD-DHBK#nd1#Điều 12, 8/2021/TT-BGDDT#nd1#Điều 11, 56/2026/TT-BGDDT#nd1#Điều 14
- Vector: 2244/QD-DHBK#nd1#Điều 12, 8/2021/TT-BGDDT#nd1#Điều 11, 56/2026/TT-BGDDT#nd1#Điều 14, 2244/QD-DHBK#nd1#Điều 13, 56/2026/TT-BGDDT#nd1#Điều 15
- Hybrid: 2244/QD-DHBK#nd1#Điều 12, 8/2021/TT-BGDDT#nd1#Điều 11, 56/2026/TT-BGDDT#nd1#Điều 14, 1779/QD-DHBK#nd1#Điều 7, 56/2026/TT-BGDDT#nd1#Điều 15
- Hybrid + KG: 2244/QD-DHBK#nd1#Điều 12, 8/2021/TT-BGDDT#nd1#Điều 11, 56/2026/TT-BGDDT#nd1#Điều 14, 1779/QD-DHBK#nd1#Điều 7, 56/2026/TT-BGDDT#nd1#Điều 15

**S23_valid_absence_procedure** — Nghỉ có lý do chính đáng thì làm thủ tục ở đâu?

- Cypher viết tay: 3604/QD-DHBK#nd1#Điều 13, 10/2016/TT-BGDDT#nd1#Điều 10, 1001/QD-DHBK#nd1#Điều 20, 2721/QD-DHDN#nd1#Điều 14, 4473/QD-DHDN#nd1#Điều 14
- BM25 (tiêu đề): 3604/QD-DHBK#nd1#Điều 13, 2244/QD-DHBK#nd1#Điều 18, 10/2016/TT-BGDDT#nd1#Điều 10, 973/QD-DHDN#nd1#8, 1001/QD-DHBK#nd2#6
- BM25 toàn văn: 3604/QD-DHBK#nd1#Điều 13, 2244/QD-DHBK#nd1#Điều 18, 10/2016/TT-BGDDT#nd1#Điều 10, 973/QD-DHDN#nd1#8, 1001/QD-DHBK#nd2#6
- Vector: 1214/QD-DHBK#nd1#Điều 40, 2244/QD-DHBK#nd1#Điều 18, 8/2021/TT-BGDDT#nd1#Điều 15, 23/2021/TT-BGDDT#nd1#Điều 13, 3875/QD-DHBK#nd1#Điều 28
- Hybrid: 2244/QD-DHBK#nd1#Điều 18, 3604/QD-DHBK#nd1#Điều 13, 1214/QD-DHBK#nd1#Điều 40, 8/2021/TT-BGDDT#nd1#Điều 15, 23/2021/TT-BGDDT#nd1#Điều 13
- Hybrid + KG: 2244/QD-DHBK#nd1#Điều 18, 3604/QD-DHBK#nd1#Điều 13, 1214/QD-DHBK#nd1#Điều 40, 8/2021/TT-BGDDT#nd1#Điều 15, 23/2021/TT-BGDDT#nd1#Điều 13

**S24_graduation_conditions** — Điều kiện để được xét công nhận tốt nghiệp là gì?

- Cypher viết tay: 2244/QD-DHBK#nd1#Điều 17, 56/2026/TT-BGDDT#nd1#Điều 17, 3875/QD-DHBK#nd1#Điều 23, 53/2026/TT-BGDDT#nd1#Điều 13, 1779/QD-DHBK#nd1#Điều 8
- BM25 (tiêu đề): 2244/QD-DHBK#nd1#Điều 17, 8/2021/TT-BGDDT#nd1#Điều 14, 56/2026/TT-BGDDT#nd1#Điều 17, QD-DHDN#nd1#Điều 4, 23/2021/TT-BGDDT#nd1#Điều 12
- BM25 toàn văn: 2244/QD-DHBK#nd1#Điều 17, 8/2021/TT-BGDDT#nd1#Điều 14, 56/2026/TT-BGDDT#nd1#Điều 17, QD-DHDN#nd1#Điều 4, 23/2021/TT-BGDDT#nd1#Điều 12
- Vector: 2244/QD-DHBK#nd1#Điều 17, 8/2021/TT-BGDDT#nd1#Điều 14, 56/2026/TT-BGDDT#nd1#Điều 17, 1214/QD-DHBK#nd1#Điều 29, QD-DHDN#nd1#Điều 4
- Hybrid: 2244/QD-DHBK#nd1#Điều 17, 8/2021/TT-BGDDT#nd1#Điều 14, 56/2026/TT-BGDDT#nd1#Điều 17, QD-DHDN#nd1#Điều 4, 1214/QD-DHBK#nd1#Điều 29
- Hybrid + KG: 2244/QD-DHBK#nd1#Điều 17, 8/2021/TT-BGDDT#nd1#Điều 14, 56/2026/TT-BGDDT#nd1#Điều 17, QD-DHDN#nd1#Điều 4, 1214/QD-DHBK#nd1#Điều 29

**S25_graduation_ranking** — Xếp hạng tốt nghiệp loại giỏi, xuất sắc cần bao nhiêu điểm?

- Cypher viết tay: 3875/QD-DHBK#nd1#Điều 24, 2858/QD-DHDN#nd1#3, 56/2026/TT-BGDDT#nd1#Điều 17, 2244/QD-DHBK#nd1#Điều 17
- BM25 (tiêu đề): 3875/QD-DHBK#nd1#Điều 24, 56/2026/TT-BGDDT#nd1#Điều 17, 2367/QD-DHDN#nd1#Điều 7, 8/2021/TT-BGDDT#nd1#Điều 14, 2244/QD-DHBK#nd1#Điều 17
- BM25 toàn văn: 3875/QD-DHBK#nd1#Điều 24, 56/2026/TT-BGDDT#nd1#Điều 17, 2367/QD-DHDN#nd1#Điều 7, 8/2021/TT-BGDDT#nd1#Điều 14, 2244/QD-DHBK#nd1#Điều 17
- Vector: 3875/QD-DHBK#nd1#Điều 24, 16/2015/TT-BGDDT#nd1#Điều 9, 3758/QD-DHDN#nd1#Điều 9, 2231/QD-DHBK#nd1#Điều 7, 8/2021/TT-BGDDT#nd1#Điều 10
- Hybrid: 3875/QD-DHBK#nd1#Điều 24, 3758/QD-DHDN#nd1#Điều 9, 56/2026/TT-BGDDT#nd1#Điều 17, 16/2015/TT-BGDDT#nd1#Điều 9, 8/2021/TT-BGDDT#nd1#Điều 14
- Hybrid + KG: 3875/QD-DHBK#nd1#Điều 24, 3758/QD-DHDN#nd1#Điều 9, 56/2026/TT-BGDDT#nd1#Điều 17, 16/2015/TT-BGDDT#nd1#Điều 9, 8/2021/TT-BGDDT#nd1#Điều 14

**S26_foreign_language_exit** — Chuẩn đầu ra ngoại ngữ của sinh viên là gì?

- Cypher viết tay: 4511/QD-DHBK#nd1#Điều 3, 4511/QD-DHBK#nd1#Điều 6, 56/2026/TT-BGDDT#nd1#Điều 27, 4511/QD-DHBK#nd1#Điều 8, 1356/QD-DHDN#nd1#Điều 2
- BM25 (tiêu đề): 4511/QD-DHBK#nd1#Điều 6, 4511/QD-DHBK#nd1#Điều 3, 1345/QD-DHBK#nd1#Điều 7, 405/QD-DHBK#nd1#Điều 6, 4511/QD-DHBK#nd1#Điều 4
- BM25 toàn văn: 4511/QD-DHBK#nd1#Điều 6, 4511/QD-DHBK#nd1#Điều 3, 1345/QD-DHBK#nd1#Điều 7, 405/QD-DHBK#nd1#Điều 6, 4511/QD-DHBK#nd1#Điều 4
- Vector: 4511/QD-DHBK#nd1#Điều 6, 4511/QD-DHBK#nd1#Điều 4, 1345/QD-DHBK#nd1#Điều 3, 4511/QD-DHBK#nd1#Điều 11, 1345/QD-DHBK#nd1#Điều 7
- Hybrid: 4511/QD-DHBK#nd1#Điều 6, 4511/QD-DHBK#nd1#Điều 4, 1345/QD-DHBK#nd1#Điều 7, 4511/QD-DHBK#nd1#Điều 3, 1345/QD-DHBK#nd1#Điều 3
- Hybrid + KG: 4511/QD-DHBK#nd1#Điều 6, 4511/QD-DHBK#nd1#Điều 4, 1345/QD-DHBK#nd1#Điều 7, 4511/QD-DHBK#nd1#Điều 3, 1345/QD-DHBK#nd1#Điều 3

**S27_credit_load_limits** — Mỗi học kỳ được đăng ký tối thiểu và tối đa bao nhiêu tín chỉ?

- Cypher viết tay: 56/2026/TT-BGDDT#nd1#Điều 9, 53/2026/TT-BGDDT#nd1#Điều 4, 1214/QD-DHBK#nd1#Điều 42, 56/2026/TT-BGDDT#nd1#Điều 21, 3875/QD-DHBK#nd1#Điều 6
- BM25 (tiêu đề): 1779/QD-DHBK#nd1#Điều 3, 8/2021/TT-BGDDT#nd1#Điều 7, 56/2026/TT-BGDDT#nd1#Điều 9, 3240/QD-DHBK#nd1#Điều 2, 2244/QD-DHBK#nd1#Điều 7
- BM25 toàn văn: 1779/QD-DHBK#nd1#Điều 3, 8/2021/TT-BGDDT#nd1#Điều 7, 56/2026/TT-BGDDT#nd1#Điều 9, 3240/QD-DHBK#nd1#Điều 2, 2244/QD-DHBK#nd1#Điều 7
- Vector: 2244/QD-DHBK#nd1#Điều 7, 8/2021/TT-BGDDT#nd1#Điều 7, 56/2026/TT-BGDDT#nd1#Điều 9, 2244/QD-DHBK#nd1#Điều 2, 3875/QD-DHBK#nd1#Điều 6
- Hybrid: 8/2021/TT-BGDDT#nd1#Điều 7, 2244/QD-DHBK#nd1#Điều 7, 56/2026/TT-BGDDT#nd1#Điều 9, 1779/QD-DHBK#nd1#Điều 3, 2244/QD-DHBK#nd1#Điều 2
- Hybrid + KG: 8/2021/TT-BGDDT#nd1#Điều 7, 2244/QD-DHBK#nd1#Điều 7, 56/2026/TT-BGDDT#nd1#Điều 9, 1779/QD-DHBK#nd1#Điều 3, 2244/QD-DHBK#nd1#Điều 2

**S28_double_degree** — Điều kiện để học cùng lúc hai chương trình là gì?

- Cypher viết tay: 2244/QD-DHBK#nd1#Điều 21, 56/2026/TT-BGDDT#nd1#Điều 21, 1214/QD-DHBK#nd1#Điều 42, 4511/QD-DHBK#nd1#Điều 5, 10/2016/TT-BGDDT#nd1#Điều 5
- BM25 (tiêu đề): 8/2021/TT-BGDDT#nd1#Điều 18, 2244/QD-DHBK#nd1#Điều 21, 56/2026/TT-BGDDT#nd1#Điều 21, 1214/QD-DHBK#nd1#Điều 42, 56/2026/TT-BGDDT#nd1#Điều 22
- BM25 toàn văn: 8/2021/TT-BGDDT#nd1#Điều 18, 2244/QD-DHBK#nd1#Điều 21, 56/2026/TT-BGDDT#nd1#Điều 21, 1214/QD-DHBK#nd1#Điều 42, 56/2026/TT-BGDDT#nd1#Điều 22
- Vector: 2244/QD-DHBK#nd1#Điều 21, 1214/QD-DHBK#nd1#Điều 42, 56/2026/TT-BGDDT#nd1#Điều 21, 8/2021/TT-BGDDT#nd1#Điều 18, 1478/QD-DHDN#nd1#Điều 20
- Hybrid: 2244/QD-DHBK#nd1#Điều 21, 8/2021/TT-BGDDT#nd1#Điều 18, 1214/QD-DHBK#nd1#Điều 42, 56/2026/TT-BGDDT#nd1#Điều 21, 56/2026/TT-BGDDT#nd1#Điều 22
- Hybrid + KG: 2244/QD-DHBK#nd1#Điều 21, 8/2021/TT-BGDDT#nd1#Điều 18, 1214/QD-DHBK#nd1#Điều 42, 56/2026/TT-BGDDT#nd1#Điều 21, 56/2026/TT-BGDDT#nd1#Điều 22

**S29_merit_scholarship** — Sinh viên được xét học bổng khuyến khích học tập như thế nào?

- Cypher viết tay: 3536/QD-DHBK#nd1#Điều 11, 84/2020/ND-CP#Điều 8, 28/VBHN-BGDDT#Điều 1, 28/VBHN-BGDDT#Điều 2, 1414/QD-DHBK#Điều 2
- BM25 (tiêu đề): 84/2020/ND-CP#Điều 8, 28/VBHN-BGDDT#Điều 1, 28/VBHN-BGDDT#Điều 2, 3536/QD-DHBK#nd1#Điều 11, 1414/QD-DHBK#nd1#Điều 3
- BM25 toàn văn: 84/2020/ND-CP#Điều 8, 28/VBHN-BGDDT#Điều 1, 28/VBHN-BGDDT#Điều 2, 3536/QD-DHBK#nd1#Điều 11, 1414/QD-DHBK#nd1#Điều 3
- Vector: 84/2020/ND-CP#Điều 8, 28/VBHN-BGDDT#Điều 2, 28/VBHN-BGDDT#Điều 1, 1414/QD-DHBK#nd1#Điều 7, 3536/QD-DHBK#nd1#Điều 11
- Hybrid: 84/2020/ND-CP#Điều 8, 28/VBHN-BGDDT#Điều 1, 28/VBHN-BGDDT#Điều 2, 3536/QD-DHBK#nd1#Điều 11, 1414/QD-DHBK#nd1#Điều 3
- Hybrid + KG: 84/2020/ND-CP#Điều 8, 28/VBHN-BGDDT#Điều 1, 28/VBHN-BGDDT#Điều 2, 3536/QD-DHBK#nd1#Điều 11, 1414/QD-DHBK#nd1#Điều 3

**S30_exam_impersonation** — Thi hộ hoặc nhờ người thi hộ bị xử lý kỷ luật thế nào?

- Cypher viết tay: 2367/QD-DHDN#nd1#Điều 8, 3875/QD-DHBK#nd1#Điều 33, 29/QD-DHBK#nd1#Điều 4, 56/2026/TT-BGDDT#nd1#Điều 24, 3707/QD-DHBK#Điều 1
- BM25 (tiêu đề): 1001/QD-DHBK#nd2#3, 2367/QD-DHDN#nd1#Điều 8, 1001/QD-DHBK#nd2#2, 973/QD-DHDN#nd1#5, 973/QD-DHDN#nd1#4
- BM25 toàn văn: 1001/QD-DHBK#nd2#3, 2367/QD-DHDN#nd1#Điều 8, 1001/QD-DHBK#nd2#2, 973/QD-DHDN#nd1#5, 973/QD-DHDN#nd1#4
- Vector: 1001/QD-DHBK#nd2#3, 1001/QD-DHBK#nd2#4, 1001/QD-DHBK#nd2#2, 8/2021/TT-BGDDT#nd1#Điều 20, 973/QD-DHDN#nd1#5
- Hybrid: 1001/QD-DHBK#nd2#3, 1001/QD-DHBK#nd2#2, 2367/QD-DHDN#nd1#Điều 8, 973/QD-DHDN#nd1#5, 8/2021/TT-BGDDT#nd1#Điều 20
- Hybrid + KG: 1001/QD-DHBK#nd2#3, 1001/QD-DHBK#nd2#2, 2367/QD-DHDN#nd1#Điều 8, 973/QD-DHDN#nd1#5, 8/2021/TT-BGDDT#nd1#Điều 20

**S31_tuition_exemption** — Đối tượng nào được miễn, giảm học phí?

- Cypher viết tay: 81/2021/ND-CP#Điều 15, 81/2021/ND-CP#Điều 16, 81/2021/ND-CP#Điều 20, 81/2021/ND-CP#Điều 19, 81/2021/ND-CP#Điều 21
- BM25 (tiêu đề): 81/2021/ND-CP#Điều 20, 81/2021/ND-CP#Điều 15, 81/2021/ND-CP#Điều 16, 81/2021/ND-CP#Điều 21, 9/2016/TTLT-BGDDT-BTC-BLDTBXH#Điều 6
- BM25 toàn văn: 81/2021/ND-CP#Điều 20, 81/2021/ND-CP#Điều 15, 81/2021/ND-CP#Điều 16, 81/2021/ND-CP#Điều 21, 9/2016/TTLT-BGDDT-BTC-BLDTBXH#Điều 6
- Vector: 9/2016/TTLT-BGDDT-BTC-BLDTBXH#Điều 4, 81/2021/ND-CP#Điều 15, 81/2021/ND-CP#Điều 20, 81/2021/ND-CP#Điều 16, 81/2021/ND-CP#Điều 19
- Hybrid: 81/2021/ND-CP#Điều 20, 81/2021/ND-CP#Điều 15, 81/2021/ND-CP#Điều 16, 81/2021/ND-CP#Điều 19, 43/2019/QH14#Điều 85
- Hybrid + KG: 81/2021/ND-CP#Điều 20, 81/2021/ND-CP#Điều 15, 81/2021/ND-CP#Điều 16, 81/2021/ND-CP#Điều 19, 43/2019/QH14#Điều 85

