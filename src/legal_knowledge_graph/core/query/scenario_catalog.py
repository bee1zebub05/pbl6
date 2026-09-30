"""
20 kịch bản Cypher chạy trên DATA THẬT (`data/clean/json/v2`, 403 Document
thật + 8.814 Article) — KHÁC mục đích với 2 catalog kia:

- `catalog.py`           : regression cơ chế trên `samples/` (17 mẫu cố định).
- `benchmark_catalog.py` : đo hiệu năng thuần trên data thật, tự nhận CHƯA
  qua thẩm định là đại diện đúng nhu cầu truy vấn thật.
- File này (`scenario_catalog.py`): 20 câu hỏi đã CHỌN LỌC theo góc nhìn
  người dùng thật (giảng viên/sinh viên/phụ huynh/cán bộ quản lý dữ liệu),
  sắp theo 5 mức độ phức tạp Cypher tăng dần (dễ -> khó), mỗi câu có ground
  truth (`expected_ids`) khi kết quả xác định rõ ràng — dùng để CHẤM ĐIỂM
  (precision/recall/F1, xem `runner.py::_score_ids()`), không chỉ đếm dòng.

Phần lớn số liệu/Cypher lấy lại từ 2 nguồn ĐÃ VERIFY THẬT thay vì bịa case
mới: `GRAPHREPORT.md` (số liệu graph) và `EXAMPLE.md` (20 câu hỏi mẫu theo
persona, có kết quả thật). `expected_ids` ở đây được chạy lại TRỰC TIẾP
trên graph thật lúc viết file này (không suy đoán từ 2 tài liệu trên).

GIỚI HẠN CÓ CHỦ ĐÍCH: Mức 4 (fulltext/hybrid) và phần ranking/distribution
của Mức 5 để `expected_ids=None` — độ liên quan của kết quả fulltext/hybrid
vốn cần NGƯỜI thẩm định thủ công (câu nào thực sự "liên quan" là phán đoán
chủ quan, không phải sự thật khách quan như 1 cạnh quan hệ có tồn tại hay
không) — KHÔNG tự bịa ground-truth chưa qua thẩm định. `_score_ids()` đã
sẵn sàng nhận `expected_ids` cho các case này khi được gán tay sau này
(lúc thật sự triển khai so sánh BM25), không cần sửa cơ chế chấm điểm.
"""

from __future__ import annotations

from .catalog import Query, hybrid_expand_cypher

