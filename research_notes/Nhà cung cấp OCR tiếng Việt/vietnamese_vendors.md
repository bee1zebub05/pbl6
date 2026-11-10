# Vietnamese domestic OCR / document-AI providers (as of 10 Nov 2026)

Scope: Vietnamese companies (plus one regional player) offering OCR for Vietnamese text, judged for a student team needing ~11,000 pages of scanned legal/administrative PDFs (diacritics, handwriting on printed forms, red stamps, two-column Công báo, tables).

Fetch status note: smartreader.vnpt.vn returned HTTP 503 (twice); the same product is mirrored on vnptai.io, which loaded and is used instead. viettelgroup.ai DNS failed; product.vinbigdata.org refused connection; voz.vn returned 403; the Quang Ngai VNPT brochure PDF is image-only and could not be read. Claims from those pages are marked snippet-only or omitted.

## 1. Which providers exist, and do they do full-page document OCR (not only ID/eKYC)?

### Takeaway
VNPT SmartReader is the only Vietnamese vendor found with a public self-serve price list per page, a free quota, and a stated document-OCR use (tables, multi-page, administrative documents). FPT.AI Reader is mostly template- or field-based, with a small free quota. Viettel AI, CMC, VinBigData and MISA publish no prices and seem to sell through sales contracts or for narrow uses (eKYC, invoices). The newest relevant entrant, VietAlphaLabs SenOCR-Vi (Aug 2026), is open model weights, not a hosted Vietnamese service.

### Cited Findings

