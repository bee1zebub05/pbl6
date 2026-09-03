// --- Ràng buộc duy nhất (khoá chính của từng nhãn) ---
CREATE CONSTRAINT doc_key IF NOT EXISTS
  FOR (d:Document) REQUIRE d.so_hieu_norm IS UNIQUE;
CREATE CONSTRAINT org_key IF NOT EXISTS
  FOR (o:Organization) REQUIRE o.orgId IS UNIQUE;
CREATE CONSTRAINT topic_key IF NOT EXISTS
  FOR (t:Topic) REQUIRE t.topicId IS UNIQUE;
CREATE CONSTRAINT content_key IF NOT EXISTS
  FOR (c:NormativeContent) REQUIRE c.contentId IS UNIQUE;
CREATE CONSTRAINT article_key IF NOT EXISTS
  FOR (a:Article) REQUIRE a.articleId IS UNIQUE;

// --- Chỉ mục cho truy vấn hay dùng ---
CREATE INDEX doc_status IF NOT EXISTS FOR (d:Document) ON (d.status);
CREATE INDEX doc_level IF NOT EXISTS FOR (d:Document) ON (d.authority_level);
CREATE INDEX doc_type IF NOT EXISTS FOR (d:Document) ON (d.documentType);

// --- Tìm kiếm toàn văn, làm baseline BM25 ngay trong Neo4j (§6.4) ---
CREATE FULLTEXT INDEX doc_text IF NOT EXISTS
  FOR (d:Document) ON EACH [d.title];
CREATE FULLTEXT INDEX article_text IF NOT EXISTS
  FOR (a:Article) ON EACH [a.heading, a.text];
