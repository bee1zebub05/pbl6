# Benchmark các hệ truy hồi — 31 kịch bản

Chạy ngày 13/10/2026 trên graph `legal_knowledge_graph` (Neo4j `LKG_NEO4J_*`). Sinh bởi `python run.py bench --compare-bm25`.

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

Trung bình macro trên 29 case có danh sách đáp án, cộng 2 câu đếm:

| Hệ | F1 | P@10 | nDCG@10 | MRR | Câu đếm đúng | Câu không trả lời được |
|---|---|---|---|---|---|---|
| Cypher viết tay | 0.73 | 0.48 | 0.86 | 0.91 | 2/2 | 0/31 |
| BM25 (tiêu đề) | 0.25 | 0.21 | 0.36 | 0.38 | 0/2 | 4/31 |
| BM25 toàn văn | 0.26 | 0.23 | 0.41 | 0.45 | 0/2 | 4/31 |
| Vector | 0.42 | 0.27 | 0.56 | 0.65 | 0/2 | 4/31 |
| Hybrid | 0.41 | 0.28 | 0.55 | 0.64 | 0/2 | 4/31 |
| Hybrid + KG | 0.39 | 0.26 | 0.54 | 0.65 | 0/2 | 4/31 |

## F1 theo mức độ

| Mức | Số case | Cypher viết tay | BM25 (tiêu đề) | BM25 toàn văn | Vector | Hybrid | Hybrid + KG |
|---|---|---|---|---|---|---|---|
| Mức 1 — 1-hop | 4 | 1.00 | 0.52 | 0.53 | 0.64 | 0.67 | 0.43 |
| Mức 2 — 1-hop nhiều quan hệ | 4 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.10 |
| Mức 3 — multi-hop | 3 | 1.00 | 0.00 | 0.00 | 0.38 | 0.36 | 0.33 |
| Mức 4 — fulltext/hybrid | 15 | 0.48 | 0.32 | 0.34 | 0.55 | 0.52 | 0.53 |
| Mức 5 — tổng hợp, đa điều kiện | 3 | 1.00 | 0.08 | 0.08 | 0.08 | 0.08 | 0.08 |

## Nhóm câu đi theo quan hệ (§6.5)

S08, S09, S10, S11, S16, S20: câu trả lời nằm ở cạnh giữa các văn bản (căn cứ, sửa đổi, thay thế), không nằm trong chữ của văn bản. Đây là nhóm mà Ontology §6.5 yêu cầu KG phải thắng rõ.

| Hệ | F1 | nDCG@10 |
|---|---|---|
| Cypher viết tay | 0.92 | 0.95 |
| BM25 (tiêu đề) | 0.00 | 0.05 |
| BM25 toàn văn | 0.00 | 0.13 |
| Vector | 0.19 | 0.18 |
| Hybrid | 0.18 | 0.17 |
| Hybrid + KG | 0.26 | 0.26 |

## F1 từng case

| Case | Câu hỏi | Số đáp án | Cypher viết tay | BM25 (tiêu đề) | BM25 toàn văn | Vector | Hybrid | Hybrid + KG |
|---|---|---|---|---|---|---|---|---|
| S01 | Trường Đại học Bách khoa còn văn bản nào đang có hiệu lực? | 62 | 1.00 | 0.52 | 0.56 | 0.65 | 0.68 | 0.39 |
| S02 | Văn bản nào áp dụng cho người học (sinh viên)? | 51 | 1.00 | 0.27 | 0.35 | 0.57 | 0.57 | 0.33 |
| S03 | Trường có văn bản nào về tuyển sinh không? | 16 | 1.00 | 0.44 | 0.56 | 0.62 | 0.75 | 0.31 |
| S04 | Những Quy chế nào đang còn hiệu lực? | 57 | 1.00 | 0.84 | 0.63 | 0.72 | 0.70 | 0.70 |
| S05 | Văn bản 4511/QĐ-ĐHBK nói gì, ai ký, thuộc lĩnh vực nào? | 1 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| S06 | Văn bản 1559/QĐ-BGDĐT có bao nhiêu Điều, nội dung ra sao? | 7 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| S07 | Văn bản 4757/QĐ-ĐHĐN nhắc tới những đơn vị nào? | 6 | 1.00 | – | – | – | – | – |
| S08 | Văn bản 4511/QĐ-ĐHBK dựa trên những căn cứ pháp lý nào? | 10 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.40 |
| S09 | Văn bản 3868/QĐ-ĐHBK đã trải qua bao nhiêu lần sửa đổi, thay thế? | 3 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| S10 | Quy chế công tác sinh viên cũ (42/2007/QĐ-BGDĐT) đã bị thay bằng văn bản nào? | 1 | 1.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 |
| S11 | Những văn bản nào bị sửa đổi một phần nhưng tổng thể vẫn còn hiệu lực? | 14 | 1.00 | 0.00 | 0.00 | 0.14 | 0.07 | 0.00 |
| S12 | Chuỗi văn bản thay thế nhau trong kho sâu tới mức nào? | (con số) | đúng | – | – | – | – | – |
| S13 | Học phí năm nay quy định ở văn bản nào? | 5 | 0.91 | 0.20 | 0.40 | 0.60 | 0.60 | 0.60 |
| S14 | Điều nào quy định trách nhiệm thi hành? | 464 | 0.75 | 0.41 | 0.41 | 0.64 | 0.59 | 0.59 |
| S15 | Có Nội quy nào liên quan không? | 2 | 1.00 | 0.00 | 0.00 | 0.00 | 0.50 | 0.50 |
| S16 | Những văn bản gốc thẩm quyền cao nào liên quan tới Đại học Đà Nẵng? | 6 | 0.50 | 0.00 | 0.00 | 0.00 | 0.00 | 0.17 |
| S17 | Cơ quan nào ban hành nhiều văn bản nhất? | 10 | 1.00 | – | – | – | – | – |
| S18 | Bao nhiêu văn bản còn hiệu lực, bao nhiêu hết hiệu lực? | (con số) | đúng | – | – | – | – | – |
| S19 | Văn bản nào về Công tác sinh viên, áp dụng cho Người học, do chính Trường ĐHBK ban hành? | 4 | 1.00 | 0.25 | 0.25 | 0.25 | 0.25 | 0.25 |
| S20 | Trong số văn bản còn hiệu lực do Trường ĐHBK ban hành, văn bản nào từng sửa đổi văn bản khác? | 4 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| S21 | Quy định tính điểm trung bình tích lũy và điểm trung bình học kỳ như thế nào? | 2 | 0.29 | 0.50 | 0.50 | 1.00 | 1.00 | 1.00 |
| S22 | Bao nhiêu điểm thì bị cảnh báo học tập hoặc buộc thôi học? | 4 | 0.57 | 0.25 | 0.25 | 0.75 | 0.50 | 0.50 |
| S23 | Nghỉ có lý do chính đáng thì làm thủ tục ở đâu? | 3 | 0.00 | 0.00 | 0.00 | 0.67 | 0.33 | 0.33 |
| S24 | Điều kiện để được xét công nhận tốt nghiệp là gì? | 3 | 0.31 | 0.33 | 0.33 | 0.67 | 0.67 | 0.67 |
| S25 | Xếp hạng tốt nghiệp loại giỏi, xuất sắc cần bao nhiêu điểm? | 4 | 0.57 | 0.25 | 0.25 | 0.00 | 0.25 | 0.25 |
| S26 | Chuẩn đầu ra ngoại ngữ của sinh viên là gì? | 1 | 0.18 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| S27 | Mỗi học kỳ được đăng ký tối thiểu và tối đa bao nhiêu tín chỉ? | 2 | 0.17 | 0.00 | 0.00 | 0.50 | 0.50 | 0.50 |
| S28 | Điều kiện để học cùng lúc hai chương trình là gì? | 3 | 0.67 | 0.67 | 0.67 | 1.00 | 0.67 | 0.67 |
| S29 | Sinh viên được xét học bổng khuyến khích học tập như thế nào? | 5 | 0.27 | 0.40 | 0.40 | 0.60 | 0.40 | 0.40 |
| S30 | Thi hộ hoặc nhờ người thi hộ bị xử lý kỷ luật thế nào? | 3 | 0.75 | 0.33 | 0.33 | 0.33 | 0.33 | 0.33 |
| S31 | Đối tượng nào được miễn, giảm học phí? | 2 | 0.33 | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 |

