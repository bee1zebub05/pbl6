# Vietnamese OCR and hard cases in administrative and legal documents (as of 9 November 2026)

Reading conventions:
- "[snippet only]" means the number or claim was seen in a search result and the page could not be opened or was not opened. Treat it as a lead, not as evidence.
- "NOT Vietnamese" flags evidence from another language. It is context, not a Vietnamese result.
- Higher is better for composite scores, TEDS and 1-NED. Lower is better for CER, NED and edit distance.

## Which engines have measured results on Vietnamese?

### Takeaway
Three independent multi-model benchmarks now include Vietnamese (SEA-Vision, MDPBench, VMMU). They favour frontier closed models and large general VLMs, plus recent OCR VLMs such as PaddleOCR-VL-1.5/1.6 and fine-tunes. None of them contains Vietnamese administrative pages, stamps or gazettes. For classic engines the main real finding is a structural one that I checked directly: official PP-OCRv5 Latin and server dictionaries cannot output most tone-marked Vietnamese vowels.

### Cited Findings

**Multi-model benchmarks with a Vietnamese column**

MDPBench (30 Mar 2026; 3,400 images across 17 languages; page-level composite of text 1-NED, table TEDS and formula CDM). Vietnamese column — [MDPBench paper](https://arxiv.org/html/2603.28130v1):

| Model | VI composite | All-language digital | All-language photographed |
|---|---|---|---|
| kimi-K2.5 | 86.2 | 85.0 | 75.0 |
| Gemini-3-pro-preview | 85.9 | 90.4 | 85.1 |
| olmOCR2 | 84.0 | 79.9 | 67.2 |
| Claude-Sonnet-4.6 | 83.1 | 85.0 | 69.3 |
| ChatGPT-5.2 | 82.1 | 85.6 | 63.0 |
| HunyuanOCR | 80.6 | 80.2 | 64.3 |
| dots.mocr | 79.9 | 90.5 | 77.2 |
| dots.ocr | 79.1 | 88.8 | 72.3 |
| PaddleOCR-VL-1.5 | 78.9 | 87.4 | 75.2 |
| Doubao-2.0-pro | 76.5 | 78.9 | 72.8 |
| Qwen3.5-Instruct-9B | 74.0 | 74.8 | 62.7 |
| Qwen3-VL-Instruct-8b | 73.4 | 78.4 | 65.0 |
| GLM-OCR | 69.2 | 77.9 | 63.7 |
| PaddleOCR-VL (original) | 66.6 | 87.6 | 63.6 |
| InternVL-3.5-8B | 57.0 | 59.7 | 37.0 |
| DeepSeek-OCR | 54.1 | 80.7 | 42.2 |
| PP-StructureV3 (pipeline) | 52.7 | 56.2 | 41.7 |
| MinerU-2.5-VLM | 46.0 | 61.9 | 40.8 |
| MinerU-2.5-pipeline | 27.6 | 57.6 | 25.4 |

- The MDPBench paper does not give a per-language sample count or a Vietnamese digital/photographed split. It records that dots.mocr shows "language drift" on Vietnamese, recognising it as Chinese — [MDPBench](https://arxiv.org/html/2603.28130v1).
- Later model cards report Vietnamese populations of different sizes from MDPBench: 160 pages in one and 39 digital plus 39 photographed in another. The counts conflict and the cause is not explained — [SenOCR-Vi card](https://huggingface.co/VietAlphaLabs/SenOCR-Vi); [Xiaomi-OCR-0-vi card](https://huggingface.co/nhtera/Xiaomi-OCR-0-vi).
- On that later comparison, chandra-ocr-2 (5B) scores 85.60, MonkeyOCRv2-B-Parsing 83.20, SenOCR-Vi 82.83 and PaddleOCR-VL-1.6 80.90. This table is self-reported by the SenOCR-Vi authors, who also removed three phantom rows caused by a scorer defect — [SenOCR-Vi card](https://huggingface.co/VietAlphaLabs/SenOCR-Vi); [VietAlpha report, 31 Aug 2026](https://www.vietalpha.org/research/senocr-vi).

SEA-Vision (16 Mar 2026). The Vietnamese parsing subset has 1,678 pages: academic literature, books, textbooks, exam papers, magazines, newspapers, notes, slides and research reports. No government or legal category exists. 11.50% of pages have tables — [SEA-Vision](https://arxiv.org/html/2603.15409).

| Model | VI end-to-end NED | VI pure-text NED | VI table TEDS | VI reading-order NED |
|---|---|---|---|---|
| Qwen3-VL-32B | 0.107 | 0.076 | 0.921 | 0.109 |
| Qwen2.5-VL-72B | 0.122 | 0.069 | 0.905 | 0.120 |
| Gemini2.5-Pro | 0.132 | 0.098 | 0.941 | 0.128 |
| PaddleOCR-VL | 0.148 | 0.172 | 0.927 | 0.114 |
| dots.ocr | 0.152 | 0.100 | 0.851 | 0.142 |
| Dolphin-1.5 | 0.167 | 0.108 | 0.821 | 0.097 |
| POINTS-Reader | 0.184 | 0.202 | 0.837 | 0.164 |
| DeepSeek-OCR | 0.216 | 0.171 | 0.763 | 0.190 |
| GPT4o | 0.244 | 0.214 | 0.744 | 0.185 |
| MinerU2.5 | 0.278 | 0.469 | 0.872 | 0.197 |
| MonkeyOCR-pro-3B | 0.370 | 0.721 | 0.806 | 0.271 |
| MonkeyOCR-pro-1.2B | 0.457 | 0.878 | 0.808 | 0.461 |
| InternVL3.5-38B | 0.587 | 0.577 | 0.307 | 0.490 |

All values are from [SEA-Vision Table 2 and Appendix B.1](https://arxiv.org/html/2603.15409).

VMMU (embedded Vietnamese text in images; a 210-question subset; ground truth was bootstrapped from o3 and then corrected by a human, which may favour o3). CER values — [VMMU Table 3](https://arxiv.org/html/2508.13680):

| Model | CER % | WER % |
|---|---|---|
| o3 | 4.09 | 5.25 |
| GPT-4.1 | 4.10 | 7.04 |
| Sonnet-4.0 | 4.24 | 7.52 |
| Gemini-3-Pro | 6.04 | 9.27 |
| Mistral-Medium-3 | 9.08 | 16.11 |
| Qwen-2.5-VL-72B | 10.73 | 18.49 |
| Gemini-2.5-Flash | 14.46 | 17.57 |
| Gemma-3-27B | 16.18 | 23.89 |
| Qwen-2.5-VL-32B | 19.05 | 24.17 |
| Gemma-3-4B | 24.79 | 37.23 |
| Llama-4-Maverick | 48.77 | 53.91 |

**Classic and open engines, single-author benchmark (1–2 May 2026)**

Neural Research Lab's project page tested 200 held-out handwriting images (`brianhuster/VietnameseOCRdataset`) and 70 synthetic in-house printed images. Clean, noisy and poor-scan images are synthetic. Authors warn this may not generalise to real scans, and latency is not comparable across rows — [nom-vn OCR page](https://nom-vn.nrl.ai/tasks/ocr).

| Engine | Clean CER % | Noisy CER % | Poor-scan CER % | Handwriting CER % |
|---|---|---|---|---|
| Tesseract 5 + vie | 0.00 | 0.70 | 30.34 | 69.34 |
| VietOCR vgg_transformer | 1.41 | 3.37 | 29.00 | 31.82 |
| EasyOCR | 1.42 | 4.87 | 87.09 | 71.52 |
| PaddleOCR PP-OCRv5 | 24.70 | 31.33 | 86.13 | 59.43 |
| RapidOCR | 63.97 | 77.83 | 100.00 | 97.20 |
| qwen2.5vl:7b (Ollama) | 33.17 | 29.90 | 81.37 | 67.53 |

- An earlier run on the same site gave Tesseract 5.53% CER (8.21% on diacritics), EasyOCR 9.39% (14.88%) and qwen2.5vl:7b 31.07% (38.45%). The authors say this VLM hallucinates on single-line crops and recommend VLMs only for whole-document work. Surya was not measured because its licence failed their review — [nom-vn OCR page](https://nom-vn.nrl.ai/tasks/ocr).
- VieSVTR v7 (self-reported, CC BY-NC): 6.13% CER on VinText (8,421 lines) versus 15.16% for the public VietOCR vgg_transformer; 6.62% versus 12.51% on MC-OCR receipts (521 lines), scored with the same script — [VieSVTR card](https://huggingface.co/ngocthua830/viesvtr).
- VietOCR's README reports 0.8800 full-sequence precision for vgg_transformer and 0.8701 for vgg_seq2seq, on its own roughly 10-million-image set. The page gives no date and no release; treat this as older information. Licence is Apache-2.0 — [VietOCR](https://github.com/pbcquoc/vietocr).
- Surya 2.5 scores a 63.6% pass rate on Vietnamese (Surya 2: 57.9%), against 74.9% across 91 languages. This is an internal test-pass benchmark, not CER, and has no competitor comparison. Weights use a modified OpenRAIL-M licence, free only for research, personal use and startups under $5M — [Surya README](https://github.com/datalab-to/surya); [Surya language table](https://raw.githubusercontent.com/datalab-to/surya/master/static/docs/multilingual.md).
- An NUS project page (1 Aug 2024) says EasyOCR, Tesseract and GOT "perform well" on Vietnamese and Thai, and that most errors are characters misclassified as other languages. It gives no numbers on that page — [NUS WING](http://www.comp.nus.edu.sg/~kanmy/wing/project/benchmarking-and-improving-ocr-on-sea-languages/).

**PaddleOCR dictionary gap, checked directly on 9 Nov 2026**

- I downloaded the official files and counted the 67 lowercase Vietnamese accented letters. `ppocrv5_latin_dict.txt` contains 22 of 67, so it lacks forms such as ạ ả ấ ầ ệ ộ ợ ự ỹ. The `latin_PP-OCRv5_mobile_rec` inference config also has 22 of 67, and `PP-OCRv5_server_rec` has 19 of 67 (it also lacks ơ and ư). The legacy `vi_dict.txt` has all 67 — [ppocrv5_latin_dict.txt](https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/main/ppocr/utils/dict/ppocrv5_latin_dict.txt); [latin mobile config](https://huggingface.co/PaddlePaddle/latin_PP-OCRv5_mobile_rec/raw/main/inference.yml); [server config](https://huggingface.co/PaddlePaddle/PP-OCRv5_server_rec/raw/main/inference.yml); [vi_dict.txt](https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/main/ppocr/utils/dict/vi_dict.txt).
- PaddleOCR nonetheless lists Vietnamese (`vi`) under `latin_PP-OCRv5_mobile_rec`, with 84.7% accuracy on a mixed 3,111-image Latin dataset and no Vietnamese-only figure or Vietnamese recognizer — [PP-OCRv5 multilingual docs](https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html).
- Independent reports agree. A May 2026 benchmark says `lang='vi'` drops tone marks even on clean print — [nom-vn](https://nom-vn.nrl.ai/tasks/ocr). A pull request dated 9 Nov 2026, on just 3 fixtures, measured macro CER of about 16.49% for the official Latin model, 16.84% for the `en` PP-OCRv6 model, and 2.83% for an unlicensed community fine-tune, which it rejected for lacking a licence — [PR #14](https://github.com/quynhonsemiconductor/ai-services/pull/14).

**Vietnamese VLMs and fine-tunes**

- Xiaomi-OCR-0-vi (self-reported, CC-BY-NC-4.0, Qwen3.5-0.8B base). Scores below are 1-NED / bag-F1 — [card](https://huggingface.co/nhtera/Xiaomi-OCR-0-vi).

| Test | Xiaomi-OCR-0-vi | SenOCR-Vi | PaddleOCR-VL-1.6 |
|---|---|---|---|
| MDPBench-VI digital (39) | 88.1 / 89.5 | 84.1 / 88.5 | 83.8 / 85.1 |
| MDPBench-VI photos (39) | 81.1 / 83.6 | 79.6 / 84.4 | 78.6 / 80.4 |
| VN-Hard (40 Wikisource pages, 1651–1975) | 91.7 / 80 | 86.4 / 76 | 89.2 / 74 |
| Công văn header order (correct pages / 32) | 27 | 20 | 19 |

- This is the only administrative-document measurement found. It measures header ordering only, on 32 pages, and the same card notes the date sometimes lands between "Số" and "V/v", and that on consolidated texts (VBHN) the issuer can appear after "CỘNG HÒA" — [card](https://huggingface.co/nhtera/Xiaomi-OCR-0-vi).
- SenOCR-Vi (31 Aug 2026, Apache-2.0, decoder-only LoRA on PaddleOCR-VL-1.6): 82.83 composite and 86.7% text on Vietnamese; edit distance fell from 0.15300 to 0.13305. Its macro EN/VI/ZH score (82.98) is slightly below the base model's (83.43) — [VietAlpha](https://www.vietalpha.org/research/senocr-vi).
- Vintern-1B-v3.5 (MIT, 0.9B): vi-MTVQA 41.9 and OCRBench 706, while its base InternVL2_5-1B scores 24.8 and 785. These are VQA-type scores, and no CER on Vietnamese documents is given — [Vintern card](https://huggingface.co/5CD-AI/Vintern-1B-v3_5).
- A Vietnamese diploma study (Oct 2025) compared DeepSeek, LLaMA-3.2-11B-Vision, EasyOCR and Gemini. The abstract page has no numbers and no dataset size. It says Gemini and LLaMA have high accuracy including on handwriting, DeepSeek "does not support Vietnamese" (which product is unclear), and EasyOCR needs manual coordinates — [JSHOU](https://jshou.edu.vn/houjs/article/view/720).

**Vendor APIs — no independent measurement**

- FPT.AI Reader's own blog (10 Mar 2025) claims "up to 98%" on library templates, handling of "red marks over text", 50 free requests (described inconsistently as per year and per key), a 5 MB per-file limit, and no public price — [FPT blog](https://fpt.ai/blogs/how-to-use-fpt-ai-reader/). FPT's OCR platform docs give no numbers, price, or mention of tables, stamps or handwriting — [FPT docs](http://docs.fpt.ai/docs/en/vision/documentation/ocr-platform/).
- VNPT Smart Reader claims up to 99.9% accuracy [snippet only; page returned 503] — [VNPT](https://smartreader.vnpt.vn/en).
- Viettel AI claims over 99% and more than 50 document types [snippet only; the fetch returned only the title] — [Viettel article](https://viettelai.vn/en/tin-tuc/cong-nghe-nhan-dang-ky-tu-quang-hoc-ocr-la-gi). Its pricing page returned no readable OCR prices — [Viettel pricing](https://viettelai.vn/en/bang-gia).
- IONE markets extraction of issuing body, number, date and signer from công văn and self-reports 90% on handwriting [snippet only] — [IONE](https://ionetech.com.vn/phan-mem-nhan-dang-chu-viet-tay-tieng-viet-trong-hinh-anh-scan-21246/).

**Datasets**

- A 2025 survey lists VNOnDB (1,146 paragraphs), VNDoc (226 documents, including legal, phone and scanner), MC-OCR (over 2,000 receipts), Cinnamon handwriting (1,838 images), a Kaggle handwriting set (over 110,000 words), DataoceanAI printed (5,006) and ViOCRVQA (over 28,000) — [survey](https://arxiv.org/html/2506.05061).
- `hvpu/document-signature-stamp-dataset` has 5,714 gated samples from Vietnamese administrative and contract pages, labelled signature, stamp, both or none, with extracted transparent object layers. It has no transcription, stated licence or model results — [Hugging Face](https://huggingface.co/datasets/hvpu/document-signature-stamp-dataset).

### Inferences
- For a default page-level engine on Vietnamese, the best-evidenced shortlist is Gemini 3 Pro and comparable frontier APIs, then large Qwen VLMs, then PaddleOCR-VL-1.5/1.6 and its fine-tunes. Rankings shift by benchmark, so no single winner is supported.
- PP-StructureV3 scoring 52.7 on Vietnamese in MDPBench is plausibly tied to the dictionary gap. The paper does not state this as the cause.
- The gap comes from the PP-OCR recognizers, not necessarily from PaddleOCR-VL, which scored much higher. Do not reject PaddleOCR as a family, and do not use `lang='vi'` PP-OCRv5 for production Vietnamese without replacing the recognizer.
- Results conflict for Qwen: 33% CER for qwen2.5vl:7b on line crops, against NED 0.069 for Qwen2.5-VL-72B on pages. Model size, quantisation and input scope differ, so these are not contradictory but should not be merged.
- Model size matters within a family, for example Qwen3-VL-32B in SEA-Vision versus Qwen3-VL-8b in MDPBench. Benchmarks differ too, so this is suggestive only.
- Non-commercial licences on several of the strongest fine-tunes (Xiaomi-OCR-0-vi, VieSVTR) restrict production use.

### Gaps
- No benchmark found contains real Vietnamese công văn, nghị định, quyết định or Công báo scans with field-level or page-level ground truth, except the 32-page header-order count.
- Gemma 4: no Vietnamese OCR numbers found. Vintern: no CER. Zalo: nothing found on OCR. FPT, VNPT, Viettel: no independent accuracy and no public per-page price I could read.
- EasyOCR, Tesseract and PP-OCRv5 on real Vietnamese scans: only synthetic or very small evidence.
- I did not verify PP-OCRv6 dictionaries myself; PR #14 reports the same gap in them.

## Stamps and seals: does removal improve OCR of the text beneath?

### Takeaway
There is evidence that removal helps classic OCR, but it is synthetic, small and non-Vietnamese. No study was found measuring it on Vietnamese documents or on current VLMs. Removal cannot restore fully hidden characters. Vietnamese rules place most stamp overlap on the signature block, which narrows where this risk occurs.

### Cited Findings
- Decree 30/2020 Article 33 requires clear, upright impressions in red ink, and says a seal over a signature covers roughly the left third of it. On appendices, the seal goes on the first page and partly covers the issuer's name or the appendix title. Cross-page seals sit near the middle of the right edge — [Điều 33, NĐ 30/2020](https://hethongphapluat.com/nghi-dinh-30-2020-nd-cp-ve-cong-tac-van-thu/dieu-33).
- DocDiff (ACM MM 2023, older): on 20 in-house synthetic patches, half watermark and half seal, Tesseract CER fell from 28.7% to 1.8% after enhancement. It is the clearest before/after number found, but seal and watermark results are pooled — [DocDiff](https://arxiv.org/html/2305.03892). DocDiff also found DE-GAN output had 13.7% CER against 4.4% for DocDiff on deblurring — [DocDiff](https://arxiv.org/html/2305.03892). A separate summary notes GAN output can have good PSNR but blurred character edges [snippet only] — [DocDiff PDF](https://arxiv.org/pdf/2305.03892).
- An older non-learned method (2013-era Springer volume) reports significantly better OCR for English and Bengali after stamp removal [snippet only; no numbers read] — [Springer](https://link.springer.com/content/pdf/10.1007/978-3-642-45062-4_75.pdf).
- A 2026 diffusion paper reports better stamp removal than GAN methods and proposes an EA-RMSE metric [snippet only; 403 on fetch] — [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2590005626001785).
- Microsoft's moderators (Jul 2026) say no documented setting removes stamps or recovers hidden text. Colour filtering may help when stamps are consistently red or blue over black text. Preprocessing works best on semi-transparent stamps, and opaque hidden characters are not recoverable. A user later reported `ocrHighResolution` did not help on stamped pages, and that question was unanswered — [Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/5941008/azure-document-intelligence-ocr-for-official-seals).
- Frontiers in Big Data (Jan 2026, Chinese seals): red-minus-green colour separation reached 94.1% segmentation accuracy on real data, against 82.3% for HSV. It then recognised seal text at 96.66% / 95.54% on 84 real images using polar unwrapping and a commercial API. It evaluates the seal's own text, and treats the black body text as interference, so it does not measure text beneath — [Frontiers paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12847014/).
- Seal2Real: word recognition under seals rose from 75.34% to 81.59% when a recogniser was trained on its realistic synthetic data rather than traditional synthetic data (SwinTextSpotter; English-language paper). This improves training data, not removal — [Seal2Real](https://arxiv.org/html/2310.00546).
- PaddleOCR's seal pipeline uses curved-text detection (`PP-OCRv4_server_seal_det` 98.40% Hmean; mobile 96.36%), with optional layout, orientation and unwarping stages. The sample output is Chinese, and neither Vietnamese nor Latin seal use is documented — [PaddleOCR seal docs](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/seal_recognition.html). Doc versions vary slightly in their Hmean figures [snippet only].
- PaddleOCR-VL-1.5's authors report seal recognition NED of 0.138, against 0.382 for Qwen3-VL-235B and 0.396 for Qwen2.5-VL-72B. This is self-reported and has no Vietnamese breakdown — [PaddleOCR-VL-1.5](https://arxiv.org/html/2601.21957).
- Xiaomi-OCR-0-vi includes red-seal data in training but reports no seal metric — [card](https://huggingface.co/nhtera/Xiaomi-OCR-0-vi).

### Inferences
- On a colour scan, a red stamp appears near white in the red channel while black text stays dark. Blue ink also stays dark. So the red channel is a cheap first experiment, and handwriting or signatures in blue ink should survive it. This is colour reasoning, not a measured result.
- It will not work on grayscale or black-and-white scans, which are common in archives. Those need a learned model or a VLM reading the original image.
- Whether removal helps a VLM is untested. VLMs read stamped pages using context, and removal could cut both ways. Test by running with and without on stamped pages. Guard against generated text, since a restorer can create plausible but wrong characters; keep the original image for audit.
- Because Article 33 places the overlap on the signature block, the fields most exposed are the signer's title and name. Số hiệu and date are not normally under the signature stamp, though this should be confirmed on real samples.
- The hvpu dataset's transparent stamp layers could build a synthetic Vietnamese "stamp over text" test set, subject to access and rights.

### Gaps
- No Vietnamese measurement of OCR beneath stamps, with any engine.
- No measurement of red-channel removal on any VLM.
- No Vietnamese seal-text recognition result.
- Signature block recognition: no evaluation found for Vietnamese signer name and title under stamps.

## Handwriting: Vietnamese results, mixed pages, and external metadata

### Takeaway
Published Vietnamese handwriting CERs range from about 3.5% to over 30%, depending on the dataset. Those numbers come from line-level or isolated data, not from digits and dates written onto printed forms. Azure does not list Vietnamese for handwriting. External-metadata correction has no measured Vietnamese result, and generic post-correction has failed on hard handwriting.

### Cited Findings
- HANDS-VNOnDB line-level test (1,634 test, 4,433 train): HTR-ConvText 3.45% CER, 8.9% WER; HTR-VT 4.26% / 11.2%; OrigamiNet 7.6% / 22.6%; GFCN 8.4% / 24.2%; CNN+BLSTM 10.53% / 29.1% — [HTR-ConvText, Dec 2025](https://arxiv.org/html/2512.05021).
- On VNOnDB line level, older work includes AED with DenseNet at 4.67% / 13.33% and an HC-based method at 4.13% / 9.47% (older, pre-2024) — [survey table](https://arxiv.org/html/2506.05061).
- A VietOCR fine-tune reports 4.01% CER and 11.02% WER, but only 34.76% exact-line match, on UIT_HWDB_line. These numbers come from the 702-line validation set, not the 201-line test set — [card](https://huggingface.co/DungHugging/vietocr-handwritten-finetune).
- On 200 held-out images, VietOCR scored 31.82%, PP-OCRv5 59.43%, qwen2.5vl:7b 67.53%, Tesseract 69.34% and EasyOCR 71.52% — [nom-vn](https://nom-vn.nrl.ai/tasks/ocr).
- Handwritten medical records: 2% CER, 12% WER (Dinh et al., via the survey; dataset size not read) — [survey](https://arxiv.org/html/2506.05061).
- Azure Document Intelligence v4.0 lists Vietnamese for printed text. Its handwriting table lists 12 languages and not Vietnamese (page updated 19 Oct 2026) — [Azure language support](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/language-support/ocr).
- Post-correction on nom-vn: on handwriting at about 70% CER, a base spell corrector moved CER from 69.34% to 69.98%, helping 35 images and hurting 103. A fine-tuned version reached 81.80% CER, with 91.3% of output words absent from raw OCR. On hard printed text, CER moved from 30.34% to 29.91%, helping 11 images and hurting 12. Authors keep it opt-in — [nom-vn](https://nom-vn.nrl.ai/tasks/ocr).
- NOT Vietnamese (Devanagari, Jun 2026): a ByT5 corrector trained on EasyOCR did not transfer to other engines and was neutral or harmful. It also raised CER under blur and low DPI — [Devanagari stress test](https://arxiv.org/html/2606.29213).
- A reference-based LLM post-OCR method for classical Vietnamese books reports a grading score of 8.72 versus 7.03 for a transformer baseline [snippet only; not a CER] — [ResearchGate](https://www.researchgate.net/publication/389494064_Reference-Based_Post-OCR_Processing_with_LLM_for_Precise_Diacritic_Text_in_Historical_Document_Recognition).
- A Research Square preprint proposes dictionary and rule-based diacritic-aware post-correction for Vietnamese scans [snippet and title only; results unread] — [Research Square](https://www.researchsquare.com/article/rs-10241038).
- `protonx-legal-tc` is a T5 corrector for Vietnamese legal text, trained on 800,000 pairs [snippet only; no CER seen] — [card](https://huggingface.co/protonx-models/protonx-legal-tc).

### Inferences
- A low CER with 34.76% exact-line match shows why CER is the wrong target for document numbers and dates: one wrong digit makes the field wrong. Measure field-level exact match instead.
- Crop-and-route is reasonable for handwritten fields, as a design choice: crop the "Số" and date zones and read them separately with a handwriting-capable model. It is unproven on these fields.
- Format and metadata checks look more defensible than free-form correction. Validate a candidate number against a pattern such as number/year/type-issuer, and check the date against the issuer and year. Then fuzzy-match against an authoritative registry such as vbpl metadata, and accept only a change that reaches an exact registry record. No evidence measures its benefit, and false matches are a risk. Log both raw and corrected values, and send disagreement to review.
- Generic LLM rewrites should not touch numbers and dates. The nom-vn hallucination results support caution here, though they concern a different task.

### Gaps
- No Vietnamese results for handwriting on printed forms, for handwritten digits in document numbers, or for dates specifically.
- No measured mixed printed and handwritten evaluation on Vietnamese pages. The general material found was vendor blogs.
- No measured results for metadata-based correction in Vietnamese or for vbpl-assisted lookup.
- Signature detection on Vietnamese pages: a dataset exists, but no published model result was found.
- Decree 30 search results state paper documents are signed in blue ink, but I did not open the clause itself. Check it before relying on ink colour for separation.

## Two-column layout and reading order

### Takeaway
Layout models that jointly predict reading order beat detection plus XY-cut on general benchmarks. They do so by a large margin, at about 0.04 versus 0.17 edit distance in one comparison. But there is no multi-column-specific score, and nothing on Công báo. Vietnamese reading-order numbers exist only as page-level averages.

### Cited Findings
- RT-DocLayout (22 Jun 2026, Cheng Cui, Tingquan Gao and others), OmniDocBench v1.5 reading-order edit distance, using PaddleOCR-VL-1.5 as recogniser: DocLayout-YOLO 0.169, MinerU2.5 layout 0.051, Dolphin-v2 layout 0.060, PP-DocLayoutV2 0.042, RT-DocLayout 0.042. RT-DocLayout has 33M parameters and runs at 132.1 FPS on an A100 at batch 32. No multi-column or newspaper numbers are given. One PP-DocLayoutV2 cell may be a copy error — [RT-DocLayout](https://arxiv.org/html/2606.23344).
- The same paper's ablation: XY-cut on bbox+mask 0.074, decoupled reading-order model 0.189, joint learning 0.041 — [RT-DocLayout](https://arxiv.org/html/2606.23344).
- PaddleOCR-VL (Oct 2025): reading-order edit 0.043 on OmniDocBench v1.5, and 0.045 EN / 0.063 ZH on v1.0 — [PaddleOCR-VL](https://arxiv.org/html/2510.14528v1). PaddleOCR-VL-1.5 reports 0.042 — [PaddleOCR-VL-1.5](https://arxiv.org/html/2601.21957). PP-StructureV3 reports 0.069 EN / 0.091 ZH — [PP-StructureV3 docs](https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-StructureV3/PP-StructureV3.html).
- Vietnamese reading-order NED on SEA-Vision, which includes 185 newspaper and 200 magazine pages but no per-type split: Dolphin-1.5 0.097, Qwen3-VL-32B 0.109, PaddleOCR-VL 0.114, Qwen2.5-VL-72B 0.120, Gemini2.5-Pro 0.128, dots.ocr 0.142, GPT4o 0.185, DeepSeek-OCR 0.190, MinerU2.5 0.197 — [SEA-Vision](https://arxiv.org/html/2603.15409).
- LayoutReader (EMNLP 2021, older): average page-level BLEU 0.9819 and ARD 1.75, against 0.6972 and 8.46 for a left-to-right heuristic. The data is ReadingBank (500,000 English pages from DocX). The paper names multi-column templates as a heuristic weakness but gives no multi-column split — [LayoutReader](https://ar5iv.labs.arxiv.org/html/2108.11591).
- PP-DocLayout-L: 90.4 mAP@0.5 on detection — [PaddleOCR docs](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/seal_recognition.html).
- Surya 2.5: layout score 95.7 on OmniParseBench (internal, Surya 2: 94.5), no reading-order score — [Surya README](https://github.com/datalab-to/surya).
- SenOCR-Vi lists dense multi-column layouts among hard cases — [card](https://huggingface.co/VietAlphaLabs/SenOCR-Vi). Xiaomi-OCR-0-vi notes it sometimes writes paragraphs as tables and vice versa — [card](https://huggingface.co/nhtera/Xiaomi-OCR-0-vi).

### Inferences
- Công báo pages are regular two-column layouts, so a simple column or XY-cut approach may be enough, particularly as a baseline. The 0.074 XY-cut ablation result is on mixed pages and does not settle this.
- Evaluate reading order on a small hand-labelled Công báo set. Include article headings spanning columns and tables crossing columns, since those are where I would expect order to break. This is an expectation, not a measurement.
- The RT-DocLayout and PaddleOCR-VL reading-order results are reported by the authors of the models being promoted, with no independent replication found.

### Gaps
- No source found on Công báo, vbpl or Vietnamese gazette OCR.
- No multi-column-only reading-order result for any listed model.
- LayoutReader and Surya have no comparable OmniDocBench reading-order number in what I read.
- PP-DocLayoutV3's mAP was not reported in the paper content read.

## Table recovery from scans

### Takeaway
On Vietnamese clean-page tables, Gemini 2.5 Pro, PaddleOCR-VL and Qwen3 lead at about 0.92–0.94 TEDS. PaddleOCR-VL also beats PP-StructureV3 on non-Vietnamese benchmarks. No Vietnamese scanned-table evaluation exists, and classic table models have no Vietnamese numbers.

### Cited Findings
- Vietnamese table recognition on SEA-Vision, shown as TEDS (NED): Gemini2.5-Pro 0.941 (0.066), PaddleOCR-VL 0.927 (0.059), Qwen3-VL-32B 0.921 (0.086), Qwen2.5-VL-72B 0.905 (0.120), MinerU2.5 0.872 (0.109), dots.ocr 0.851 (0.136), DeepSeek-OCR 0.763 (0.221), GPT4o 0.744 (0.248), InternVL3.5-38B 0.307 (0.755), average 0.808 — [SEA-Vision Table A6](https://arxiv.org/html/2603.15409). Its page types do not include government documents, and scan share is not read.
- SenOCR-Vi reports 70.7 TEDS on its controlled mini-population and says it is not a table specialist — [SenOCR-Vi](https://huggingface.co/VietAlphaLabs/SenOCR-Vi).
- NOT Vietnamese: on OmniDocBench v1.5, PaddleOCR-VL scores TEDS 89.76 / TEDS-S 93.52, and PP-StructureV3 81.68 / 89.48. On v1.0, 88.0 EN and 92.1 ZH against 77.2 and 83.9. On In-house-Table, PaddleOCR-VL scores 0.8699 / 0.9066 — [PaddleOCR-VL](https://arxiv.org/html/2510.14528v1).
- NOT Vietnamese: on a "high-difficulty Chinese table dataset", SLANeXt_wired scores 69.65%, SLANet_plus 63.69% and SLANet 59.52%. GPU times are 85.92, 23.43 and 23.96 ms — [PaddleOCR table docs](https://www.paddleocr.ai/v3.3.2/en/version3.x/module_usage/table_structure_recognition.html).
- NOT Vietnamese: TableFormer scores TEDS 95.4 simple, 90.1 complex and 93.6 overall. The model card gives no scanned or non-Latin evidence — [Docling models](https://huggingface.co/docling-project/docling-models).
- Surya 2.5 scores 78.3 on OmniParseBench tables and 58.1 on multilingual tables. It does not return row and column geometry — [Surya README](https://github.com/datalab-to/surya).

### Inferences
- If cell geometry is needed for review or field mapping, VLM HTML output may not be enough. Surya's limitation shows this is a practical concern.
- PP-StructureV3's table module would inherit the PP-OCR text recognizer gap unless its recogniser is replaced. Structure-only scores would hide this, so measure TEDS with text as well as TEDS-S.
- Tabular legal annexes need a per-cell number and diacritic check, because TEDS can look good while one cell value is wrong.

### Gaps
- No measured table result on Vietnamese scanned legal documents.
- No TableFormer, SLANet, SLANeXt or PP-StructureV3 table-only Vietnamese results.
- Stamps crossing tables, multi-page tables and merged-cell Vietnamese tables: no evidence.

## Image preprocessing: does it still help with modern models?

### Takeaway
Restoration clearly helps Tesseract and helps a VLM far less, on one large non-Vietnamese study. Modern OCR VLMs vary widely in robustness, so a model-specific test is needed. There is no Vietnamese preprocessing study and no DPI curve on Vietnamese. No VLM measurement of binarisation or super-resolution was found.

### Cited Findings
- PreP-OCR (May 2025; 13,831 real degraded pages from English, French and Spanish books; NOT Vietnamese): diffusion restoration (ResShift) took Tesseract CER from 5.91% to 2.81% in English, 5.16% to 2.89% in French, and 7.12% to 3.42% in Spanish. GOT went from 11.18% to 7.11%. GPT-4o barely changed: 2.34% to 2.20% excluding outliers, and 6.51% to 6.06% on all pages — [PreP-OCR](https://arxiv.org/html/2505.20429).
- Devanagari stress test (Jun 2026; 100 sentences per condition; synthetic degradations; NOT Vietnamese), corpus CER clean → blur → low-DPI: EasyOCR 2.82 → 3.05 → 3.07; Qwen3-VL-8B 1.44 → 1.56 → 1.62; olmOCR 3.92 → 3.37 → 3.43; DeepSeek-OCR 3.58 → 111.8 → 51.9, with output up to 71.6 times the reference length. DeepSeek-OCR's median CER stays low (1.50 under blur) while its mean is 73.65, so the authors recommend reporting median and catastrophic rate alongside the mean — [Devanagari stress test](https://arxiv.org/html/2606.29213).
- PaddleOCR-VL-1.5 on Real5-OmniDocBench (authors' own; NOT Vietnamese): overall 92.05, scanning 93.43, warping 91.25, screen 91.76, illumination 92.16, skew 91.66, against 77.47 on skew for the original PaddleOCR-VL — [PaddleOCR-VL-1.5](https://arxiv.org/html/2601.21957).
- MDPBench all-language digital → photographed: Gemini-3-pro-preview 90.4 → 85.1; PaddleOCR-VL-1.5 87.4 → 75.2; PaddleOCR-VL 87.6 → 63.6; ChatGPT-5.2 85.6 → 63.0; DeepSeek-OCR 80.7 → 42.2 — [MDPBench](https://arxiv.org/html/2603.28130v1). Photographed pages are not the same as low-quality scans.
- Vietnamese-specific: digital → photo goes 88.1 → 81.1 for Xiaomi-OCR-0-vi and 83.8 → 78.6 for PaddleOCR-VL-1.6 (self-reported, 39 pages each) — [card](https://huggingface.co/nhtera/Xiaomi-OCR-0-vi). Synthetic clean → poor scan goes 0.00 → 30.34 for Tesseract and 1.41 → 29.00 for VietOCR — [nom-vn](https://nom-vn.nrl.ai/tasks/ocr).
- DocDiff deblurring with Tesseract: DE-GAN 13.7%, DE-GAN+HRR 7.6%, DocDiff 4.4% CER (2023, 30 patches, older) — [DocDiff](https://arxiv.org/html/2305.03892).
- Azure moderators advise noise reduction, contrast, deskewing and sharpening, with no measurements — [Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/5941008/azure-document-intelligence-ocr-for-official-seals).

### Inferences
- Preprocessing's value probably depends on the engine: higher for Tesseract and VietOCR on bad scans, lower for frontier VLMs. This rests on non-Vietnamese data.
- Deskew is likely still worthwhile and low-risk: it is cheap, and the original PaddleOCR-VL's skew score shows that some VLMs are skew-sensitive. PaddleOCR-VL-1.5's improvement also suggests this varies by version.
- Diacritics are small marks, so aggressive binarisation or denoising could erase them. I found no Vietnamese measurement of this, so treat it as a hypothesis to test, for example by reporting diacritic-only CER.
- Super-resolution and generative restoration can invent characters, which is a serious risk for legal numbers and dates. Use them only as a retry path, with the original image kept and disagreements reviewed.
- A practical test: run the Vietnamese sample at about 150, 200 and 300 DPI, with and without deskew and restoration, tracking median CER, catastrophic rate, diacritic CER, and field exact match.

### Gaps
- No Vietnamese DPI or resolution study; no measured Vietnamese binarisation, deskew or super-resolution effect on VLMs.
- No study of JPEG compression on Vietnamese diacritics. The Research Square paper describes the degradation mechanism, but I could not read its results.
- Vendor claims about DPI thresholds were seen, but no method was published, so none are included here.
