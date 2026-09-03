# Tiến độ — KG Văn bản pháp quy DUT/ĐHĐN

> Cập nhật: **03/09/2026** — graph xong, khối đánh giá §6 đã có code chạy được
> Đặc tả đích: [rules/Ontology.md](../rules/Ontology.md) — Mức 3 (paper)
> Hướng dẫn chạy: [README.md](../README.md) mục 10–15

---

## 1. Đang ở đâu

**Knowledge graph đã dựng xong và chạy được trong Neo4j.** Phần còn thiếu để ra
paper Mức 3 là toàn bộ khối **đánh giá** (§6) — gold set, query set, so sánh
BM25 / KG / Hybrid, ablation, error analysis.

| Giai đoạn (§8 Ontology) | Việc | Trạng thái |
|---|---|---|
| P1 — Mức 1 | Crawl → metadata → Neo4j (node + quan hệ dễ) | ✅ **xong** |
| P2 | OCR + regex → `BASED_ON`/`REFERENCES` + stub | ✅ **xong** |
| P3 | Quan hệ hiệu lực + `NormativeContent`/`Article` | ✅ **xong** |
| P4 — Mức 2 | BM25 baseline + query set + gold set | 🔶 code xong, **chờ người gán** (§5) |
| P5 — Mức 3 | Hybrid + metrics + ablation + error analysis | 🔶 ablation + error analysis **đã có số** (§5.6) |

Sáu bước thi công graph:

| Bước | Việc | Trạng thái |
|---|---|---|
| 0 | Bảng `Document` — gộp trùng, bậc thẩm quyền, hiệu lực | ✅ 27/08 |
| 1 | Cắt vùng: header / Căn cứ / thân / điều khoản thi hành | ✅ 27/08 |
| 2 | Trích + resolve số hiệu → cạnh + stub | ✅ 27/08 |
| 3 | Phân loại `REPLACES` / `AMENDS` / `REPEALS` | ✅ 27/08 |
| 4 | `NormativeContent` + `Article` | ✅ 27/08 |
| 5 | Nạp Neo4j + bộ Cypher mẫu | ✅ 27/08 |

Chạy lại tất cả: `python run.py kg all && python run.py kg load --wipe` (~3 phút).

---

## 2. Graph hiện có

**10.978 node · 14.120 cạnh**, trong Neo4j tại `bolt://localhost:7687`.

| Node | Số lượng | Quan hệ | Số lượng |
|---|---|---|---|
| `Article` | 9.518 | `HAS_ARTICLE` | 9.518 |
| `Document` | 1.244 (450 thật + 794 stub) | `BASED_ON` | 1.853 |
| `NormativeContent` | 178 | `REFERENCES` | 1.194 |
| `Organization` | 20 | `ISSUED_BY` | 742 |
| `Topic` | 18 | `HAS_TOPIC` | 454 |
| | | `PROMULGATES` | 178 |
| | | `REPLACES` | 88 |
| | | `AMENDS` | 56 |
| | | `REPEALS` | 23 |
| | | `PART_OF` | 14 |

Đầu ra dạng file, nạp lại được ở máy khác không cần session:

```
data/kg/documents.jsonl           1.244 Document
data/kg/organizations.jsonl          20 Organization + parentOrg
data/kg/topics.jsonl                 18 Topic
data/kg/segments.jsonl              448 cấu trúc văn bản (Bước 1)
data/kg/relations.jsonl           3.208 cạnh Document->Document
data/kg/normative_contents.jsonl    178 NormativeContent
data/kg/articles.jsonl            9.518 Article (kèm toàn văn, 21 MB)
data/kg/schema.cypher                 ràng buộc + chỉ mục + full-text index
data/kg/queries.cypher                bộ truy vấn mẫu §6.3
```

### Kho văn bản nguồn

| Chỉ số | Con số |
|---|---|
| PDF đã crawl | 501 file / 11.420 trang |
| Đã OCR | 501/501 (EasyOCR tại máy) |
| Đã hiệu đính bằng Gemma | 460, thiếu 2 văn bản (xem §4.2) |
| Văn bản phân biệt sau khi gộp trùng | **450** |
| Tổng ký tự sau hiệu đính | 20,2 triệu |
| Vị trí | `data/clean/text_clean_gemma/<lĩnh vực>/*.txt` |