`–`: hệ không có cách trả lời loại đáp án này (không có index cho tổ chức, không đếm được).

## Top 5 từng hệ (để soi lỗi)

**S01_docs_by_org_active** — Trường Đại học Bách khoa còn văn bản nào đang có hiệu lực?

- Cypher viết tay: 107/QĐ-ĐHBK, 5247/QĐ-ĐHBK, 4532/QĐ-ĐHBK, 3868/QĐ-ĐHBK, 3707/QĐ-ĐHBK
- BM25 (tiêu đề): 441/QĐ-ĐHBK, 2465/QĐ-ĐHBK, 2888/QĐ-ĐHBK, 542/QĐ-ĐHBK, 1838/QĐ-ĐHBK
- BM25 toàn văn: 441/QĐ-ĐHBK, 2465/QĐ-ĐHBK, 542/QĐ-ĐHBK, 448/QĐ-ĐHBK, 338/QĐ-ĐHBK
- Vector: 2465/QĐ-ĐHBK, 542/QĐ-ĐHBK, 487/QĐ-ĐHBK, 338/QĐ-ĐHBK, 3536/QĐ-ĐHBK
- Hybrid: 2465/QĐ-ĐHBK, 542/QĐ-ĐHBK, 338/QĐ-ĐHBK, 760/QĐ-ĐHBK, 806/QĐ-ĐHBK
- Hybrid + KG: 2465/QĐ-ĐHBK, 542/QĐ-ĐHBK, 338/QĐ-ĐHBK, 760/QĐ-ĐHBK, 806/QĐ-ĐHBK

**S02_docs_by_target_group** — Văn bản nào áp dụng cho người học (sinh viên)?

- Cypher viết tay: 29/QĐ-ĐHBK, 16/2015/TT-BGDĐT, 1395/QĐ-ĐHBK, 35/2011/TT-BGDĐT, 1899/QĐ-ĐHĐN
- BM25 (tiêu đề): 2888/QĐ-ĐHBK, 10/2026/NQ-CP, 2058/QĐ-ĐHĐN, 4036/QĐ-ĐHĐN, 1414/QĐ-ĐHBK
- BM25 toàn văn: 2058/QĐ-ĐHĐN, 80/2015/QH13, 2888/QĐ-ĐHBK, 4420/QĐ-ĐHBK, 3226/QĐ-ĐHĐN
- Vector: 10/2016/TT-BGDĐT, 81/2021/NĐ-CP, 4511/QĐ-ĐHBK, 4420/QĐ-ĐHBK, 16/2015/TT-BGDĐT
- Hybrid: 4420/QĐ-ĐHBK, 10/2016/TT-BGDĐT, 3226/QĐ-ĐHĐN, 1980/QĐ-ĐHBK, 29/QĐ-ĐHBK
- Hybrid + KG: 4420/QĐ-ĐHBK, 10/2016/TT-BGDĐT, 3226/QĐ-ĐHĐN, 1980/QĐ-ĐHBK, 29/QĐ-ĐHBK

**S03_docs_by_topic** — Trường có văn bản nào về tuyển sinh không?

- Cypher viết tay: 18/2017/QĐ-TTg, 4757/QĐ-ĐHĐN, 4481/QĐ-ĐHĐN, 618/QĐ-BGDĐT, 07/2020/TT-BGDĐT
- BM25 (tiêu đề): 441/QĐ-ĐHBK, 3183/QĐ-ĐHĐN, 2888/QĐ-ĐHBK, 09/2020/TT-BGDĐT, 1609/QĐ-ĐHBK
- BM25 toàn văn: 09/2020/TT-BGDĐT, 1609/QĐ-ĐHBK, 3297/QĐ-ĐHĐN, 4481/QĐ-ĐHĐN, 80/2015/QH13
- Vector: 1609/QĐ-ĐHBK, 1248/QĐ-ĐHĐN, 06/2026/TT-BGDĐT, 2414/QĐ-ĐHĐN, 1478/QĐ-ĐHĐN
- Hybrid: 1609/QĐ-ĐHBK, 06/2026/TT-BGDĐT, 4481/QĐ-ĐHĐN, 2414/QĐ-ĐHĐN, 09/2020/TT-BGDĐT
- Hybrid + KG: 1609/QĐ-ĐHBK, 06/2026/TT-BGDĐT, 4481/QĐ-ĐHĐN, 2414/QĐ-ĐHĐN, 09/2020/TT-BGDĐT

**S04_normative_content_active** — Những Quy chế nào đang còn hiệu lực?

