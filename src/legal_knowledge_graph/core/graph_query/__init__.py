"""
Truy vấn đồ thị tri thức — mọi thứ cần để hỏi Neo4j một cách an toàn, không
phụ thuộc chatbot hay LLM nào:

    templates/            kho 68 template Cypher đã kiểm duyệt (6 nhóm nghiệp vụ)
    schema.py             mô tả schema graph (cho prompt và whitelist của guard)
    cypher_guard.py       kiểm duyệt Cypher do LLM viết (chặn ghi/xoá, whitelist, EXPLAIN, ép LIMIT)
    entity_resolver.py    biến tên thô (cơ quan, người ký, số hiệu...) thành khoá trong graph
    entity_aliases.py     bảng tên viết tắt (reference/aliases_seed.json)
    graph_context.py      GraphRAG: Điều hạt giống (vector + fulltext) và mở rộng theo quan hệ
    article_embeddings.py backfill embedding cho Article (lệnh `lkg embed-articles`)

Chatbot (`core/chat/`) dùng các khối này qua adapter ở `core/chat/adapters/`. Kết nối và chạy Cypher: `core/db.py`.
"""