> ⚠️ `data/raw/pdf/` và `data/raw/metadata.csv` **đã bị xoá khỏi máy**. Nguồn
> metadata duy nhất còn lại là `data/manifest.jsonl` (xuất 17/08). Đừng xoá file
> đó — ngày ban hành, cơ quan ban hành, tình trạng hiệu lực chỉ còn ở đấy.

---

## 3. Chất lượng từng bước (con số để viết §5 của paper)

| Bước | Chỉ số | Kết quả |
|---|---|---|
| 0 | Bậc thẩm quyền (§3) phủ | 450/450 |
| 0 | Header khớp metadata | 386/448 = **86%** |
| 1 | Vùng `Căn cứ` tìm được | 427/448 = **95%** |
| 1 | Nội dung kèm theo tách được | 178 phần |
| 1 | Nhãn metadata vs cấu trúc text (đối chiếu chéo) | khớp **76%** |
| 2 | Trích dẫn nối được vào `Document` | 5.371/6.090 = **88%** |
| 2 | Tỷ lệ stub / văn bản thật | 1,8 : 1 |
| 4 | `Article` lập được danh mục | 9.518 |

Ba đánh đổi đã chốt, cần nói rõ trong paper:

1. **Ngưỡng stub = ≥2 lần HOẶC nằm trong vùng Căn cứ.** Không đặt ngưỡng thì
   3/4 graph là node rỗng; đặt ngưỡng thuần đếm thì mất những `Luật` chỉ được
   viện dẫn một lần — mà đó chính là mắt xích của chuỗi `BASED_ON`.
2. **Quan hệ hiệu lực thiên về precision.** Kho có 1.922 lần "sửa đổi, bổ sung"
   nhưng chỉ 118 thành `AMENDS`. Ba ràng buộc chống gán nhầm chủ thể (README
   mục 12) loại đúng những ca sai đã kiểm bằng mắt, nhưng chắc chắn cũng loại
   theo một số ca đúng. **Recall thật phải chờ gold set đo.**
3. **`HAS_ARTICLE` nới domain so với §2.7** — nhận cả `Document` lẫn
   `NormativeContent`, vì 270/448 văn bản không có nội dung kèm theo.

---

## 4. Tồn đọng

### 4.1 Ảnh hưởng chất lượng cạnh — 34 văn bản header lệch

`python run.py kg review --grep header-lech`

Không phải nhiễu — đây là **lỗi metadata và lỗi OCR thật**:

```
1/2024/TT-NBV     header ghi TT-BNV      <- metadata gõ nhầm BNV -> NBV
2453/QĐ-ĐHBK      header ghi QĐ-ĐHĐN     <- đúng cảnh báo normalize.py từng nêu
53/2022/NĐ-VP     header ghi NĐ-CP       <- metadata sai hậu tố
17/2021/TT-BGDĐT  header ghi 7/2021      <- OCR nuốt mất chữ số đầu
```

Sửa số hiệu là **đổi khoá chính**, nên phải người xác nhận rồi mới sửa. Trong
lúc chờ, mỗi cạnh sinh ra từ các văn bản này đều mang cờ
`source_header_check: "lech"` trong `relations.jsonl` để lọc ra khi chấm điểm.

Ngoài ra 28 văn bản header không đọc ra số hiệu nào.

### 4.2 Nên làm sớm — 2 văn bản chưa hiệu đính

| doc_id | Số hiệu | Ghi chú |
|---|---|---|
| 0166 | `115/2020/NĐ-CP` | **bị trích dẫn 119 lần** — đáng chạy lại nhất |
| 0307 | `14/2021/TT-BGDDT` | metadata ghi `BGDDT` (thiếu `Đ`) |

`python run.py fix` rồi copy kết quả vào `data/clean/text_clean_gemma/`.

### 4.3 Ghi nhận

- **5 file không có trong manifest** (0148, 0151, 0158, 0161, 0352) — metadata
  lấy từ tên file nên thiếu ngày ban hành và tình trạng hiệu lực.