- Cypher viết tay: 10/2016/TT-BGDDT#nd1, 16/2015/TT-BGDDT#nd1, 2721/QD-DHDN#nd1, 1001/QD-DHBK#nd1, 27/2009/TT-BGDDT#nd1
- BM25 (tiêu đề): 4511/QD-DHBK#nd1, 1749/QD-BGDDT#nd1, 998/QD-DHDN#nd1, 4036/QD-DHDN#nd1, 8/2021/TT-BGDDT#nd1
- BM25 toàn văn: 5/NQ-HDDH#nd1, 4511/QD-DHBK#nd1, 1676/QD-DHDN#nd1, 1250/QD-DHBK#nd1, 3536/QD-DHBK#nd1
- Vector: 1474/QD-DHBK#nd1, 1199/QD-DHBK#nd1, 1250/QD-DHBK#nd1, 5/NQ-HDT#nd1, 595/QD-DHBK#nd1
- Hybrid: 5/NQ-HDDH#nd1, 1250/QD-DHBK#nd1, 5/NQ-HDT#nd1, 1474/QD-DHBK#nd1, 2352/QD-DHBK#nd1
- Hybrid + KG: 5/NQ-HDDH#nd1, 1250/QD-DHBK#nd1, 5/NQ-HDT#nd1, 1474/QD-DHBK#nd1, 2352/QD-DHBK#nd1

**S05_document_detail** — Văn bản 4511/QĐ-ĐHBK nói gì, ai ký, thuộc lĩnh vực nào?

- Cypher viết tay: 4511/QĐ-ĐHBK
- BM25 (tiêu đề): 08/2025/TT-BGDĐT, 618/QĐ-BGDĐT, 754/QĐ-BGDĐT, 441/QĐ-ĐHBK, 03/2025/TT-BGDĐT
- BM25 toàn văn: 2155/QĐ-ĐHBK, 01/2011/TT-BNV, 08/2025/TT-BGDĐT, 2465/QĐ-ĐHBK, 30/2020/NĐ-CP
- Vector: 1605/QĐ-ĐHBK, 3536/QĐ-ĐHBK, 23/NQ-HĐT, 1199/QĐ-ĐHBK, 595/QĐ-ĐHBK
- Hybrid: 2465/QĐ-ĐHBK, 2155/QĐ-ĐHBK, 1616/QĐ-ĐHBK, 3646/QĐ-ĐHBK, 800/QĐ-ĐHBK
- Hybrid + KG: 2465/QĐ-ĐHBK, 2155/QĐ-ĐHBK, 1616/QĐ-ĐHBK, 3646/QĐ-ĐHBK, 800/QĐ-ĐHBK

**S06_document_articles** — Văn bản 1559/QĐ-BGDĐT có bao nhiêu Điều, nội dung ra sao?

- Cypher viết tay: 1559/QD-BGDDT#Điều 1, 1559/QD-BGDDT#Điều 4, 1559/QD-BGDDT#Điều 5, 1559/QD-BGDDT#Điều 6, 1559/QD-BGDDT#Điều 7
- BM25 (tiêu đề): 4801/QD-DHDN#nd1#Điều 14, 1616/QD-DHBK#nd1#Điều 14, 806/QD-DHBK#nd1#Điều 18, 806/QD-DHBK#nd1#Điều 19, 30/2020/ND-CP#Điều 25
- BM25 toàn văn: 4801/QD-DHDN#nd1#Điều 14, 1616/QD-DHBK#nd1#Điều 14, 806/QD-DHBK#nd1#Điều 18, 806/QD-DHBK#nd1#Điều 19, 30/2020/ND-CP#Điều 25
- Vector: 4/2016/TT-BGDDT#Điều 1, 3758/QD-DHDN#Điều 1, 1325/QD-BGDDT#Điều 2, 16/2015/TT-BGDDT#Điều 2, 23/2016/TT-BGDDT#Điều 13
- Hybrid: 30/2020/TT-BGDDT#Điều 2, 46/2021/TT-BGDDT#Điều 1, 30/2020/TT-BGDDT#Điều 1, 80/2015/QH13#Điều 11, 1749/QD-BGDDT#Điều 2
- Hybrid + KG: 30/2020/TT-BGDDT#Điều 2, 46/2021/TT-BGDDT#Điều 1, 30/2020/TT-BGDDT#Điều 1, 80/2015/QH13#Điều 11, 1749/QD-BGDDT#Điều 2

**S07_document_mentions** — Văn bản 4757/QĐ-ĐHĐN nhắc tới những đơn vị nào?

- Cypher viết tay: hoi_dong_dai_hoc_da_nang, chinh_phu, bo_giao_duc_va_dao_tao, ban_dao_tao_va_dam_bao_chat_luong_giao_duc, thu_tuong_chinh_phu

**S08_document_based_on** — Văn bản 4511/QĐ-ĐHBK dựa trên những căn cứ pháp lý nào?

- Cypher viết tay: 08/NQ-HĐĐH, 17/2021/TT-BGDĐT, 22/NQ-HĐT, 05/NQ-HĐT, 32/CP
- BM25 (tiêu đề): 80/2015/QH13, 2888/QĐ-ĐHBK, 2858/QĐ-ĐHĐN, 448/QĐ-ĐHBK, 104/KH-UBND
- BM25 toàn văn: 80/2015/QH13, 01/2011/TT-BNV, 2888/QĐ-ĐHBK, 2155/QĐ-ĐHBK, 30/2020/NĐ-CP
- Vector: 1676/QĐ-ĐHĐN, 36/QĐ-ĐHĐN, 3536/QĐ-ĐHBK, 1605/QĐ-ĐHBK, 4768/QĐ-ĐHĐN
- Hybrid: 2888/QĐ-ĐHBK, 80/2015/QH13, 1214/QĐ-ĐHBK, 1616/QĐ-ĐHBK, 23/NQ-HĐT
- Hybrid + KG: 2888/QĐ-ĐHBK, 80/2015/QH13, 1214/QĐ-ĐHBK, 1616/QĐ-ĐHBK, 23/NQ-HĐT

**S09_amend_replace_chain** — Văn bản 3868/QĐ-ĐHBK đã trải qua bao nhiêu lần sửa đổi, thay thế?

- Cypher viết tay: 760/QĐ-ĐHBK, 2652/QĐ-ĐHBK, 2929/QĐ-ĐHBK
- BM25 (tiêu đề): 10/2026/NQ-CP, 800/QĐ-ĐHBK, 3237/QĐ-ĐHĐN, 4495/QĐ-ĐHĐN, 07/2024/TT-BGDĐT
- BM25 toàn văn: 5166/QĐ-ĐHĐN, 800/QĐ-ĐHBK, 80/2015/QH13, 107/QĐ-ĐHBK, 4495/QĐ-ĐHĐN
- Vector: 423/QĐ-ĐHBK, 3646/QĐ-ĐHBK, 542/QĐ-ĐHBK, 2244/QĐ-ĐHBK, 338/QĐ-ĐHBK
- Hybrid: 5166/QĐ-ĐHĐN, 542/QĐ-ĐHBK, 107/QĐ-ĐHBK, 22/NQ-HĐT, 800/QĐ-ĐHBK
- Hybrid + KG: 5166/QĐ-ĐHĐN, 542/QĐ-ĐHBK, 107/QĐ-ĐHBK, 22/NQ-HĐT, 800/QĐ-ĐHBK

