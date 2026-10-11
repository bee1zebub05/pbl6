"""
Bộ Cypher viết tay để đo và đối chiếu (lệnh `query`), tách khỏi chatbot:

    catalog.py           regression trên samples/ (assert số dòng)
    benchmark_catalog.py đo hiệu năng trên data thật
    scenario_catalog.py  20 kịch bản dễ -> khó có ground truth, chấm P/R/F1 (đối chiếu BM25)
    runner.py            chạy một bộ, đo thời gian, đọc PROFILE
"""
