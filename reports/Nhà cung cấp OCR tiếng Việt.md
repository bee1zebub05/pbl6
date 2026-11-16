# Để trang của nhóm chọn engine OCR

**Nhóm nên thử trước, theo thứ tự: Google Document AI Enterprise OCR, SenOCR-Vi/PaddleOCR-VL-1.6, Gemini, VNPT SmartReader, rồi một recognizer tiếng Việt chạy CPU (AsterNet).** Lý do của thứ tự này là bằng chứng và chi phí. Không có lý do nào là "đã được chứng minh tốt nhất", vì **không có benchmark độc lập nào xếp hạng các nhà cung cấp này trên văn bản hành chính, pháp quy tiếng Việt**. Mọi con số về FPT, VNPT, Viettel và VinBigData đều là quảng cáo không nêu bộ dữ liệu. Benchmark nhiều mô hình duy nhất có cột tiếng Việt (MDPBench) không chứa công văn, Công báo, con dấu hay biểu mẫu viết tay. Vì vậy lựa chọn cuối cùng phải đến từ một đợt thử trên chính trang của nhóm. Tin tốt là chi phí gần như không phải rào cản. Với 11.000 trang, các dịch vụ cloud có hỗ trợ tiếng Việt chỉ tốn khoảng **10–45 USD**, riêng VNPT khoảng **10,35 triệu VND** (chưa VAT), và mỗi bên đều có gói miễn phí đủ cho một đợt thử khoảng 40 trang. Rào cản thật nằm ở ba chỗ. Thứ nhất, độ chính xác trên trang khó chưa ai đo. Thứ hai, Gemini bị chặn đầu ra (RECITATION) trên văn bản luật. Thứ ba, máy chỉ có CPU, nên phần lớn mô hình mã nguồn mở mạnh nhất phải chạy trên GPU thuê hoặc GPU miễn phí. Kết luận của nghiên cứu trước vẫn giữ nguyên: **đo trước, chưa OCR lại toàn kho**. Bộ chuẩn gõ tay khoảng 40 trang chính là công cụ để biến danh sách dưới đây thành một quyết định.

Báo cáo dùng năm nhãn để tách loại bằng chứng:

| Nhãn | Ý nghĩa |
|---|---|
| **[VI-độc lập]** | Đo trên tiếng Việt bởi bên không bán sản phẩm đó |
| **[VI-tự báo]** | Đo trên tiếng Việt bởi chính tác giả hoặc nhà cung cấp |
| **[Quảng cáo]** | Con số trên trang bán hàng, không nêu bộ dữ liệu |
| **[Khác]** | Đo trên ngôn ngữ khác, chỉ dùng làm ngữ cảnh |
| **[Suy luận]** | Lập luận hoặc phép tính của người nghiên cứu, không phải kết quả công bố |

## Năm bên đáng thử trước, xếp theo bằng chứng và chi phí

| Hạng | Ứng viên | Vì sao đứng ở vị trí này | Thử miễn phí | Chi phí 11.000 trang | Rủi ro chính |
|---|---|---|---|---|---|
| 1 | Google Document AI Enterprise OCR (cloud) | Là dịch vụ thương mại duy nhất tìm thấy có hỗ trợ chính thức tiếng Việt **cả chữ in lẫn chữ viết tay**, không ở mức thử nghiệm. Engine không sinh văn bản, nên khó bịa câu hay bị chặn [Suy luận] | 1.000 trang đầu | Khoảng 15 USD | Độ chính xác tiếng Việt chưa ai đo |
| 2 | SenOCR-Vi / PaddleOCR-VL-1.6 (mã nguồn mở, Apache-2.0) | Mô hình riêng cho tiếng Việt có bằng chứng tốt nhất trong nhóm cho phép dùng thương mại. Không có bộ lọc của nhà cung cấp, nên dùng được làm phương án dự phòng cho trang bị Gemini chặn | Miễn phí | 0 USD, nhưng cần GPU miễn phí cho cả kho | Chưa có số đo tốc độ CPU. Tác giả tự nhận yếu ở bố cục nhiều cột và bảng |
| 3 | Gemini (3.1 Flash-Lite batch; 3 Pro cho trang khó) | Đứng đầu nhóm dẫn cột tiếng Việt trên MDPBench | Tùy hạn mức | Khoảng 10 USD (Flash-Lite batch) | RECITATION chặn cố định trên văn bản luật, nhóm đã tự ghi nhận |
| 4 | VNPT SmartReader (trong nước) | Nhà cung cấp trong nước duy nhất có bảng giá công khai, gói miễn phí và nêu rõ dùng cho văn bản hành chính và bảng | 150 trang (thêm 300 trang Trial) | 10.350.000 VND chưa VAT | Chưa rõ có nhận PDF không và định dạng đầu ra |
| 5 | AsterNet (MIT) thay recognizer sau bộ dò chữ EasyOCR (CPU) | Đường nâng cấp rẻ nhất chạy được trên máy CPU hiện có | Miễn phí | 0 USD, ước tính 7–8 giờ CPU | Chỉ đọc theo dòng. Số liệu tự báo, bộ đánh giá không nêu tên |