**S10_replaced_by** — Quy chế công tác sinh viên cũ (42/2007/QĐ-BGDĐT) đã bị thay bằng văn bản nào?

- Cypher viết tay: 10/2016/TT-BGDĐT
- BM25 (tiêu đề): 05/2022/QĐ-TTg, 10/2026/NQ-CP, 2858/QĐ-ĐHĐN, 800/QĐ-ĐHBK, 07/2024/TT-BGDĐT
- BM25 toàn văn: 05/2022/QĐ-TTg, 10/2016/TT-BGDĐT, 1325/QĐ-BGDĐT, 5166/QĐ-ĐHĐN, 10/2026/TT-BGDĐT
- Vector: 10/2016/TT-BGDĐT, 1325/QĐ-BGDĐT, 2721/QĐ-ĐHĐN, 1001/QĐ-ĐHBK, 27/2009/TT-BGDĐT
- Hybrid: 10/2016/TT-BGDĐT, 1325/QĐ-BGDĐT, 1001/QĐ-ĐHBK, 2721/QĐ-ĐHĐN, 27/2009/TT-BGDĐT
- Hybrid + KG: 10/2016/TT-BGDĐT, 1325/QĐ-BGDĐT, 1001/QĐ-ĐHBK, 2721/QĐ-ĐHĐN, 27/2009/TT-BGDĐT

**S11_amends_target_still_active** — Những văn bản nào bị sửa đổi một phần nhưng tổng thể vẫn còn hiệu lực?

- Cypher viết tay: 05/NQ-HĐT, 10/2016/TT-BGDĐT, 1199/QĐ-ĐHBK, 1899/QĐ-ĐHĐN, 2231/QĐ-ĐHBK
- BM25 (tiêu đề): 10/2026/NQ-CP, 01/2011/TT-BNV, 754/QĐ-BGDĐT, 1060/QĐ-BGDĐT, 79/2020/NĐ-CP
- BM25 toàn văn: 01/2011/TT-BNV, 80/2015/QH13, 52/2019/QH14, 01/VBHN-VPQH, 47/2005/QH11
- Vector: 80/2015/QH13, 5166/QĐ-ĐHĐN, 10/2026/NQ-CP, 542/QĐ-ĐHBK, 338/QĐ-ĐHBK
- Hybrid: 80/2015/QH13, 5166/QĐ-ĐHĐN, 01/2011/TT-BNV, 542/QĐ-ĐHBK, 10/2026/NQ-CP
- Hybrid + KG: 80/2015/QH13, 5166/QĐ-ĐHĐN, 01/2011/TT-BNV, 542/QĐ-ĐHBK, 10/2026/NQ-CP

**S13_fulltext_doc_content** — Học phí năm nay quy định ở văn bản nào?

- Cypher viết tay: 81/2021/NĐ-CP, 3443/ĐHĐN-KHTC, 09/2016/TTLT-BGDĐT-BTC-BLĐTBXH, 97/2023/NĐ-CP, 4532/QĐ-ĐHBK
- BM25 (tiêu đề): 441/QĐ-ĐHBK, 80/2015/QH13, 09/2016/TTLT-BGDĐT-BTC-BLĐTBXH, 5166/QĐ-ĐHĐN, 2858/QĐ-ĐHĐN
- BM25 toàn văn: 80/2015/QH13, 5166/QĐ-ĐHĐN, 01/2011/TT-BNV, 09/2016/TTLT-BGDĐT-BTC-BLĐTBXH, 81/2021/NĐ-CP
- Vector: 97/2023/NĐ-CP, 81/2021/NĐ-CP, 09/2016/TTLT-BGDĐT-BTC-BLĐTBXH, 43/2019/QH14, 1340/QĐ-ĐHBK
- Hybrid: 81/2021/NĐ-CP, 09/2016/TTLT-BGDĐT-BTC-BLĐTBXH, 97/2023/NĐ-CP, 1340/QĐ-ĐHBK, 1214/QĐ-ĐHBK
- Hybrid + KG: 81/2021/NĐ-CP, 09/2016/TTLT-BGDĐT-BTC-BLĐTBXH, 97/2023/NĐ-CP, 1340/QĐ-ĐHBK, 1214/QĐ-ĐHBK

**S14_fulltext_article** — Điều nào quy định trách nhiệm thi hành?

- Cypher viết tay: 19/2024/TT-BGDDT#Điều 6, 1489/QD-DHDN#nd1#Điều 36, 3226/QD-DHDN#nd1#Điều 25, 69/2017/ND-CP#Điều 5, 232/2026/ND-CP#Điều 19
- BM25 (tiêu đề): 1489/QD-DHDN#nd1#Điều 36, 3226/QD-DHDN#nd1#Điều 25, 77/2021/ND-CP#Điều 8, 30/2020/ND-CP#Điều 38, 42/2013/ND-CP#Điều 29
- BM25 toàn văn: 3226/QD-DHDN#nd1#Điều 25, 1489/QD-DHDN#nd1#Điều 36, 77/2021/ND-CP#Điều 8, 30/2020/ND-CP#Điều 38, 42/2013/ND-CP#Điều 29
- Vector: 64/2014/ND-CP#Điều 24, 84/2020/ND-CP#Điều 12, 48/2023/ND-CP#Điều 3, 2721/QD-DHDN#nd1#Điều 24, 53/2022/ND-CP#Điều 30
- Hybrid: 28/2013/ND-CP#Điều 13, 84/2020/ND-CP#Điều 12, 1489/QD-DHDN#nd1#Điều 36, 64/2014/ND-CP#Điều 24, 79/2020/ND-CP#Điều 12
- Hybrid + KG: 28/2013/ND-CP#Điều 13, 84/2020/ND-CP#Điều 12, 1489/QD-DHDN#nd1#Điều 36, 64/2014/ND-CP#Điều 24, 79/2020/ND-CP#Điều 12

**S15_fulltext_content** — Có Nội quy nào liên quan không?

