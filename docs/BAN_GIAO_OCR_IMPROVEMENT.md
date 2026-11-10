# Bàn giao: nhánh `ocr-improvement`

Tài liệu này để một phiên Claude Code mới làm tiếp mà không cần lịch sử chat cũ.
Viết ngày 10/11/2026. Mọi con số dưới đây đã chạy hoặc kiểm trên máy này; chỗ nào
chưa kiểm thì ghi rõ.

**Làm mọi việc trên nhánh `ocr-improvement`** (người dùng yêu cầu). Đầu phiên chạy
`git switch ocr-improvement && git pull`; không commit vào `main`.

## 1. Trạng thái

- Nhánh `ocr-improvement`, đã push lên `origin` (commit `723b9c6`). `main` chưa đổi.
- PDF gốc: 455 file trong `data/raw/pdf/` (2,3 GB, nằm ngoài git qua `.gitignore`),
  chép từ `C:\Users\Hello\Downloads\pdf\pdf`, đã so MD5 từng file: khớp 100%.
  - 5 PDF không có trong `text_final`: `0198`, `0282`, `0326`, `0327`, `0329`
    (nhiều khả năng là 5 văn bản website gắn nhầm file, mục 9.2 báo cáo).
  - 4 văn bản trong `text_final` không có PDF: `0148`, `0151`, `0161`, `0352`.
- Test: `cd src/legal_knowledge_graph && python -m pytest -q` → 121 passed,
  72 skipped (test live cần Neo4j).
- Docker Desktop đã cài; đã bật Virtual Machine Platform và WSL nhưng **cần khởi
  động lại máy**. Chưa chạy được Neo4j, nên rerank và graph có số trang chưa đo
  được đầu–cuối.
- Key Gemini duy nhất trong `.env` bị từ chối: `401 UNAUTHENTICATED … service
  account bound to the API key is deleted or disabled`. Cần key mới.

## 2. Ba khâu đã làm

### 2.1. Bộ chuẩn OCR theo trang

- Code: `tools/kiem_tra/ocr_gold.py` (`chon`, `cham`). Dữ liệu và quy ước:
  `data/eval/ocr_gold/README.md`. Kết quả: `data/eval/ocr_gold/ket_qua.md`, `ket_qua.json`.
- 20 trang, seed 6, một trang mỗi văn bản, 8 trang là trang 1 (đầu văn bản có số
  hiệu, ngày điền tay, con dấu), 12 trang ngẫu nhiên. Bỏ văn bản chỉ có mốc theo
  khúc `[Trang a-b]`.
- **Bản chuẩn do Claude gõ lại từ ảnh trang** (một người gán, số viết tay phóng to
  400 DPI). Chưa có người gán thứ hai; người dùng được khuyên cho một thành viên
  soát lại 20 file `chuan/*.txt`. Khi viết vào báo cáo phải nói rõ điều này.
- Cách chấm: NFC, gộp khoảng trắng, quy nháy cong / gạch dài / "…" về một dạng.
  Không tin mốc `[Trang N]`; CER tính trên đoạn khớp nhất trong toàn văn bản
  (cửa sổ trượt theo cụm 4 từ, rồi edit distance bán toàn cục).

| Chỉ số (20 trang) | Kết quả |
|---|---|
| CER giữ dấu (gộp) | 2,35% |
| CER bỏ dấu (gộp) | 2,31% |
| CER trung vị theo trang | 2,26% |
| Từ thiếu / từ thừa (không xét thứ tự) | 1,47% / 1,41% |
| Token chứa chữ số khớp nguyên dạng | 475/483 |
| Trang có mốc `[Trang N]` trỏ đúng nội dung | 10/20 |

Lỗi nội dung thật tìm được:

- `0415` trang 1: mất trọn câu "Căn cứ Nghị định số 32/CP ngày 04/4/1994 của Chính
  phủ về việc thành lập Đại học Đà Nẵng;" và chữ "Về việc" ở trích yếu — đúng chỗ
  dấu "ĐẾN" của văn thư đè lên. Đồ thị thiếu cạnh căn cứ này.
- `0077` trang 1: số hiệu thành "2352/QĐ-ĐHBK.2 IQĐ-ĐHBK" — bước tiêm số hiệu ghi
  đúng, rác OCR cũ còn lại phía sau.