Mốc so sánh là pipeline hiện tại, EasyOCR cộng Gemma. Ứng viên tùy chọn là Datalab API/Chandra 2 (gói tín dụng miễn phí 10–20 USD mỗi tháng) và Mistral OCR 4.1.

**Document AI đứng đầu vì nó gom đủ ba điều kiện mà các bên khác chỉ có một phần.** Thứ nhất, Google ghi tiếng Việt được hỗ trợ cả chữ viết tay ([ngôn ngữ Document AI](https://docs.cloud.google.com/document-ai/docs/languages)). Thứ hai, giá **1,50 USD/1.000 trang**, miễn phí 1.000 trang đầu ([giá](https://cloud.google.com/document-ai/pricing)). Thứ ba, đây là engine OCR cổ điển trả về text kèm khung và độ tin cậy. **[Suy luận]** Vì không phải mô hình sinh, nó khó bịa câu và khó gặp kiểu chặn RECITATION đã làm khổ nhóm. Chưa có nguồn nào xác nhận điều này. Điểm yếu: **chưa ai đo độ chính xác tiếng Việt của Document AI**, kể cả độc lập lẫn tự báo. Đây là ứng viên "rủi ro thấp", không phải "đã chứng minh tốt nhất".

**SenOCR-Vi đứng thứ hai vì nó là mô hình tiếng Việt có bằng chứng tốt nhất trong nhóm dùng thương mại được.** Mô hình do VietAlphaLabs phát hành ngày 31/8/2026, có 0,96 tỷ tham số, là bản tinh chỉnh LoRA trên PaddleOCR-VL-1.6, giấy phép Apache-2.0. Trên MDPBench-VI, tác giả tự báo 82,83 điểm tổng hợp, độ chính xác text 86,7% và bảng chỉ 70,7 TEDS [VI-tự báo] ([VietAlpha](https://www.vietalpha.org/research/senocr-vi)). Tác giả cũng tự nêu bố cục nhiều cột dày đặc là điểm khó, đúng vào kiểu trang Công báo, và khuyến nghị có người duyệt khi chép văn bản luật ([VietAlpha](https://www.vietalpha.org/research/senocr-vi)). Chạy trên CPU là khả thi về mặt kỹ thuật, vì PaddleOCR-VL hỗ trợ CPU x64 qua PaddlePaddle, Transformers và llama.cpp. Tuy vậy **không có số đo giây/trang trên CPU** ([PaddleOCR-VL docs](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL.html)). Con số duy nhất thấy được là khoảng 32,65 giây/trang trên một trang tổng hợp, và chỉ đọc được qua đoạn trích kết quả tìm kiếm ([ThakiCloud](https://thakicloud.github.io/en/research/paddleocr-vl-09b-multilingual-document-parsing/)). **[Suy luận]** Ở tốc độ đó, 40 trang thử mất khoảng 20 phút, còn 11.000 trang mất khoảng 100 giờ CPU. Vì vậy nên dùng CPU để đo trên bộ chuẩn, còn chạy cả kho thì đưa lên GPU miễn phí. Lưu ý: T4 không có bfloat16, và vLLM trên T4 dễ timeout ([PaddleOCR docs](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL.html); [Granite-Docling](https://huggingface.co/ibm-granite/granite-docling-258M)).

**Gemini xếp thứ ba dù có điểm tiếng Việt cao nhất nhóm.** Gemini-3-pro-preview đạt 85,9 trên cột VI của MDPBench [VI-độc lập] ([MDPBench](https://huggingface.co/datasets/Delores-Lin/MDPBench/blob/main/README.md)). Lý do bị đẩy xuống là RECITATION. Nhóm đã ghi nhận lệnh chặn là cố định, thử lại vô ích, và 11 trang bảng, phụ lục chỉ qua được khi cắt thành bốn góc ([recitation.md](../docs/recitation.md)). Người dùng khác cũng báo cùng hiện tượng: trên sách thuộc phạm vi công cộng, tỷ lệ chặn nhầm tăng từ 1/2000 lên 1/50 ([diễn đàn Google](https://discuss.ai.google.dev/t/new-recitation-false-positives-in-public-domain-works/142749)). **VNPT đứng thứ tư** vì là lựa chọn trong nước duy nhất thử được ngay, nhưng mọi bằng chứng về nó đều là quảng cáo. **AsterNet đứng thứ năm** vì nó là đường nâng cấp rẻ nhất chạy được trên chính máy CPU hiện có, dù chỉ nâng cấp được khâu nhận dạng dòng.

## Bảng so sánh toàn bộ nhà cung cấp

Giá VND giữ nguyên vì ghi chép không cho tỷ giá. Giá cho 11.000 trang là phép tính của người nghiên cứu trên giá niêm yết [Suy luận]. Chi phí ước tính cho các mô hình ngôn ngữ lớn (LLM) giả định mỗi trang 258 token đầu vào và khoảng 1.200 token đầu ra. "Viết tay" là mức hỗ trợ chính thức hoặc tuyên bố của nhà cung cấp, không phải độ chính xác đã đo.

### Dịch vụ trong nước và khu vực

| Bên | Tiếng Việt | Viết tay | Giá / 1.000 trang | Giá 11.000 trang | Chạy ở | Giấy phép / truy cập | Bằng chứng độ chính xác (ai đo) |
|---|---|---|---|---|---|---|---|
| **VNPT SmartReader** | Có, có nhóm văn bản Hành chính và Luật ([vnptai.io](https://vnptai.io/smartreader/en)) | Brochure nói nhận dạng chữ số viết tay (chỉ thấy qua đoạn trích tìm kiếm) ([brochure](https://chuyendoiso.quangngai.gov.vn/items/share/143.pdf)) | 685.000–700.000 VND ([bảng giá](https://vnptai.io/smartreader/en/price)) | 10.350.000 VND (Reader 10 + Reader 5 = 15.000 trang) hoặc 20.550.000 VND (Reader 30); chưa VAT | Cloud | Tự đăng ký qua console; miễn phí 150 trang, Trial 300 trang | "Tới 99,9%" số hóa, "tới 99%" OCR [Quảng cáo], VNPT tự nêu ([vnptai.io](https://vnptai.io/smartreader/en)) |
| **FPT.AI Reader** | Có | Tự nói 80–85% với chữ viết tay (2022) ([blog FPT](https://fpt.ai/blogs/recognize-and-extract-handwritt-data-fptai-reader/)) | "Liên hệ" ([FPT Cloud](https://fptcloud.com/product/fpt-ai-read/)) | Không tính được | Cloud | FPT ID và API key; 50 request/năm; PDF tối đa 5 MB ([hướng dẫn](https://fpt.ai/blogs/how-to-use-fpt-ai-reader/)) | "Trên 90%", ">95%" chữ in, "tới 98%": các con số tự mâu thuẫn [Quảng cáo]. Chủ yếu trích trường theo mẫu, tài liệu không mô tả OCR toàn trang ([docs](https://docs.fpt.ai/docs/vi/vision/documentation/ocr-platform/)) |
| **Viettel OCR** | Có, nhận PDF ảnh | "Từ 90%" | Không công bố | Không tính được | Cloud/API | Chỉ qua form liên hệ hoặc hotline; chưa rõ trang này là của Viettel hay đại lý ([trang giải pháp](https://giaiphapdoanhnghiepviettel.vn/giai-phap-thi-giac-may-tinh-viettel-ocr)) | Chữ in "từ 99%" [Quảng cáo] |
| **CMC CATI-VLM / SmartDoc** | Có | Không rõ | Không bán dạng API | Không | Nội bộ CMC | Không tiếp cận được | Top 12 RRC DocVQA, không có điểm số, không phải OCR tiếng Việt ([VnExpress](https://e.vnexpress.net/news/tech/vietnam-innovation/vietnam-s-new-ai-model-masters-complex-document-analysis-4909592.html)) |
| **VinBigData VinOCR** | Có | Tự nói có | Không công bố | Không | Không rõ | Chủ yếu dùng cho eKYC | 96% eKYC, 93% danh thiếp, chỉ thấy qua đoạn trích [Quảng cáo] ([VinBigData](https://product.vinbigdata.org/en/category/vinbase-vision-en)) |
| **MISA** | Chỉ hóa đơn | — | Nằm trong phần mềm | Không | Trong sản phẩm | Không có API OCR riêng ([meInvoice](https://www.meinvoice.vn/xu-ly-hoa-don-dau-vao/)) | Không có |
| **Naver CLOVA OCR** | **Không có bằng chứng** ([spec](https://guide.ncloud-docs.com/docs/en/clovaocr-spec)) | — | Trả theo dùng | — | Cloud Hàn Quốc / Nhật | — | Loại |

Ngoài ra, không tìm thấy sản phẩm OCR công khai của Zalo AI. Trang tài liệu OCR của GreenNode trả về 404 ([GreenNode](https://docs.greennode.ai/vn/ai-stack/ai-platform/model-as-a-service/huong-dan-su-dung-api-ocr)).

### Dịch vụ quốc tế

| Bên | Tiếng Việt | Viết tay | Giá / 1.000 trang | Giá 11.000 trang | Chạy ở | Giấy phép / truy cập | Bằng chứng độ chính xác (ai đo) |
|---|---|---|---|---|---|---|---|
| **Google Document AI Enterprise OCR** | Có ([ngôn ngữ](https://docs.cloud.google.com/document-ai/docs/languages)) | **Có** | 1,50 USD ([giá](https://cloud.google.com/document-ai/pricing)) | Khoảng 15 USD (1.000 trang đầu miễn phí) | Cloud | Thương mại | Chưa có số đo tiếng Việt |
| **Google Cloud Vision** | Có ([ngôn ngữ](https://docs.cloud.google.com/vision/docs/languages)) | **Thử nghiệm** | Chưa kiểm | — | Cloud | Thương mại | Chưa có |
| **Azure Document Intelligence Read** | Chữ in có ([Azure](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/language-support/ocr)) | **Không** | 1,50 USD, theo nguồn thứ ba ([activepieces](https://www.activepieces.com/blog/azure-document-intelligence-pricing-per-model-in-2026)) | Khoảng 16 USD | Cloud | F0: 500 trang/tháng | CER 0,04 trên sách tiếng Việt in 1850–2003 [VI-độc lập] ([Do và cộng sự](https://arxiv.org/html/2410.13305v1)) |
| **AWS Textract** | **Không** ([AWS](https://docs.aws.amazon.com/textract/latest/dg/textract-best-practices.html)) | — | 1,50 USD | — | Cloud | — | Loại |
| **Mistral OCR 4.1** | Có ([Mistral](https://docs.mistral.ai/resources/languages)) | Không nhắc tới | 4 USD; batch 2 USD theo nguồn thứ hai ([model card](https://docs.mistral.ai/models/model-cards/ocr-4-1)) | 22–44 USD | Cloud hoặc container tự host | Thương mại | Chưa có số đo tiếng Việt |
| **Datalab API (công ty làm Chandra)** | Có | — | 0,50 / 4 / 10 USD theo chế độ ([giá](https://www.datalab.to/pricing)) | 5,5 / 44 / 110 USD | Cloud | Tín dụng miễn phí 10–20 USD/tháng ([billing](https://documentation.datalab.to/platform/billing.md)) | 85,0 trên tiếng Việt, không rõ chế độ nào [VI-tự báo] ([Chandra](https://github.com/datalab-to/chandra)) |
| **Gemini 3.1 Flash-Lite / 3.1 Pro** | Có, đã đo | Có bài nói "chính xác cao" nhưng không kèm số ([JSHOU](https://jshou.edu.vn/houjs/article/view/720)) | Khoảng 1,9 (batch 0,9) / khoảng 15 USD ([giá token](https://aistudio.google.com/docs/pricing)) | Khoảng 10–21 / khoảng 83–165 USD | Cloud | Thương mại | Gemini-3-pro 85,9 MDPBench-VI; Gemini-3-Pro CER 6,04% trên VMMU [VI-độc lập] ([MDPBench](https://huggingface.co/datasets/Delores-Lin/MDPBench/blob/main/README.md); [VMMU](https://arxiv.org/html/2508.13680)) |
| **Claude (Sonnet / Haiku 5.5)** | Có, đã đo | Không có số liệu | Từ khoảng 12 / 0,6 USD, chỉ tính token đầu ra ([giá](https://claude.com/pricing)) | Từ khoảng 132 / 7 USD | Cloud | Thương mại | Sonnet-4.6 83,1 MDPBench-VI; Sonnet-4.0 CER 4,24% VMMU [VI-độc lập]. Đây là đời cũ hơn bản đang bán |
| **OpenAI (gpt-5.4-mini)** | Có, đã đo | Không có số liệu | Từ khoảng 5,4 USD, chỉ tính token đầu ra ([giá](https://developers.openai.com/api/docs/pricing)) | Từ khoảng 59 USD | Cloud | Thương mại | ChatGPT-5.2 82,1 MDPBench-VI; GPT-4o CER 0,05 trên sách tiếng Việt [VI-độc lập] |
| **Kimi-K2.5** | Có, đã đo | — | — | — | Cloud | **Đã ngừng hỗ trợ** ([Kimi](https://platform.kimi.ai/docs/pricing/chat-k25)) | 86,2 MDPBench-VI [VI-độc lập] |

### Mô hình mã nguồn mở

| Mô hình | Tiếng Việt | Viết tay | Giá | Chạy ở | Giấy phép | Bằng chứng độ chính xác (ai đo) |
|---|---|---|---|---|---|---|
| **SenOCR-Vi** (0,96B) | Riêng cho tiếng Việt | Dữ liệu huấn luyện có 23.046 bản ghi viết tay | 0 | CPU được nhưng chưa đo; GPU cho cả kho | Apache-2.0 | 82,83 MDPBench-VI; header công văn đúng 20/32 trang [VI-tự báo] ([VietAlpha](https://www.vietalpha.org/research/senocr-vi); [Xiaomi card](https://huggingface.co/nhtera/Xiaomi-OCR-0-vi)) |
| **PaddleOCR-VL-1.6** (0,9B) | Có | — | 0 | CPU qua llama.cpp/Transformers; GPU | Apache-2.0 | 79,3 MDPBench-VI [VI-độc lập]; VietAlpha lại trích 80,90, hai con số chưa khớp |
| **Xiaomi-OCR-0-vi** (0,8B) | Riêng cho tiếng Việt | — | 0 | GPU | **CC-BY-NC** (phi thương mại) | 88,1 MDPBench-VI trang số; header công văn đúng 27/32 trang [VI-tự báo] ([card](https://huggingface.co/nhtera/Xiaomi-OCR-0-vi)) |
| **Chandra 2** (5B) | Có | — | 0 | GPU (chỉ công bố tốc độ trên H100) | Trọng số OpenRAIL-M, miễn phí cho nghiên cứu ([Chandra](https://github.com/datalab-to/chandra)) | 85,6 MDPBench-VI [VI-độc lập] |
| **olmOCR 2** (7B) | Có | — | 0 | GPU NVIDIA từ 12 GB | Apache-2.0 ([olmOCR](https://github.com/allenai/olmocr)) | 84,0 MDPBench-VI [VI-độc lập] |
| **AsterNet** (10,6M) | Riêng cho tiếng Việt, chỉ đọc theo dòng | — | 0 | **CPU, khoảng 60 ms/dòng** | MIT ([card](https://huggingface.co/asterxlabs/asternet-vietnamese-ocr)) | CER 3,45% so với VietOCR 3,85%, nhưng WER kém hơn; bộ đánh giá không nêu tên [VI-tự báo] |
| **PaddleOCR-VL-1.6-Vietnamese GGUF** | Riêng cho tiếng Việt, chỉ đọc theo dòng | — | 0 | CPU qua llama.cpp, chưa có số đo tốc độ | Apache-2.0, cần xin quyền tải ([card](https://huggingface.co/tieubaoca/PaddleOCR-VL-1.6-Vietnamese-GGUF)) | CER 0,234 xuống 0,066 trên 160 mẫu của chính tác giả [VI-tự báo] |
| **MinerU2.5-Pro vi-ocr-v2** | Có | **Viết tay theo dòng** | 0 | GPU | CC-BY-NC ([card](https://huggingface.co/Faust345/MinerU2.5-Pro-1.2B-vi-ocr-v2)) | CER 0,608 xuống 0,218, n = 300 [VI-tự báo] |
| **VietOCR** | Có, đọc theo dòng | Kém | 0 | CPU | Apache-2.0 | CER 1,41% ảnh sạch, 29,00% ảnh scan kém, 31,82% viết tay [VI-độc lập, một tác giả, ảnh tổng hợp] ([nom-vn](https://nom-vn.nrl.ai/tasks/ocr)) |
| **Tesseract 5 + vie** | Có | Kém (69,34%) | 0 | CPU | Apache-2.0 | 0,00% / 30,34% (ảnh sạch / scan kém) [VI-độc lập, ảnh tổng hợp] ([nom-vn](https://nom-vn.nrl.ai/tasks/ocr)) |
| **EasyOCR** (đang dùng) | Có | Kém (71,52%) | 0 | CPU | — | 1,42% / 87,09% (nom-vn); CER 0,25 trên sách tiếng Việt [VI-độc lập] ([Do và cộng sự](https://arxiv.org/html/2410.13305v1)) |
| **Surya 2.5 / Marker** | Có | — | 0 | CPU qua llama.cpp, khoảng 4,8 GB RAM | OpenRAIL-M | Tỷ lệ đạt 63,6% trên tiếng Việt [VI-tự báo] ([Surya](https://github.com/datalab-to/surya)) |
| **MinerU 4.x** | Có | — | 0 | CPU 8 GB RAM | Apache-2.0 tùy biến | MinerU-2.5-Pro 74,2 MDPBench-VI [VI-độc lập] ([MinerU](https://github.com/opendatalab/MinerU)) |
| **PP-OCRv5 / v6** | **Thiếu dấu thanh** | — | 0 | CPU | Apache-2.0 | Từ điển chỉ có 19–23/67 chữ có dấu [đã kiểm trực tiếp] ([PP-OCRv6 config](https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec/resolve/main/inference.yml)). **Không dùng** |
| **Vintern-1B-v3.5** | Có | — | 0 | GPU nhỏ | MIT | Chỉ có điểm dạng hỏi đáp trên ảnh (VQA), không có CER ([card](https://huggingface.co/5CD-AI/Vintern-1B-v3_5)) |

## Không benchmark độc lập nào xếp hạng các bên trên văn bản hành chính tiếng Việt

**Kết luận phải nói thẳng trước: bằng chứng hiện có không đủ để chọn ra "bên tốt nhất" cho PDF scan pháp quy tiếng Việt.** Phần dưới tách bằng chứng theo bốn loại, để thấy mỗi loại nói được gì và không nói được gì.

**[VI-độc lập] Đo trên tiếng Việt, nhưng không phải văn bản hành chính.** Bằng chứng mạnh nhất là MDPBench, do Đại học Khoa học và Công nghệ Hoa Trung cùng Kingsoft Office xây dựng. Trên cột tiếng Việt, **kimi-K2.5 đạt 86,2, Gemini-3-pro 85,9, chandra-ocr-2 85,6, olmOCR2 84,0, Claude-Sonnet-4.6 83,1 và ChatGPT-5.2 82,1**. Pipeline cổ điển PP-StructureV3 chỉ đạt 52,7 ([MDPBench](https://huggingface.co/datasets/Delores-Lin/MDPBench/blob/main/README.md); [bài báo](https://arxiv.org/html/2603.28130v1)). Bộ này gồm trang số và trang chụp, không phải trang scan công văn, và không công bố số trang tiếng Việt. SEA-Vision có 1.678 trang tiếng Việt (sách, báo, đề thi) nhưng **không có loại văn bản nhà nước nào**. Trên đó, Qwen3-VL-32B có NED 0,107, Gemini2.5-Pro 0,132 và PaddleOCR-VL 0,148 ([SEA-Vision](https://arxiv.org/html/2603.15409)). Trên sách tiếng Việt in giai đoạn 1850–2003, Azure đạt CER 0,04, GPT-4o 0,05 và EasyOCR 0,25 ([Do và cộng sự](https://arxiv.org/html/2410.13305v1)). Đây là số đo tiếng Việt độc lập duy nhất cho một dịch vụ OCR cổ điển. Không bộ nào trong số này có VNPT, FPT, Viettel, Document AI hay Mistral. Bảng xếp hạng MDPBench đã có thêm Kimi-K3 và các mô hình mới, nhưng các dòng mới không có điểm tiếng Việt ([MDPBench](https://huggingface.co/datasets/Delores-Lin/MDPBench)).

**[VI-tự báo] Do chính tác giả đo.** SenOCR-Vi, Xiaomi-OCR-0-vi, AsterNet, bản GGUF và Datalab đều tự chấm mô hình của mình. Phép đo gần văn bản hành chính nhất chỉ là thứ tự phần đầu công văn trên 32 trang: Xiaomi-OCR-0-vi đúng 27 trang, SenOCR-Vi 20 và PaddleOCR-VL-1.6 19 ([card](https://huggingface.co/nhtera/Xiaomi-OCR-0-vi)). Trên chính benchmark của Datalab, Gemini 2.5 Flash (89,5) còn xếp trên API của Datalab (85,0) ([Chandra](https://github.com/datalab-to/chandra)). Một nhà cung cấp tự công bố kết quả bất lợi cho mình thì đáng tin hơn bình thường.

**[Quảng cáo] Toàn bộ nhà cung cấp trong nước.** VNPT nói "tới 99,9%", Viettel "từ 99%", FPT có các con số "trên 90%", ">95%" và "tới 98%" tự mâu thuẫn nhau. Không bên nào nêu bộ dữ liệu, và không bên nào được đưa vào bất kỳ phép so sánh công khai nào ([vnptai.io](https://vnptai.io/smartreader/en); [Viettel](https://giaiphapdoanhnghiepviettel.vn/giai-phap-thi-giac-may-tinh-viettel-ocr); [FPT Cloud](https://fptcloud.com/product/fpt-ai-read/)). **[Suy luận]** Các con số 99% nhiều khả năng là độ chính xác ký tự trên chữ in sạch, hoặc độ chính xác trường trên mẫu cố định. Không nên kỳ vọng chúng đúng với trang có con dấu, chữ viết tay hay bố cục hai cột.

**[Khác] Bảng xếp hạng chung gần như không nói gì về tiếng Việt.** OXR-1.0 (97,03), TeleOCR (96,91) và PaddleOCR-VL-1.6 (96,34) dẫn OmniDocBench, trên Gemini 3 Pro (92,91) ([OmniDocBench](https://github.com/opendatalab/OmniDocBench)). Nhưng PaddleOCR-VL-1.6 chỉ đạt 79,3 trên cột tiếng Việt, và thẻ mô hình TeleOCR chỉ nêu tiếng Trung và tiếng Anh ([TeleOCR](https://huggingface.co/StarDoc-AI/TeleOCR)). Ở hạng mục "Old Scans" của olmOCR-Bench, điểm tốt nhất đã được kiểm chứng chỉ khoảng 59 ([OXR rerun](https://huggingface.co/npario/OXR-1.0-mlx-8bit)). Nghĩa là trang scan cũ vẫn khó với mọi mô hình. Chênh lệch 1–3 điểm giữa các mô hình dẫn đầu nằm trong mức nhiễu (± khoảng 1 điểm) ([olmOCR](https://github.com/allenai/olmocr)).

## Các ca khó của văn bản pháp quy chưa ai đo

Năm đặc điểm khiến kho này khó cũng chính là năm chỗ bằng chứng mỏng nhất.

**Dấu tiếng Việt** là chỗ có một phát hiện cứng duy nhất. Từ điển của PP-OCRv5 và PP-OCRv6 chỉ chứa 19–23 trên 67 chữ thường có dấu. Recognizer kiểu CTC không thể in ra ký tự không có trong từ điển, nên "Nội dung" thành "Ni Dung" ([PR #14](https://github.com/quynhonsemiconductor/ai-services/pull/14)). Lỗ hổng nằm ở recognizer PP-OCR chứ không ở PaddleOCR-VL.

**Chữ viết tay trên biểu mẫu** chỉ có số đo ở mức dòng hoặc ảnh rời. Trên 200 ảnh viết tay, VietOCR có CER 31,82%, còn EasyOCR và Tesseract khoảng 70% ([nom-vn](https://nom-vn.nrl.ai/tasks/ocr)). Không có số đo nào cho số hiệu hay ngày tháng viết tay trên mẫu in. Trong dịch vụ cloud, chỉ Document AI hỗ trợ chính thức. Cloud Vision ghi "Experimental", Azure không hỗ trợ ([Vision](https://docs.cloud.google.com/vision/docs/languages); [Azure](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/language-support/ocr)).

**Con dấu đỏ** không được nhà cung cấp nào mô tả cách xử lý. Theo Điều 33 Nghị định 30/2020, dấu đóng trùm khoảng 1/3 chữ ký bên trái ([NĐ 30/2020](https://hethongphapluat.com/nghi-dinh-30-2020-nd-cp-ve-cong-tac-van-thu/dieu-33)). Vì vậy trường bị ảnh hưởng nhiều nhất là chức danh và tên người ký, không phải số hiệu. **[Suy luận]** Với bản scan màu, dùng riêng kênh đỏ là thí nghiệm rẻ nhất để làm mờ dấu, nhưng cách này không dùng được với bản scan xám.

**Công báo hai cột**: SenOCR-Vi tự nhận bố cục nhiều cột là điểm khó. Không có số đo thứ tự đọc nào riêng cho trang nhiều cột, và không nguồn nào nói về Công báo ([VietAlpha](https://www.vietalpha.org/research/senocr-vi); [RT-DocLayout](https://arxiv.org/html/2606.23344)).

**Bảng biểu**: trên trang tiếng Việt sạch, Gemini2.5-Pro đạt 0,941 TEDS và PaddleOCR-VL 0,927, nhưng chưa có số đo nào cho bảng scan ([SEA-Vision](https://arxiv.org/html/2603.15409)).

## Nghiên cứu trước đã kết luận: đo trước, OCR lại sau

Nghiên cứu trước về giải pháp OCR PDF tiếng Việt khuyến nghị **không làm sạch lại toàn bộ kho lúc này**, vì ba lý do. Thứ nhất, lỗi trung vị của kho chỉ 0,13%, và chỉ 54 văn bản có lỗi từ 1% trở lên ([TIEN_DO.md](../docs/TIEN_DO.md)). Thứ hai, máy hiện không còn PDF gốc. Thứ ba, chưa có bằng chứng engine mới nào đọc văn bản pháp quy tiếng Việt sạch hơn mức hiện tại.

Nghiên cứu đó còn đưa ra ba điểm vẫn đúng với báo cáo này:

- **Không chuyển sang PP-OCRv5/v6** vì lỗ hổng từ điển nêu ở phần trên.
- **Giả thuyết "lớp OCR ẩn cũ"**: nhiều file "lớp text hỏng" có thể là lớp OCR cũ nằm đè lên ảnh, không phải font VNI/TCVN3. Kiểm được bằng `get_texttrace()` và `pdffonts` ([PyMuPDF](https://pymupdf.readthedocs.io/en/latest/functions.html)).
- **Hiệu đính bằng LLM trên toàn kho dễ làm hỏng văn bản đã tốt.** Một nghiên cứu ghi nhận độ chính xác ký tự tụt từ 99,56% xuống 51,66% khi cho LLM sửa văn bản đã sạch ([Gómez Rey và cộng sự](https://arxiv.org/html/2608.24976v1)).

Lộ trình đề xuất khi đó là: tìm lại PDF gốc, quét lớp ẩn, dựng bộ chuẩn khoảng 40 trang, kiểm số hiệu, so engine trên 50–100 trang, rồi chỉ sửa có chốt chặn trong 54 văn bản. Báo cáo này bổ sung **danh sách nhà cung cấp** cho bước so engine. Báo cáo không thay đổi kết luận đó. **[Suy luận]** Nếu 11.000 trang là phạm vi OCR lại, thì khoản tiền dịch vụ (vài chục USD hoặc khoảng 10 triệu VND) vẫn nhỏ hơn nhiều so với rủi ro thay một engine chưa đo bằng một engine khác cũng chưa đo.

## Dùng bộ chuẩn 40 trang để chọn engine

**[Suy luận]** Bộ chuẩn 40 trang ban đầu được thiết kế để hiệu chỉnh bộ kiểm lỗi, gồm 20 trang lỗi nặng, 10 trang biên và 10 trang sạch. Để chọn engine, nên phân tầng thêm theo ca khó, ví dụ:

| Tầng | Số trang |
|---|---|
| Công báo hai cột | Khoảng 8 |
| Biểu mẫu có chữ viết tay | Khoảng 8 |
| Trang có dấu đỏ và chữ ký | Khoảng 8 |
| Bảng và phụ lục | Khoảng 8 |
| Trang thường | Khoảng 8 |

Nên cộng thêm 11 trang đã từng bị RECITATION ([recitation.md](../docs/recitation.md)). Mỗi văn bản chỉ lấy một hoặc hai trang, chọn ngẫu nhiên.

Cách làm bộ chuẩn đã có trong ghi chép trước:

- **Gõ lại từ ảnh trang, không sửa từ đầu ra OCR**, vì sửa từ đầu ra dễ khiến người gõ đi theo lỗi sẵn có.
- **Gõ đôi độc lập 10–20% số trang** để đo mức sai lệch giữa người gõ. Ở một kho tiếng Yiddish, dấu làm độ đồng thuận giảm rõ (alpha 0,977 so với 0,992 khi bỏ dấu) ([Jochre 3](https://arxiv.org/html/2501.08442)).
- **Chấm bằng CER chặt sau chuẩn hóa NFC, đếm theo cụm grapheme.** dinglehopper làm sẵn việc này ([mã nguồn](https://raw.githubusercontent.com/qurator-spk/dinglehopper/master/src/dinglehopper/character_error_rate.py)). Nên viết unit test cho chữ `ế` ở dạng NFC và NFD trước khi dùng.

**Mỗi engine chạy trên cùng các trang, và cần báo cáo đủ các chỉ số sau:**

| Nhóm chỉ số | Cụ thể |
|---|---|
| Chất lượng ký tự | CER chặt; CER sau khi bỏ dấu; tỷ lệ lỗi dấu |
| Chất lượng trường | Khớp chính xác số hiệu, ngày và người ký |
| Phân bố lỗi | Trung vị CER và tỷ lệ trang hỏng nặng, ngoài trung bình. Một mô hình có trung vị 1,5% nhưng trung bình tới 73,65% khi ảnh mờ ([Devanagari](https://arxiv.org/html/2606.29213)) |
| Vận hành | Tỷ lệ bị chặn hoặc trả rỗng; giây/trang trên CPU của nhóm; chi phí /1.000 trang |

**Về cỡ mẫu [Suy luận]:** giả định khoảng 2.500 ký tự/trang, 40 trang tương đương khoảng 95.000 ký tự. Với hệ số thiết kế giả định là 10, cỡ này đủ ước lượng CER quanh 1% với sai số khoảng ±0,2%. Đủ để phân biệt engine chênh nhau vài điểm phần trăm, nhưng không đủ cho chênh lệch vài phần nghìn. Kiểm riêng 500–1.000 token chứa số: nếu không sai token nào, cận trên 95% của tỷ lệ lỗi là khoảng 0,3–0,6% theo quy tắc ba ([rule of three](https://en.wikipedia.org/wiki/Rule_of_three_(statistics))). **Quy tắc quyết định:** chỉ thay engine khi nó thắng rõ trên trang của nhóm theo cặp từng trang, có khoảng tin cậy bootstrap theo văn bản, và không làm tăng lỗi số hiệu ([HIPE](https://arxiv.org/html/2607.08143v1)).

Đợt thử gần như miễn phí:

| Bên | Nguồn miễn phí |
|---|---|
| Document AI | 1.000 trang miễn phí |
| VNPT | 150 trang miễn phí, thêm 300 trang Trial |
| FPT | 50 request/năm |
| Datalab | 10–20 USD tín dụng mỗi tháng |
| SenOCR-Vi, AsterNet | Chạy trên CPU của nhóm, 40 trang mất vài chục phút |

Gemini cho 40 trang tốn chưa tới 1 USD.

**Rủi ro dữ liệu [Suy luận]:** văn bản pháp quy là công khai, nên gửi lên cloud nước ngoài ít đáng lo. Riêng biểu mẫu có chữ viết tay có thể chứa thông tin cá nhân, nên kiểm tra trước khi gửi. Không nhà cung cấp nào nêu nơi lưu dữ liệu.

## Kết luận

Thị trường OCR tiếng Việt tháng 11/2026 có một nghịch lý. Các nhà cung cấp trong nước, những bên lẽ ra hiểu văn bản hành chính nhất, lại là nhóm duy nhất không có lấy một số đo kiểm chứng được. Trong khi đó, bằng chứng tiếng Việt tốt nhất lại đến từ benchmark Trung Quốc và các mô hình mã nguồn mở tự công bố. Vì vậy, với nhóm, câu hỏi "bên nào tốt nhất" thực chất là câu hỏi "bên nào để lộ lỗi rẻ nhất trên trang của chúng ta". Document AI và SenOCR-Vi thắng ở tiêu chí đó, không phải vì điểm benchmark.

Hệ quả rộng hơn: một bộ chuẩn 40 trang có nhãn theo ca khó (Công báo hai cột, con dấu, viết tay, bảng), chấm ở mức trường, sẽ là **phép so sánh công khai đầu tiên** giữa VNPT, FPT, Google và các mô hình mở trên văn bản pháp quy tiếng Việt. Nếu nhóm công bố bộ này, nó trả lời được câu hỏi mà toàn bộ tài liệu đã đọc đều chưa trả lời, và có giá trị lâu hơn bất kỳ lựa chọn engine nào.
