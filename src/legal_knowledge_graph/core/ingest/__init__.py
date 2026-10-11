"""
Nạp JSON gán tay vào Neo4j:

    validate.py         kiểm JSON theo schema + kiểm tra chéo (lệnh `validate`)
    collision_check.py  báo số hiệu chuẩn hoá bị trùng (lệnh `check-collisions`)
    graph_model.py      dựng đồ thị trong bộ nhớ từ thư mục JSON
    graph_loader.py     ghi đồ thị vào Neo4j (MERGE, idempotent)
    build.py            lệnh `build`: validate + dựng + ghi
    build_pipeline.py   lệnh `all`: kiểm trùng + build + đếm kiểm tra
"""