- `0077`, `0045`: chữ trong con dấu lẫn vào văn bản ("B8CHR Cekcuccac").
- `0013`: ghi chú viết tay chuyển văn bản bị đưa vào như nội dung.
- Phần lớn CER còn lại: khối đầu văn bản hai cột đọc xen dòng, khối ký thành
  "(Đã ký)", dấu "-" đầu dòng Nơi nhận bị bỏ; bảng biểu ra dạng `|`.

Giới hạn: 20 trang đủ để thấy kiểu lỗi, chưa đủ để ước lượng chắc CER toàn kho
(cần khoảng 40–120 trang, xem `reports/Giải pháp OCR PDF tiếng Việt.md`).

### 2.2. Rerank sau RRF

- Code: `src/legal_knowledge_graph/core/llm/rerank.py`; nối vào
  `core/chat/retrieval/graph_rag.py` (`GraphRagService.select_seeds`, hàm `rerank`),
  `core/chat/container.py`, `core/chat/adapters/graph_retriever.py`.
- Cấu hình (`core/config.py`): `LKG_RERANK_PROVIDER` = `none` (mặc định) |
  `gemini` | `cross_encoder`; `LKG_RERANK_MODEL` (mặc định `gemini-3.1-flash-lite`
  hoặc `BAAI/bge-reranker-v2-m3`); `LKG_RERANK_CANDIDATES=16`;
  `LKG_RERANK_PASSAGE_CHARS=1200`.
- Hành vi: gộp vector + fulltext bằng RRF như cũ, đưa 16 Điều đầu vào reranker
  (đoạn = số hiệu + tiêu đề + 1.200 ký tự đầu), xếp lại theo điểm, hoà điểm giữ thứ
  tự RRF. Reranker lỗi → lùi về thứ tự RRF, ghi log `graph_rag.rerank_failed`.
- Benchmark: hệ mới `hybrid_rerank` trong `src/cypher_benchmark/retrievers.py`.
- **Chưa đo** trên benchmark của nhóm (thiếu Neo4j và key Gemini hợp lệ). Bằng
  chứng ngoài: ViDoRe V3 (4/2026), rerank nâng nDCG@10 truy hồi văn bản 50,4 → 63,6
  (`reports/Pipeline chuẩn OCR scan sang embedding.md`). Không được viết là đã cải
  thiện kết quả của nhóm.
- Test: 4 test mới trong `tests/test_graph_rag.py` (xếp lại, chỉ chạm nhóm ứng
  viên, lỗi lùi về RRF, không có câu hỏi thì bỏ qua).

### 2.3. Truy nguồn Điều về trang PDF gốc

- Code: `tools/kiem_tra/nguon_trang.py`; ra `data/clean/nguon_trang/`:
  `pdf_manifest.json` (455 PDF: đường dẫn, SHA-256, số trang, chất lượng mốc) và
  `dieu_v1.json`, `dieu_v2.json`, `dieu_v4.json` (articleId → PDF, trang đầu, trang
  cuối, độ tin cậy). Đã commit cả ba.
- Chất lượng mốc `[Trang N]` của 450 văn bản có PDF: `cao` (đủ 1..N, khớp số trang
  PDF) 285; `trung_binh` (tăng dần nhưng thiếu trang) 82; `thap` (lộn xộn, lặp, hoặc
  theo khúc 5 trang) 83.
- Số Điều theo độ tin cậy:

| Phiên bản | Tổng Điều | cao | trung_binh | thap | khong_ro |
|---|---|---|---|---|---|
| v1, v2 | 10.020 | 6.967 | 1.807 | 1.633 | 65 |
| v4 | 2.281 | 1.093 | 687 | 375 | 126 |

  Lưu ý: 10.020 là số node Article sau khi dựng `articleId` (trùng khoá bị gộp), khác
  con số "10.472 Điều, mục" trong bảng 10.6 của báo cáo. Đừng sửa con số trong báo
  cáo theo số này.
- Kiểm chéo với bộ chuẩn: Điều mức `cao` được ánh xạ về một trang chuẩn thì 21/22
  đúng trang (ca còn lại đúng trang nhưng OCR làm rơi dấu gạch nên phép so trượt).
  Mức `trung_binh`/`thap` sai nhiều (vd `0447` Điều 3–7 bị ghi trang 1).