QUERIES: list[Query] = [
    # ============================================================
    # Mức 1 — 1-hop đơn giản (1 MATCH + 1 điều kiện lọc, có index)
    # ============================================================

    # Tình huống (giảng viên): "Trường Đại học Bách khoa còn văn bản nào
    # đang có hiệu lực?" — câu hỏi phổ biến nhất, 1 tổ chức + 1 trạng thái.
    Query(
        name="S01_docs_by_org_active",
        cypher="""
            MATCH (d:Document)-[:ISSUED_BY]->(:Organization {orgId: 'truong_dai_hoc_bach_khoa'})
            WHERE d.status = 'CON_HIEU_LUC'
            RETURN d.documentNumber AS documentNumber, d.title AS title
            ORDER BY d.issueDate DESC
        """,
        expected_rows=62,
        kind="lookup",
        note="62 văn bản còn hiệu lực của Trường ĐHBK — khớp EXAMPLE.md câu 1 (đã verify thật).",
        id_field="documentNumber",
        expected_ids=frozenset({
            "1394/QĐ-ĐHBK", "1216/QĐ-ĐHBK", "1199/QĐ-ĐHBK", "5247/QĐ-ĐHBK", "2525/QĐ-ĐHBK",
            "441/QĐ-ĐHBK", "1414/QĐ-ĐHBK", "199/QĐ-ĐHBK", "806/QĐ-ĐHBK", "3536/QĐ-ĐHBK",
            "338/QĐ-ĐHBK", "1177/QĐ-ĐHBK", "2155/QĐ-ĐHBK", "5780/QĐ-ĐHBK", "1001/QĐ-ĐHBK",
            "2673/QĐ-ĐHBK", "1838/QĐ-ĐHBK", "2479/QĐ-ĐHBK", "800/QĐ-ĐHBK", "4532/QĐ-ĐHBK",
            "1404/QĐ-ĐHBK", "2465/QĐ-ĐHBK", "2522/ĐHBK-TCHC", "1250/QĐ-ĐHBK", "1340/QĐ-ĐHBK",
            "3492/QĐ-ĐHBK", "1980/QĐ-ĐHBK", "1616/QĐ-ĐHBK", "1562/QĐ-ĐHBK", "493/QĐ-ĐHBK",
            "542/QĐ-ĐHBK", "1606/HD-ĐHBK", "4511/QĐ-ĐHBK", "107/QĐ-ĐHBK", "1088/QĐ-ĐHBK",
            "2352/QĐ-ĐHBK", "3521/QĐ-ĐHBK", "3092/QĐ-ĐHBK", "1690/QĐ-ĐHBK", "448/QĐ-ĐHBK",
            "05/NQ-HĐT", "479/QĐ-ĐHBK", "334/QĐ-ĐHBK", "2971/QĐ-ĐHBK", "1478/QĐ-ĐHBK",
            "2266/QĐ-ĐHBK", "3868/QĐ-ĐHBK", "2888/QĐ-ĐHBK", "2533/QĐ-ĐHBK", "3707/QĐ-ĐHBK",
            "730/QĐ-ĐHBK", "22/NQ-HĐT", "2569/QĐ-ĐHBK", "1475/QĐ-ĐHBK", "771/QĐ-ĐHBK",
            "23/NQ-HĐT", "1092/QĐ-ĐHBK", "1605/QĐ-ĐHBK", "1474/QĐ-ĐHBK", "3819/QĐ-ĐHBK",
            "2061/QĐ-ĐHBK", "1274/QĐ-ĐHBK",
        }),
    ),

    # Tình huống (sinh viên): "Văn bản nào áp dụng cho người học (sinh
    # viên)?" — lọc theo nhóm đối tượng áp dụng, không quan tâm hiệu lực.
    Query(
        name="S02_docs_by_target_group",
        cypher="""
            MATCH (d:Document)-[:APPLIES_TO]->(:TargetGroup {targetGroupId: 'nguoi_hoc'})
            RETURN d.documentNumber AS documentNumber, d.title AS title
        """,
        expected_rows=51,
        kind="lookup",
        note="51 văn bản áp dụng cho 'Người học' — khớp EXAMPLE.md câu 2.",
        id_field="documentNumber",
        expected_ids=frozenset({
            "11/2020/TT-BGDĐT", "10/2016/TT-BGDĐT", "2347/QĐ-ĐHBK", "1899/QĐ-ĐHĐN", "2352/QĐ-ĐHBK",
            "175/QĐ-ĐHBK", "30/2018/TT-BGDĐT", "3226/QĐ-ĐHĐN", "1980/QĐ-ĐHBK", "1414/QĐ-ĐHBK",
            "1404/QĐ-ĐHBK", "2721/QĐ-ĐHĐN", "35/2011/TT-BGDĐT", "3154/QĐ-ĐHĐN", "81/2021/NĐ-CP",
            "3604/QĐ-ĐHBK", "29/2023/TT-BGDĐT", "1395/QĐ-ĐHBK", "09/2016/TTLT-BGDĐT-BTC-BLĐTBXH",
            "840/QĐ-ĐHBK", "107/QĐ-ĐHBK", "199/QĐ-ĐHBK", "07/2026/TT-BGDĐT", "2268/QĐ-ĐHĐN",
            "1345/QĐ-ĐHBK", "27/2009/TT-BGDĐT", "2231/QĐ-ĐHBK", "1001/QĐ-ĐHBK", "4511/QĐ-ĐHBK",
            "1829/QĐ-BGDĐT", "1489/QĐ-ĐHĐN", "1092/QĐ-ĐHBK", "3240/QĐ-ĐHBK", "4768/QĐ-ĐHĐN",
            "2058/QĐ-ĐHĐN", "1214/QĐ-ĐHBK", "23/NQ-HĐT", "145/2020/NĐ-CP", "2244/QĐ-ĐHBK",
            "1177/QĐ-ĐHBK", "3337/QĐ-ĐHBK", "405/QĐ-ĐHBK", "86/2021/NĐ-CP", "3646/QĐ-ĐHBK",
            "16/2015/TT-BGDĐT", "3758/QĐ-ĐHĐN", "29/QĐ-ĐHBK", "2367/QĐ-ĐHĐN", "1779/QĐ-ĐHBK",
            "4420/QĐ-ĐHBK", "3828/QĐ-ĐHĐN",
        }),
    ),

    # Tình huống (phụ huynh): "Trường có văn bản nào về tuyển sinh không?"
    # — lọc theo lĩnh vực nghiệp vụ (Topic.name, KHÔNG có index — chỉ
    # topicId có, xem catalog.py Q2 cùng khuôn).
    Query(
        name="S03_docs_by_topic",
        cypher="""
            MATCH (d:Document)-[:HAS_TOPIC]->(:Topic {name: 'Tuyển sinh'})
            RETURN d.documentNumber AS documentNumber, d.title AS title
        """,
        expected_rows=16,
        kind="distribution",  # Topic.name không index (chỉ topicId có) — cùng lý do với catalog.py Q2
        note="16 văn bản thuộc lĩnh vực Tuyển sinh — khớp EXAMPLE.md câu 3.",
        id_field="documentNumber",
        expected_ids=frozenset({
            "18/2017/QĐ-TTg", "4757/QĐ-ĐHĐN", "2414/QĐ-ĐHĐN", "03/2022/TT-BGDĐT", "07/2020/TT-BGDĐT",
            "4473/QĐ-ĐHĐN", "1340/QĐ-ĐHBK", "1478/QĐ-ĐHĐN", "3183/QĐ-ĐHĐN", "1248/QĐ-ĐHĐN",
            "3297/QĐ-ĐHĐN", "1609/QĐ-ĐHBK", "09/2020/TT-BGDĐT", "4481/QĐ-ĐHĐN", "23/2021/TT-BGDĐT",
            "618/QĐ-BGDĐT",
        }),
    ),

    # Tình huống (giảng viên): "Những Quy chế nào đang còn hiệu lực?" —
    # lọc nội dung kèm theo (NormativeContent) theo loại + trạng thái.
    Query(
        name="S04_normative_content_active",
        cypher="""
            MATCH (:Document)-[:PROMULGATES]->(c:NormativeContent)
            WHERE c.contentType = 'Quy chế' AND c.status = 'CON_HIEU_LUC'
            RETURN c.contentId AS contentId, c.title AS title
        """,
        expected_rows=57,
        kind="distribution",  # contentType/status của NormativeContent không có index
        note="57 Quy chế còn hiệu lực — khớp EXAMPLE.md câu 5.",
        id_field="contentId",
        expected_ids=frozenset({
            "10/2016/TT-BGDDT#nd1", "16/2015/TT-BGDDT#nd1", "2721/QD-DHDN#nd1", "1001/QD-DHBK#nd1",
            "27/2009/TT-BGDDT#nd1", "1092/QD-DHBK#nd1", "1474/QD-DHBK#nd1", "1475/QD-DHBK#nd1",
            "2352/QD-DHBK#nd1", "1099/QD-BGDDT#nd1", "25/2025/TT-BGDDT#nd1", "1250/QD-DHBK#nd1",
            "1214/QD-DHDN#nd1", "2479/QD-DHBK#nd1", "4897/QD-DHDN#nd1", "5166/QD-DHDN#nd1",
            "2858/QD-BGDDT#nd1", "1609/QD-BGDDT#nd1", "23/2021/TT-BGDDT#nd1", "9/2020/TT-BGDDT#nd1",
            "18/2021/TT-BGDDT#nd1", "3297/QD-DHDN#nd1", "1248/QD-DHDN#nd1", "4481/QD-DHDN#nd1",
            "4473/QD-DHDN#nd1", "6/2026/TT-BGDDT#nd1", "1478/QD-DHDN#nd1", "2414/QD-DHDN#nd1",
            "53/2026/TT-BGDDT#nd1", "3536/QD-DHBK#nd1", "1676/QD-DHDN#nd1", "5/NQ-HDDH#nd1",
            "36/QD-DHDN#nd1", "423/QD-DHBK#nd1", "5/NQ-HDT#nd1", "1199/QD-DHBK#nd1",
            "1177/QD-DHBK#nd1", "23/NQ-HDT#nd1", "3819/QD-DHBK#nd1", "10/2020/TT-BGDDT#nd1",
            "8/NQ-HDDH#nd1", "2390/QD-DHDN#nd1", "4343/QD-DHDN#nd1", "637/QD-DHDN#nd1",
            "36/2017/TT-BGDDT#nd1", "5005/QD-DHDN#nd1", "3086/QD-BGDDT#nd1", "595/QD-DHBK#nd1",
            "32/NQ-HDDH#nd1", "1818/QD-BGDDT#nd1", "2152/QD-DHDN#nd1", "1616/QD-DHBK#nd1",
            "4801/QD-DHDN#nd1", "8/2021/TT-BGDDT#nd1", "28/2023/TT-BGDDT#nd1", "10/2026/TT-BGDDT#nd1",
            "56/2026/TT-BGDDT#nd1",
        }),
    ),

    # ============================================================
    # Mức 2 — 1-hop nhưng nhiều node/quan hệ (OPTIONAL MATCH toả ra từ
    # 1 Document gốc, hoặc 1 loại quan hệ duy nhất nhưng nhiều target)
    # ============================================================

    # Tình huống (giảng viên): "Văn bản 4511/QĐ-ĐHBK nói gì, ai ký, thuộc
    # lĩnh vực nào?" — tra cứu chi tiết 1 văn bản, gộp nhiều quan hệ khác
    # loại (ISSUED_BY/SIGNED_BY/HAS_TOPIC) trong 1 câu.
    Query(
        name="S05_document_detail",
        cypher="""
            MATCH (d:Document {normalizedNumber: '4511/QD-DHBK'})
            OPTIONAL MATCH (d)-[:ISSUED_BY]->(org:Organization)
            OPTIONAL MATCH (d)-[:SIGNED_BY]->(signer:Person)
            OPTIONAL MATCH (d)-[:HAS_TOPIC]->(topic:Topic)
            RETURN d.documentNumber AS documentNumber, d.title AS title, d.status AS status,
                   org.name AS issuedBy, signer.fullName AS signedBy,
                   collect(DISTINCT topic.name) AS topics
        """,
        expected_rows=1,
        kind="lookup",
        note="Chi tiết đầy đủ 1 văn bản (4511/QĐ-ĐHBK) — minh hoạ tại GRAPHREPORT.md §2.",
        id_field="documentNumber",
        expected_ids=frozenset({"4511/QĐ-ĐHBK"}),
    ),

    # Tình huống (sinh viên): "Văn bản 1559/QĐ-BGDĐT có bao nhiêu Điều,
    # nội dung ra sao?" — liệt kê toàn bộ Article vỏ bọc của 1 Document.
    Query(
        name="S06_document_articles",
        cypher="""
            MATCH (d:Document {normalizedNumber: '1559/QD-BGDDT'})-[:HAS_ARTICLE]->(a:Article)
            RETURN a.articleId AS articleId, a.heading AS heading
        """,
        expected_rows=7,
        kind="lookup",
        note="7 Điều của 1559/QĐ-BGDĐT — khớp EXAMPLE.md câu 15.",
        id_field="articleId",
        expected_ids=frozenset({
            "1559/QD-BGDDT#Điều 1", "1559/QD-BGDDT#Điều 2", "1559/QD-BGDDT#Điều 3",
            "1559/QD-BGDDT#Điều 4", "1559/QD-BGDDT#Điều 5", "1559/QD-BGDDT#Điều 6",
            "1559/QD-BGDDT#Điều 7",
        }),
    ),

    # Tình huống (phụ huynh): "Văn bản này nhắc tới những đơn vị nào?" —
    # tra MENTIONS (tổ chức được nhắc tới, không phải bên ban hành/ký).
    Query(
        name="S07_document_mentions",
        cypher="""
            MATCH (d:Document {normalizedNumber: '4757/QD-DHDN'})-[:MENTIONS]->(o:Organization)
            RETURN o.orgId AS orgId, o.name AS name
        """,
        expected_rows=6,
        kind="lookup",
        note="6 tổ chức được 4757/QĐ-ĐHĐN nhắc tới trong 'Trách nhiệm thi hành' — khớp EXAMPLE.md câu 16.",
        id_field="orgId",
        expected_ids=frozenset({
            "bo_giao_duc_va_dao_tao", "truong_dai_hoc_bach_khoa",
            "ban_dao_tao_va_dam_bao_chat_luong_giao_duc", "chinh_phu",
            "hoi_dong_dai_hoc_da_nang", "thu_tuong_chinh_phu",
        }),
    ),

    # Tình huống (giảng viên): "Văn bản 4511/QĐ-ĐHBK dựa trên những căn cứ
    # pháp lý nào?" — tra BASED_ON, không hàm ý bên bị trỏ tới hết hiệu lực.
    Query(
        name="S08_document_based_on",
        cypher="""
            MATCH (d:Document {normalizedNumber: '4511/QD-DHBK'})-[:BASED_ON]->(t:Document)
            RETURN t.documentNumber AS documentNumber
        """,
        expected_rows=10,
        kind="lookup",
        note="10 căn cứ pháp lý của 4511/QĐ-ĐHBK (thật + stub) — số đo trực tiếp trên graph hiện tại.",
        id_field="documentNumber",
        expected_ids=frozenset({
            "08/NQ-HĐĐH", "17/2021/TT-BGDĐT", "22/NQ-HĐT", "05/NQ-HĐT", "32/CP",
            "788/ĐHĐN-ĐT", "99/2019/NĐ-CP", "1691/QĐ-ĐHBK", "08/2021/TT-BGDĐT", "13/NQ-HĐĐH",
        }),
    ),

    # ============================================================
    # Mức 3 — multi-hop (quan hệ hiệu lực đệ quy, độ dài biến đổi)
    # ============================================================

    # Tình huống (giảng viên): "Văn bản 3868/QĐ-ĐHBK đã trải qua bao nhiêu
    # lần sửa đổi/thay thế?" — truy vết chuỗi AMENDS/REPLACES nhiều đời.
    Query(
        name="S09_amend_replace_chain",
        cypher="""
            MATCH (d:Document {normalizedNumber: '3868/QD-DHBK'})-[:AMENDS|REPLACES*1..5]->(b:Document)
            RETURN DISTINCT b.documentNumber AS documentNumber
        """,
        expected_rows=3,
        kind="multihop",
        note="Chuỗi thật 3868/QĐ-ĐHBK → 760 → 2652 → 2929/QĐ-ĐHBK (3 bước) — khớp EXAMPLE.md câu 7.",
        id_field="documentNumber",
        expected_ids=frozenset({"760/QĐ-ĐHBK", "2652/QĐ-ĐHBK", "2929/QĐ-ĐHBK"}),
    ),

    # Tình huống (sinh viên): "Quy chế công tác sinh viên cũ (42/2007/QĐ-
    # BGDĐT) đã bị thay bằng văn bản nào?" — chiều NGƯỢC của S09.
    Query(
        name="S10_replaced_by",
        cypher="""
            MATCH (new:Document)-[:REPLACES]->(:Document {normalizedNumber: '42/2007/QD-BGDDT'})
            RETURN new.documentNumber AS documentNumber
        """,
        expected_rows=1,
        kind="lookup",
        note="42/2007/QĐ-BGDĐT bị thay bởi đúng 10/2016/TT-BGDĐT — khớp EXAMPLE.md câu 6.",
        id_field="documentNumber",
        expected_ids=frozenset({"10/2016/TT-BGDĐT"}),
    ),

    # Tình huống (cán bộ pháp chế): "Những văn bản nào bị sửa đổi một
    # phần (AMENDS) nhưng tổng thể vẫn còn hiệu lực?" — phân biệt AMENDS
    # (sửa 1 phần) với REPLACES/REPEALS (chấm dứt hiệu lực).
    Query(
        name="S11_amends_target_still_active",
        cypher="""
            MATCH (a:Document)-[:AMENDS]->(b:Document)
            WHERE b.status = 'CON_HIEU_LUC'
            RETURN b.documentNumber AS documentNumber, collect(a.documentNumber) AS amenders
            ORDER BY documentNumber
        """,
        expected_rows=14,
        kind="lookup",
        note="14 văn bản bị AMENDS một phần nhưng vẫn CON_HIEU_LUC — cùng khuôn catalog.py Q5, đo trên data thật.",
        id_field="documentNumber",
        expected_ids=frozenset({
            "33/2024/QH15", "10/2016/TT-BGDĐT", "2231/QĐ-ĐHBK", "55/2011/NĐ-CP", "25/2019/TT-BGDĐT",
            "4765/QĐ-ĐHĐN", "81/2021/NĐ-CP", "05/NQ-HĐT", "1199/QĐ-ĐHBK", "58/2014/QH13",
            "5005/QĐ-ĐHĐN", "29/QĐ-ĐHBK", "4481/QĐ-ĐHĐN", "1899/QĐ-ĐHĐN",
        }),
    ),

    # Tình huống (cán bộ quản lý dữ liệu): "Chuỗi văn bản thay thế nhau
    # trong kho sâu tới mức nào?" — nhìn tổng thể độ sâu chuỗi hiệu lực
    # toàn graph, không phải 1 văn bản cụ thể.
    Query(
        name="S12_chain_depth_distribution",
        cypher="""
            MATCH p = (:Document)-[:AMENDS|REPLACES*1..5]->(:Document)
            RETURN length(p) AS depth, count(*) AS total
            ORDER BY depth
        """,
        expected_rows=4,
        kind="distribution",
        note="Phân bố độ sâu chuỗi thật: 1 bước 250 · 2 bước 44 · 3 bước 7 · 4 bước 2 — khớp GRAPHREPORT.md §3.",
        # Đây là câu đếm/group theo depth, không phải danh sách ID để chấm
        # điểm recall — giữ id_field/expected_ids=None như các câu sanity/
        # distribution khác của catalog.py.
    ),

    # ============================================================
    # Mức 4 — fulltext/hybrid (Lucene index + graph traversal). Ground
    # truth để None có chủ đích — xem docstring đầu file.
    # ============================================================

    # Tình huống (phụ huynh): "Học phí năm nay quy định ở văn bản nào?" —
    # tìm theo NỘI DUNG, không chỉ tiêu đề.
    Query(
        name="S13_fulltext_doc_content",
        cypher="""
            CALL db.index.fulltext.queryNodes('doc_text', '"học phí"') YIELD node, score
            RETURN node.documentNumber AS documentNumber, node.title AS title, score
            ORDER BY score DESC
            LIMIT 20
        """,
        expected_rows=None,
        kind="fulltext",
        note="Khớp EXAMPLE.md câu 4 (5 kết quả đầu đã verify thật) — expected_ids=None, độ liên quan cần người thẩm định.",
    ),

    # Tình huống (giảng viên): "Điều nào quy định trách nhiệm thi hành?"
    # — tìm cấp Article, cụm hành chính rất phổ biến trong văn bản.
    Query(
        name="S14_fulltext_article",
        cypher="""
            CALL db.index.fulltext.queryNodes('article_text', '"trách nhiệm thi hành"') YIELD node, score
            RETURN node.articleId AS articleId, node.heading AS heading, score
            ORDER BY score DESC
            LIMIT 20
        """,
        expected_rows=None,
        kind="fulltext",
        note="Cụm hành chính chuẩn, xuất hiện ở hầu hết Điều thi hành — expected_ids=None (chưa thẩm định).",
    ),

    # Tình huống (sinh viên): "Có Nội quy nào liên quan không?" — tìm
    # theo tên NormativeContent (khác cụm 'Quy chế' đã dùng ở B13 benchmark
    # để tránh trùng lặp, dùng đúng index content_text thứ 3).
    Query(
        name="S15_fulltext_content",
        cypher="""
            CALL db.index.fulltext.queryNodes('content_text', '"Nội quy"') YIELD node, score
            RETURN node.contentId AS contentId, node.title AS title, score
            ORDER BY score DESC
            LIMIT 20
        """,
        expected_rows=None,
        kind="fulltext",
        note="2 NormativeContent khớp 'Nội quy' trên data thật — expected_ids=None (chưa thẩm định).",
    ),

    # Tình huống (giảng viên): "Những văn bản gốc thẩm quyền cao nào liên
    # quan tới Đại học Đà Nẵng?" — kết hợp tìm nội dung (fulltext) rồi
    # truy vết quan hệ căn cứ (multi-hop) trong CÙNG 1 câu.
    Query(
        name="S16_hybrid_expand",
        cypher=hybrid_expand_cypher(fulltext_query='"Đại học Đà Nẵng"', seed_limit=5, final_limit=20),
        expected_rows=None,
        kind="hybrid",
        note="Khớp EXAMPLE.md câu 10 (5 văn bản gốc đã verify: 86/2015/NĐ-CP, 55/2015/TTLT-BTC-BKHCN, "
             "191/2013/NĐ-CP, 1219/QĐ-ĐHĐN, 58/2016/TT-BTC) — expected_ids=None theo quy ước Mức 4.",
    ),

    # ============================================================
    # Mức 5 — Tổng hợp toàn graph (ranking/distribution) và kết hợp
    # NHIỀU điều kiện/quan hệ cùng lúc (khó nhất — BM25 không làm được)
    # ============================================================

    # Tình huống (phụ huynh): "Cơ quan nào ban hành nhiều văn bản nhất?"
    # — xếp hạng, không phải danh sách ID để so recall.
    Query(
        name="S17_top_organizations",
        cypher="""
            MATCH (d:Document)-[:ISSUED_BY]->(o:Organization)
            RETURN o.name AS organization, count(d) AS total
            ORDER BY total DESC
            LIMIT 10
        """,
        expected_rows=10,
        kind="ranking",
        note="Top 10 tổ chức ban hành nhiều văn bản nhất — khớp EXAMPLE.md câu 8 (Bộ GD&ĐT 115, ĐHĐN 85, ĐHBK 67...).",
    ),

    # Tình huống (giảng viên): "Bao nhiêu văn bản còn hiệu lực, bao nhiêu
    # hết hiệu lực?" — phân bố tổng quan toàn kho.
    Query(
        name="S18_status_distribution",
        cypher="""
            MATCH (d:Document) WHERE d.isStub = false
            RETURN d.status AS status, count(d) AS total
            ORDER BY total DESC
        """,
        expected_rows=3,
        kind="distribution",
        note="381 CON_HIEU_LUC · 21 chưa gán · 1 HET_HIEU_LUC — khớp EXAMPLE.md câu 9.",
    ),

    # Tình huống (cán bộ Phòng Công tác sinh viên): "Văn bản nào về Công
    # tác sinh viên, áp dụng cho Người học, do chính Trường ĐHBK ban
    # hành?" — 3 điều kiện ĐỘC LẬP cùng lúc (topic + targetGroup + org),
    # đúng dạng câu hỏi BM25/keyword search không biểu diễn được (không
    # có khái niệm AND đa facet cấu trúc) — case then chốt cho việc sau
    # này so sánh với BM25.
    Query(
        name="S19_multi_facet_and",
        cypher="""
            MATCH (d:Document)-[:HAS_TOPIC]->(:Topic {name: 'Công tác sinh viên'})
            MATCH (d)-[:APPLIES_TO]->(:TargetGroup {targetGroupId: 'nguoi_hoc'})
            MATCH (d)-[:ISSUED_BY]->(:Organization {orgId: 'truong_dai_hoc_bach_khoa'})
            RETURN d.documentNumber AS documentNumber, d.title AS title
        """,
        expected_rows=4,
        kind="lookup",
        note="4/17 văn bản (lọc thêm org từ 17 văn bản Công tác sinh viên + Người học) — case multi-facet "
             "đúng tinh thần ví dụ trong docx gốc dự án ('Học bổng' + 'Sinh viên năm nhất' + 'Phòng CTSV').",
        id_field="documentNumber",
        expected_ids=frozenset({"1414/QĐ-ĐHBK", "1001/QĐ-ĐHBK", "4511/QĐ-ĐHBK", "1345/QĐ-ĐHBK"}),
    ),

    # Tình huống (cán bộ pháp chế): "Trong số văn bản còn hiệu lực do
    # Trường ĐHBK ban hành, văn bản nào từng sửa đổi văn bản khác?" —
    # kết hợp lookup (org + status) VÀ multihop (quan hệ AMENDS) trong
    # cùng 1 câu — case khó nhất về số lớp quan hệ chồng nhau.
    Query(
        name="S20_active_org_docs_that_amend",
        cypher="""
            MATCH (d:Document)-[:ISSUED_BY]->(:Organization {orgId: 'truong_dai_hoc_bach_khoa'})
            WHERE d.status = 'CON_HIEU_LUC'
            MATCH (d)-[:AMENDS]->(:Document)
            RETURN DISTINCT d.documentNumber AS documentNumber
        """,
        expected_rows=4,
        kind="lookup",
        note="4 văn bản còn hiệu lực của ĐHBK từng sửa đổi (AMENDS) văn bản khác — kết hợp lookup+multihop.",
        id_field="documentNumber",
        expected_ids=frozenset({"2525/QĐ-ĐHBK", "1088/QĐ-ĐHBK", "22/NQ-HĐT", "1274/QĐ-ĐHBK"}),
    ),
]
