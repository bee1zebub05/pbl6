"""
20 kịch bản Cypher chạy trên DATA THẬT (`data/clean/json/v2`, 403 Document
thật + 8.814 Article) — KHÁC mục đích với 2 catalog kia:

- `samples.py`   : regression cơ chế trên `samples/` (17 mẫu cố định).
- `benchmark.py` : đo hiệu năng thuần trên data thật, tự nhận CHƯA qua thẩm
  định là đại diện đúng nhu cầu truy vấn thật.
- File này (`scenarios.py`): 20 câu hỏi đã CHỌN LỌC theo góc nhìn
  người dùng thật (giảng viên/sinh viên/phụ huynh/cán bộ quản lý dữ liệu),
  sắp theo 5 mức độ phức tạp Cypher tăng dần (dễ -> khó), mỗi câu có ground
  truth (`expected_ids`) khi kết quả xác định rõ ràng — dùng để CHẤM ĐIỂM
  (precision/recall/F1, xem `scoring.score_ids()`), không chỉ đếm dòng.

Phần lớn số liệu/Cypher lấy lại từ 2 nguồn ĐÃ VERIFY THẬT thay vì bịa case
mới: `docs/GRAPHREPORT.md` (số liệu graph) và `docs/EXAMPLE.md` (20 câu hỏi mẫu theo
persona, có kết quả thật). `expected_ids` ở đây được chạy lại TRỰC TIẾP
trên graph thật lúc viết file này (không suy đoán từ 2 tài liệu trên).

Mức 4 (S13–S16) và S17: `expected_ids` được GÁN TAY ngày 12/10/2026 (độ
liên quan là phán đoán, không phải sự thật khách quan như một cạnh có tồn
tại hay không) — tiêu chí ghi ở `note` từng case, S14 ở
`gold_s14_articles.json`. Nên có thêm một người kiểm lại.

S12 và S18 là câu đếm/thống kê, đáp án là con số chứ không phải danh sách
ID nên vẫn để `expected_ids=None`; đúng/sai của Cypher kiểm qua
`expected_rows` + số liệu trong `note`.

Mỗi case có `question` (câu hỏi tiếng Việt) làm đầu vào cho BM25 — xem
`bm25.py`, `compare.py`.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from ..query import Query

# Ground truth S14 quá dài để viết inline (464 Điều) — tách file, kèm tiêu chí gán.
_S14_GOLD = frozenset(json.loads(
    (Path(__file__).with_name("gold_s14_articles.json")).read_text(encoding="utf-8")
)["expected_ids"])

QUERIES: list[Query] = [
    # ============================================================
    # Mức 1 — 1-hop đơn giản (1 MATCH + 1 điều kiện lọc, có index)
    # ============================================================

    # Tình huống (giảng viên): "Trường Đại học Bách khoa còn văn bản nào
    # đang có hiệu lực?" — câu hỏi phổ biến nhất, 1 tổ chức + 1 trạng thái.
    Query(
        name="S01_docs_by_org_active",
        question="Trường Đại học Bách khoa còn văn bản nào đang có hiệu lực?",
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
        question="Văn bản nào áp dụng cho người học (sinh viên)?",
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
    # topicId có, xem samples.py Q2 cùng khuôn).
    Query(
        name="S03_docs_by_topic",
        question="Trường có văn bản nào về tuyển sinh không?",
        cypher="""
            MATCH (d:Document)-[:HAS_TOPIC]->(:Topic {name: 'Tuyển sinh'})
            RETURN d.documentNumber AS documentNumber, d.title AS title
        """,
        expected_rows=16,
        kind="distribution",  # Topic.name không index (chỉ topicId có) — cùng lý do với samples.py Q2
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
        question="Những Quy chế nào đang còn hiệu lực?",
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
        question="Văn bản 4511/QĐ-ĐHBK nói gì, ai ký, thuộc lĩnh vực nào?",
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
        question="Văn bản 1559/QĐ-BGDĐT có bao nhiêu Điều, nội dung ra sao?",
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
        question="Văn bản 4757/QĐ-ĐHĐN nhắc tới những đơn vị nào?",
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
        question="Văn bản 4511/QĐ-ĐHBK dựa trên những căn cứ pháp lý nào?",
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
        question="Văn bản 3868/QĐ-ĐHBK đã trải qua bao nhiêu lần sửa đổi, thay thế?",
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
        question="Quy chế công tác sinh viên cũ (42/2007/QĐ-BGDĐT) đã bị thay bằng văn bản nào?",
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
        question="Những văn bản nào bị sửa đổi một phần nhưng tổng thể vẫn còn hiệu lực?",
        cypher="""
            MATCH (a:Document)-[:AMENDS]->(b:Document)
            WHERE b.status = 'CON_HIEU_LUC'
            RETURN b.documentNumber AS documentNumber, collect(a.documentNumber) AS amenders
            ORDER BY documentNumber
        """,
        expected_rows=14,
        kind="lookup",
        note="14 văn bản bị AMENDS một phần nhưng vẫn CON_HIEU_LUC — cùng khuôn samples.py Q5, đo trên data thật.",
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
        question="Chuỗi văn bản thay thế nhau trong kho sâu tới mức nào?",
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
        # distribution khác của samples.py.
    ),

    # ============================================================
    # Mức 4 — fulltext/hybrid (Lucene index + graph traversal). Ground
    # truth để None có chủ đích — xem docstring đầu file.
    # ============================================================

    # Tình huống (phụ huynh): "Học phí năm nay quy định ở văn bản nào?" —
    # tìm theo NỘI DUNG, không chỉ tiêu đề.
    Query(
        name="S13_fulltext_doc_content",
        question="Học phí năm nay quy định ở văn bản nào?",
        cypher="""
            CALL db.index.fulltext.queryNodes('doc_text', '"học phí"') YIELD node, score
            RETURN node.documentNumber AS documentNumber, node.title AS title, score
            ORDER BY score DESC
            LIMIT 20
        """,
        expected_rows=None,
        kind="fulltext",
        note="Khớp EXAMPLE.md câu 4. Ground truth gán tay: 5 văn bản có chủ đề CHÍNH là học phí "
             "(văn bản chỉ nhắc tới phí/kinh phí khác — phí tuyển sinh, ký túc xá, chi tiêu nội bộ — không tính).",
        id_field="documentNumber",
        expected_ids=frozenset({
            "81/2021/NĐ-CP", "97/2023/NĐ-CP", "09/2016/TTLT-BGDĐT-BTC-BLĐTBXH", "3443/ĐHĐN-KHTC", "4532/QĐ-ĐHBK",
        }),
    ),

    # Tình huống (giảng viên): "Điều nào quy định trách nhiệm thi hành?"
    # — tìm cấp Article, cụm hành chính rất phổ biến trong văn bản.
    Query(
        name="S14_fulltext_article",
        question="Điều nào quy định trách nhiệm thi hành?",
        cypher="""
            CALL db.index.fulltext.queryNodes('article_text', '"trách nhiệm thi hành"') YIELD node, score
            RETURN node.articleId AS articleId, node.heading AS heading, score
            ORDER BY score DESC
        """,
        expected_rows=None,
        kind="fulltext",
        note="Cụm hành chính chuẩn, xuất hiện ở hầu hết Điều thi hành. Ground truth gán tay: 464 Điều giao "
             "trách nhiệm thi hành chính văn bản chứa nó (tiêu chí trong gold_s14_articles.json). Bản trước "
             "có LIMIT 20 nên chỉ trả 20/464 (recall 0,04) — bỏ LIMIT ngày 12/10/2026.",
        id_field="articleId",
        expected_ids=_S14_GOLD,
    ),

    # Tình huống (sinh viên): "Có Nội quy nào liên quan không?" — tìm
    # theo tên NormativeContent (khác cụm 'Quy chế' đã dùng ở B13 benchmark
    # để tránh trùng lặp, dùng đúng index content_text thứ 3).
    Query(
        name="S15_fulltext_content",
        question="Có Nội quy nào liên quan không?",
        cypher="""
            CALL db.index.fulltext.queryNodes('content_text', '"Nội quy"') YIELD node, score
            RETURN node.contentId AS contentId, node.title AS title, score
            ORDER BY score DESC
            LIMIT 20
        """,
        expected_rows=None,
        kind="fulltext",
        note="2 NormativeContent loại 'Nội quy' trên data thật (contentType = 'Nội quy', gán tay đã đối chiếu).",
        id_field="contentId",
        expected_ids=frozenset({"176/QD-DHBK#nd1", "479/QD-DHBK#nd1"}),
    ),

    # Tình huống (giảng viên): "Những văn bản gốc thẩm quyền cao nào liên
    # quan tới Đại học Đà Nẵng?" — kết hợp tìm nội dung (fulltext) rồi
    # truy vết quan hệ căn cứ (multi-hop) trong CÙNG 1 câu.
    Query(
        name="S16_hybrid_expand",
        question="Những văn bản gốc thẩm quyền cao nào liên quan tới Đại học Đà Nẵng?",
        # Bản trước: hybrid_expand_cypher('"Đại học Đà Nẵng"', seed_limit=5, final_limit=20) — tìm
        # văn bản có NHẮC chữ "Đại học Đà Nẵng" rồi mở rộng căn cứ, nên ra văn bản về học phí, tài
        # chính... (F1 0,08). Bản này đi thẳng theo cấu trúc: căn cứ cấp trên (Luật/Nghị định/
        # Thông tư/QĐ-TTg, kể cả stub) của chính các văn bản ĐHĐN ban hành, xếp theo số văn bản
        # ĐHĐN viện dẫn — "gốc" = được dùng làm nền nhiều nhất.
        cypher="""
            MATCH (d:Document)-[:ISSUED_BY]->(:Organization {orgId: 'dai_hoc_da_nang'})
            MATCH (d)-[:BASED_ON]->(t:Document)
            WHERE coalesce(t.authorityLevel, 0) >= 3
               OR (t.isStub AND t.documentNumber =~ '.*(/QH|NĐ-CP|/CP$|TT-|QĐ-TTg).*')
            WITH t, count(DISTINCT d) AS cited
            RETURN t.documentNumber AS documentNumber, cited
            ORDER BY cited DESC, documentNumber
            LIMIT 10
        """,
        expected_rows=None,
        kind="multihop",
        note="Đổi Cypher ngày 12/10/2026 (xem comment). Bản cũ khớp EXAMPLE.md câu 10 (5 văn bản gốc đã verify: 86/2015/NĐ-CP, 55/2015/TTLT-BTC-BKHCN, "
             "191/2013/NĐ-CP, 1219/QĐ-ĐHĐN, 58/2016/TT-BTC — verify là chạy đúng, không phải là liên quan). "
             "Ground truth gán tay: văn bản cấp trên ĐHĐN tạo nền pháp lý cho chính ĐHĐN — Nghị định thành "
             "lập (32/CP), Quy chế đại học vùng cũ/mới (08/2014, 10/2020/TT-BGDĐT), Luật GDĐH + luật sửa đổi "
             "+ nghị định hướng dẫn (08/2012/QH13, 34/2018/QH14, 99/2019/NĐ-CP).",
        id_field="documentNumber",
        expected_ids=frozenset({
            "32/CP", "08/2014/TT-BGDĐT", "10/2020/TT-BGDĐT", "08/2012/QH13", "34/2018/QH14", "99/2019/NĐ-CP",
        }),
    ),

    # ============================================================
    # Mức 5 — Tổng hợp toàn graph (ranking/distribution) và kết hợp
    # NHIỀU điều kiện/quan hệ cùng lúc (khó nhất — BM25 không làm được)
    # ============================================================

    # Tình huống (phụ huynh): "Cơ quan nào ban hành nhiều văn bản nhất?"
    # — xếp hạng, không phải danh sách ID để so recall.
    Query(
        name="S17_top_organizations",
        question="Cơ quan nào ban hành nhiều văn bản nhất?",
        cypher="""
            MATCH (d:Document)-[:ISSUED_BY]->(o:Organization)
            RETURN o.name AS organization, count(d) AS total
            ORDER BY total DESC
            LIMIT 10
        """,
        expected_rows=10,
        kind="ranking",
        note="Top 10 tổ chức ban hành nhiều văn bản nhất — khớp EXAMPLE.md câu 8 (Bộ GD&ĐT 115, ĐHĐN 85, ĐHBK 67...). "
             "Hạng 10 không hoà (4 so với 1), nên tập top 10 xác định duy nhất.",
        id_field="organization",
        expected_ids=frozenset({
            "Bộ Giáo dục và Đào tạo", "Đại học Đà Nẵng", "Trường Đại học Bách khoa", "Chính phủ", "Quốc hội",
            "Trường Đại học Bách khoa, Đại học Đà Nẵng", "Thủ tướng Chính phủ", "Thanh tra Chính phủ",
            "Bộ Nội vụ", "Hội đồng Đại học Đà Nẵng",
        }),
    ),

    # Tình huống (giảng viên): "Bao nhiêu văn bản còn hiệu lực, bao nhiêu
    # hết hiệu lực?" — phân bố tổng quan toàn kho.
    Query(
        name="S18_status_distribution",
        question="Bao nhiêu văn bản còn hiệu lực, bao nhiêu hết hiệu lực?",
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
        question="Văn bản nào về Công tác sinh viên, áp dụng cho Người học, do chính Trường ĐHBK ban hành?",
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
        question="Trong số văn bản còn hiệu lực do Trường ĐHBK ban hành, văn bản nào từng sửa đổi văn bản khác?",
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

    # ============================================================
    # S21–S23 — câu hỏi nội dung quy chế đào tạo của sinh viên (thêm
    # 13/10/2026, xếp mức 4). Khác S01–S11: `expected_ids` GÁN TAY TỪ
    # VĂN BẢN GỐC (`text_final`), không lấy từ output của câu Cypher, nên
    # điểm Cypher ở đây đo được độ đúng thật. Đáp án là Điều của văn bản
    # còn hiệu lực áp dụng cho đại học chính quy và trực tiếp nêu quy định
    # được hỏi; Điều chỉ dẫn chiếu sang văn bản khác, văn bản đã bị thay
    # thế, quy định thạc sĩ / tiến sĩ / liên thông không tính.
    #
    # Cypher viết theo MỘT quy tắc chung, chốt trước khi chấm và không
    # chỉnh theo đáp án: cụm từ khoá lấy từ câu hỏi -> full-text trên Điều
    # -> bỏ văn bản đã bị REPLACES/REPEALS -> top 10. Không lọc APPLIES_TO
    # Người học vì 56/2026/TT-BGDĐT chưa được gắn nhãn này.
    # ============================================================

    # Tình huống (sinh viên): cách tính điểm trung bình học kỳ và tích lũy.
    Query(
        name="S21_gpa_rule",
        question="Quy định tính điểm trung bình tích lũy và điểm trung bình học kỳ như thế nào?",
        cypher="""
            CALL db.index.fulltext.queryNodes('article_text', '"điểm trung bình học kỳ" AND "điểm trung bình tích lũy"')
            YIELD node, score
            MATCH (d:Document)-[:HAS_ARTICLE|PROMULGATES*1..2]->(node)
            WHERE NOT (d)<-[:REPLACES|REPEALS]-(:Document)
            RETURN DISTINCT node.articleId AS articleId, node.heading AS heading, score
            ORDER BY score DESC
            LIMIT 10
        """,
        expected_rows=None,
        kind="fulltext",
        note="Ground truth gán tay từ văn bản gốc: Điều 11 Quy định 2244/QĐ-ĐHBK (công thức DTBHK, DTBNH, DTBTL) "
             "và Điều 13 Thông tư 56/2026/TT-BGDĐT. Không tính Điều 10 Thông tư 08/2021 (đã bị 56/2026 thay thế) "
             "và Điều 24 Quy định 1214/QĐ-ĐHBK (chỉ dẫn về quy định hiện hành).",
        id_field="articleId",
        expected_ids=frozenset({"2244/QD-DHBK#nd1#Điều 11", "56/2026/TT-BGDDT#nd1#Điều 13"}),
    ),

    # Tình huống (sinh viên): ngưỡng điểm bị cảnh báo học tập, buộc thôi học.
    Query(
        name="S22_academic_warning",
        question="Bao nhiêu điểm thì bị cảnh báo học tập hoặc buộc thôi học?",
        cypher="""
            CALL db.index.fulltext.queryNodes('article_text', '("cảnh báo học tập" OR "cảnh báo kết quả học tập" OR "buộc thôi học") AND điểm')
            YIELD node, score
            MATCH (d:Document)-[:HAS_ARTICLE|PROMULGATES*1..2]->(node)
            WHERE NOT (d)<-[:REPLACES|REPEALS]-(:Document)
            RETURN DISTINCT node.articleId AS articleId, node.heading AS heading, score
            ORDER BY score DESC
            LIMIT 10
        """,
        expected_rows=None,
        kind="fulltext",
        note="Ground truth gán tay từ văn bản gốc: Điều nêu NGƯỠNG điểm — 2244/QĐ-ĐHBK Điều 12 (tín chỉ: DTBHK < 0,80/1,00; "
             "DTBTL < 1,20/1,40/1,60/1,80) và Điều 13 (niên chế); 56/2026/TT-BGDĐT Điều 14, 15. Không tính 08/2021 "
             "(đã bị thay), 1779/QĐ-ĐHBK Điều 7 (liên thông, dẫn chiếu), 1214/QĐ-ĐHBK Điều 25 (chỉ quy trình xét).",
        id_field="articleId",
        expected_ids=frozenset({
            "2244/QD-DHBK#nd1#Điều 12", "2244/QD-DHBK#nd1#Điều 13",
            "56/2026/TT-BGDDT#nd1#Điều 14", "56/2026/TT-BGDDT#nd1#Điều 15",
        }),
    ),

    # Tình huống (sinh viên): nghỉ có lý do chính đáng thì làm thủ tục ở đâu.
    Query(
        name="S23_valid_absence_procedure",
        question="Nghỉ có lý do chính đáng thì làm thủ tục ở đâu?",
        cypher="""
            CALL db.index.fulltext.queryNodes('article_text', '"lý do chính đáng" AND (nghỉ OR thủ tục)')
            YIELD node, score
            MATCH (d:Document)-[:HAS_ARTICLE|PROMULGATES*1..2]->(node)
            WHERE NOT (d)<-[:REPLACES|REPEALS]-(:Document)
            RETURN DISTINCT node.articleId AS articleId, node.heading AS heading, score
            ORDER BY score DESC
            LIMIT 10
        """,
        expected_rows=None,
        kind="fulltext",
        note="Câu hỏi mơ hồ, có hai cách hiểu cho sinh viên: vắng thi có lý do chính đáng -> thủ tục hoãn thi "
             "(2244/QĐ-ĐHBK Điều 9: trong 10 ngày, Trường báo qua DUT-SIS) và nghỉ học tạm thời -> 2244/QĐ-ĐHBK "
             "Điều 18 (điều kiện, thời hạn) + 1214/QĐ-ĐHBK Điều 40 (lập đơn trên DUT-SIS, nộp tại Khu hành chính "
             "một cửa, Phòng Đào tạo tiếp nhận). Ground truth gán tay gồm cả ba. Không tính 56/2026 Điều 12 "
             "(chỉ nêu quyền dự thi lại, không có thủ tục).",
        id_field="articleId",
        expected_ids=frozenset({"2244/QD-DHBK#nd1#Điều 9", "2244/QD-DHBK#nd1#Điều 18", "1214/QD-DHBK#nd1#Điều 40"}),
    ),

    # ============================================================
    # S24–S31 — thêm 13/10/2026 theo cùng cách làm của S21–S23: ứng viên
    # gom từ BM25 + vector (top 12 mỗi hệ, kiểu pooling TREC), đáp án gán
    # tay từ văn bản gốc; Cypher theo cùng quy tắc chung (cụm từ khoá của
    # câu hỏi -> full-text Điều -> bỏ văn bản bị REPLACES/REPEALS -> top 10).
    # ============================================================

    Query(
        name="S24_graduation_conditions",
        question="Điều kiện để được xét công nhận tốt nghiệp là gì?",
        cypher="""
            CALL db.index.fulltext.queryNodes('article_text', '"công nhận tốt nghiệp" AND "điều kiện"')
            YIELD node, score
            MATCH (d:Document)-[:HAS_ARTICLE|PROMULGATES*1..2]->(node)
            WHERE NOT (d)<-[:REPLACES|REPEALS]-(:Document)
            RETURN DISTINCT node.articleId AS articleId, node.heading AS heading, score
            ORDER BY score DESC
            LIMIT 10
        """,
        expected_rows=None,
        kind="fulltext",
        note="Ground truth: 2244/QĐ-ĐHBK Điều 17 khoản 3, 56/2026/TT-BGDĐT Điều 17 khoản 1 (danh sách điều kiện), 4511/QĐ-ĐHBK Điều 6 (chuẩn ngoại ngữ đầu ra là một điều kiện tốt nghiệp). Không tính 1214/QĐ-ĐHBK Điều 29 (dẫn chiếu Điều 17 Quy định 2244), 08/2021 (đã bị thay), quy định thạc sĩ.",
        id_field="articleId",
        expected_ids=frozenset({"2244/QD-DHBK#nd1#Điều 17", "56/2026/TT-BGDDT#nd1#Điều 17", "4511/QD-DHBK#nd1#Điều 6"}),
    ),

    Query(
        name="S25_graduation_ranking",
        question="Xếp hạng tốt nghiệp loại giỏi, xuất sắc cần bao nhiêu điểm?",
        cypher="""
            CALL db.index.fulltext.queryNodes('article_text', '"hạng tốt nghiệp" AND (giỏi OR "xuất sắc")')
            YIELD node, score
            MATCH (d:Document)-[:HAS_ARTICLE|PROMULGATES*1..2]->(node)
            WHERE NOT (d)<-[:REPLACES|REPEALS]-(:Document)
            RETURN DISTINCT node.articleId AS articleId, node.heading AS heading, score
            ORDER BY score DESC
            LIMIT 10
        """,
        expected_rows=None,
        kind="fulltext",
        note="Ground truth: Điều nói hạng tốt nghiệp theo điểm trung bình tích lũy và bị giảm một mức khi nào (2244 Điều 17, 56/2026 Điều 17) cộng Điều chứa thang điểm mà chúng dẫn tới (2244 Điều 11 khoản 5: xuất sắc 3,60–4,00, giỏi 3,20–3,59; 56/2026 Điều 13 khoản 5). Không tính 3875/QĐ-ĐHBK Điều 24 (thạc sĩ).",
        id_field="articleId",
        expected_ids=frozenset({"2244/QD-DHBK#nd1#Điều 17", "2244/QD-DHBK#nd1#Điều 11", "56/2026/TT-BGDDT#nd1#Điều 17", "56/2026/TT-BGDDT#nd1#Điều 13"}),
    ),

    Query(
        name="S26_foreign_language_exit",
        question="Chuẩn đầu ra ngoại ngữ của sinh viên là gì?",
        cypher="""
            CALL db.index.fulltext.queryNodes('article_text', '"chuẩn đầu ra" AND "ngoại ngữ"')
            YIELD node, score
            MATCH (d:Document)-[:HAS_ARTICLE|PROMULGATES*1..2]->(node)
            WHERE NOT (d)<-[:REPLACES|REPEALS]-(:Document)
            RETURN DISTINCT node.articleId AS articleId, node.heading AS heading, score
            ORDER BY score DESC
            LIMIT 10
        """,
        expected_rows=None,
        kind="fulltext",
        note="Ground truth: 4511/QĐ-ĐHBK Điều 6 (yêu cầu chuẩn ngoại ngữ đầu ra khi tốt nghiệp). Không tính 1345/QĐ-ĐHBK (đã bị 4511 thay thế), các Điều về đầu vào / từng năm học / thủ tục nộp chứng chỉ của 4511.",
        id_field="articleId",
        expected_ids=frozenset({"4511/QD-DHBK#nd1#Điều 6"}),
    ),

    Query(
        name="S27_credit_load_limits",
        question="Mỗi học kỳ được đăng ký tối thiểu và tối đa bao nhiêu tín chỉ?",
        cypher="""
            CALL db.index.fulltext.queryNodes('article_text', '"đăng ký" AND "tối thiểu" AND "tối đa" AND "tín chỉ"')
            YIELD node, score
            MATCH (d:Document)-[:HAS_ARTICLE|PROMULGATES*1..2]->(node)
            WHERE NOT (d)<-[:REPLACES|REPEALS]-(:Document)
            RETURN DISTINCT node.articleId AS articleId, node.heading AS heading, score
            ORDER BY score DESC
            LIMIT 10
        """,
        expected_rows=None,
        kind="fulltext",
        note="Ground truth: 2244/QĐ-ĐHBK Điều 7 (không ít hơn 12, không quá 25 tín chỉ mỗi học kỳ chính; 10 tín chỉ học kỳ hè) và 56/2026/TT-BGDĐT Điều 9 (2/3 đến 3/2 khối lượng trung bình một học kỳ). Không tính 08/2021 (đã bị thay).",
        id_field="articleId",
        expected_ids=frozenset({"2244/QD-DHBK#nd1#Điều 7", "56/2026/TT-BGDDT#nd1#Điều 9"}),
    ),

    Query(
        name="S28_double_degree",
        question="Điều kiện để học cùng lúc hai chương trình là gì?",
        cypher="""
            CALL db.index.fulltext.queryNodes('article_text', '"hai chương trình" AND "điều kiện"')
            YIELD node, score
            MATCH (d:Document)-[:HAS_ARTICLE|PROMULGATES*1..2]->(node)
            WHERE NOT (d)<-[:REPLACES|REPEALS]-(:Document)
            RETURN DISTINCT node.articleId AS articleId, node.heading AS heading, score
            ORDER BY score DESC
            LIMIT 10
        """,
        expected_rows=None,
        kind="fulltext",
        note="Ground truth: 2244/QĐ-ĐHBK Điều 21 (từ năm thứ hai, điểm trung bình tích lũy từ 2,50), 56/2026/TT-BGDĐT Điều 21, 1214/QĐ-ĐHBK Điều 42 (dẫn chiếu điều kiện nhưng có điều kiện riêng: tối thiểu 04 tín chỉ, dừng khi điểm học kỳ dưới 2,50). Không tính 08/2021 (đã bị thay), quy chế tuyển sinh chương trình thứ hai.",
        id_field="articleId",
        expected_ids=frozenset({"2244/QD-DHBK#nd1#Điều 21", "56/2026/TT-BGDDT#nd1#Điều 21", "1214/QD-DHBK#nd1#Điều 42"}),
    ),

    Query(
        name="S29_merit_scholarship",
        question="Sinh viên được xét học bổng khuyến khích học tập như thế nào?",
        cypher="""
            CALL db.index.fulltext.queryNodes('article_text', '"học bổng khuyến khích học tập"')
            YIELD node, score
            MATCH (d:Document)-[:HAS_ARTICLE|PROMULGATES*1..2]->(node)
            WHERE NOT (d)<-[:REPLACES|REPEALS]-(:Document)
            RETURN DISTINCT node.articleId AS articleId, node.heading AS heading, score
            ORDER BY score DESC
            LIMIT 10
        """,
        expected_rows=None,
        kind="fulltext",
        note="Ground truth: 1414/QĐ-ĐHBK Điều 5 (tiêu chuẩn), Điều 6 (mức), Điều 7 (trình tự xét); 84/2020/NĐ-CP Điều 8; 28/VBHN-BGDĐT Điều 2 (học bổng KKHT ở cơ sở giáo dục đại học — tính vì trong kho không có văn bản nào thay thế; cần người kiểm xác nhận còn áp dụng). Không tính 3536/QĐ-ĐHBK Điều 11 (dẫn chiếu 1414).",
        id_field="articleId",
        expected_ids=frozenset({"1414/QD-DHBK#nd1#Điều 5", "1414/QD-DHBK#nd1#Điều 6", "1414/QD-DHBK#nd1#Điều 7", "84/2020/ND-CP#Điều 8", "28/VBHN-BGDDT#Điều 2"}),
    ),

    Query(
        name="S30_exam_impersonation",
        question="Thi hộ hoặc nhờ người thi hộ bị xử lý kỷ luật thế nào?",
        cypher="""
            CALL db.index.fulltext.queryNodes('article_text', '"thi hộ" AND "kỷ luật"')
            YIELD node, score
            MATCH (d:Document)-[:HAS_ARTICLE|PROMULGATES*1..2]->(node)
            WHERE NOT (d)<-[:REPLACES|REPEALS]-(:Document)
            RETURN DISTINCT node.articleId AS articleId, node.heading AS heading, score
            ORDER BY score DESC
            LIMIT 10
        """,
        expected_rows=None,
        kind="fulltext",
        note="Ground truth: 29/QĐ-ĐHBK Điều 4 (liêm chính học thuật: đình chỉ 01 năm, tái phạm buộc thôi học) và 3707/QĐ-ĐHBK Điều 1 — văn bản 25/7/2025 SỬA điều khoản đó thành đình chỉ học tập 02 học kỳ; trả lời đúng phải nêu bản sửa. Graph không có cạnh 3707 -> 29, chỉ 3707 REPLACES 1274 AMENDS 29. Thêm 2367/QĐ-ĐHĐN Điều 8 (học phần GDTC). Không tính 56/2026 Điều 24 (chỉ phân nhóm, giao trường quy định mức kỷ luật), 10/2016 Điều 6 (chỉ liệt kê hành vi cấm), 3875 Điều 33 (thạc sĩ), 08/2021 (đã bị thay).",
        id_field="articleId",
        expected_ids=frozenset({"29/QD-DHBK#nd1#Điều 4", "3707/QD-DHBK#Điều 1", "2367/QD-DHDN#nd1#Điều 8"}),
    ),

    Query(
        name="S31_tuition_exemption",
        question="Đối tượng nào được miễn, giảm học phí?",
        cypher="""
            CALL db.index.fulltext.queryNodes('article_text', '("miễn học phí" OR "giảm học phí") AND "đối tượng"')
            YIELD node, score
            MATCH (d:Document)-[:HAS_ARTICLE|PROMULGATES*1..2]->(node)
            WHERE NOT (d)<-[:REPLACES|REPEALS]-(:Document)
            RETURN DISTINCT node.articleId AS articleId, node.heading AS heading, score
            ORDER BY score DESC
            LIMIT 10
        """,
        expected_rows=None,
        kind="fulltext",
        note="Ground truth: 81/2021/NĐ-CP Điều 15 (đối tượng miễn) và Điều 16 (đối tượng giảm 70%, 50%). Không tính Luật Giáo dục 43/2019/QH14 Điều 85 (chính sách chung), Điều 19–22 Nghị định 81 (thủ tục, cấp bù), 4532/QĐ-ĐHBK (miễn học phí học phần được công nhận cho học viên cao học).",
        id_field="articleId",
        expected_ids=frozenset({"81/2021/ND-CP#Điều 15", "81/2021/ND-CP#Điều 16"}),
    ),
]


# Gold gán trên kho v2 (403 văn bản) không dùng được cho graph dựng từ v4 (103
# văn bản): phần lớn đáp án không còn trong kho, articleId đổi dạng. Bản cho v4
# nằm ở `gold_v4.json` (cách làm ghi trong từng case); case không trả lời được
# trên v4 bị bỏ hẳn thay vì chấm 0.
_GOLD_V4 = Path(__file__).with_name("gold_v4.json")


def for_corpus(corpus: str) -> list[Query]:
    if corpus == "v2":
        return QUERIES
    gold = json.loads(_GOLD_V4.read_text(encoding="utf-8"))
    out = []
    for q in QUERIES:
        if q.name[:3] in gold["excluded"]:
            continue
        case = gold["cases"].get(q.name)
        out.append(replace(q, expected_ids=frozenset(case["expected_ids"])) if case else q)
    return out
