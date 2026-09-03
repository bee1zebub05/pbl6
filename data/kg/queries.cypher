// ============================================================
// Bộ truy vấn mẫu — §6.3 Ontology
// ============================================================

// --- single-hop: văn bản còn hiệu lực của một đơn vị ---
MATCH (d:Document)-[:ISSUED_BY]->(o:Organization {name: 'Trường Đại học Bách khoa'})
WHERE d.status = 'CON_HIEU_LUC'
RETURN d.so_hieu, d.title, d.issueDate
ORDER BY d.issueDate DESC;

// --- single-hop: văn bản theo lĩnh vực ---
MATCH (d:Document)-[:HAS_TOPIC]->(t:Topic {name: 'Công tác sinh viên'})
WHERE d.status = 'CON_HIEU_LUC'
RETURN d.so_hieu, d.title, d.authority_level
ORDER BY d.authority_level DESC;

// --- multi-hop: truy ngược lên văn bản gốc thẩm quyền cao nhất (§3) ---
MATCH path = (d:Document {so_hieu_norm: '1425/QD-DHDN'})-[:BASED_ON*1..3]->(b:Document)
RETURN b.so_hieu, b.title, b.authority_level, length(path) AS bac
ORDER BY b.authority_level DESC, bac;

// --- multi-hop: chuỗi kế thừa trong một lĩnh vực ---
MATCH (d:Document)-[:HAS_TOPIC]->(t:Topic {name: 'Đào tạo'})
MATCH (d)-[:BASED_ON*1..2]->(b:Document)
WHERE b.authority_level >= 4
RETURN DISTINCT b.so_hieu, b.title, b.authority_level
ORDER BY b.authority_level DESC;

// --- hiệu lực: văn bản nào đang thay thế văn bản này ---
MATCH (new:Document)-[:REPLACES]->(old:Document {so_hieu_norm: '8/2014/TT-BGDDT'})
RETURN new.so_hieu, new.title, new.issueDate;

// --- hiệu lực: văn bản còn hiệu lực nhưng đã bị sửa đổi ---
MATCH (a:Document)-[:AMENDS]->(b:Document)
WHERE b.status = 'CON_HIEU_LUC'
RETURN b.so_hieu, b.title, collect(a.so_hieu) AS cac_van_ban_sua_doi;

// --- NormativeContent: hỏi vào nội dung, không hỏi vào quyết định bọc ngoài ---
MATCH (d:Document)-[:PROMULGATES]->(c:NormativeContent)
WHERE c.contentType = 'Quy chế' AND c.status = 'CON_HIEU_LUC'
RETURN c.title, d.so_hieu, d.issueDate
ORDER BY d.issueDate DESC;

// --- Article: retrieval cấp điều khoản (§2.7) ---
CALL db.index.fulltext.queryNodes('article_text', 'học bổng khuyến khích')
YIELD node, score
MATCH (node)<-[:HAS_ARTICLE]-(parent)
OPTIONAL MATCH (parent)<-[:PROMULGATES]-(doc:Document)
RETURN node.number, node.heading, coalesce(doc.so_hieu, parent.so_hieu_norm) AS van_ban, score
ORDER BY score DESC LIMIT 10;

// --- baseline BM25 cấp văn bản, để đối chứng với KG (§6.4) ---
CALL db.index.fulltext.queryNodes('doc_text', 'công tác sinh viên')
YIELD node, score
RETURN node.so_hieu, node.title, score
ORDER BY score DESC LIMIT 10;

// --- hybrid: BM25 lọc ứng viên rồi mở rộng theo quan hệ (§6.4) ---
CALL db.index.fulltext.queryNodes('doc_text', 'đánh giá rèn luyện')
YIELD node, score
WITH node, score ORDER BY score DESC LIMIT 5
MATCH (node)-[:BASED_ON|REFERENCES*0..2]->(mo_rong:Document)
RETURN DISTINCT mo_rong.so_hieu, mo_rong.title, mo_rong.authority_level
ORDER BY mo_rong.authority_level DESC;

// --- kiểm tra sau khi nạp ---
MATCH (n) RETURN labels(n)[0] AS nhan, count(*) AS so_luong ORDER BY so_luong DESC;
MATCH ()-[r]->() RETURN type(r) AS quan_he, count(*) AS so_luong ORDER BY so_luong DESC;
