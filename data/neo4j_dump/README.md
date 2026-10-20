# Dựng lại graph Neo4j

File `neo4j.dump` **không nằm trong git** — 26 MB nhị phân mà `.git` của repo
mới 53 MB, đẩy vào là phình vĩnh viễn và muốn gỡ phải viết lại lịch sử. Nó tái
tạo được từ JSON đã có sẵn trong repo, nên cách dưới đây nhanh hơn là chờ tải file.

## Cách nhanh nhất: dựng thẳng từ JSON

```bash
docker compose up -d neo4j-lkg
cd src
python -m legal_knowledge_graph.core.ingest.build --dir ../data/clean/json/v4 --wipe
```

Xong phải ra **2.891 node / 4.496 quan hệ**:

| Label | Số lượng |
|---|---|
| Article | 2.281 |
| Document | 438 (103 thật + 335 stub sinh từ trích dẫn) |
| NormativeContent | 75 |
| Organization | 42 |
| Person | 29 |
| Topic | 18 |
| TargetGroup | 8 |

**Lưu ý `--dir`:** `normalize.iter_json_files` bỏ qua mọi thư mục con bắt đầu
bằng `_`, nên trỏ thẳng vào `data/clean/json/v4` chỉ nạp **80 file**, mất 23 file
trong `_nghi_ngo/`. Cả 23 file đó đều validate sạch — `_nghi_ngo` là hàng đợi
soi tay, không phải thùng rác. Muốn đủ 103 thì gom phẳng ra thư mục tạm trước:

```bash
python - <<'EOF'
import shutil
from pathlib import Path
ra = Path("/tmp/nap_v4")
for p in Path("data/clean/json/v4").rglob("*.json"):
    bo = [x for x in p.relative_to("data/clean/json/v4").parts if not x.startswith("_")]
    d = ra.joinpath(*bo); d.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, d)
EOF
```

## Nếu vẫn muốn dùng file dump

Xin file `neo4j.dump` rồi nạp. Phải **giữ nguyên tên file** vì
`neo4j-admin database load` tìm theo tên database.

```bash
docker stop <ten-container>
docker run --rm -v <ten-volume>:/data -v /duong/dan/chua/dump:/dump:ro \
  neo4j:5 neo4j-admin database load neo4j --from-path=/dump --overwrite-destination=true
docker start <ten-container>
```

`--overwrite-destination=true` **ghi đè sạch** database `neo4j` đang có.

Container trong `docker-compose.yml` là Neo4j **Community Edition**, mà
`STOP DATABASE neo4j` là lệnh Enterprise-only — Community sẽ từ chối với
`Unsupported administration command`. Nên phải `docker stop` cả container như
trên, không dừng riêng database được.

Dump tạo từ Neo4j 5.26.32, nạp vào `neo4j:5`. Neo4j 4.x không tương thích.

## Sau khi nạp

GraphRAG còn thiếu một chân: Article **chưa có embedding**, nên tìm theo ngữ
nghĩa đang tắt, chỉ còn tìm toàn văn (log chat hiện `graph_rag.seed vector=0`).
Bật bằng `lkg embed-articles` — tốn lượt gọi Gemini cho 2.281 Điều.
