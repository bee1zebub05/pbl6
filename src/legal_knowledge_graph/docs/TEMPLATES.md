# Kho template Cypher của chatbot

Tệp này được sinh tự động bằng `python run.py lkg templates` từ `core/graph_query/templates/` — không sửa tay.

**68 template**, 56 action (cộng `other` -> agent).

| Mức | Ý nghĩa | Số template |
|---|---|---|
| 1 | tra cứu 1 bước | 17 |
| 2 | nhiều quan hệ / nhiều điều kiện | 30 |
| 3 | nhiều bước, full-text có lọc | 14 |
| 4 | chuỗi nhiều tầng, kết hợp | 5 |
| 5 | tổng hợp toàn graph | 2 |

Mỗi nhóm sắp từ đơn giản tới phức tạp; cột *Người hay hỏi* cho biết câu hỏi phổ biến với ai.
Slot in đậm là bắt buộc. Ví dụ tham số lấy từ dữ liệu thật và được kiểm bằng `tests/test_templates_live.py`.

## Tra cứu danh sách văn bản

| # | Template | Mức | Action | Slot | Người hay hỏi | Ví dụ câu hỏi |
|---|---|---|---|---|---|---|
| 1 | `TPL_DOCS_BY_ORG_STATUS` | 1 | `list_documents` | **org**, limit, status | sinh viên, phụ huynh, giảng viên | Văn bản nào do Trường Đại học Bách khoa ban hành còn hiệu lực? |
| 2 | `TPL_DOCS_BY_TOPIC` | 1 | `list_documents` | **topic**, limit, status | sinh viên, phụ huynh, giảng viên | Văn bản nào thuộc lĩnh vực Đào tạo? |
| 3 | `TPL_DOCS_BY_TARGET_GROUP` | 1 | `list_documents` | **target_group**, limit, status | sinh viên, phụ huynh, giảng viên | Văn bản nào áp dụng cho sinh viên? |
| 4 | `TPL_DOCS_BY_TYPE` | 1 | `list_documents` | **doc_type**, limit, status | giảng viên, cán bộ quản lý/pháp chế | Trong kho có những Luật nào? |
| 5 | `TPL_DOCS_BY_YEAR` | 1 | `list_documents` | **year**, limit, status | giảng viên, cán bộ quản lý/pháp chế | Năm 2024 có những văn bản nào được ban hành? |
| 6 | `TPL_DOCS_RECENT` | 1 | `recent_documents` | limit | sinh viên, phụ huynh, giảng viên | Có văn bản nào mới ban hành gần đây không? |
| 7 | `TPL_DOCS_BY_SIGNER` | 1 | `documents_signed_by` | **person**, limit | giảng viên, cán bộ quản lý/pháp chế | Thầy Đoàn Quang Vinh đã ký những văn bản nào? |
| 8 | `TPL_DOCS_SIGNED_BY_POSITION` | 2 | `documents_signed_by` | **position**, limit, org | giảng viên, cán bộ quản lý/pháp chế | Những văn bản nào do Hiệu trưởng ký? |
| 9 | `TPL_DOCS_FILTERED` | 2 | `list_documents` | doc_type, limit, org, status, target_group, topic, year | sinh viên, phụ huynh, giảng viên | Văn bản về Công tác sinh viên do Trường Đại học Bách khoa ban hành |
| 10 | `TPL_DOCS_SINCE_YEAR` | 2 | `list_documents` | **since_year**, limit, org, status, topic | giảng viên, cán bộ quản lý/pháp chế | Từ năm 2023 đến nay ĐHBK ban hành những văn bản nào? |
| 11 | `TPL_COUNT_DOCS` | 2 | `count_documents` | doc_type, org, status, target_group, topic, year | sinh viên, phụ huynh, giảng viên | ĐHBK có bao nhiêu văn bản về Đào tạo? |
| 12 | `TPL_DOCUMENT_FULLTEXT_SEARCH` | 2 | `search_documents` | **phrase**, limit | sinh viên, phụ huynh, giảng viên | Văn bản nào có tên chứa 'Chiến lược'? |
| 13 | `TPL_LATEST_DOC_ABOUT` | 2 | `latest_document_about` | **phrase**, limit | sinh viên, phụ huynh, giảng viên | Quy định mới nhất về học bổng là văn bản nào? |
| 14 | `TPL_DOCS_MENTIONING_ORG` | 2 | `documents_mentioning_org` | **org**, limit | giảng viên, cán bộ quản lý/pháp chế | Văn bản nào giao nhiệm vụ cho Phòng Tổ chức Hành chính? |
| 15 | `TPL_SUPERSEDED_DOCS` | 3 | `superseded_documents` | limit, org | giảng viên, cán bộ quản lý/pháp chế | Những văn bản nào của ĐHBK đã bị thay thế? |