- **459 stub chưa suy được bậc thẩm quyền** — mã cơ quan lạ (`VBQPPL`, `PLIII`,
  `TSC`…), phần lớn là mảnh vụn OCR. Bổ sung vào `norm._ORG_BY_CODE` nếu gặp mã
  nào đáng kể.
- **719 trích dẫn không nối được** vào node nào (12%) — dưới ngưỡng stub.

---

## 5. Chạy khối đánh giá §6

> **Toàn bộ kết quả ghi vào `data/eval/`.** Không có gì chỉ hiện trên màn hình.
> Chạy ở máy nào cũng được, xong **copy nguyên thư mục `data/eval/` về** là đọc
> được đầy đủ. Code: `src/vanban/eval/`.

### 5.0 Chuẩn bị trên máy sẽ chạy

```powershell
git clone <repo> && cd PBL6
pip install -r requirements.txt

# Kho text đã hiệu đính (~500 MB) và data/kg/ KHÔNG nằm trong git.
# Copy hai thư mục này từ máy cũ sang:
#   data/clean/text_clean_gemma/
#   data/kg/                       (hoặc dựng lại bằng lệnh dưới)

# Dựng lại graph từ đầu nếu không copy data/kg — mất ~3 phút:
python run.py kg all

# Neo4j: bắt buộc cho §6.3–6.5, không cần cho §6.1–6.2 và §6.6–6.7
docker run -d --name neo4j-pbl6 -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/12345678 neo4j:5
pip install neo4j
python run.py kg load --wipe
```

### 5.1 Chạy một phát tất cả

```powershell
python run.py eval all
```

Chạy mọi thứ **chạy được lúc này**, bỏ qua êm phần còn thiếu đầu vào, rồi gom
thành `data/eval/BAO_CAO.md`. Chạy lại bao nhiêu lần cũng được — phần người đã
điền (phiếu gán, đáp án câu hỏi) không bị ghi đè.

Mở `BAO_CAO.md` là thấy ngay phần nào đã có số, phần nào còn chờ người.

### 5.2 Từng bước, nếu muốn chạy lẻ

| Lệnh | Làm gì | Cần gì trước |
|---|---|---|
| `python run.py eval sample` | §6.1 — chọn gold set phân tầng, sinh phiếu gán | graph |
| `python run.py eval kappa` | §6.1 — Cohen's κ giữa hai người gán | phiếu đã điền |
| `python run.py eval extraction` | §6.2 — P/R/F1 từng loại quan hệ | phiếu đã điền |
| `python run.py eval queries` | §6.3 — sinh 45 câu hỏi, tự điền đáp án nhóm metadata | Neo4j |
| `python run.py eval retrieval` | §6.4–6.5 — chạy BM25 / KG / Hybrid, chấm điểm | Neo4j + `queries.csv` |
| `python run.py eval errors` | §6.6–6.7 — ablation + phân tích lỗi | graph |
| `python run.py eval report` | Gom số đo đã có thành `BAO_CAO.md` | — |

### 5.3 File nào ra ở đâu

```
data/eval/
├── BAO_CAO.md                 ← MỞ CÁI NÀY TRƯỚC. Gom mọi số đo, nói rõ phần nào còn thiếu
│
├── goldset/
│   ├── huong_dan_gan.md       ← quy ước gán, ĐƯA CHO NGƯỜI GÁN ĐỌC
│   ├── danh_sach.csv          ← 131 văn bản trong gold set, kèm tầng
│   ├── phan_tang.json         ← seed + cỡ mẫu, để tái lập đúng y hệt
│   ├── phieu_gan/*.csv        ← 131 phiếu, mỗi phiếu 1 văn bản  ← NGƯỜI ĐIỀN
│   ├── nguoi_gan_1/*.csv      ← người thứ nhất chép phiếu đã điền vào đây
│   ├── nguoi_gan_2/*.csv      ← người thứ hai
│   └── he_thong.jsonl         ← nhãn máy, KHÔNG đưa cho người gán
│
├── queries.csv                ← 45 câu hỏi; cột DAP_AN  ← NGƯỜI ĐIỀN 31 câu
│
├── extraction.md              ← §6.1–6.2 đầy đủ + bảng bất đồng giữa hai người
├── retrieval.md               ← §6.3–6.5 đầy đủ, tách theo nhóm câu hỏi
├── ablation_va_loi.md         ← §6.6–6.7
├── retrieval_runs.jsonl       ← kết quả thô từng câu × từng hệ, để soi lỗi
└── *.json                     ← cùng số liệu, dạng máy đọc được
```