**VNPT SmartReader (VNPT AI / VNPT IT)**
- Positioned as an AI assistant for digitizing documents and extracting data. It claims to handle "complex documents such as tables, multi-page documents, and those with decorative backgrounds", has pre-configured document types for Administration, Finance & Banking, Insurance, Education and Law, and lets extracted fields be "converted into API format" — [vnptai.io SmartReader](https://vnptai.io/smartreader/en)
- Extracted fields come with accuracy scores and warning indicators, which works as a per-field confidence output — [vnptai.io SmartReader](https://vnptai.io/smartreader/en)
- Plan features listed: "character recognition for each file", information extraction, text summarization, multi-file character recognition (Free and above), plus customizable data extraction and a document library (Trial and above) — [vnptai.io price page](https://vnptai.io/smartreader/en/price)
- The product page does not mention PDF input, handwriting, stamps, layout output or deployment model — [vnptai.io SmartReader](https://vnptai.io/smartreader/en)
- A Sept 2024 VNPT brochure (search snippet only; the PDF is image-only and could not be read) describes accurate Vietnamese character recognition, extraction of typed text and **handwritten digits**, and complex-table analysis — snippet-only via search of [chuyendoiso.quangngai.gov.vn PDF](https://chuyendoiso.quangngai.gov.vn/items/share/143.pdf)

**FPT.AI Reader / FPT.AI Read (FPT Smart Cloud)**
- FPT Cloud product page: handles "mọi mẫu giấy tờ, không giới hạn về cấu trúc" (invoices, receipts, CVs, contracts, survey forms, quotations), deep learning plus NLP, API integration. It does not mention PDF, output format, handwriting, or data residency. Price is "Liên hệ" (contact us). Copyright 2025 — [FPT Cloud – FPT.AI Read](https://fptcloud.com/product/fpt-ai-read/)
- Official docs describe two app types. "Crop" apps cut out the document. "OCR" apps are trained by drawing labelled rectangles on sample documents, which is zone or template extraction. A Marketplace offers pre-built services (personal, insurance, finance, banking, general documents). The docs **do not describe general full-page text OCR**, and give no JSON schema, bounding boxes or confidence. Export is to Excel or through the API — [docs.fpt.ai OCR platform](https://docs.fpt.ai/docs/vi/vision/documentation/ocr-platform/)
- How-to guide (10 Mar 2025): uploads accept JPG, PNG and **PDF**, max 5 MB per file. Custom document models need at least 3 sample templates. It does not describe free-form OCR of arbitrary text — [FPT.AI blog, how to use](https://fpt.ai/blogs/how-to-use-fpt-ai-reader/)
- Handwriting: a 2022 blog claims handwriting and handwritten numbers are recognised at 80–85%, and printed text at over 95%. It says blurry or damaged inputs and stylized handwriting are unsuitable. Target documents: medical records, payment orders, customer forms — [FPT.AI blog, handwriting (8 Jul 2022)](https://fpt.ai/blogs/recognize-and-extract-handwritt-data-fptai-reader/)

**Viettel AI – Viettel OCR**
- A page branded "Giải pháp doanh nghiệp Viettel" says Viettel OCR converts scanner and camera images and **image-based PDFs** into editable text or Word. It covers structured, semi-structured and unstructured documents, automatic document classification, roughly 5 s per page in parallel, and API/Webservice integration. **No prices** appear, despite the title "Bảng giá … 2024". The footer says ©2023. It is unclear whether this is an official Viettel site or a reseller — [giaiphapdoanhnghiepviettel.vn](https://giaiphapdoanhnghiepviettel.vn/giai-phap-thi-giac-may-tinh-viettel-ocr)
- A Viettel AI handwriting-recognition technology won a VIFOTEC award. The search snippet credits a VIFOTEC 2024 study on extracting information from document images with varied layouts, tables and Vietnamese handwriting. Snippet-only: the fetched article body was truncated — [viettelai.vn article](https://viettelai.vn/en/tin-tuc/cong-nghe-viet-nhan-dien-chu-viet-tay-tu-giai-thuong-vifotec-den-ung-dung-doi-song)
- Viettel AI has announced real-time table-structure extraction. Title only, not opened — [vnreview](https://vnreview.vn/threads/viettel-ai-cong-bo-giai-phap-tu-dong-trich-xuat-cau-truc-bang-bieu-trong-thoi-gian-thuc.49181/)

**CMC (CMC ATI – CATI-VLM; SmartDoc)**
- CATI-VLM is a visual-document-understanding model with 3B parameters, trained on 5 TB. CMC plans to embed it in the C.OpenAI ecosystem: the legal-document assistant CLS, the document-digitization platform SmartDoc, and CMC KMS. The article (3 Jul 2025) **does not say it is sold as an API** — [VnExpress International](https://e.vnexpress.net/news/tech/vietnam-innovation/vietnam-s-new-ai-model-masters-complex-document-analysis-4909592.html); [VietnamNet](https://vietnamnet.vn/en/cmc-s-vietnamese-ai-model-ranks-top-12-globally-in-document-understanding-2417697.html)
- No source found for products named "C-OCR" or "CIVAMS" as OCR services. The searches returned nothing relevant.
- Samsung SDS R&D Vietnam launched an AI OCR (key-information extraction, e.g. driver's licences) on CMC Cloud. Snippet-only, not opened — [Samsung SDS VN](https://www.samsungsds.com/vn/story/optical-character-recognition.html)

**VinBigData – VinOCR (VinBase Vision)**
- Search snippets of the vendor page: VinOCR detects, identifies and extracts written information from images. It claims formatted and unformatted documents, tables, graphs and handwriting. The main use is eKYC (VinID e-wallet). It quotes 96% accuracy and under 1 s for remote customer identification, and 93% for business cards. **Snippet-only**: product.vinbigdata.org refused the connection — [VinBigData VinBase Vision](https://product.vinbigdata.org/en/category/vinbase-vision-en)
- No public API, pricing, or full-page document OCR offering was found.

**MISA**
- OCR exists only inside MISA meInvoice and AMIS Kế toán, for invoices: reading invoices from photos and files, and automatic booking through the MISA AVA assistant. **No standalone OCR API** was found — [MISA meInvoice](https://www.meinvoice.vn/xu-ly-hoa-don-dau-vao/); [AMIS help](https://helpact.misa.vn/kb/tro-thu-ai-tren-amis-ke-toan/)

**Zalo AI**
- No public Zalo AI OCR product or API was found (search returned only unrelated vendors).

**Naver CLOVA OCR (regional)**
- CLOVA OCR offers General, Template and Document domains, is available in the Korea and Japan regions, and returns text through a REST API — [NCloud CLOVA OCR overview](https://guide.ncloud-docs.com/docs/en/clovaocr-overview)
- Supported languages (prerequisites page, snippet-only): Korean, English, Japanese. **No evidence of Vietnamese support** — [CLOVA OCR spec](https://guide.ncloud-docs.com/docs/en/clovaocr-spec)

**VietAlphaLabs SenOCR-Vi (new, Aug 2026)**
- Released 31 Aug 2026. It is a 0.96B-parameter LoRA fine-tune of PaddleOCR-VL-1.6 for Vietnamese document OCR, under Apache-2.0. It is published as **Hugging Face weights; no hosted API or price is mentioned** on the release page — [VietAlpha research](https://www.vietalpha.org/research/senocr-vi); [HF model card](https://huggingface.co/VietAlphaLabs/SenOCR-Vi)
- A third-party inference endpoint listing exists on Friendli. Not opened; snippet-only — [friendli.ai](https://friendli.ai/models/VietAlphaLabs/SenOCR-Vi)
- The training data includes a Vietnamese handwriting lane of 23,046 records. **Dense multi-column layouts** and complex tables are listed as hard. The authors recommend human review for legal transcription — [VietAlpha research](https://www.vietalpha.org/research/senocr-vi)

**GreenNode (VNG) OCR API**
- A GreenNode docs URL for an OCR API turned up in search, but the page returns "Page Not Found". Status unknown — [docs.greennode.ai](https://docs.greennode.ai/vn/ai-stack/ai-platform/model-as-a-service/huong-dan-su-dung-api-ocr)

### Inferences
- VNPT SmartReader is the only domestic vendor whose public offering combines general "character recognition per file", tables, an administrative-document category, and a public per-page price. It is the most practical commercial candidate to trial.
- From its official docs, FPT.AI Reader is built for field extraction from known templates. It is a poor fit for transcribing full pages of Công báo unless a general-OCR Marketplace service exists, which the team should check in the console.
- CMC CATI-VLM shows research strength, but there is no accessible product for students.
- SenOCR-Vi is the most relevant free option, but it is self-hosted, not a vendor service.

### Gaps
- TechCity: no search was run with results; existence and offerings unverified.
- Lạc Việt also appeared in search ("document digitization comprehensive service OCR", [lacviet.vn](https://lacviet.vn/en/?p=40145)) but the page was not opened.
- Viettel AI's official OCR product page (viettelgroup.ai/service/ocr) failed DNS. Its API docs and output format are unknown.
- No vendor documents stamp (con dấu) handling or two-column reading-order output.

## 2. PDF input, output format, handwriting, price, free trial, student access, data residency

### Takeaway
Only VNPT publishes prices: about 700 VND per page on small plans, with 150 free pages. FPT gives 50 free requests per year and says it bills per request, but shows no public rates. Everyone else is "contact us". PDF input is confirmed only for FPT (≤5 MB) and Viettel (image PDFs). Bounding boxes and layout output are undocumented across all vendors.

### Cited Findings
- **VNPT SmartReader prices (excl. VAT):** Free 150 pages = 0; Trial 300 pages = 0; Reader 5 = 5,000 pages for 3,500,000 VND; Reader 10 = 10,000 pages for 6,850,000 VND; Reader 30 = 30,000 pages for 20,550,000 VND; Reader 50 = 33,500,000; Reader 60 = 40,200,000; Reader 80 = 53,600,000; Reader 120 = 78,600,000; Reader 300 = 196,500,000; Reader 600 = 385,800,000; Enterprise = contact. Validity tabs (1/6/12 months) are shown but not tied to prices. Sign-up goes through console-smartreader.vnpt.vn/subscription/info, and Enterprise goes through VNPT IT — [vnptai.io price](https://vnptai.io/smartreader/en/price)
- VNPT purchase requires logging in before payment, and the API key is tied to the account — snippet-only from the shopping-guide search result ([smartreader.vnpt.vn shopping guide](https://smartreader.vnpt.vn/en/shopping-guide); the site returned 503)
- **FPT.AI Reader:** free tier of "50 requests per year". API billed "based on the actual number of requests", with extra capacity bought in Settings. Needs an FPT ID (id.fptcloud.com) and a Console.fpt.ai API key — [FPT.AI blog, 10 Mar 2025](https://fpt.ai/blogs/how-to-use-fpt-ai-reader/). The FPT Cloud page lists price only as "Liên hệ" — [FPT Cloud](https://fptcloud.com/product/fpt-ai-read/)
- **Viettel OCR:** no prices; contact form or hotline 0868681600 — [giaiphapdoanhnghiepviettel.vn](https://giaiphapdoanhnghiepviettel.vn/giai-phap-thi-giac-may-tinh-viettel-ocr)
- **CLOVA OCR:** pay-as-you-go, with rates shown in the console. A maintenance fee applies to plans other than General and free (snippet). The recommended rate is 1 TPS per account, and demo uploads take jpg, png, pdf or tiff ≤50 MB (snippet) — [CLOVA OCR spec](https://guide.ncloud-docs.com/docs/en/clovaocr-spec)
- **SenOCR-Vi:** free weights under Apache-2.0. Memory figures are storage estimates of 3.83 GB FP32 and 1.92 GB BF16, not measured VRAM. Speed has not been measured — [VietAlpha research](https://www.vietalpha.org/research/senocr-vi)

### Inferences
- Cost of 11,000 pages on VNPT, computed from the listed prices: Reader 10 + Reader 5 = 10,350,000 VND, or Reader 30 = 20,550,000 VND (enough with spare). Both are before 10% VAT, and the validity period is unclear. Small plans work out to about 685–700 VND per page. The free 150 pages, plus 300 on Trial if it is separate, are enough for a pilot.
- FPT's free 50 requests per year is enough only for a small pilot.
- Data residency: no vendor page states where data is stored. VNPT, FPT and Viettel are domestic clouds (inferred, not documented). CLOVA runs only in the Korea and Japan regions.

### Gaps
- Whether VNPT SmartReader accepts PDFs, its maximum pages per file, and its output (plain text, Word, JSON with bounding boxes) are not documented on the pages that loaded.
- Whether VNPT's plans are monthly or one-off, and whether an individual or student without a company can buy (VAT invoice or business requirements), is unverified.
- Rate limits are documented only for CLOVA. VNPT, FPT and Viettel publish none.
- A Vietnamese phone number or company registration requirement is not documented for any vendor.

## 3. Accuracy evidence (vendor claims vs independent)

### Takeaway
Every number for domestic vendors is a vendor claim with no dataset named. No independent benchmark comparing FPT, VNPT, Viettel and others on Vietnamese administrative documents was found. The only reproducible numbers are SenOCR-Vi's self-reported results on a public benchmark, and those are also produced by its own authors.

### Cited Findings
- VNPT SmartReader: "up to 99.9%" accuracy for digitization and "up to 99%" for OCR recognition. Vendor claim, no dataset — [vnptai.io](https://vnptai.io/smartreader/en)
- FPT.AI Read: "trên 90%" for Vietnamese text recognition (FPT Cloud page, ©2025) — [FPT Cloud](https://fptcloud.com/product/fpt-ai-read/). Printed text over 95% and handwriting 80–85% (2022 blog) — [FPT.AI blog](https://fpt.ai/blogs/recognize-and-extract-handwritt-data-fptai-reader/). A FPT.AI Vietnamese page claims over 98% on clear documents (search snippet only) — [fpt.ai vi](https://fpt.ai/vi/so-hoa-tai-lieu-doanh-nghiep-chi-trong-1-giay-voi-phan-mem-ocr-fptai-reader). These vendor figures conflict with each other.
- Viettel OCR: printed text "from 99%", handwriting "from 90%", ID-card fields over 98%. Vendor claim, no dataset — [giaiphapdoanhnghiepviettel.vn](https://giaiphapdoanhnghiepviettel.vn/giai-phap-thi-giac-may-tinh-viettel-ocr)
- CMC CATI-VLM: top 12 worldwide and first in Vietnam in the RRC DocVQA category (June 2025), topping 4 of 7 RRC datasets. **No numeric score given**. DocVQA is mostly English question answering, not Vietnamese OCR — [VnExpress Intl, 3 Jul 2025](https://e.vnexpress.net/news/tech/vietnam-innovation/vietnam-s-new-ai-model-masters-complex-document-analysis-4909592.html)
- VinOCR: 96% (eKYC) and 93% (business cards). Snippet-only vendor claim — [VinBigData](https://product.vinbigdata.org/en/category/vinbase-vision-en)
- SenOCR-Vi (self-reported, 31 Aug 2026): Vietnamese composite (MDPBench) 82.83, against chandra-ocr-2 85.60, MonkeyOCRv2-B 83.20, Claude-Sonnet-4.6 83.10, ChatGPT-5.2 82.10 and PaddleOCR-VL-1.6 80.90. Vietnamese text recognition was 86.7% (page edit distance 0.133) on a corrected 160-page set. Tables scored 70.7 TEDS. Photographed pages scored 80.8 against 91.1 for digital pages. **No domestic commercial vendor is included in the comparison** — [VietAlpha research](https://www.vietalpha.org/research/senocr-vi)

### Inferences
- The team cannot rank vendors from published evidence. They should run a pilot themselves: about 50–100 representative pages (Công báo two-column, forms with handwriting, stamped pages, tables) through the VNPT free quota, the FPT free quota and SenOCR-Vi, scored by CER/WER against hand-corrected ground truth.
- Vendor "99%" claims are probably character-level on clean printed text or field-level on templates. They are unlikely to hold for stamped, handwritten or two-column scans.

### Gaps
- No independent Vietnamese benchmark of domestic commercial OCR APIs was found (2025–2026).
- No vendor reports results on stamps, two-column reading order, or handwriting on administrative forms.
- A voz.vn thread asking for the best Vietnamese administrative-document OCR exists, but returned 403, so its user experiences could not be read — [voz.vn](https://voz.vn/p/42881288/)

## 4. Practical access (sign-up, contracts, rate limits)

### Takeaway
VNPT (self-serve console, free 150 pages) and FPT (FPT ID plus console API key, 50 free requests per year) can be tried by students immediately. Viettel, CMC, VinBigData and MISA need sales contact or a product subscription.

### Cited Findings
- VNPT: Free, Trial and Reader plans have a "Register now" button to console-smartreader.vnpt.vn. Enterprise is "Contact us" — [vnptai.io price](https://vnptai.io/smartreader/en/price)
- FPT: register at id.fptcloud.com, use reader.fpt.ai (VI/EN UI), and create an API key at Console.fpt.ai. A new key gets 50 requests by default — [FPT.AI blog](https://fpt.ai/blogs/how-to-use-fpt-ai-reader/)
- Viettel: contact form or hotline only — [giaiphapdoanhnghiepviettel.vn](https://giaiphapdoanhnghiepviettel.vn/giai-phap-thi-giac-may-tinh-viettel-ocr)
- CLOVA: recommended 1 TPS per account (snippet) — [CLOVA spec](https://guide.ncloud-docs.com/docs/en/clovaocr-spec)

### Inferences
- With 11,000 pages, the free tiers cover only evaluation. Full processing on a vendor means paying VNPT about 10–21 million VND, or negotiating with others. Self-hosting SenOCR-Vi, or another open model, avoids per-page fees but needs a GPU.

### Gaps
- Whether a Vietnamese phone number, CCCD or company tax code is needed at VNPT or FPT sign-up, and whether students get academic discounts, is undocumented.
- Rate limits and maximum file size for VNPT are undocumented. FPT's limit is 5 MB per file.