- Cypher viết tay: 176/QD-DHBK#nd1, 479/QD-DHBK#nd1
- BM25 (tiêu đề): 1779/QD-DHBK#nd1, 1829/QD-BGDDT#nd1, QD-DHDN#nd1, 36/QD-DHDN#nd1, 1676/QD-DHDN#nd1
- BM25 toàn văn: 1829/QD-BGDDT#nd1, 423/QD-DHBK#nd1, 1676/QD-DHDN#nd1, 5166/QD-DHDN#nd1, 36/QD-DHDN#nd1
- Vector: 3758/QD-DHDN#nd1, 16/2015/TT-BGDDT#nd1, 479/QD-DHBK#nd1, 2352/QD-DHBK#nd1, 1562/QD-DHBK#nd1
- Hybrid: 479/QD-DHBK#nd1, 16/2015/TT-BGDDT#nd1, 36/QD-DHDN#nd1, 423/QD-DHBK#nd1, 1676/QD-DHDN#nd1
- Hybrid + KG: 479/QD-DHBK#nd1, 16/2015/TT-BGDDT#nd1, 36/QD-DHDN#nd1, 423/QD-DHBK#nd1, 1676/QD-DHDN#nd1

**S16_hybrid_expand** — Những văn bản gốc thẩm quyền cao nào liên quan tới Đại học Đà Nẵng?

- Cypher viết tay: 10/2020/TT-BGDĐT, 32/CP, 08/2021/TT-BGDĐT, 115/2020/NĐ-CP, 99/2019/NĐ-CP
- BM25 (tiêu đề): 2858/QĐ-ĐHĐN, 80/2015/QH13, 542/QĐ-ĐHBK, 806/QĐ-ĐHBK, 18/2017/QĐ-TTg
- BM25 toàn văn: 2858/QĐ-ĐHĐN, 806/QĐ-ĐHBK, 1356/QĐ-ĐHĐN, 1779/QĐ-ĐHBK, 10/2026/TT-BGDĐT
- Vector: 5166/QĐ-ĐHĐN, 1356/QĐ-ĐHĐN, 1248/QĐ-ĐHĐN, 2858/QĐ-ĐHĐN, 1280/QĐ-ĐHĐN
- Hybrid: 2858/QĐ-ĐHĐN, 1356/QĐ-ĐHĐN, 5166/QĐ-ĐHĐN, 806/QĐ-ĐHBK, 08/NQ-HĐĐH
- Hybrid + KG: 2858/QĐ-ĐHĐN, 1356/QĐ-ĐHĐN, 5166/QĐ-ĐHĐN, 806/QĐ-ĐHBK, 08/NQ-HĐĐH

**S17_top_organizations** — Cơ quan nào ban hành nhiều văn bản nhất?

- Cypher viết tay: Bộ Giáo dục và Đào tạo, Đại học Đà Nẵng, Trường Đại học Bách khoa, Chính phủ, Quốc hội

**S19_multi_facet_and** — Văn bản nào về Công tác sinh viên, áp dụng cho Người học, do chính Trường ĐHBK ban hành?

- Cypher viết tay: 1001/QĐ-ĐHBK, 1414/QĐ-ĐHBK, 1345/QĐ-ĐHBK, 4511/QĐ-ĐHBK
- BM25 (tiêu đề): 2888/QĐ-ĐHBK, 1414/QĐ-ĐHBK, 2721/QĐ-ĐHĐN, 10/2026/NQ-CP, 1001/QĐ-ĐHBK
- BM25 toàn văn: 2721/QĐ-ĐHĐN, 10/2016/TT-BGDĐT, 1001/QĐ-ĐHBK, 2465/QĐ-ĐHBK, 1616/QĐ-ĐHBK
- Vector: 1001/QĐ-ĐHBK, 2231/QĐ-ĐHBK, 1214/QĐ-ĐHBK, 10/2016/TT-BGDĐT, 4420/QĐ-ĐHBK
- Hybrid: 1001/QĐ-ĐHBK, 10/2016/TT-BGDĐT, 1616/QĐ-ĐHBK, 2721/QĐ-ĐHĐN, 4420/QĐ-ĐHBK
- Hybrid + KG: 1001/QĐ-ĐHBK, 10/2016/TT-BGDĐT, 1616/QĐ-ĐHBK, 2721/QĐ-ĐHĐN, 4420/QĐ-ĐHBK

**S20_active_org_docs_that_amend** — Trong số văn bản còn hiệu lực do Trường ĐHBK ban hành, văn bản nào từng sửa đổi văn bản khác?

- Cypher viết tay: 2525/QĐ-ĐHBK, 22/NQ-HĐT, 1274/QĐ-ĐHBK, 1088/QĐ-ĐHBK
- BM25 (tiêu đề): 441/QĐ-ĐHBK, 80/2015/QH13, 01/2011/TT-BNV, 46/2021/TT-BGDĐT, 448/QĐ-ĐHBK
- BM25 toàn văn: 80/2015/QH13, 01/2011/TT-BNV, 1616/QĐ-ĐHBK, 30/2020/NĐ-CP, 5166/QĐ-ĐHĐN
- Vector: 338/QĐ-ĐHBK, 2465/QĐ-ĐHBK, 1616/QĐ-ĐHBK, 1478/QĐ-ĐHBK, 542/QĐ-ĐHBK
- Hybrid: 1616/QĐ-ĐHBK, 2465/QĐ-ĐHBK, 542/QĐ-ĐHBK, 2888/QĐ-ĐHBK, 338/QĐ-ĐHBK
- Hybrid + KG: 1616/QĐ-ĐHBK, 2465/QĐ-ĐHBK, 542/QĐ-ĐHBK, 2888/QĐ-ĐHBK, 338/QĐ-ĐHBK

**S21_gpa_rule** — Quy định tính điểm trung bình tích lũy và điểm trung bình học kỳ như thế nào?

- Cypher viết tay: 2231/QD-DHBK#nd1#Điều 4, 56/2026/TT-BGDDT#nd1#Điều 14, 2244/QD-DHBK#nd1#Điều 12, 2244/QD-DHBK#nd1#Điều 11, 2244/QD-DHBK#nd1#Điều 10
- BM25 (tiêu đề): 2244/QD-DHBK#nd1#Điều 9, 56/2026/TT-BGDDT#nd1#Điều 13, 8/2021/TT-BGDDT#nd1#Điều 10, 2244/QD-DHBK#nd1#Điều 10, 2244/QD-DHBK#nd1#Điều 11
- BM25 toàn văn: 2244/QD-DHBK#nd1#Điều 9, 56/2026/TT-BGDDT#nd1#Điều 13, 8/2021/TT-BGDDT#nd1#Điều 10, 2244/QD-DHBK#nd1#Điều 10, 2244/QD-DHBK#nd1#Điều 11
- Vector: 2244/QD-DHBK#nd1#Điều 11, 56/2026/TT-BGDDT#nd1#Điều 13, 8/2021/TT-BGDDT#nd1#Điều 10, 2367/QD-DHDN#nd1#Điều 4, 1779/QD-DHBK#nd1#Điều 6
- Hybrid: 56/2026/TT-BGDDT#nd1#Điều 13, 2244/QD-DHBK#nd1#Điều 11, 8/2021/TT-BGDDT#nd1#Điều 10, 2244/QD-DHBK#nd1#Điều 9, 1779/QD-DHBK#nd1#Điều 6
- Hybrid + KG: 56/2026/TT-BGDDT#nd1#Điều 13, 2244/QD-DHBK#nd1#Điều 11, 8/2021/TT-BGDDT#nd1#Điều 10, 2244/QD-DHBK#nd1#Điều 9, 1779/QD-DHBK#nd1#Điều 6

