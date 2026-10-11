"""Nhóm 5 — Người ký và cơ quan: hồ sơ người ký, ai ký nhiều nhất, cơ cấu tổ
chức, cơ quan ban hành nhiều nhất, cơ quan ban hành theo lĩnh vực."""

from __future__ import annotations

from .base import GV, ORG_IS, VARIANT_OF_O, P_LIMIT, P_ORG, P_PERSON, P_TOP_N, PH, QL, SV, Template, doc_filters, filter_params

TEMPLATES: list[Template] = [
    # ---------------------------------------------------------------- mức 1
    Template(
        name="TPL_TOP_ORGS_BY_DOC_COUNT", action="rank_orgs", level=1, audience=(PH, GV),
        description="Xếp hạng cơ quan / đơn vị theo số văn bản đã ban hành.",
        nl_examples=("Cơ quan nào ban hành nhiều văn bản nhất?", "Top 5 đơn vị ban hành nhiều văn bản nhất"),
        cypher="""
            MATCH (o:Organization)<-[:ISSUED_BY]-(d:Document)
            RETURN o.name AS organization, count(d) AS total
            ORDER BY total DESC
            LIMIT $limit
        """,
        params=(P_TOP_N,), example_params={"limit": 5},
    ),
    Template(
        name="TPL_PERSON_PROFILE", action="person_profile", level=1, audience=(SV, PH, GV),
        description="Thông tin một người ký: học hàm học vị, các chức danh, số văn bản đã ký, văn bản đầu / cuối.",
        nl_examples=("Đoàn Quang Vinh là ai, giữ chức vụ gì?", "Thầy Nguyễn Hữu Hiếu đã ký bao nhiêu văn bản?"),
        cypher="""
            MATCH (p:Person {personId: $personId})
            OPTIONAL MATCH (d:Document)-[:SIGNED_BY]->(p)
            WITH p, d ORDER BY d.issueDate IS NULL, d.issueDate DESC
            WITH p, collect(d) AS docs
            RETURN p.fullName AS fullName, p.academicTitle AS academicTitle, p.position AS positions,
                   size(docs) AS signedCount,
                   reduce(m = null, x IN docs | CASE WHEN m IS NULL OR x.issueDate < m THEN x.issueDate ELSE m END)
                     AS firstSigned,
                   docs[0].issueDate AS lastSigned, [x IN docs[0..5] | x.documentNumber] AS latestDocuments
        """,
        params=(P_PERSON,), example_params={"personId": "Nguyễn Hữu Hiếu"},
    ),
    # ---------------------------------------------------------------- mức 2
    Template(
        name="TPL_TOP_SIGNERS", action="rank_signers", level=2, audience=(GV, QL),
        description="Ai ký nhiều văn bản nhất, có thể giới hạn trong văn bản của một cơ quan.",
        nl_examples=("Ai ký nhiều văn bản nhất?", "Ở ĐHBK ai là người ký nhiều quyết định nhất?"),
        cypher=f"""
            MATCH (d:Document)-[:SIGNED_BY]->(p:Person)
            WHERE {doc_filters("orgId")}
            RETURN p.fullName AS signer, p.position AS positions, count(d) AS total
            ORDER BY total DESC
            LIMIT $limit
        """,
        params=(*filter_params("orgId"), P_TOP_N), example_params={"orgId": "Trường Đại học Bách khoa"},
    ),
    Template(
        name="TPL_SIGNERS_OF_ORG", action="org_signers", level=2, audience=(GV, QL),
        description="Những người từng ký văn bản của một cơ quan, kèm chức danh và giai đoạn ký.",
        nl_examples=("Những ai đã từng ký văn bản của Trường Đại học Bách khoa?",
                     "Lãnh đạo Đại học Đà Nẵng nào ký văn bản trong kho?"),
        cypher=f"""
            MATCH (o:Organization)<-[:ISSUED_BY]-(d:Document)-[:SIGNED_BY]->(p:Person)
            WHERE {ORG_IS}
            RETURN p.fullName AS signer, p.position AS positions, count(d) AS total,
                   min(d.issueDate) AS fromDate, max(d.issueDate) AS toDate
            ORDER BY toDate DESC
            LIMIT $limit
        """,
        params=(P_ORG, P_LIMIT), example_params={"orgId": "Đại học Đà Nẵng"},
    ),
    Template(
        name="TPL_ORG_PROFILE", action="org_profile", level=2, audience=(PH, GV),
        description="Thông tin một cơ quan: loại, cơ quan cấp trên, số văn bản ban hành, lĩnh vực chính, văn bản mới nhất.",
        nl_examples=("Đại học Đà Nẵng ban hành bao nhiêu văn bản, chủ yếu về lĩnh vực gì?",
                     "Cho biết về Trường Đại học Bách khoa trong kho văn bản"),
        cypher=f"""
            MATCH (o:Organization {{orgId: $orgId}})
            OPTIONAL MATCH (o)-[:PART_OF]->(parent:Organization)
            CALL (o) {{
                MATCH (v:Organization) WHERE {VARIANT_OF_O}
                OPTIONAL MATCH (v)<-[:ISSUED_BY]-(d:Document)
                RETURN count(DISTINCT d) AS issued, max(d.issueDate) AS latestIssue
            }}
            CALL (o) {{
                MATCH (v:Organization) WHERE {VARIANT_OF_O}
                OPTIONAL MATCH (v)<-[:ISSUED_BY]-(:Document)-[:HAS_TOPIC]->(t:Topic)
                WITH t, count(*) AS n WHERE t IS NOT NULL ORDER BY n DESC
                RETURN collect(t.name)[0..3] AS mainTopics
            }}
            RETURN o.name AS organization, o.orgType AS orgType, parent.name AS parentOrg,
                   issued AS documentsIssued, latestIssue, mainTopics
        """,
        params=(P_ORG,), example_params={"orgId": "Đại học Đà Nẵng"},
    ),
    Template(
        name="TPL_ORG_SUBUNITS", action="org_structure", level=2, audience=(PH, GV),
        description="Cơ cấu tổ chức quanh một cơ quan: đơn vị trực thuộc và các cấp quản lý phía trên.",
        nl_examples=("Đại học Đà Nẵng gồm những đơn vị trực thuộc nào trong dữ liệu?",
                     "Trường Đại học Bách khoa trực thuộc cơ quan nào?"),
        cypher=f"""
            MATCH (o:Organization {{orgId: $orgId}})
            CALL (o) {{
                OPTIONAL MATCH (child:Organization)-[:PART_OF]->(o)
                RETURN collect(child.name) AS subUnits
            }}
            CALL (o) {{
                OPTIONAL MATCH up = (o)-[:PART_OF*1..4]->(:Organization)
                WITH up ORDER BY length(up) DESC LIMIT 1
                RETURN CASE WHEN up IS NULL THEN [] ELSE [n IN tail(nodes(up)) | n.name] END AS parents
            }}
            RETURN o.name AS organization, subUnits, parents
        """,
        params=(P_ORG,), example_params={"orgId": "Đại học Đà Nẵng"},
    ),
    # ---------------------------------------------------------------- mức 3
    Template(
        name="TPL_ORG_TOPIC_BREAKDOWN", action="org_topic_breakdown", level=3, audience=(GV, QL),
        description="Một cơ quan ban hành bao nhiêu văn bản ở từng lĩnh vực.",
        nl_examples=("ĐHBK ban hành văn bản về những lĩnh vực nào, mỗi lĩnh vực bao nhiêu?",
                     "Bộ GD&ĐT có bao nhiêu văn bản theo từng lĩnh vực?"),
        cypher=f"""
            MATCH (o:Organization)<-[:ISSUED_BY]-(d:Document)-[:HAS_TOPIC]->(t:Topic)
            WHERE {ORG_IS}
            RETURN t.name AS topic, count(DISTINCT d) AS total
            ORDER BY total DESC
        """,
        params=(P_ORG,), example_params={"orgId": "Trường Đại học Bách khoa"},
    ),
]
