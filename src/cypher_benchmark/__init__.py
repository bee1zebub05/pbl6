"""
Bộ đo Cypher trên graph của legal_knowledge_graph — tách khỏi chatbot.

    catalogs/   ba bộ câu Cypher (samples / benchmark / scenarios)
    query.py    kiểu Query dùng chung + Cypher hybrid fulltext -> mở rộng
    scoring.py  chấm P/R/F1 theo tập ID (tái dùng khi đối chiếu BM25)
    runner.py   chạy một bộ, đo thời gian, đọc PROFILE, in bảng
    db.py       kết nối Neo4j (biến LKG_NEO4J_*)

Chạy: `python run.py bench --source samples|benchmark|scenarios [--verbose]`.
"""