**S22_academic_warning** — Bao nhiêu điểm thì bị cảnh báo học tập hoặc buộc thôi học?

- Cypher viết tay: 2244/QD-DHBK#nd1#Điều 12, 56/2026/TT-BGDDT#nd1#Điều 14, 56/2026/TT-BGDDT#nd1#Điều 15, 2347/QD-DHBK#nd1#Điều 17, 2244/QD-DHBK#nd1#Điều 9
- BM25 (tiêu đề): 1779/QD-DHBK#nd1#Điều 7, 3875/QD-DHBK#nd1#Điều 29, 2244/QD-DHBK#nd1#Điều 12, 8/2021/TT-BGDDT#nd1#Điều 11, 56/2026/TT-BGDDT#nd1#Điều 14
- BM25 toàn văn: 1779/QD-DHBK#nd1#Điều 7, 3875/QD-DHBK#nd1#Điều 29, 2244/QD-DHBK#nd1#Điều 12, 8/2021/TT-BGDDT#nd1#Điều 11, 56/2026/TT-BGDDT#nd1#Điều 14
- Vector: 2244/QD-DHBK#nd1#Điều 12, 8/2021/TT-BGDDT#nd1#Điều 11, 56/2026/TT-BGDDT#nd1#Điều 14, 2244/QD-DHBK#nd1#Điều 13, 56/2026/TT-BGDDT#nd1#Điều 15
- Hybrid: 2244/QD-DHBK#nd1#Điều 12, 8/2021/TT-BGDDT#nd1#Điều 11, 56/2026/TT-BGDDT#nd1#Điều 14, 1779/QD-DHBK#nd1#Điều 7, 56/2026/TT-BGDDT#nd1#Điều 15
- Hybrid + KG: 2244/QD-DHBK#nd1#Điều 12, 8/2021/TT-BGDDT#nd1#Điều 11, 56/2026/TT-BGDDT#nd1#Điều 14, 1779/QD-DHBK#nd1#Điều 7, 56/2026/TT-BGDDT#nd1#Điều 15

**S23_valid_absence_procedure** — Nghỉ có lý do chính đáng thì làm thủ tục ở đâu?

- Cypher viết tay: 551/QD-DHDN#nd1#Điều 49, 3604/QD-DHBK#nd1#Điều 13, 10/2016/TT-BGDDT#nd1#Điều 10, 1001/QD-DHBK#nd1#Điều 20, 2721/QD-DHDN#nd1#Điều 14
- BM25 (tiêu đề): 259/2026/ND-CP#Điều 54, 551/QD-DHDN#nd1#Điều 49, 50/2022/ND-CP#Điều 4, 1/VBHN-VPQH#Điều 126, 100/2015/QH13#Điều 126
- BM25 toàn văn: 259/2026/ND-CP#Điều 54, 551/QD-DHDN#nd1#Điều 49, 50/2022/ND-CP#Điều 4, 1/VBHN-VPQH#Điều 126, 100/2015/QH13#Điều 126
- Vector: 1214/QD-DHBK#nd1#Điều 40, 2244/QD-DHBK#nd1#Điều 18, 8/2021/TT-BGDDT#nd1#Điều 15, 3604/QD-DHBK#nd1#Điều 13, 1199/QD-DHBK#nd1#Điều 21
- Hybrid: 3604/QD-DHBK#nd1#Điều 13, 2244/QD-DHBK#nd1#Điều 18, 551/QD-DHDN#nd1#Điều 49, 1974/QD-DHDN#nd1#Điều 8, 1214/QD-DHBK#nd1#Điều 40
- Hybrid + KG: 3604/QD-DHBK#nd1#Điều 13, 2244/QD-DHBK#nd1#Điều 18, 551/QD-DHDN#nd1#Điều 49, 1974/QD-DHDN#nd1#Điều 8, 1214/QD-DHBK#nd1#Điều 40

**S24_graduation_conditions** — Điều kiện để được xét công nhận tốt nghiệp là gì?

- Cypher viết tay: 2244/QD-DHBK#nd1#Điều 17, 56/2026/TT-BGDDT#nd1#Điều 17, 3875/QD-DHBK#nd1#Điều 23, 53/2026/TT-BGDDT#nd1#Điều 13, 1779/QD-DHBK#nd1#Điều 8
- BM25 (tiêu đề): 2244/QD-DHBK#nd1#Điều 17, 23/2016/TT-BGDDT#Điều 13, 8/2021/TT-BGDDT#nd1#Điều 14, 56/2026/TT-BGDDT#nd1#Điều 17, 1779/QD-DHBK#nd1#Điều 8
- BM25 toàn văn: 2244/QD-DHBK#nd1#Điều 17, 23/2016/TT-BGDDT#Điều 13, 8/2021/TT-BGDDT#nd1#Điều 14, 56/2026/TT-BGDDT#nd1#Điều 17, 1779/QD-DHBK#nd1#Điều 8
- Vector: 2244/QD-DHBK#nd1#Điều 17, 8/2021/TT-BGDDT#nd1#Điều 14, 56/2026/TT-BGDDT#nd1#Điều 17, 1214/QD-DHBK#nd1#Điều 29, QD-DHDN#nd1#Điều 4
- Hybrid: 2244/QD-DHBK#nd1#Điều 17, 8/2021/TT-BGDDT#nd1#Điều 14, 56/2026/TT-BGDDT#nd1#Điều 17, 23/2016/TT-BGDDT#Điều 13, 1214/QD-DHBK#nd1#Điều 29
- Hybrid + KG: 2244/QD-DHBK#nd1#Điều 17, 8/2021/TT-BGDDT#nd1#Điều 14, 56/2026/TT-BGDDT#nd1#Điều 17, 23/2016/TT-BGDDT#Điều 13, 1214/QD-DHBK#nd1#Điều 29

