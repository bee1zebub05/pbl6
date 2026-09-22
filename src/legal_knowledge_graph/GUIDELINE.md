# Hướng dẫn vận hành

Chạy mọi lệnh từ **thư mục gốc của repo** (nơi có `run.py` và
`requirements.txt` cấp cao nhất), không phải từ `src/legal_knowledge_graph/`.

## 0. Yêu cầu

- Python (venv gốc repo đã cài `requirements.txt`), Docker Desktop, Node.js
  (chỉ cần nếu chạy frontend).
- `.env` ở gốc repo (copy từ `.env.example`) — điền `LKG_GEMINI_API_KEY_0`
  nếu muốn dùng `ask`/`nlq-eval`/chat UI.

## 1. Khởi động hạ tầng

```powershell
pip install -r requirements.txt
docker compose up -d
```

Kiểm tra Neo4j sống: `docker ps --filter name=neo4j-pbl6-lkg`. Browser tại
`http://localhost:7475`, Bolt `bolt://localhost:7688`.

## 2. Các lệnh CLI (`python run.py lkg <lệnh>`)

| Lệnh | Cú pháp | Khi nào dùng |
|---|---|---|
| `validate` | `validate [--dir DIR]` | Vừa gán/sửa file JSON, kiểm lỗi trước khi nạp |
| `check-collisions` | `check-collisions [--dir DIR]` | Dò `normalizedNumber` bị trùng |
| `build` | `build [--dir DIR] [--wipe]` | Nạp JSON vào Neo4j; `--wipe` xoá sạch trước khi nạp |
| `all` | `all --dir DIR [--no-wipe]` | 1 lệnh: check-collisions → validate → build --wipe → sanity |
| `query` | `query --source samples\|benchmark` | Chạy bộ Cypher kiểm tra — xem lưu ý bên dưới |
| `ask` | `ask "<câu hỏi>"` hoặc `ask --template TPL_X --param k=v` | Hỏi bằng ngôn ngữ tự nhiên → Cypher → kết quả |
| `nlq-eval` | `nlq-eval [--verbose]` | Chạy bộ câu hỏi gold cho NLQ (tốn quota Gemini) |
| `serve-api` | `serve-api [--port PORT] [--reload]` | Chạy backend chat UI |

**`query --source samples`** chỉ đúng khi Neo4j đang chứa data từ
`samples/` (17 văn bản). Muốn kiểm cơ chế:
```powershell
python run.py lkg build --dir src/legal_knowledge_graph/samples --wipe
python run.py lkg query --source samples      # kỳ vọng 16/16 PASS
python run.py lkg all --dir data/clean/json/v2   # nạp lại data thật
```

**`ask --template`** không gọi Gemini (test cơ chế, không tốn quota).
**`ask "<câu hỏi>"`** cần `LKG_GEMINI_API_KEY_0`.

## 3. Chat UI (backend + frontend)

Chạy 2 terminal song song:

```powershell
# terminal 1 — backend
python run.py lkg serve-api          # http://localhost:8000

# terminal 2 — frontend
cd src/legal_knowledge_graph/frontend
npm install                           # chỉ lần đầu
npm run dev                           # http://localhost:5173
```

Frontend gọi backend qua `VITE_API_BASE_URL` (`frontend/.env`, copy từ
`frontend/.env.example`, mặc định `http://localhost:8000` — chỉ cần sửa
nếu backend chạy port khác).

## 4. Quy trình thường gặp

**Vừa gán xong 1 file JSON mới:**
```powershell
python run.py lkg validate --dir data/clean/json/v2
python run.py lkg build --dir data/clean/json/v2
```
(không cần `--wipe` — `MERGE` tự cập nhật, không nhân đôi dữ liệu cũ)

**Nạp lại toàn bộ data thật từ đầu:**
```powershell
python run.py lkg all --dir data/clean/json/v2
```

**Demo chat UI từ đầu:**
```powershell
docker compose up -d
python run.py lkg serve-api
# terminal khác:
cd src/legal_knowledge_graph/frontend && npm run dev
```

## 5. Xử lý sự cố

| Triệu chứng | Nguyên nhân / cách xử lý |
|---|---|
| Không kết nối được Neo4j (`ServiceUnavailable`/connection refused) | Docker Desktop chưa chạy, hoặc container đã tắt — `docker ps -a`, `docker start neo4j-pbl6-lkg` |
| Gemini trả `404` model not found | `LKG_GEMINI_MODEL` trong `.env` trỏ tới model đã ngừng hỗ trợ — đổi sang model khác còn dùng được |
| Gemini trả `429` liên tục | Hết quota key hiện tại — thêm `LKG_GEMINI_API_KEY_1`, `_2`... vào `.env`, `gemini_client.py` tự xoay vòng |
| `query --source samples` FAIL hàng loạt | Neo4j đang chứa data thật (v2) chứ không phải `samples/` — build lại `samples/ --wipe` trước |
| Frontend gọi API bị chặn CORS | Backend chỉ mở CORS cho `localhost:5173`/`127.0.0.1:5173` (`core/api/app.py`) — kiểm tra frontend chạy đúng port mặc định của Vite |
| `ask`/`serve-api` báo thiếu key | `.env` chưa có `LKG_GEMINI_API_KEY_0` |