## Hỏi về một văn bản cụ thể

| # | Template | Mức | Action | Slot | Người hay hỏi | Ví dụ câu hỏi |
|---|---|---|---|---|---|---|
| 16 | `TPL_DOCUMENT_DETAIL` | 1 | `document_detail` | **doc_number** | sinh viên, phụ huynh, giảng viên | Văn bản 4511/QĐ-ĐHBK nói gì? |
| 17 | `TPL_DOC_STATUS` | 1 | `document_status` | **doc_number** | sinh viên, phụ huynh, giảng viên | Quyết định 1345/QĐ-ĐHBK còn hiệu lực không? |
| 18 | `TPL_DOC_SIGNER` | 1 | `document_signer` | **doc_number** | sinh viên, phụ huynh, giảng viên | Ai ký Quyết định 1001/QĐ-ĐHBK? |
| 19 | `TPL_DOC_TOPICS_TARGETS` | 1 | `document_applies_to` | **doc_number** | sinh viên, phụ huynh, giảng viên | Quy định 4511/QĐ-ĐHBK áp dụng cho ai? |
| 20 | `TPL_DOC_ISSUER_HIERARCHY` | 2 | `document_issuer` | **doc_number** | phụ huynh, giảng viên | Văn bản 4511/QĐ-ĐHBK do cơ quan nào ban hành, cấp nào? |
| 21 | `TPL_DOC_ARTICLE_LIST` | 2 | `document_articles` | **doc_number**, limit | sinh viên, giảng viên | Quy chế 1001/QĐ-ĐHBK gồm những Điều nào? |
| 22 | `TPL_DOC_ARTICLE_TEXT` | 2 | `article_text` | **article_number**, **doc_number** | sinh viên, phụ huynh, giảng viên | Điều 5 của Quyết định 1001/QĐ-ĐHBK nói gì? |
| 23 | `TPL_DOC_SCOPE_ARTICLES` | 2 | `document_scope` | **doc_number** | sinh viên, phụ huynh, giảng viên | Phạm vi điều chỉnh của 08/2021/TT-BGDĐT là gì? |
| 24 | `TPL_DOC_IMPLEMENTATION_CLAUSES` | 2 | `document_implementation` | **doc_number** | giảng viên, cán bộ quản lý/pháp chế | Văn bản 4511/QĐ-ĐHBK có hiệu lực từ khi nào, ai chịu trách nhiệm thi hành? |
| 25 | `TPL_DOC_PROMULGATED_CONTENT` | 2 | `document_contents` | **doc_number** | sinh viên, giảng viên | Quyết định 1001/QĐ-ĐHBK ban hành kèm theo quy chế gì? |
| 26 | `TPL_DOC_MENTIONED_ORGS` | 2 | `document_mentions` | **doc_number**, limit | giảng viên, cán bộ quản lý/pháp chế | Văn bản 4757/QĐ-ĐHĐN giao trách nhiệm cho những đơn vị nào? |
| 27 | `TPL_DOC_ARTICLE_SEARCH` | 3 | `search_articles` | **doc_number**, **phrase**, limit | sinh viên, phụ huynh, giảng viên | Trong Quy chế 1001/QĐ-ĐHBK, điều nào nói về khen thưởng? |

## Quan hệ giữa các văn bản