**S25_graduation_ranking** — Xếp hạng tốt nghiệp loại giỏi, xuất sắc cần bao nhiêu điểm?

- Cypher viết tay: 3875/QD-DHBK#nd1#Điều 24, 56/2026/TT-BGDDT#nd1#Điều 17, 2244/QD-DHBK#nd1#Điều 17
- BM25 (tiêu đề): 3875/QD-DHBK#nd1#Điều 24, 56/2026/TT-BGDDT#nd1#Điều 17, 1818/QD-BGDDT#nd1#Điều 19, 8/2021/TT-BGDDT#nd1#Điều 14, 3086/QD-BGDDT#nd1#Điều 12
- BM25 toàn văn: 3875/QD-DHBK#nd1#Điều 24, 56/2026/TT-BGDDT#nd1#Điều 17, 1818/QD-BGDDT#nd1#Điều 19, 8/2021/TT-BGDDT#nd1#Điều 14, 1818/QD-BGDDT#nd1#Điều 13
- Vector: 3875/QD-DHBK#nd1#Điều 24, 16/2015/TT-BGDDT#nd1#Điều 9, 3758/QD-DHDN#nd1#Điều 9, 2231/QD-DHBK#nd1#Điều 7, 1414/QD-DHBK#nd1#Điều 6
- Hybrid: 3875/QD-DHBK#nd1#Điều 24, 56/2026/TT-BGDDT#nd1#Điều 17, 8/2021/TT-BGDDT#nd1#Điều 14, 3758/QD-DHDN#nd1#Điều 9, 2244/QD-DHBK#nd1#Điều 17
- Hybrid + KG: 3875/QD-DHBK#nd1#Điều 24, 56/2026/TT-BGDDT#nd1#Điều 17, 8/2021/TT-BGDDT#nd1#Điều 14, 3758/QD-DHDN#nd1#Điều 9, 2244/QD-DHBK#nd1#Điều 17

**S26_foreign_language_exit** — Chuẩn đầu ra ngoại ngữ của sinh viên là gì?

- Cypher viết tay: 4511/QD-DHBK#nd1#Điều 6, 56/2026/TT-BGDDT#nd1#Điều 27, 4511/QD-DHBK#nd1#Điều 8, 1356/QD-DHDN#nd1#Điều 2, 4511/QD-DHBK#nd1#Điều 7
- BM25 (tiêu đề): 4511/QD-DHBK#nd1#Điều 6, 4511/QD-DHBK#nd1#Điều 3, 1345/QD-DHBK#nd1#Điều 7, 4511/QD-DHBK#nd1#Điều 4, 4511/QD-DHBK#nd1#Điều 9
- BM25 toàn văn: 4511/QD-DHBK#nd1#Điều 6, 4511/QD-DHBK#nd1#Điều 3, 1345/QD-DHBK#nd1#Điều 7, 4511/QD-DHBK#nd1#Điều 4, 4511/QD-DHBK#nd1#Điều 9
- Vector: 4511/QD-DHBK#nd1#Điều 6, 4511/QD-DHBK#nd1#Điều 4, 4511/QD-DHBK#nd1#Điều 11, 1345/QD-DHBK#nd1#Điều 3, 4511/QD-DHBK#nd1#Điều 5
- Hybrid: 4511/QD-DHBK#nd1#Điều 6, 4511/QD-DHBK#nd1#Điều 4, 4511/QD-DHBK#nd1#Điều 3, 1345/QD-DHBK#nd1#Điều 7, 4511/QD-DHBK#nd1#Điều 10
- Hybrid + KG: 4511/QD-DHBK#nd1#Điều 6, 4511/QD-DHBK#nd1#Điều 4, 4511/QD-DHBK#nd1#Điều 3, 1345/QD-DHBK#nd1#Điều 7, 4511/QD-DHBK#nd1#Điều 10

**S27_credit_load_limits** — Mỗi học kỳ được đăng ký tối thiểu và tối đa bao nhiêu tín chỉ?

- Cypher viết tay: 56/2026/TT-BGDDT#nd1#Điều 9, 53/2026/TT-BGDDT#nd1#Điều 4, 1214/QD-DHBK#nd1#Điều 42, 56/2026/TT-BGDDT#nd1#Điều 21, 3875/QD-DHBK#nd1#Điều 6
- BM25 (tiêu đề): 1779/QD-DHBK#nd1#Điều 3, 8/2021/TT-BGDDT#nd1#Điều 7, 56/2026/TT-BGDDT#nd1#Điều 9, 45/2019/QH14#Điều 91, 3240/QD-DHBK#nd1#Điều 2
- BM25 toàn văn: 1779/QD-DHBK#nd1#Điều 3, 8/2021/TT-BGDDT#nd1#Điều 7, 56/2026/TT-BGDDT#nd1#Điều 9, 45/2019/QH14#Điều 91, 3240/QD-DHBK#nd1#Điều 2
- Vector: 2244/QD-DHBK#nd1#Điều 7, 8/2021/TT-BGDDT#nd1#Điều 7, 56/2026/TT-BGDDT#nd1#Điều 9, 2244/QD-DHBK#nd1#Điều 2, 17/2021/TT-BGDDT#Điều 7
- Hybrid: 8/2021/TT-BGDDT#nd1#Điều 7, 56/2026/TT-BGDDT#nd1#Điều 9, 2244/QD-DHBK#nd1#Điều 7, 1779/QD-DHBK#nd1#Điều 3, 2244/QD-DHBK#nd1#Điều 2
- Hybrid + KG: 8/2021/TT-BGDDT#nd1#Điều 7, 56/2026/TT-BGDDT#nd1#Điều 9, 2244/QD-DHBK#nd1#Điều 7, 1779/QD-DHBK#nd1#Điều 3, 2244/QD-DHBK#nd1#Điều 2

**S28_double_degree** — Điều kiện để học cùng lúc hai chương trình là gì?

