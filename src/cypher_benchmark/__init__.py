"""
Bộ đo Cypher trên graph của legal_knowledge_graph — tách khỏi chatbot.

    catalogs/   ba bộ câu Cypher (samples / benchmark / scenarios)
    query.py    kiểu Query dùng chung + Cypher hybrid fulltext -> mở rộng
    scoring.py  chấm P/R/F1 theo tập ID (tái dùng khi đối chiếu BM25)
    runner.py   chạy một bộ, đo thời gian, đọc PROFILE, in bảng
    bm25.py        baseline BM25: câu hỏi -> full-text index Neo4j
    retrievers.py  các hệ đối chứng: BM25 toàn văn, vector, hybrid, hybrid + KG
    chatbot.py     chạy chatbot legal_knowledge_graph đầu-cuối (tiến trình con)
    compare.py     so sánh mọi hệ trên 20 kịch bản, ghi báo cáo
    db.py       kết nối Neo4j (biến LKG_NEO4J_*)

Chạy: `python run.py bench --source samples|benchmark|scenarios [--verbose]`,
      `python run.py bench --compare-bm25 [--out FILE.md] [--no-chatbot] [--rerun-chatbot]`.
"""