- Graph: đặt `LKG_PAGE_PROVENANCE=data/clean/nguon_trang/dieu_v4.json` khi build →
  Article có `sourcePdf`, `pageStart`, `pageEnd`, `pageConfidence`
  (`core/ingest/graph_model.py`, `graph_loader.py`); truy vấn hạt giống trả các
  trường này (`core/graph_query/graph_context.py`); evidence ghi `[PDF trang X–Y]`
  **chỉ khi** độ tin cậy `cao` (`core/chat/answering/evidence.py`).
- Chưa có toạ độ vùng chữ (bounding box): OCR hiện tại không lưu toạ độ.

## 3. Việc còn lại

1. Sau khi khởi động lại máy: mở Docker Desktop, `docker version`, rồi trong repo
   `docker compose up -d` (Neo4j cho legal_knowledge_graph: bolt 7688, Browser
   http://localhost:7475). Build graph với `LKG_PAGE_PROVENANCE`, chạy benchmark có
   `hybrid_rerank` (`python run.py bench --compare-bm25`). Cần key Gemini mới hoặc
   `pip install sentence-transformers` + `LKG_RERANK_PROVIDER=cross_encoder`.
2. Ghi ba phần mới vào Google Doc (mục 4).
3. Chưa sửa (người dùng chưa yêu cầu): `data/README.md` ghi toàn bộ PDF là scan
   không có lớp text, mâu thuẫn `docs/PIPELINE_TU_DONG.md` (27 file lớp text tốt);
   docstring `src/vanban/eval/errors.py` còn ghi PDF đã bị xoá.

## 4. Ghi vào Google Doc

- File: https://docs.google.com/document/d/1zDadYybJv4BTTEEImwtwbktLV97uyxgF_2DTXPGgjrQ
  (tiêu đề "BÁO CÁO PBL6"), **chỉ tab "Xử lý dữ liệu"**, tabId `t.lsba5hsj4awk`.
- Cần connector Google Docs trong phiên (kiểm bằng `/mcp`). Không có thì dừng và báo,
  không tạo file khác.
- Ràng buộc người dùng đã đặt cho tab này ở các lượt trước:
  - Không sửa các tab khác ("Cơ sở lý thuyết", "Đánh giá", "Chatbot").
  - Chỉ thêm / sửa đúng chỗ cần, không xoá rồi dựng lại cả tab.
  - Giữ nguyên Hình 1 và 15 bảng đang có; giữ chữ "chẳng hạng" ở mục 10.6.
  - Toàn tab là Times New Roman cỡ 13 (đã đặt ngày 10/11/2026); nội dung thêm vào
    cũng phải Times New Roman 13, tiêu đề dùng đúng Heading 2/3 như các mục khác,
    và giữ chữ đậm như các tiêu đề hiện có. Cảnh báo: `updateTextStyle` đặt font
    trên cả vùng có thể làm mất chữ đậm — lần trước đã phải khôi phục.
  - Nội dung phải đúng như code và kết quả đã chạy, không bịa số.
  - Không chép comment của báo cáo Claude Docs sang.
- Tab hiện có 12 mục, mục 11 "Kết quả", mục 12 "Hạn chế và hướng phát triển".
  Đánh số tiêu đề là gõ tay ("9.4.", "10.6."). Bảng: hàng đầu nền xám, chữ không đậm.
- Báo cáo Claude Docs https://claude.ai/artifact/4Va2f98x8aA65mCeT6K9kD từng được giữ
  khớp với tab này. **Hỏi người dùng** có thêm cả vào bản Claude Docs không.
- Vị trí đề xuất (hỏi người dùng xác nhận trước khi ghi):
  - "9.5. Đối chiếu với bản gốc theo trang" — sau mục 9.4 (cùng nhóm kiểm tra kho).
  - "9.6. Truy nguồn Điều về trang PDF gốc" — sau 9.5.
  - Rerank thuộc truy hồi của chatbot; đề xuất đặt ở tab "Chatbot" hoặc thêm một đoạn
    ngắn ở mục 12.2. Người dùng đã nói thêm "3 cái" vào tab "Xử lý dữ liệu", nên nếu
    người dùng không đổi ý thì thêm "9.7. Xếp hạng lại Điều khi truy hồi" — hỏi lại.
  - Mục 12.1 có gạch đầu dòng "Thước đo gián tiếp"; có thể thêm một câu dẫn sang 9.5.

### Bản nháp nội dung (đã đối chiếu số liệu ở mục 2)

**9.5. Đối chiếu với bản gốc theo trang**

Các thước đo ở mục 9.3 và 9.4 chỉ ước lượng chất lượng, không so với chữ thật trên
trang. Vì vậy nhóm dựng một bộ chuẩn 20 trang chọn ngẫu nhiên, mỗi văn bản một
trang, trong đó 8 trang là trang đầu văn bản có số hiệu, ngày điền tay và con dấu.
Mỗi trang được gõ lại từ ảnh PDF gốc; bản chuẩn này do mô hình Claude gõ và chưa có
người gán thứ hai, nên còn cần người soát lại. ocr_gold.py so text_final với bản
chuẩn sau khi chuẩn hoá Unicode và dấu câu, trên đoạn khớp nhất trong toàn văn bản
thay vì theo mốc trang:

| Chỉ số | Kết quả |
|---|---|
| Tỷ lệ lỗi ký tự, giữ dấu | 2,35% |
| Tỷ lệ lỗi ký tự, bỏ dấu | 2,31% |
| Từ thiếu so với bản gốc | 1,47% |
| Số hiệu, ngày, trích dẫn chứa chữ số khớp nguyên dạng | 475/483 |
| Trang có mốc [Trang N] trỏ đúng nội dung | 10/20 |

Lỗi dấu gần như không còn; phần lớn sai khác đến từ khối đầu văn bản hai cột đọc
xen dòng và chữ trong con dấu lẫn vào văn bản. Bộ chuẩn cũng tìm ra lỗi nội dung mà
các thước đo cũ bỏ sót: văn bản 0415 mất trọn câu căn cứ Nghị định 32/CP ở đúng chỗ
dấu "ĐẾN" của văn thư đè lên, và số hiệu của 0077 còn dính rác OCR sau bước tiêm
số hiệu. 20 trang đủ để thấy các kiểu lỗi, chưa đủ để ước lượng chắc tỷ lệ lỗi của
toàn kho.

**9.6. Truy nguồn Điều về trang PDF gốc**

nguon_trang.py lập manifest 455 PDF gốc kèm mã SHA-256, để kiểm được bản PDF đang
có đúng là bản đã OCR, và ánh xạ từng Điều về trang PDF chứa nó. Mốc [Trang N] trong
text_final chỉ khớp đủ với số trang PDF ở 285/450 văn bản; 82 văn bản có mốc tăng
dần nhưng thiếu trang, 83 văn bản có mốc lộn xộn hoặc chia theo khúc 5 trang. Vì
vậy mỗi ánh xạ được gắn độ tin cậy:

| Độ tin cậy | Điều kiện | Số Điều (v1) |
|---|---|---|
| Cao | Mốc đủ 1..N, khớp số trang PDF | 6.967 |
| Trung bình | Mốc tăng dần nhưng thiếu trang | 1.807 |
| Thấp | Mốc lộn xộn hoặc theo khúc | 1.633 |
| Không rõ | Không tìm thấy Điều trong text_final | 65 |

Đối chiếu với bộ chuẩn ở mục 9.5, 21/22 Điều mức cao nằm đúng trang. Khi nạp đồ thị,
mỗi Article có thêm trang PDF và độ tin cậy; chatbot chỉ dẫn số trang khi độ tin cậy
là cao. Chưa có toạ độ vùng chữ trên trang vì bước OCR hiện tại không lưu toạ độ.

**9.7. Xếp hạng lại Điều khi truy hồi** (hỏi vị trí trước)

Truy hồi gộp kết quả tìm theo vector và theo từ khoá bằng Reciprocal Rank Fusion,
vốn chỉ dùng thứ hạng mà không đọc lại câu hỏi cùng nội dung Điều. Nhóm thêm bước
xếp hạng lại: 16 Điều đầu sau khi gộp được đưa vào một reranker chấm mức liên quan
với câu hỏi, dùng Gemini hoặc cross-encoder bge-reranker-v2-m3 chạy tại máy. Bước
này mặc định tắt; khi reranker lỗi, hệ thống giữ thứ tự cũ. Trên benchmark ViDoRe
V3, bước rerank nâng nDCG@10 của truy hồi văn bản từ 50,4 lên 63,6; trên benchmark
của nhóm, hệ hybrid_rerank đã được thêm nhưng chưa chạy, nên chưa có số đo.