- Cypher viết tay: 2244/QD-DHBK#nd1#Điều 21, 56/2026/TT-BGDDT#nd1#Điều 21, 1214/QD-DHBK#nd1#Điều 42, 4511/QD-DHBK#nd1#Điều 5, 10/2016/TT-BGDDT#nd1#Điều 5
- BM25 (tiêu đề): 8/2021/TT-BGDDT#nd1#Điều 18, 2244/QD-DHBK#nd1#Điều 21, 56/2026/TT-BGDDT#nd1#Điều 21, 1214/QD-DHBK#nd1#Điều 42, 56/2026/TT-BGDDT#nd1#Điều 22
- BM25 toàn văn: 8/2021/TT-BGDDT#nd1#Điều 18, 2244/QD-DHBK#nd1#Điều 21, 56/2026/TT-BGDDT#nd1#Điều 21, 1214/QD-DHBK#nd1#Điều 42, 56/2026/TT-BGDDT#nd1#Điều 22
- Vector: 2244/QD-DHBK#nd1#Điều 21, 1214/QD-DHBK#nd1#Điều 42, 56/2026/TT-BGDDT#nd1#Điều 21, 8/2021/TT-BGDDT#nd1#Điều 18, 1248/QD-DHDN#nd1#Điều 20
- Hybrid: 2244/QD-DHBK#nd1#Điều 21, 8/2021/TT-BGDDT#nd1#Điều 18, 1214/QD-DHBK#nd1#Điều 42, 56/2026/TT-BGDDT#nd1#Điều 21, 1248/QD-DHDN#nd1#Điều 20
- Hybrid + KG: 2244/QD-DHBK#nd1#Điều 21, 8/2021/TT-BGDDT#nd1#Điều 18, 1214/QD-DHBK#nd1#Điều 42, 56/2026/TT-BGDDT#nd1#Điều 21, 1248/QD-DHDN#nd1#Điều 20

**S29_merit_scholarship** — Sinh viên được xét học bổng khuyến khích học tập như thế nào?

- Cypher viết tay: 3536/QD-DHBK#nd1#Điều 11, 84/2020/ND-CP#Điều 8, 28/VBHN-BGDDT#Điều 1, 28/VBHN-BGDDT#Điều 2, 1414/QD-DHBK#Điều 2
- BM25 (tiêu đề): 84/2020/ND-CP#Điều 8, 28/VBHN-BGDDT#Điều 1, 28/VBHN-BGDDT#Điều 2, 3536/QD-DHBK#nd1#Điều 11, 1414/QD-DHBK#Điều 2
- BM25 toàn văn: 84/2020/ND-CP#Điều 8, 28/VBHN-BGDDT#Điều 1, 28/VBHN-BGDDT#Điều 2, 3536/QD-DHBK#nd1#Điều 11, 1414/QD-DHBK#Điều 2
- Vector: 28/VBHN-BGDDT#Điều 2, 84/2020/ND-CP#Điều 8, 28/VBHN-BGDDT#Điều 1, 1414/QD-DHBK#nd1#Điều 7, 1414/QD-DHBK#nd1#Điều 3
- Hybrid: 84/2020/ND-CP#Điều 8, 28/VBHN-BGDDT#Điều 2, 28/VBHN-BGDDT#Điều 1, 3536/QD-DHBK#nd1#Điều 11, 1414/QD-DHBK#nd1#Điều 3
- Hybrid + KG: 84/2020/ND-CP#Điều 8, 28/VBHN-BGDDT#Điều 2, 28/VBHN-BGDDT#Điều 1, 3536/QD-DHBK#nd1#Điều 11, 1414/QD-DHBK#nd1#Điều 3

**S30_exam_impersonation** — Thi hộ hoặc nhờ người thi hộ bị xử lý kỷ luật thế nào?

- Cypher viết tay: 2367/QD-DHDN#nd1#Điều 8, 3875/QD-DHBK#nd1#Điều 33, 29/QD-DHBK#nd1#Điều 4, 56/2026/TT-BGDDT#nd1#Điều 24, 3707/QD-DHBK#Điều 1
- BM25 (tiêu đề): 2367/QD-DHDN#nd1#Điều 8, 58/2014/QH13#Điều 35, 23/2021/TT-BGDDT#nd1#Điều 16, 3875/QD-DHBK#nd1#Điều 33, 1/VBHN-VPQH#Điều 336
- BM25 toàn văn: 2367/QD-DHDN#nd1#Điều 8, 58/2014/QH13#Điều 35, 3875/QD-DHBK#nd1#Điều 33, 23/2021/TT-BGDDT#nd1#Điều 16, 100/2015/QH13#Điều 336
- Vector: 2367/QD-DHDN#nd1#Điều 8, 8/2021/TT-BGDDT#nd1#Điều 20, 1274/QD-DHBK#Điều 1, 3707/QD-DHBK#Điều 1, 1980/QD-DHBK#nd1#Điều 29
- Hybrid: 2367/QD-DHDN#nd1#Điều 8, 8/2021/TT-BGDDT#nd1#Điều 20, 3875/QD-DHBK#nd1#Điều 33, 23/2021/TT-BGDDT#nd1#Điều 16, 29/QD-DHBK#nd1#Điều 4
- Hybrid + KG: 2367/QD-DHDN#nd1#Điều 8, 8/2021/TT-BGDDT#nd1#Điều 20, 3875/QD-DHBK#nd1#Điều 33, 23/2021/TT-BGDDT#nd1#Điều 16, 29/QD-DHBK#nd1#Điều 4

**S31_tuition_exemption** — Đối tượng nào được miễn, giảm học phí?

- Cypher viết tay: 81/2021/ND-CP#Điều 15, 81/2021/ND-CP#Điều 16, 81/2021/ND-CP#Điều 20, 81/2021/ND-CP#Điều 19, 81/2021/ND-CP#Điều 21
- BM25 (tiêu đề): 81/2021/ND-CP#Điều 20, 81/2021/ND-CP#Điều 15, 81/2021/ND-CP#Điều 16, 81/2021/ND-CP#Điều 21, 9/2016/TTLT-BGDDT-BTC-BLDTBXH#Điều 6
- BM25 toàn văn: 81/2021/ND-CP#Điều 20, 81/2021/ND-CP#Điều 15, 81/2021/ND-CP#Điều 16, 81/2021/ND-CP#Điều 21, 9/2016/TTLT-BGDDT-BTC-BLDTBXH#Điều 6
- Vector: 81/2021/ND-CP#Điều 15, 9/2016/TTLT-BGDDT-BTC-BLDTBXH#Điều 4, 81/2021/ND-CP#Điều 20, 81/2021/ND-CP#Điều 16, 81/2021/ND-CP#Điều 19
- Hybrid: 81/2021/ND-CP#Điều 15, 81/2021/ND-CP#Điều 20, 81/2021/ND-CP#Điều 16, 81/2021/ND-CP#Điều 19, 9/2016/TTLT-BGDDT-BTC-BLDTBXH#Điều 6
- Hybrid + KG: 81/2021/ND-CP#Điều 15, 81/2021/ND-CP#Điều 20, 81/2021/ND-CP#Điều 16, 81/2021/ND-CP#Điều 19, 9/2016/TTLT-BGDDT-BTC-BLDTBXH#Điều 6

