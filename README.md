# PBL6 — Kho văn bản pháp quy DUT/ĐHĐN

Pipeline: **crawl PDF → OCR → hiệu đính bằng Gemini → manifest** để làm dữ liệu
đầu vào cho knowledge graph (xem [docs/ghi_chu_knowledge_graph.txt](docs/ghi_chu_knowledge_graph.txt)).

📍 **Đang làm tới đâu → [docs/TIEN_DO.md](docs/TIEN_DO.md)**

Mọi bước đều lưu tiến độ vào **session** — Ctrl+C lúc nào cũng được, chạy lại
lệnh cũ là đi tiếp từ đúng chỗ đang dở.

---

## 1. Cấu trúc thư mục

```
PBL6/
├── run.py                     ← điểm vào duy nhất, xem `python run.py --help`
├── .env                       ← key thật (KHÔNG commit) — tạo từ .env.example
├── .env.example
├── requirements.txt
│
├── src/vanban/                ← code pipeline
│   ├── config.py              ← đường dẫn + tham số, đọc từ .env
│   ├── naming.py              ← chuẩn hoá / phục hồi tên file PDF
│   ├── session.py             ← trạng thái chạy (SQLite), dừng-tiếp tục
│   ├── pdf_text.py            ← trích text bằng PyMuPDF + chấm điểm tiếng Việt
│   ├── ocr_local.py           ← OCR tại máy bằng EasyOCR (engine mặc định)
│   ├── ocr_client.py          ← gọi API OCR, retry, tải file kết quả
│   ├── normalize.py           ← tiêm số hiệu/ngày từ metadata + bỏ phiếu trích dẫn
│   ├── gemini_fix.py          ← cắt khối + hiệu đính bằng Gemma/Gemini
│   ├── pipeline.py            ← điều phối các bước
│   ├── cli.py                 ← định nghĩa câu lệnh
│   └── kg/                    ← xây knowledge graph (rules/Ontology.md)
│       ├── norm.py            ← số hiệu chuẩn, authority_level, hiệu lực, tổ chức
│       ├── session.py         ← tiến độ xây graph (SQLite riêng, kg.db)
│       └── documents.py       ← Bước 0: chốt bảng Document
│
├── scripts/
│   ├── crawl_vanban.py        ← crawler gốc (dut.udn.vn), ghi vào data/raw/
│   └── viz_ontology.py        ← vẽ KG trong rules/Ontology.md ra docs/*.png
│
├── rules/
│   └── Ontology.md            ← đặc tả ontology v0.3 (7 node type, 12 quan hệ)
│
├── data/
│   ├── raw/
│   │   ├── pdf/<lĩnh vực>/*.pdf     ← 501 PDF đã tải
│   │   └── metadata.csv            ← metadata từ crawler
│   ├── interim/ocr_pdf/            ← PDF đã OCR (chỉ khi OCR_KEEP_PDF=true)
│   ├── processed/
│   │   ├── text_raw/<lĩnh vực>/*.txt   ← text OCR THÔ (để đối chiếu)
│   │   ├── text_norm/<lĩnh vực>/*.txt  ← đã tiêm số hiệu/ngày + sửa trích dẫn
│   │   └── text_clean/<lĩnh vực>/*.md  ← text đã Gemini hiệu đính
│   └── manifest.jsonl              ← 1 dòng JSON / văn bản, gộp mọi metadata
│
├── sessions/<tên>/state.db    ← tiến độ từng file, từng bước
├── logs/
└── docs/
```

---

## 2. Cài đặt

```powershell
pip install -r requirements.txt
Copy-Item .env.example .env
```