| # | Template | Mức | Action | Slot | Người hay hỏi | Ví dụ câu hỏi |
|---|---|---|---|---|---|---|
| 28 | `TPL_DOC_LEGAL_BASIS` | 2 | `document_legal_basis` | **doc_number**, limit | giảng viên, cán bộ quản lý/pháp chế | Quyết định 4511/QĐ-ĐHBK căn cứ vào những văn bản nào? |
| 29 | `TPL_DOC_REFERENCES` | 2 | `document_references` | **doc_number**, limit | giảng viên, cán bộ quản lý/pháp chế | Văn bản 1214/QĐ-ĐHBK có nhắc tới văn bản nào khác? |
| 30 | `TPL_DOC_CITED_BY` | 2 | `document_cited_by` | **doc_number**, limit | giảng viên, cán bộ quản lý/pháp chế | Những văn bản nào căn cứ vào Thông tư 08/2021/TT-BGDĐT? |
| 31 | `TPL_REPLACED_BY` | 2 | `replaced_by` | **doc_number**, limit | sinh viên, phụ huynh, giảng viên | Văn bản nào đã thay thế 42/2007/QĐ-BGDĐT? |
| 32 | `TPL_DOC_AMENDED_BY` | 2 | `amended_by` | **doc_number**, limit | sinh viên, giảng viên, cán bộ quản lý/pháp chế | Thông tư 10/2016/TT-BGDĐT đã được sửa đổi bởi văn bản nào? |
| 33 | `TPL_DOC_REPEALED_BY` | 2 | `repealed_by` | **doc_number**, limit | giảng viên, cán bộ quản lý/pháp chế | Thông tư 30/2023/TT-BGDĐT bị bãi bỏ bởi văn bản nào? |
| 34 | `TPL_DOC_WHAT_IT_AMENDS` | 2 | `what_it_amends` | **doc_number**, limit | giảng viên, cán bộ quản lý/pháp chế | Quyết định 1088/QĐ-ĐHBK sửa đổi văn bản nào? |
| 35 | `TPL_DOC_WHAT_IT_REPEALS` | 2 | `what_it_repeals` | **doc_number**, limit | giảng viên, cán bộ quản lý/pháp chế | Thông tư 49/2026/TT-BGDĐT bãi bỏ những văn bản nào? |
| 36 | `TPL_AMEND_REPLACE_CHAIN` | 3 | `what_it_replaced` | **doc_number**, limit | giảng viên, cán bộ quản lý/pháp chế | 4511/QĐ-ĐHBK đã thay thế những văn bản nào? |
| 37 | `TPL_DOC_LATEST_VERSION` | 3 | `latest_version` | **doc_number** | sinh viên, phụ huynh, giảng viên | Bản mới nhất thay cho 2929/QĐ-ĐHBK là văn bản nào? |
| 38 | `TPL_DOC_VERSION_HISTORY` | 3 | `version_history` | **doc_number**, limit | giảng viên, cán bộ quản lý/pháp chế | Lịch sử các lần sửa đổi, thay thế của 2652/QĐ-ĐHBK |
| 39 | `TPL_DOC_ALL_RELATIONS` | 3 | `document_relations` | **doc_number** | giảng viên, cán bộ quản lý/pháp chế | Văn bản 4511/QĐ-ĐHBK liên quan tới những văn bản nào? |
| 40 | `TPL_DOC_LEGAL_BASIS_CHAIN` | 4 | `legal_basis_chain` | **doc_number**, limit | giảng viên, cán bộ quản lý/pháp chế | Quyết định 1092/QĐ-ĐHBK suy cho cùng dựa trên Luật nào? |
| 41 | `TPL_DOC_RELATED` | 4 | `related_documents` | **doc_number**, limit | sinh viên, giảng viên | Ngoài 4511/QĐ-ĐHBK còn văn bản nào liên quan cần đọc thêm? |
| 42 | `TPL_DOCS_SHARING_BASIS` | 5 | `documents_sharing_basis` | **doc_number**, limit | cán bộ quản lý/pháp chế | Văn bản nào có cùng căn cứ pháp lý với 4511/QĐ-ĐHBK? |

## Tìm theo nội dung quy định

| # | Template | Mức | Action | Slot | Người hay hỏi | Ví dụ câu hỏi |
|---|---|---|---|---|---|---|
| 43 | `TPL_NORMATIVE_CONTENT_BY_TYPE` | 1 | `list_contents` | **content_type**, limit, status | sinh viên, giảng viên | Có những Quy chế nào còn hiệu lực? |
| 44 | `TPL_CONTENT_TITLE_SEARCH` | 2 | `search_contents` | **phrase**, limit | sinh viên, phụ huynh, giảng viên | Quy chế công tác sinh viên là văn bản nào? |
| 45 | `TPL_ARTICLE_FULLTEXT_SEARCH` | 3 | `search_articles` | **phrase**, limit | sinh viên, phụ huynh, giảng viên | Điều nào quy định về học bổng khuyến khích học tập? |
| 46 | `TPL_ARTICLE_SEARCH_ACTIVE` | 3 | `search_articles` | **phrase**, **status**, limit | sinh viên, phụ huynh, giảng viên | Quy định hiện hành về học phí nằm ở điều nào? |
| 47 | `TPL_ARTICLE_SEARCH_BY_ORG` | 3 | `search_articles` | **org**, **phrase**, limit | sinh viên, phụ huynh, giảng viên | Trường Đại học Bách khoa quy định gì về ký túc xá? |
| 48 | `TPL_ARTICLE_SEARCH_FOR_GROUP` | 3 | `search_articles` | **phrase**, **target_group**, limit | sinh viên, phụ huynh, giảng viên | Sinh viên bị kỷ luật thế nào? |
| 49 | `TPL_ARTICLE_SEARCH_BY_TOPIC` | 3 | `search_articles` | **phrase**, **topic**, limit | giảng viên, cán bộ quản lý/pháp chế | Trong lĩnh vực Tài chính, kế toán, điều nào nói về công tác phí? |
| 50 | `TPL_HYBRID_FULLTEXT_EXPAND` | 4 | `legal_basis` | **phrase**, limit | giảng viên, cán bộ quản lý/pháp chế | Những văn bản gốc thẩm quyền cao nào làm căn cứ cho các văn bản về Đại học Đà Nẵng? |