Ba file `.md` in đậm ở trên là thứ đọc trực tiếp được. Các file `.json` dành cho
khi cần vẽ biểu đồ hoặc nhúng số vào paper.

### 5.4 Hai chỗ máy không làm thay được

**Gán gold set** — 131 phiếu trong `goldset/phieu_gan/`, tổng 1.746 dòng cần
gán. Hai người gán độc lập, chép kết quả vào `nguoi_gan_1/` và `nguoi_gan_2/`.
Đọc `goldset/huong_dan_gan.md` trước.

Quy trình đúng theo §6.1: gán thử **20 văn bản đầu** → `eval kappa` → xem chỗ
bất đồng (`extraction.md` có bảng liệt kê) → **sửa `huong_dan_gan.md`** → gán
lại 20 cái đó → gán nốt phần còn lại.

**Đáp án bộ câu hỏi** — 14/45 câu máy tự điền được (nhóm single-hop, đáp án suy
thẳng từ metadata crawler nên không thiên lệch). **31 câu còn lại phải người
điền** cột `DAP_AN` trong `queries.csv`, ngăn nhau bằng dấu `;`.

Không tự sinh đáp án cho nhóm `multi-hop` và `hieu-luc` là **cố ý**: đáp án của
chúng phụ thuộc vào chính những quan hệ đang được đem ra chấm, lấy graph làm
đáp án rồi chấm graph là lập luận vòng tròn.

### 5.5 Gold set được chọn thế nào, và vì sao không lấy hết

Gán hết 448 văn bản = 9.962 trang × 2 người ≈ **224 giờ mỗi người**. Lấy 131 văn
bản ≈ 1 tuần mỗi người.

Nhưng bốc ngẫu nhiên 75 văn bản như §6.1 gợi ý thì hỏng ở nhóm hiếm: `REPEALS`
chỉ có mặt ở 38/448 văn bản, bốc ngẫu nhiên chỉ bắt được **~9 thể hiện** — khoảng
tin cậy 95% rộng ±20 điểm phần trăm, trong khi §6.2 lại yêu cầu báo cáo P/R/F1
**riêng từng loại quan hệ**.

Nên `eval sample` chia ba tầng:

| Tầng | Cỡ | Chọn theo | Đo được gì |
|---|---|---|---|
| **A** | 71/166 | hệ thống có gán `REPLACES`/`AMENDS`/`REPEALS` | **precision** nhóm hiếm |
| **B** | 30/88 | có trích dẫn trong điều khoản thi hành nhưng máy **im lặng** | **recall** — nơi false negative trú ngụ |
| **C** | 30/194 | ngẫu nhiên toàn kho | ước lượng **không thiên lệch** |

Tầng B là tầng quan trọng nhất và dễ bị bỏ quên nhất. Chỉ lấy mẫu ở chỗ máy đã
gán (tầng A) thì mãi mãi chỉ biết "cái nó nói có đúng không", không bao giờ biết
"nó bỏ sót bao nhiêu" — mà recall thấp đang là **nghi ngờ lớn nhất** với bộ trích
xuất này (xem §3).

Tầng B định nghĩa bằng **cấu trúc** (Bước 1: trích dẫn nằm trong điều khoản thi
hành) chứ không bằng đầu ra Bước 3 — đó là điều kiện để nó không thiên lệch theo
chính hệ thống đang bị chấm.

Đổi cỡ mẫu: `python run.py eval sample --co-mau 71,30,30`. Cùng `--seed` thì
cùng kết quả, chạy máy nào cũng vậy.

### 5.6 Kết quả đã có sẵn (chưa cần người gán)

Chạy `eval all` lần đầu đã cho ngay ba thứ:

**§6.4 — ba hệ tìm kiếm** (trên 14 câu single-hop có đáp án tự sinh):

| Hệ | P@5 | R@10 | MRR | nDCG@10 |
|---|---|---|---|---|
| BM25 | 0,586 | 0,162 | 0,729 | 0,659 |
| KG | 1,000 | 0,294 | 1,000 | 1,000 |
| Hybrid | 0,943 | 0,254 | 1,000 | 0,926 |

KG thắng tuyệt đối ở nhóm này là **đúng như kỳ vọng, không phải kết quả đáng
khoe**: câu hỏi single-hop hỏi thẳng vào metadata (cơ quan ban hành, lĩnh vực,
tình trạng hiệu lực) — KG tra đúng thuộc tính, còn BM25 phải đoán qua tiêu đề.
Chỗ đáng quan tâm là nhóm **multi-hop**, và nhóm đó chưa có đáp án.

**§6.6 — ablation:** bỏ cắt vùng (Bước 1) mất **63% số cạnh**; bỏ stub mất
**68,7%**. Riêng `-OCR` chưa đo được vì `data/raw/pdf/` đã bị xoá khỏi máy.

**§6.7 — phân tích lỗi:** 342/354 văn bản (96,6%) có ít nhất một nhánh `BASED_ON`
chết ở stub; `ablation_va_loi.md` liệt kê 15 văn bản nên crawl bổ sung, xếp theo
số lần bị viện dẫn (`32/CP` 172 lần, `13/NQ-HĐĐH` 97 lần…).

### 5.7 Mang kết quả về

```powershell
# trên máy chạy
tar -czf eval.tar.gz data/eval/

# về máy đọc — chỉ cần thư mục này, không cần gì khác
tar -xzf eval.tar.gz
```

`data/eval/` nặng khoảng vài MB (trừ khi giữ `retrieval_runs.jsonl` của bộ câu
hỏi lớn). **Nên commit `goldset/nguoi_gan_*/`** — đó là công sức người gán,
dựng lại được bằng máy đâu.

---

## 6. Nhật ký

| Ngày | Việc |
|---|---|
| 03/09/2026 | **Khối đánh giá §6 có code** — gói `src/vanban/eval/`, lệnh `python run.py eval`. Sinh gold set phân tầng 3 tầng (131 VB / 1.746 ứng viên), bộ 45 câu hỏi, chạy BM25/KG/Hybrid, ablation + phân tích lỗi. Mọi kết quả ghi ra `data/eval/`. Sửa 2 lỗi thật lộ ra khi chạy: `kg load` nuốt 3 câu Cypher có dòng chú thích phía trên (mất full-text index `doc_text` → BM25 trả rỗng), và `split_so_hieu` tra bảng có dấu nên mọi stub `ND-CP` mất `documentType` (stub có bậc thẩm quyền: 342 → 693) |
| 27/08/2026 | **Bước 2→5 xong** — 3.208 cạnh Document→Document, 178 `NormativeContent`, 9.518 `Article`; nạp Neo4j thành công (10.978 node / 14.120 cạnh). Sửa 3 lỗi gán nhầm chủ thể quan hệ hiệu lực, vá 1.554 lượt trích dẫn có số hiệu cụt |
| 27/08/2026 | **Bước 1 xong** — cắt vùng 448 văn bản, tách 178 phần `NormativeContent`, 9.860 `Điều` |
| 27/08/2026 | **Bước 0 xong** — 450 `Document` + 20 `Organization` + 18 `Topic`; phát hiện 34 header lệch (có lỗi metadata thật) |
| 26/08/2026 | Hiệu đính Gemma xong 460/501, kết quả về `data/clean/text_clean_gemma/` |
| 25/08/2026 | Chốt `rules/Ontology.md` v0.3 (Mức 3); vẽ `docs/kg_ontology.png`, `docs/kg_instance.png` |
| 21/08/2026 | `normalize` xong 501/501 |
| 17/08/2026 | Xuất `data/manifest.jsonl` (501 dòng) |
| — | OCR 501/501 bằng EasyOCR tại máy; crawl 501 PDF từ `dut.udn.vn` |