Mở `.env`, điền API key Gemini (lấy ở https://aistudio.google.com/apikey).
**Điền được bao nhiêu key thì điền** — pipeline xoay tua qua tất cả:

```
GEMINI_API_KEY_0=AIza...
GEMINI_API_KEY_1=AIza...
GEMINI_API_KEY_2=AIza...
```

Xem mục 7 để biết nó xoay tua thế nào.

Kiểm tra:

```powershell
python run.py health     # API OCR + key Gemini
python run.py models     # model Gemma nào key này gọi được
```

### Dùng Gemma thay Gemini

Gemma gọi qua **chính Gemini API, cùng một API key** — chỉ cần đổi `GEMINI_MODEL`
trong `.env`:

```
GEMINI_MODEL=gemma-4-31b-it
```

Pipeline tự thích ứng, không cần sửa code (chi tiết ở mục 6).
Chạy `python run.py models` để xem đúng tên model key của bạn gọi được.

---

## 3. Chạy

```powershell
python run.py scan          # quét data/raw/pdf vào session   (đã chạy: 501 file)
python run.py plan          # xem còn bao nhiêu trang, mất bao lâu
python run.py ocr           # OCR bằng EasyOCR tại máy — miễn phí (mặc định)
python run.py normalize     # tiêm số hiệu/ngày từ metadata (xem mục 6b) — chạy TRƯỚC fix
python run.py review        # liệt kê văn bản bị gắn cờ, cần soi tay
python run.py fix           # hiệu đính bằng Gemma/Gemini
python run.py export        # ghi data/manifest.jsonl
```

Xây knowledge graph (§ `rules/Ontology.md`, xem mục 10):

```powershell
python run.py kg docs       # Bước 0 — chốt bảng Document
python run.py kg status     # xem tiến độ
python run.py kg review     # văn bản cần soi tay
```

Vẽ sơ đồ:

```powershell
python scripts/viz_ontology.py          # sơ đồ ontology  -> docs/kg_ontology.png
python scripts/viz_ontology.py --data   # đồ thị thật     -> docs/kg_instance.png
```

Hoặc gộp: `python run.py all`

Xem tiến độ bất kỳ lúc nào: `python run.py status`

### Dừng và chạy tiếp

Ctrl+C một lần → pipeline hoàn tất các file đang dở rồi thoát êm.
Chạy lại đúng lệnh đó → tiếp tục, các file đã xong bị bỏ qua.

Chạy nhiều session song song để thử nghiệm:

```powershell
python run.py --session thunghiem ocr --limit 5
python run.py status --list
```

### Hai engine OCR

```powershell
python run.py ocr                  # local: EasyOCR tại máy, miễn phí (mặc định)
python run.py ocr --engine api     # api: nhanh hơn nhưng tốn credit
```

Đổi mặc định lâu dài: `OCR_ENGINE=local` trong `.env`. Xem mục 5 để biết vì sao
local là mặc định (nó chính xác **hơn** api).

### Engine api: chạy tới khi gần hết credit rồi dừng

Chỉ áp dụng cho `--engine api`. Mặc định dừng khi credit còn **100**:

```powershell
python run.py ocr --engine api                      # sàn mặc định 100
python run.py ocr --engine api --min-credits 300    # chừa lại nhiều hơn
python run.py ocr --engine api --min-credits 0      # chạy đến cạn
```

Đổi mặc định lâu dài: `OCR_MIN_CREDITS=100` trong `.env`.

Khi chạm sàn nó in ra còn bao nhiêu file chưa OCR và ghi luôn vào session.
**Nạp thêm credit lúc nào cũng được, rồi chạy lại đúng lệnh cũ** — nó tự đọc
credit mới và đi tiếp từ chỗ đang dở, không làm lại file nào:

```
  >> DỪNG VÌ CHẠM SÀN CREDIT (còn 2,280, sàn 2,280).
     Còn 473 file chưa OCR — session đã nhớ.
     Nạp thêm credit rồi chạy lại:  python run.py ocr
```

`python run.py status` cũng nhắc lại nếu lần trước dừng vì hết credit.

### Chạy lại phần lỗi

```powershell
python run.py reset ocr         # đưa các file lỗi về pending
python run.py reset fix --all   # hiệu đính lại TOÀN BỘ
```

---

## 4. ⚠️ Credit OCR tính theo TRANG

Đo thực tế: OCR 4 file / 29 trang → trừ **31 credit**. Không phải mỗi file 1 credit.

Hai cái bẫy khi đếm credit, cả hai đều đã xử lý trong `CreditGuard`:

- **`remaining_credits` trong response bị trễ.** Đo được một file 10 trang mà
  response chỉ báo trừ 2 credit. Tin thẳng con số đó là tiêu lố sàn. Pipeline
  vì vậy tự giữ sổ theo **số trang** (chính xác: 39 trang đặt chỗ / 37 credit bị
  trừ) và chỉ nghe theo API khi API báo **thấp hơn** sổ.
- **`/v1/admin/key-status` báo số dư của key khác.** Server xoay vòng nhiều key;
  endpoint đó chỉ thấy key 0 (báo 2.398 trong khi key phục vụ mình còn 2.343).
  Lúc bắt đầu pipeline lấy **con số thấp hơn** giữa endpoint này và số lần chạy
  trước ghi lại. Nếu ước lượng lỡ thấp hơn thực tế (ví dụ bạn vừa nạp thêm
  credit), nó chạy thử **một file ít trang nhất** để lấy con số thật rồi mới
  chạy tiếp — nhờ vậy không bị kẹt cứng sau khi nạp tiền.

Nhờ hai chốt này, lần chạy thử với sàn 2.280 dừng đúng ở **2.280**, tiêu vừa
khít 26/26 trang ngân sách.

Tổng kho là **501 file / 11.420 trang**, tức muốn OCR hết bằng API thì cần
~11.400 credit. Thực tế credit đã cạn sau 225 file.

**Không cần lo nữa** — engine `local` (mục 5) làm phần còn lại, miễn phí và không
giới hạn. Phần credit này chỉ còn ý nghĩa nếu bạn muốn dùng API cho nhanh.

`python run.py plan` luôn in ra con số cập nhật cho cả hai engine.

---

## 5. Vì sao OCR tại máy lại là mặc định

Đã benchmark 4 engine trên **chính file scan trong kho này**, đo bằng
`vietnamese_score` (tỷ lệ chữ cái mang dấu — text tiếng Việt sạch ≈ 0,25–0,30):

| Engine | `vi_score` | Tốc độ CPU | Kết luận |
|---|---|---|---|
| **EasyOCR `vi`** | **0,284 – 0,319** | 12,7 s/trang @150 DPI | **Chọn cái này** |
| API (Tesseract) | 0,262 – 0,302 | ~3 s/trang | Tốt, nhưng tốn credit |
| PaddleOCR `vi` | 0,153 – 0,165 | 110 s/trang | Mất dấu nặng hàng loạt |
| RapidOCR mặc định | 0,008 | 10 s/trang | Model Trung+Anh, mất sạch dấu |

Cùng một dòng, khác nhau thấy rõ:

```
Chuẩn      : CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM   BỘ GIÁO DỤC VÀ ĐÀO TẠO
EasyOCR    : CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM   BỘ GIÁO DỤC VÀ ĐÀO TẠO
API        : CONG HÒA XA HỌI CHỦ NGHĨA VIỆT NAM   BỘ GIÁO DỤC VÀ ĐÀO TAO
PaddleOCR  : CONG HOÀ XÃ HQI CHÙ NGHÎA VIĘT NAM   B GIÁO DĘC VÀ ĐÀO TO
```

EasyOCR **chính xác hơn API** trên cả 3 file thử, lại miễn phí và không giới hạn.
Đổi lại là chậm hơn: **~360 trang/giờ** (nhịp duy trì, đo trên một lần chạy thật
87 trang liên tục — benchmark ngắn cho 431 nhưng đó là pool đã ấm). Cả kho
11.400 trang mất khoảng **30 giờ**. Ctrl+C lúc nào cũng được, session nhớ hết.

Nó còn cứu được nhóm file lớp text hỏng ở mục 6. Ví dụ thật:

```
Lớp text trong PDF   : DI HOC  DA NANG / TR1NG 031 HQC BACH KHOA / QUYET BNH
EasyOCR đọc lại ảnh  : ĐẠI HỌC ĐÀ NẴNG / TRƯỜNG ĐẠI HỌC BÁCH KHOA / QUYẾT ĐỊNH
                       (vi_score 0,065 -> 0,298)
```

Ba tham số đều đã đo, đừng chỉnh bừa:

- **`LOCAL_OCR_DPI=150`** — quét từ 120 đến 300 DPI, `vi_score` chỉ dao động
  0,250–0,255 và số ký tự y hệt nhau, nhưng 300 DPI **chậm hơn 2,3 lần**.
- **`LOCAL_OCR_WORKERS=4` × `LOCAL_OCR_THREADS=3`** — throughput bão hoà ở đây
  (1 tiến trình: 246 trang/giờ → 4 tiến trình: 431 → 6 tiến trình: 430).
  Thêm tiến trình không nhanh hơn vì torch đã ăn hết 12 nhân.
- **`paragraph=False`** trong `ocr_local.py` — EasyOCR trả về từng dòng rồi
  pipeline tự gom theo toạ độ. Cùng nội dung / cùng `vi_score` / cùng tốc độ với
  `paragraph=True`, nhưng giữ **29 dòng thay vì gộp còn 4**. Cấu trúc
  Điều/Khoản là thứ bước hiệu đính và knowledge graph cần.

Song song ở mức **trang** chứ không phải mức file: văn bản dài nhất trong kho có
155 trang, giao trọn cho một tiến trình thì Ctrl+C mất cả nửa tiếng công.

Manifest và cột `ocr_engine` trong session ghi lại mỗi file được OCR bằng engine
nào, nên sau này muốn chạy lại nhóm `api` bằng `local` cho đồng đều thì biết
đường mà lọc.

---

## 7. Nhiều API key: xoay tua tự động

Free tier của Gemini/Gemma tính hạn mức **trên từng key** (mỗi phút và mỗi
ngày). Có N key nghĩa là có N lần hạn mức đó — miễn là biết trải request ra.

Khai báo bao nhiêu key cũng được, ba cách đều nhận và **gộp chung**:

```
GEMINI_API_KEY_0=...        # đánh số tuỳ ý, không cần liên tục
GEMINI_API_KEY_7=...
GEMINI_API_KEY=...          # cách cũ, vẫn chạy
GEMINI_API_KEYS=k1,k2,k3    # nhét hết vào một dòng
```

Key trùng nhau bị tự loại (dán nhầm hai lần cũng không sao).

### Cách chọn key

Mỗi lượt gọi mượn một key từ bể (`src/vanban/key_pool.py`), chọn theo
**key nào đang gánh ít request nhất**, hoà thì lấy key lâu chưa dùng. Cách này
trải tải đều dù số luồng nhiều hay ít hơn số key.

Mỗi key có ba trạng thái:

| Trạng thái | Khi nào | Xử lý |
|---|---|---|
| khoẻ | bình thường | gọi được ngay |
| nghỉ | vừa dính 429 | khoá tạm, hết giờ tự quay lại |
| chết | 401/403, key sai/bị thu hồi | loại vĩnh viễn khỏi vòng xoay |

**Điểm mấu chốt:** khi một key dính 429, lượt gọi đó được thử **lại ngay trên
key khác** chứ không ngồi chờ hết cooldown. Chỉ khi *mọi* key cùng nghỉ thì
luồng mới ngủ, và ngủ đúng đến lúc key sớm nhất tỉnh dậy.

Thời gian nghỉ lấy theo `retryDelay` mà API gửi kèm; không có thì dùng
`GEMINI_KEY_COOLDOWN` (45s). Riêng lỗi hết quota **ngày** thì nghỉ hẳn
`GEMINI_KEY_COOLDOWN_DAILY` (1 giờ) — thử lại sớm hơn chỉ tốn công.

Hết sạch key còn sống thì mẻ dừng lại, các file chưa làm được trả về
`pending` (không phải `failed`) để chạy lại là đi tiếp.

### Số luồng

Hai con số điều khiển độ song song:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `GEMINI_MAX_INFLIGHT_PER_KEY` | 2 | tối đa bao nhiêu request bay cùng lúc **trên một key** |
| `GEMINI_WORKERS` | (trống) | số luồng; để trống = `2 x số key`, trần 16 |

Chặn theo từng key quan trọng hơn tổng số luồng: hạn mức free tier tính theo
key, mà vượt trần thì mất cả lượt gọi lẫn thời gian nghỉ phạt. Giữ 2 request
đồng thời/key thì gần như không bao giờ chạm 429 — đo thực tế trên 4 key sống,
8 văn bản liên tiếp, **không có 429 nào**.

6 key -> 12 luồng. Muốn ghì lại thì điền `GEMINI_WORKERS` số cụ thể.

### Kiểm tra key

```powershell
python run.py health
```

Nó gọi thử **từng key một** và báo key nào hỏng:

```
GEMINI: 6 key, model gemma-4-26b-a4b-it, 16 luồng
  #0               AIzaSy…28P4  OK
  #2               AQ.Ab8…M3BA  HỎNG: 403 PERMISSION_DENIED. Your project has been denied access
  #3               AQ.Ab8…P-vA  OK
  -> 4/6 key dùng được
```

Cuối mỗi mẻ `fix` cũng in lại tình trạng từng key (số lượt đã gọi, đang nghỉ
hay đã chết).

---

## 6. ⚠️ Bẫy: PDF "có text" nhưng text là chữ rác

Trực giác thông thường là "PDF nào đã có lớp text thì khỏi OCR". **Ở kho này
trực giác đó sai.** Rất nhiều văn bản cũ soạn bằng font tiếng Việt đời cũ
(VNI/TCVN3), lớp text copy ra thành:

```
"ĐẠI HỌC ĐÀ NẴNG"   ->   "DI HOC  DA NANG"
"Nghị định số"       ->   "Ngh/ d/nh sO'"
"QUYẾT ĐỊNH"         ->   "QUYET BNH"
```

Pipeline phát hiện bằng **tỷ lệ chữ cái mang dấu tiếng Việt** (`vietnamese_score`
trong `pdf_text.py`). Đo trên kho này:

| Loại | Điểm |
|---|---|
| Text tiếng Việt bình thường | ~0,25 |
| Lớp text hỏng do font cũ | 0,00 – 0,09 |

Ngưỡng `VI_SCORE_OK = 0.15`. Kết quả quét toàn bộ 501 file:

| | |
|---|---|
| Lớp text **lành** — bỏ OCR được | **27 file** |
| Lớp text **hỏng** — buộc phải OCR | **184 file** |
| Bản scan, không có text | phần còn lại |

Điểm này được dùng ở 2 chỗ, để pipeline không bao giờ ghi chữ rác ra file:

- `skip-native` chỉ nhận file đạt ngưỡng, và **kiểm tra lại trên toàn văn bản**
  (lúc scan chỉ đọc 5 trang đầu cho nhanh).
- Khi OCR thất bại hết lượt retry, chỉ quay về dùng lớp text sẵn có nếu lớp đó
  đạt ngưỡng; không đạt thì để `failed` — thà thiếu còn hơn sai.

---

## 6b. ⚠️ Số hiệu và ngày ban hành là **chữ viết tay**

Đây là lớp lỗi nặng nhất của kho này, và nó không sửa được bằng cách OCR tốt hơn.

Biểu mẫu quyết định của ĐHĐN/ĐHBK in sẵn `Số:      /QĐ-ĐHĐN` và
`ngày ... tháng ... năm 20..`, phần trống điền tay **sau khi in**. EasyOCR train
trên chữ in nên đọc nét viết tay ra ký tự chữ cái:

| OCR đọc được | Thực tế |
|---|---|
| `Số:234+ /QĐ-ĐHBK` … `ngày A4 tháng 11` | `2347/QĐ-ĐHBK`, ngày 14 |
| `Số: 138 IQĐ-ĐHĐN` | `738/QĐ-ĐHĐN` |
| `Số:24S3/QĐ-ĐHĐN` … `ngày 26 tháng G` | `2453/…`, tháng 6 |
| `Số:   /9A IQĐ-ĐHĐN` … `ngày /6 tháng 01` | `191/QĐ-ĐHĐN`, ngày 16 |

Đo trên 501 văn bản đã OCR:

| | Trước | Sau `normalize` |
|---|---|---|
| Số hiệu đúng | **25,5 %** | **94,6 %** |
| Ngày ban hành đúng | **40,7 %** | **82,0 %** |
| Hậu tố IN (`QĐ-ĐHĐN`) đúng | 75,2 % | — |

Chênh lệch 25 % / 75 % trên **cùng một dòng** chính là ranh giới giữa phần viết
tay và phần in.

### Cách xử lý: không OCR lại, mà tiêm từ metadata

Crawler đã lấy sẵn `so_hieu` và `ngay_ban_hanh` cho cả 501 văn bản trong
`data/raw/metadata.csv`. Không có kỹ thuật OCR nào thắng được việc đã biết đáp
án, nên `normalize` ghi đè thẳng vào header trang 1 — chính xác tuyệt đối, chi
phí bằng 0.

Ba ràng buộc an toàn trong [`normalize.py`](src/vanban/normalize.py):

- **Chỉ đụng vào vùng header**, dừng trước chữ `Căn cứ` đầu tiên. Phần căn cứ
  pháp lý cũng viết `ngày 04 tháng 04 năm 1994` nhưng đó là chữ IN của văn bản
  **khác** — ghi đè vào đó là phá dữ liệu.
- **Neo vào hậu tố in** (`/QĐ-ĐHBK`) chứ không vào chữ `Số:`. Chữ "Số" nhỏ nên
  OCR trả về `S6:`, `$6:`, có file mất hẳn — neo vào đó thì trượt 66/457 file.
- **Không tìm thấy thì bỏ qua và gắn cờ**, thà không sửa còn hơn sửa nhầm.

`text_raw/` không bao giờ bị ghi đè; kết quả ghi sang `text_norm/`.

### Trích dẫn trong nội dung: bỏ phiếu chéo

Khác hẳn: 4.571 trích dẫn (~9,1 mỗi văn bản) kiểu
`Căn cứ Nghị định số 32/CP ngày 04/4/1994` là **chữ in**, và không có đáp án ở
đâu cả. Nhưng chúng lặp lại giữa các văn bản, nên sửa được bằng bỏ phiếu:

```
79x  115/2020/NĐ-CP      ← bản đúng
 1x  115/202O/NĐ-CP      ← thua phiếu, sửa theo bản đúng
```

1.162 trích dẫn, 358 cái đủ ≥3 phiếu, sửa được **64** chỗ hỏng.

Quy tắc an toàn bắt buộc: **chỉ sửa trích dẫn có ký tự không thể là chữ số.**
`l15/2020/NĐ-CP` sửa được vì `l` không phải chữ số. `15/2020/NĐ-CP` thì KHÔNG
đụng tới — nó có thể là một văn bản khác thật.

### Cờ cần soi tay

`python run.py review` liệt kê các văn bản `normalize` không tự tin. 137/501 file,
gồm 3 loại:

```
0031  542/QĐ-ĐHBK    khong-tim-thay-so-hieu
0067  3604/QĐ-ĐHBK   ngay-vo-ly: ngày 30 tháng 42 năm 2021
0439  2453/QĐ-ĐHBK   metadata-nghi-ngo: nguoi-ky-la-DHDN
```

Loại thứ ba đáng chú ý: nó bắt lỗi của **chính metadata**. Doc 0439 crawler ghi
`QĐ-ĐHBK`, nhưng bản scan lẫn chức danh người ký đều là Đại học Đà Nẵng — ở đây
OCR đúng, metadata sai. Chức danh người ký là chữ in trong thân văn bản nên dùng
được làm trọng tài.

`ngay-vo-ly` chỉ gắn cờ, **không tự sửa**: `tháng 42` gần như chắc là `tháng 12`,
nhưng `ngày 34` có thể là 31, 14 hay 24 — đoán bừa còn tệ hơn để nguyên.

### Vì sao phải chạy TRƯỚC `fix`

Prompt Gemini có quy tắc *"số hiệu, ngày tháng chỉ sửa khi chắc chắn, không chắc
thì GIỮ NGUYÊN"*. Với số viết tay thì nó không bao giờ chắc được, nên nếu chạy
`fix` trước, `ngày 4Í tháng 22` sẽ đi thẳng vào dữ liệu cuối. Đưa sẵn giá trị
đúng vào text là cách duy nhất làm quy tắc đó vừa an toàn vừa có ích.

`fix` tự động đọc `text_norm/` nếu có, không thì quay về `text_raw/`.

---

## 7. Bước hiệu đính hoạt động thế nào

OCR tiếng Việt sai theo vài kiểu rất đặc trưng. Trích từ một file thật trong kho:

| OCR ra | Đúng phải là |
|---|---|
| `16 chức` | `tổ chức` |
| `Gido dục` | `Giáo dục` |
| `ngdn sách` | `ngân sách` |
| `vé việc` | `về việc` |
| `QUYET ĐỊNH` | `QUYẾT ĐỊNH` |
| `Quyết dmh` | `Quyết định` |
| `NO-HĐĐH` | `NQ-HĐĐH` |

Kết quả thật từ lần chạy trên kho này (`gemma-4-26b-a4b-it`):

```
TRUONG                          -> TRƯỜNG
QUYET                           -> QUYẾT
Số:2569 /QĐ-PHBK                -> Số: 2569/QĐ-ĐHBK
điền hình tiên tiên             -> điển hình tiên tiến
VADPAOTAO CONG                  -> VÀ ĐÀO TẠO CỘNG
Ỉ1'r Ng'h,z' quyét s6 08/NQAHD£'>angdy  -> cứ Nghị quyết số 08/NQ-HĐĐH ngày
```

Độ dài giữ nguyên **99%** (không tóm tắt), `vi_score` tăng 0,274 → 0,303.
Tốc độ ~9,6 file/phút, cả kho 501 file mất khoảng **1 giờ**.

Ba chốt chặn để model không "sáng tác":

1. **Prompt ràng buộc chặt** — cấm tóm tắt, cấm thêm nội dung, giữ nguyên
   Điều/Khoản/Điểm và đánh dấu trang; số hiệu/ngày tháng không chắc thì để nguyên.
2. **Cắt khối theo ranh giới trang** (mặc định ~7.000 ký tự) — đã kiểm chứng
   round-trip không mất chữ, tránh cụt output với văn bản dài (có file 155 trang).
3. **Kiểm tra độ dài** — bản sửa ngắn hơn 60% bản gốc bị coi là model đã tóm tắt
   → thử lại, hết lượt thì **giữ nguyên text thô** thay vì ghi kết quả sai.

Text thô luôn được giữ ở `data/processed/text_raw/` nên lúc nào cũng đối chiếu
được model đã sửa những gì.

### Gemma khác Gemini ở đâu

Gemma dùng chung API và chung key với Gemini nhưng khác ở ba chỗ, cả ba đều đã
đo trên `gemma-4-26b-a4b-it`:

| | Gemini | Gemma |
|---|---|---|
| Hướng dẫn hệ thống | `system_instruction` | **ghép vào đầu lượt `user`** — Gemma chỉ có vai `user`/`model`, truyền `system_instruction` là lỗi `Developer instruction is not enabled` |
| Tắt reasoning | `thinking_budget=0` | **`thinking_level="minimal"`** — `thinking_budget` bị trả `400 not supported`, và ngược lại |
| Kích thước khối | 7.000 ký tự | **4.500** (`GEMMA_CHUNK_CHARS`), hạn mức output nhỏ hơn |

**Bắt buộc tắt thinking, không phải cho nhanh mà vì không tắt là hỏng hẳn.**
Gemma 4 là model có reasoning. Để mặc định, với một khối OCR 3.200 ký tự nó tiêu
**32.765 token vào phần suy nghĩ**, chạm `MAX_TOKENS` rồi trả về **rỗng hoàn toàn**
(0 token đầu ra). Cùng prompt đó khi đặt `thinking_level="minimal"`: **2 giây, 0
token suy nghĩ, sửa đúng hết**.

Vì vậy `requirements.txt` ghim **`google-genai>=2.0`** — SDK 1.x chưa có trường
`thinking_level`, cài bản cũ là chắc chắn dính lỗi trả về rỗng.

Khi model trả về rỗng, client **không** thử lại y hệt (vô ích, tốn thời gian) mà
hạ ngay sang cấu hình đơn giản hơn, và log ra lý do thật:
`trả về rỗng (tiêu 32765 token vào thinking, finish=[MAX_TOKENS])`.

Ngoài ra client có **cơ chế tự hạ cấu hình**: nếu model từ chối một tham số
(`not supported` / `not enabled` / `invalid_argument`), nó tự lùi sang cấu hình
đơn giản hơn, in ra một dòng thông báo rồi nhớ luôn cho các lần sau. Lỗi quota
(`429`) **không** kích hoạt cơ chế này — cái đó đi theo đường retry + backoff
bình thường. Nhờ vậy đổi sang model Gemma nào cũng chạy được, kể cả model ra
sau này.

File đầu ra `data/processed/text_clean/<lĩnh vực>/<file>.md` có front-matter:

```yaml
---
doc_id: "0028"
so_hieu: "175/QĐ-ĐHBK"
linh_vuc: "Thanh tra, kiểm tra"
ten_van_ban: "Quy định tiếp công dân, giải quyết khiếu nại..."
so_trang: 4
nguon_pdf: "Thanh tra, kiểm tra/0028_175_QĐ-ĐHBK_....pdf"
ocr_status: "done"
hieu_dinh: "gemini-2.5-flash"
khoi_da_sua: "2/2"
---
```

---

## 8. Ghi chú kỹ thuật

- **API OCR hay lỗi.** Nó xoay vòng 9 key upstream (iLovePDF); trúng key hỏng thì
  trả `HTTP 500` kèm `401 Unauthorized`. Gọi lại thường là được — client retry 5
  lần với exponential backoff. Quan sát thực tế: ~1/6 request cần retry.
- **`download_url` chỉ sống 300 giây** và chứa ký tự tiếng Việt chưa encode →
  client tự percent-encode và tải ngay sau khi OCR xong.
- **OCR hỏng vẫn cố cứu file.** Hết lượt retry mà PDF gốc có lớp text **lành**
  (xem mục 6) thì pipeline dùng luôn lớp đó và đánh dấu `fallback`; lớp text
  hỏng thì để `failed`, chạy `python run.py reset ocr` để thử lại sau.
- **46 file có tên hỏng** (crawler parse nhầm cả header bảng, dồn hết vào thư mục
  `ID`). `naming.py` moi lại được `doc_id` + lĩnh vực thật từ trong tên, nên
  thư mục `ID` biến mất khỏi kết quả — các file đã về đúng lĩnh vực của chúng.
  Cột `ten_file_hong` trong manifest đánh dấu nhóm này.
- **Số hiệu văn bản lấy từ `metadata.csv`**, không parse từ tên file: crawler đã
  thay `/` thành `_` khi đặt tên nên `24/2018/QH14` không tách ngược lại được.
- Console Windows mặc định cp1252 sẽ vỡ khi in tiếng Việt — `cli.py` tự ép UTF-8.

---

## 9. Tinh chỉnh

Sửa trong `.env`:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `OCR_ENGINE` | local | `local` = EasyOCR tại máy, `api` = gọi API |
| `LOCAL_OCR_LANGS` | vi | ngôn ngữ EasyOCR (`vi,en` nếu cần kèm tiếng Anh) |
| `LOCAL_OCR_DPI` | 150 | **đã đo — đừng tăng**, 300 DPI chậm 2,3× mà không chính xác hơn |
| `LOCAL_OCR_WORKERS` | 4 | **đã đo — đừng tăng**, throughput bão hoà ở 4 |
| `LOCAL_OCR_THREADS` | 3 | luồng torch mỗi tiến trình |
| `OCR_MIN_CREDITS` | 100 | sàn dừng, chỉ với `--engine api` |
| `OCR_WORKERS` | 3 | luồng OCR song song (chỉ với `--engine api`) |
| `OCR_MAX_ATTEMPTS` | 5 | số lần retry khi API lỗi |
| `OCR_KEEP_PDF` | false | giữ lại PDF đã OCR (rất tốn ổ cứng) |
| `GEMINI_MODEL` | gemma-4-31b-it | model hiệu đính (`python run.py models` để xem key gọi được gì) |
| `GEMMA_THINKING_LEVEL` | minimal | **đừng đổi** — bật thinking là Gemma trả về rỗng |
| `GEMMA_CHUNK_CHARS` | 4500 | trần khối riêng cho Gemma |
| `GEMINI_MAX_OUTPUT_TOKENS` | 16000 | trần output mỗi khối |
| `GEMINI_WORKERS` | 4 | luồng gọi Gemini (free tier để 2–4) |
| `GEMINI_CHUNK_CHARS` | 7000 | kích thước mỗi khối gửi lên |
| `GEMINI_THINKING_BUDGET` | 0 | >0 nếu muốn model cẩn thận hơn |
| `NATIVE_TEXT_THRESHOLD` | 200 | ký tự/trang để coi PDF là bản số |
| `KG_CORPUS_DIR` | data/clean/text_clean_gemma | kho text đã hiệu đính dùng để xây graph |
#   p b l 6 
 
 

---

## 10. Xây knowledge graph — Bước 0: bảng `Document`

Đặc tả ở [rules/Ontology.md](rules/Ontology.md). Lộ trình §8 chia 5 giai đoạn;
phần code hiện có mới làm xong **Bước 0** — chốt bảng `Document`, tức khoá chính
mà mọi quan hệ ở các bước sau sẽ nối vào.

```powershell
python run.py kg docs        # thu thập + suy diễn + xuất data/kg/*.jsonl
python run.py kg status      # xem lại số liệu bất kỳ lúc nào
python run.py kg review      # 73 văn bản có ghi chú, cần soi tay
python run.py kg review --grep header-lech    # lọc theo loại ghi chú
```

Dừng bằng Ctrl+C lúc nào cũng được, chạy lại đúng lệnh đó là đi tiếp — tiến độ
nằm trong `sessions/<tên>/kg.db`, **tách riêng** khỏi `state.db` của pipeline OCR
(lý do ở đầu file `src/vanban/kg/session.py`).

### Kết quả trên kho hiện tại

```
450 Document phân biệt        (từ 501 dòng manifest + 460 file text)
 14 Organization              (kèm cây PART_OF)
 18 Topic
```

| Bậc thẩm quyền (§3) | Số văn bản |
|---|---|
| 6 — Hiến pháp | 1 |
| 5 — Luật / Pháp lệnh | 50 |
| 4 — Nghị định | 49 |
| 3 — Thông tư / Thủ tướng / bộ ngành | 158 |
| 2 — Đại học Đà Nẵng | 94 |
| 1 — Trường ĐHBK | 98 |

Hiệu lực: 430 còn hiệu lực, 15 hết hiệu lực (đã tách được `expiryDate`), 5 chưa
rõ (nhóm file không có trong manifest).

### Ba việc bước này làm

**1. Neo vào kho text CÓ THẬT.** `data/manifest.jsonl` xuất ngày 17/8, ghi
`fix_status: pending` cho 498/501 và `text_clean: null` — trong khi 460 văn bản
đã hiệu đính xong và nằm ở `data/clean/text_clean_gemma/`. Nên nguồn chuẩn về
**text** là thư mục trên đĩa; manifest chỉ còn là nguồn chuẩn về **metadata**
(ngày ban hành, cơ quan, tình trạng hiệu lực — `data/raw/metadata.csv` đã bị xoá
cùng thư mục PDF nên không còn nguồn nào khác).

**2. Gộp trùng theo số hiệu.** 501 dòng manifest chỉ ứng với 445 số hiệu phân
biệt: 55 nhóm trùng, 11 nhóm được crawler cấp **hai `doc_id` khác nhau** cho cùng
một văn bản (`1980/QĐ-ĐHBK` = 0044 + 0213). §2.1 lấy `so_hieu_norm` làm khoá
chính — không gộp thì `MERGE` trong Neo4j sẽ vỡ. Bốn nhóm nằm ở **hai lĩnh vực
khác nhau**; đó không phải xung đột mà đúng bản chất `HAS_TOPIC` n→m (§4), nên
gộp bằng cách hợp nhất danh sách topic chứ không chọn một bỏ một.

**3. Suy các thuộc tính ontology.** `authority_level` (§3), `status` +
`expiryDate` tách từ chuỗi `"Hết hiệu lực 01/01/2024"`, `documentType` tách khỏi
`"Quyết định, Quy định"` (§2.6), `orgId`/`orgType`/`parentOrg` (§2.2).

### ⚠️ Bậc thẩm quyền phải xét theo CƠ QUAN, không theo LOẠI

Bảng §3 trộn hai tiêu chí: bốn bậc trên xét theo loại văn bản, hai bậc dưới xét
theo cơ quan. Với kho này phải lấy **cơ quan** làm chính — 252/501 văn bản mang
loại `"Quyết định, Quy định"` nhưng do đủ mọi cấp ban hành, từ Thủ tướng xuống
tới trường. Xét theo loại thì cả 252 cái rơi chung một bậc, vô nghĩa.

Mỗi node vì vậy mang thêm `level_note` ghi rõ bậc đó tra thẳng từ ontology
(`onto`) hay là suy rộng (`suy-rong: chinh-quyen-dia-phuong` — UBND thành phố
không có bậc nào trong §3).

### ⚠️ Nhãn `"Luật, Pháp lệnh"` là tên NHÓM, không phải loại văn bản

50 văn bản dùng chung nhãn này, nghĩa là "Luật **hoặc** Pháp lệnh". Tách theo dấu
phẩy như `"Quyết định, Quy định"` là sai — phải nhìn số hiệu mới biết cái nào là
cái nào (`100/2015/QH13` → Luật). Xem `norm.GROUP_LABELS`.

### Đối chiếu header: thước đo văn bản nào tin được

Bước này mở text đã hiệu đính, đọc vùng đầu trang 1, so số hiệu in trong đó với
metadata. Bước `normalize` trước đây đã tiêm số hiệu vào đúng chỗ này (mục 6b),
nên tỷ lệ khớp chính là **thước đo header nào đáng tin** — Bước 1 (cắt vùng) và
Bước 2 (trích dẫn) dựa hết vào đó.

| Kết luận | Số VB | Nghĩa |
|---|---|---|
| `khop` | 381 | header có đúng số hiệu này |
| `gan-khop` | 5 | khớp số + năm, đuôi bị cắt do xuống dòng |
| `lech` | 34 | header có số hiệu **khác hẳn** — cần soi tay |
| `khong-thay` | 28 | header không đọc ra số hiệu nào |
| `khong-co-file` | 2 | chưa có text hiệu đính |

386/448 (86%) header tin được. Nhóm `lech` không phải rác — nó bắt được **lỗi
metadata thật**:

```
1/2024/TT-NBV     header-lech: 1/2024/TT-BNV      <- metadata gõ nhầm BNV -> NBV
2453/QĐ-ĐHBK      header-lech: 2453/QD-DHDN       <- đúng cảnh báo normalize.py đã nêu
53/2022/NĐ-VP     header-lech: 53/2022/ND-CP      <- metadata sai hậu tố
17/2021/TT-BGDĐT  header-lech: 7/2021/TT-BGDDT    <- OCR nuốt mất chữ số đầu
```

### Đầu ra

```
data/kg/documents.jsonl       450 dòng — node Document (§2.1)
data/kg/organizations.jsonl    14 dòng — node Organization + parentOrg (§2.2)
data/kg/topics.jsonl           18 dòng — node Topic (§2.4)
```

Một dòng `documents.jsonl`:

```json
{
  "so_hieu_norm": "10/2016/TT-BGDDT",
  "so_hieu": "10/2016/TT-BGDĐT",
  "title": "Quy chế Công tác sinh viên đối với chương trình đào tạo hệ chính quy",
  "documentType": "Thông tư",
  "normativeType": null,
  "authority_level": 3,
  "status": "CON_HIEU_LUC",
  "issueDate": "2016-04-05",
  "effectiveDate": "2016-05-23",
  "expiryDate": null,
  "orgId": "bo_giao_duc_va_dao_tao",
  "topics": ["Công tác sinh viên"],
  "doc_ids": ["0005"],
  "clean_path": "data/clean/text_clean_gemma/Công tác sinh viên/0005_...txt",
  "clean_chars": 37884,
  "header_check": "khop",
  "level_note": "onto",
  "is_stub": false
}
```

Chú ý `normativeType: null` ở ví dụ trên dù tiêu đề rõ ràng là **Quy chế**:
metadata chỉ ghi `loai = "Thông tư"`. Metadata bắt được 224/450 trường hợp
`NormativeContent`; số còn lại nằm trong tiêu đề và thân văn bản, phải chờ
Bước 4 mới moi ra được.

`is_stub` luôn `false` ở đây — node stub (§1: văn bản bị viện dẫn nhưng chưa
crawl) sẽ do Bước 2 sinh ra. Toàn bộ hàm trong `norm.py` chỉ cần **số hiệu** nên
chạy được cho cả stub, không phải viết lại.

### Chạy lại

```powershell
python run.py kg docs --limit 20          # chạy thử 20 văn bản
python run.py kg reset doc --all          # đưa toàn bộ về pending
python run.py kg docs --rebuild           # xoá bảng, dựng lại từ đầu
python run.py kg export                   # chỉ xuất lại JSONL, không tính lại
python run.py --session thunghiem kg docs # session riêng, không đụng session chính
```

`--rebuild` xoá cả tiến độ của các bước KG sau này — chỉ dùng khi đổi nguồn dữ
liệu hoặc sửa logic suy diễn.

### Bước tiếp theo

| Bước | Việc | Trạng thái |
|---|---|---|
| 0 | Bảng `Document` — gộp trùng, bậc thẩm quyền, hiệu lực | ✅ xong |
| 1 | Cắt vùng: header / Căn cứ / thân Điều-Khoản / điều khoản thi hành | chưa |
| 2 | Trích + resolve số hiệu → `BASED_ON` / `REFERENCES` + stub | chưa |
| 3 | Phân loại `REPLACES` / `AMENDS` / `REPEALS` theo vùng + trigger | chưa |
| 4 | `NormativeContent` + `Article` (§2.6, §2.7) | chưa |
| 5 | Nạp Neo4j + bộ Cypher mẫu | chưa |

Song song với Bước 1–5: **gold set** (§6.1) — 50–100 văn bản gán tay, 2 người gán
độc lập để đo Cohen's κ. Ontology ghi rõ "làm sớm"; đây là thứ duy nhất bị ràng
buộc bởi lịch người thật, mà cả phần đánh giá của paper treo vào nó.