## Người ký và cơ quan

| # | Template | Mức | Action | Slot | Người hay hỏi | Ví dụ câu hỏi |
|---|---|---|---|---|---|---|
| 51 | `TPL_TOP_ORGS_BY_DOC_COUNT` | 1 | `rank_orgs` | limit | phụ huynh, giảng viên | Cơ quan nào ban hành nhiều văn bản nhất? |
| 52 | `TPL_PERSON_PROFILE` | 1 | `person_profile` | **person** | sinh viên, phụ huynh, giảng viên | Đoàn Quang Vinh là ai, giữ chức vụ gì? |
| 53 | `TPL_TOP_SIGNERS` | 2 | `rank_signers` | limit, org | giảng viên, cán bộ quản lý/pháp chế | Ai ký nhiều văn bản nhất? |
| 54 | `TPL_SIGNERS_OF_ORG` | 2 | `org_signers` | **org**, limit | giảng viên, cán bộ quản lý/pháp chế | Những ai đã từng ký văn bản của Trường Đại học Bách khoa? |
| 55 | `TPL_ORG_PROFILE` | 2 | `org_profile` | **org** | phụ huynh, giảng viên | Đại học Đà Nẵng ban hành bao nhiêu văn bản, chủ yếu về lĩnh vực gì? |
| 56 | `TPL_ORG_SUBUNITS` | 2 | `org_structure` | **org** | phụ huynh, giảng viên | Đại học Đà Nẵng gồm những đơn vị trực thuộc nào trong dữ liệu? |
| 57 | `TPL_ORG_TOPIC_BREAKDOWN` | 3 | `org_topic_breakdown` | **org** | giảng viên, cán bộ quản lý/pháp chế | ĐHBK ban hành văn bản về những lĩnh vực nào, mỗi lĩnh vực bao nhiêu? |

## Thống kê và phân tích toàn kho

| # | Template | Mức | Action | Slot | Người hay hỏi | Ví dụ câu hỏi |
|---|---|---|---|---|---|---|
| 58 | `TPL_DOC_DISTRIBUTION_BY_STATUS` | 1 | `status_distribution` | — | phụ huynh, giảng viên | Có bao nhiêu văn bản còn hiệu lực, bao nhiêu hết hiệu lực? |
| 59 | `TPL_DOC_COUNT_BY_TYPE` | 1 | `stats_by_type` | — | phụ huynh, giảng viên | Kho có bao nhiêu văn bản mỗi loại? |
| 60 | `TPL_DOC_COUNT_BY_TOPIC` | 1 | `stats_by_topic` | org | sinh viên, phụ huynh, giảng viên | Lĩnh vực nào có nhiều văn bản nhất? |
| 61 | `TPL_DOC_COUNT_BY_YEAR` | 2 | `stats_by_year` | org, topic | giảng viên, cán bộ quản lý/pháp chế | Mỗi năm ĐHBK ban hành bao nhiêu văn bản? |
| 62 | `TPL_DOC_COUNT_BY_AUTHORITY_LEVEL` | 2 | `stats_by_authority_level` | — | giảng viên, cán bộ quản lý/pháp chế | Kho có bao nhiêu văn bản cấp trường, bao nhiêu văn bản cấp Bộ? |
| 63 | `TPL_CITATION_RELATION_COUNTS` | 2 | `relation_counts` | — | cán bộ quản lý/pháp chế, quản trị dữ liệu | Có bao nhiêu quan hệ trích dẫn trong đồ thị? |
| 64 | `TPL_AMENDS_TARGET_STILL_ACTIVE` | 3 | `amended_still_active` | limit, status | giảng viên, cán bộ quản lý/pháp chế | Những văn bản nào bị sửa đổi nhưng vẫn còn hiệu lực? |
| 65 | `TPL_MOST_CITED_DOCS` | 3 | `most_cited` | limit | giảng viên, cán bộ quản lý/pháp chế | Văn bản nào được căn cứ nhiều nhất? |
| 66 | `TPL_MISSING_CITED_DOCS` | 4 | `missing_documents` | limit | cán bộ quản lý/pháp chế, quản trị dữ liệu | Văn bản nào hay được nhắc tới nhưng kho chưa có? |
| 67 | `TPL_LONGEST_REPLACEMENT_CHAINS` | 4 | `longest_chains` | limit | cán bộ quản lý/pháp chế, quản trị dữ liệu | Quy định nào đã được thay thế, sửa đổi qua nhiều đời nhất? |
| 68 | `TPL_ORG_CITATION_FLOW` | 5 | `org_citation_flow` | limit, org | cán bộ quản lý/pháp chế, quản trị dữ liệu | Văn bản của ĐHBK chủ yếu căn cứ vào văn bản của cơ quan nào? |
