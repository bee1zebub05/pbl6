# Parsing stages of a scanned-document → structured-text pipeline for RAG / KG (state as of Nov 2026)

Research note conventions:
- "Opened" = I fetched the page and the claim comes from its text. "Snippet-only" = claim seen only in a search-engine summary, page not opened; treat as unverified.
- "Vendor claim" = self-reported by the system's maker. "Independent" = third-party or academic evaluation not by the system's author.
- All sources are 2025–2026 unless marked [OLDER].

---

## Q1. What reference architectures do major vendors and frameworks publish?

### Takeaway
Every major cloud now publishes the same shape: an OCR-grounded layout parser that detects elements, including headings, tables, figures, and page headers/footers. It emits Markdown or JSON with page and bounding-box provenance, adds an LLM/VLM "verbalisation" of figures and tables, and then does layout-aware chunking. Google and Databricks put a Gemini/foundation model inside the parser. Azure keeps a classical layout model (Document Intelligence v4.0) in its AI Search skill. AWS offers a choice between a text-only default parser, Bedrock Data Automation (BDA), or a foundation-model-as-parser. Open-source tools split into modular pipelines (Docling, Marker, MinerU-pipeline, PaddleOCR-VL's two-stage) and end-to-end page-VLMs (olmOCR 2, dots.ocr, DeepSeek-OCR, Chandra).

### Cited Findings

**Google: Document AI Layout Parser + Vertex AI RAG Engine**
- The Gemini Layout Parser "combines Google's OCR models with Gemini." Its stages are: parse and structure (keeping the heading/paragraph/table hierarchy), then annotate and verbalise figures and tables with Gemini (Preview), then chunk and augment. Chunks are augmented with ancestor headings and table headers so they remain meaningful when retrieved alone. Google says building on OCR "grounds extraction in the document's actual text, reducing hallucinations." (opened) — [Google Cloud docs: Layout Parser](https://docs.cloud.google.com/document-ai/docs/layout-parse-chunk)
- Model versions listed (opened, Google's own doc):
  - stable default `pretrained-layout-parser-v1.0-2024-06-03` (not described as Gemini-based)
  - v1.5 on Gemini 2.5 Flash/Pro (2025-08-25)
  - v1.6 on Gemini 3.0 Pro (2025-12-01) and Gemini 3.0 Flash (2026-01-13)
  - `v3.1-lite-2026-08-11` on Gemini 3.1 Flash Lite
  - v1.6 uses the global endpoint and is not data-residency compliant.

  — [Google Cloud docs](https://docs.cloud.google.com/document-ai/docs/layout-parse-chunk)
- PDF elements detected: figures, paragraphs, tables, titles, headings, page headers, and page footers. Tables spanning pages "may split into two tables." Limits: online processing allows 20 MB and 15 pages per PDF; batch allows 1 GB and 500 pages per PDF. (opened) — [Google Cloud docs](https://docs.cloud.google.com/document-ai/docs/layout-parse-chunk)
- In Vertex AI RAG Engine, the layout parser makes "context-aware chunks." "All text in a chunk comes from the same layout entity" (heading, subheading, list). The import path has limits of 20 MB and 500 pages per PDF. The console recommends a chunk size of 1024 with overlap 256; the API sample uses 512 with overlap 100. Files imported without the layout parser must be deleted and re-imported to use it. (snippet-only, from search summary of the doc page) — [Vertex AI: Use Document AI layout parser with RAG Engine](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/layout-parser-integration)

**Microsoft: Azure Document Intelligence layout model + Azure AI Search "Document Layout" skill**
- The skill calls Document Intelligence layout model **v4.0 (2024-11-30)**. It outputs Markdown (default) or text. `markdownHeaderDepth` (h1–h6) controls section splitting: each Markdown section object carries an `h1/h2/h3…` ancestor dictionary and an `ordinal_position`. (opened; page updated 2026-08-08) — [Microsoft Learn: Document Layout skill](https://learn.microsoft.com/en-us/azure/search/cognitive-search-skill-document-intelligence-layout)
- With `extractionOptions: ["images","locationMetadata"]`, the skill emits `locationMetadata` with `pageNumber`, `ordinalPosition`, and `boundingPolygons` for each text chunk and extracted image. The images can then be "verbalised" by an LLM for multimodal search. Text mode supports character chunking (300–50,000 characters, overlap less than half). (opened) — [Microsoft Learn](https://learn.microsoft.com/en-us/azure/search/cognitive-search-skill-document-intelligence-layout)
- Limits: up to 2,000 pages for PDF/TIFF; images between 50×50 and 10,000×10,000 px; a 5-minute processing timeout, after which you are still charged. DOCX and PDF "may produce different results" in image handling, so Microsoft suggests converting to PDF for consistency. (opened) — [Microsoft Learn](https://learn.microsoft.com/en-us/azure/search/cognitive-search-skill-document-intelligence-layout)
- Azure AI Search also underpins "Foundry IQ," a managed, permission-aware knowledge layer for agents. (opened) — [Microsoft Learn](https://learn.microsoft.com/en-us/azure/search/cognitive-search-skill-document-intelligence-layout)

**AWS: Bedrock Knowledge Bases parsing options**
- There are three parsers:
  1. **Default parser.** Text only (txt/md/html/doc(x)/xls(x)/pdf) and free. It does not handle figures, tables, or images.
  2. **Bedrock Data Automation (BDA).** Fully managed, no prompting, priced per page.
  3. **Foundation model as parser.** The prompt can be customised, it is priced per token, and there is a 100 GB total file limit.

  BDA and FM parsers extract figures, charts, tables, and images to S3 and can return them in source attribution. (opened) — [AWS Bedrock docs: Parsing options](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-advanced-parsing.html)
- If BDA or FM parsing is chosen, it is applied to **all** PDFs in the data source, including text-only ones. There is no per-page routing; you pay for every page. (opened) — [AWS Bedrock docs](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-advanced-parsing.html)

**Databricks: `ai_parse_document` (Agent Bricks)**
- Announced in Public Preview on 11 Nov 2025. It is a single SQL function that replaces "OCR services, layout detection APIs, and figure captioning tools." It captures tables (including merged and nested cells) and figures with AI-generated descriptions, plus bounding boxes "for citations and validation." Output goes to Unity Catalog. It runs incrementally in Spark Declarative Pipelines, with Lakeflow handling retries, checkpointing, and scaling. (opened) — [Databricks blog: PDFs to Production](https://www.databricks.com/blog/pdfs-production-announcing-state-art-document-intelligence-databricks)
- Vendor claims: the "highest quality for its price category" and "quality competitive with the best competitor offerings at 3–5x lower cost." The comparisons use the OmniOCR benchmark and an internal benchmark, with no numeric scores in the text. The blog does not disclose the internal stages or models. (opened) — [Databricks blog](https://www.databricks.com/blog/pdfs-production-announcing-state-art-document-intelligence-databricks)
- Docs: version 2.0 represents tables as HTML. Parameters include `version`, `imageOutputPath`, `descriptionElementTypes`, and `pageRange`. Output feeds `ai_prep_search` for RAG. The function requires DBR 17.1+. (snippet-only) — [Databricks docs: ai_parse_document](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_parse_document)

**Docling (IBM, open source): modular pipeline**
- Stages:
  1. The PDF backend (docling-parse on qpdf; pypdfium as an alternative) extracts text tokens with their coordinates and renders a page bitmap. Image inputs are wrapped as scanned PDFs.
  2. An RT-DETR-derived layout detector trained on DocLayNet and proprietary data predicts element boxes and classes. Boxes are then intersected with text tokens to form paragraphs, titles, list items, captions, figures, and tables.
  3. OCR (EasyOCR by default, Tesseract as an alternative) runs **only** on scanned pages and bitmap regions detected by layout.
  4. TableFormer predicts table structure from the crop and the text cells. Its output is matched back to PDF cells, so table text is not re-transcribed.
  5. Per-page results are aggregated, and post-processing fixes reading order and matches figures to captions.

  (opened; arXiv Jan 2025) — [Docling technical report, arXiv:2501.17887](https://arxiv.org/html/2501.17887v1)
- Output is the `DoclingDocument` Pydantic model. It holds text, tables, pictures, captions, lists, the section hierarchy, bounding boxes, and provenance (page numbers, origin). Page headers and footers are separated from the body as "furniture." It serialises losslessly to JSON and lossily to Markdown and HTML. (opened) — [arXiv:2501.17887](https://arxiv.org/html/2501.17887v1)
- Throughput per page (vendor measurement):

  | Hardware | Average | Median |
  |---|---|---|
  | x86 CPU | 3.1 s | 0.79 s |
  | M3 Max | 1.26 s | 0.32 s |
  | NVIDIA L4 | 481 ms | 114 ms |

  When OCR is needed it dominates: about 13 s per page on x86 and 1.6 s on L4. (opened) — [arXiv:2501.17887](https://arxiv.org/html/2501.17887v1)
- Stated rationale: task-specific models recover only structure, and the text comes from the PDF or OCR. This "avoids the hallucination risk of generative VLMs" and runs on commodity hardware. (opened) — [arXiv:2501.17887](https://arxiv.org/html/2501.17887v1)

**Marker (Datalab, open source): text-layer-first hybrid**
- Stages:
  1. pdftext extracts embedded text in reading order.
  2. Layout is detected with rf-detr (fast mode) or a VLM (balanced mode).
  3. Each page is checked for usable embedded text. Garbled or scanned pages go to OCR.
  4. The VLM handles math.
  5. Tables are rebuilt from the text layer with CPU heuristics. **Low-confidence tables fall back to the VLM.**
  6. An optional LLM pass (`--use_llm`) merges cross-page tables and extracts form values.

  (opened; README as of Nov 2026) — [GitHub datalab-to/marker](https://github.com/datalab-to/marker)
- OCR routing granularity:
  - Balanced mode re-OCRs the whole page if any embedded text looks bad.
  - Fast mode repairs individual bad blocks and does a full-page pass only on scanned or mostly bad pages.
  - Flags: `--force_ocr`, `--strip_existing_ocr`, `--disable_ocr`.

  (opened) — [Marker README](https://github.com/datalab-to/marker)
- Outputs:
  - Markdown with LaTeX math
  - HTML
  - JSON tree of typed blocks with page polygons and section hierarchy
  - "Chunks" (a flat list of top-level blocks for RAG)
  - Per-page extraction stats

  (opened) — [Marker README](https://github.com/datalab-to/marker)

**Unstructured (open source / platform)**
- `partition_pdf` strategies:
  - `auto` (default; chosen from document characteristics)
  - `fast` (rule-based text extraction, about 100x faster than image-to-text models, "not recommended for image-based file types")
  - `hi_res` (model-based layout detection for element classification)
  - `ocr_only`

  Images support `auto`, `hi_res`, and `ocr_only`. The page did not detail the `auto` decision logic or the hi_res models, and it did not mention a `vlm` strategy. (opened) — [Unstructured docs: partitioning strategies](https://docs.unstructured.io/open-source/concepts/partitioning-strategies)

**Reducto (commercial)**
- Hybrid design: character-level OCR plus VLMs for visual context (tables, multi-column). It outputs per-block bounding boxes and block types for citations and chunking. "Agentic OCR" is a multi-pass self-correction review for complex scans and handwriting. Claims are about 20 pp better on RD-TableBench in "some implementations" (vendor/partner claim). (snippet-only; Elastic Search Labs post and Reducto page not opened) — [Elastic Search Labs: Reducto + Elasticsearch](https://www.elastic.co/search-labs/blog/unstructured-documents-reducto-parsing-elasticsearch); [Reducto: Document understanding for RAG](https://llms.reducto.ai/document-understanding-for-rag-and-agents)

**PaddleOCR-VL (Baidu, open source): two-stage**
- Stage 1, PP-DocLayoutV2: an RT-DETR detector finds and classifies layout elements, and a 6-layer pointer network predicts **reading order**.
- Stage 2, PaddleOCR-VL-0.9B (NaViT-style dynamic-resolution encoder + ERNIE-4.5-0.3B): recognises each cropped element as text, table, formula, or chart.
- Post-processing merges the stages into Markdown and JSON. A multithreaded pipeline overlaps PDF rendering, layout inference, and VLM inference.

(opened; arXiv Oct 2025, v4 Nov 2025) — [PaddleOCR-VL, arXiv:2510.14528](https://arxiv.org/html/2510.14528v4)

**MinerU2.5 (OpenDataLab, open source): decoupled coarse-to-fine VLM**
- The 1.2B model first does global layout analysis on a downsampled page, then recognises content on **native-resolution crops** guided by that layout. High-resolution compute goes only to small regions. (opened, abstract; arXiv Sep 2025) — [MinerU2.5, arXiv:2509.22186](https://arxiv.org/abs/2509.22186)

**olmOCR 2 (AI2, open source): end-to-end page VLM**
- olmOCR-2-7B-1025 is fine-tuned from Qwen2.5-VL-7B and then trained with RL using "unit test" rewards. Pages are rendered at **1288 px on the longest edge** (up from 1024 px in v1).
- Output is YAML with front-matter metadata (primary language, **rotation correction**), Markdown body, HTML tables, and LaTeX equations.
- Retry logic: dynamic temperature runs from 0.1 up to 0.8 when the model fails to emit EOS, i.e. a repetition loop. Switching from JSON to YAML reduced retries.

(opened; arXiv Oct 2025) — [olmOCR 2, arXiv:2510.19817](https://arxiv.org/html/2510.19817v1)
- Cost: the README advertises under $200 per million pages. The original olmOCR paper estimated about $176 per million [OLDER, Feb 2025]. An independent reviewer estimated about $350 per million on a $2/h H100. (snippet-only; not opened) — [allenai/olmocr](https://github.com/allenai/olmocr); [dev.to review](https://dev.to/andrew-ooo/olmocr-review-allenais-vlm-beats-mistral-marker-on-pdfs-4cci)

**Surveys**
- The main survey splits document parsing into (a) modular pipeline systems (layout analysis followed by discrete per-element subprocesses: OCR, tables, formulas) and (b) end-to-end VLM approaches. Later versions flag the reliability of VLM parsing as an open challenge. (snippet-only; arXiv Oct 2024 [OLDER], v4/v5 revised 2025) — [Document Parsing Unveiled, arXiv:2410.21169](https://arxiv.org/abs/2410.21169v4)

### Inferences
- Across vendors, the common reference shape is: **file intake → (render page images) → OCR/text-layer extraction → layout detection, including page headers/footers → table structure + figure handling (crop + LLM verbalisation) → reading order + section hierarchy → Markdown/JSON with page + bbox provenance → layout-aware chunking with ancestor headings.** Google, Azure, Databricks, Docling, Marker, and PaddleOCR-VL all expose most of these stages explicitly.
- The cloud services differ mainly in **where generative models enter**:
  - Azure Document Layout skill: none in the parse; LLM verbalisation is a separate skill.
  - Google: Gemini inside the parser, on top of OCR.
  - AWS: all-or-nothing choice of a BDA or FM parser per data source.
  - Databricks: an undisclosed "agentic system."
- AWS's "applies to all PDFs" rule means that per-page born-digital vs scanned routing must be built *before* Bedrock if cost matters. This follows from the AWS doc; it is not stated by AWS as advice.

### Gaps
- I did not open Azure's Document Intelligence layout-model concept page, so I cannot confirm here how it reports figures, selection marks, barcodes, handwriting style, or confidence. The newer Azure Content Understanding service was also not covered.
- I did not open AWS Textract or BDA output-schema pages. Textract per-word/line confidence scores and BDA's standard output (Markdown/HTML/JSON, bounding boxes) remain unverified.
- LlamaParse: no 2025–2026 page opened. Its modes (fast/cost-effective/agentic/agentic-plus) and their routing logic are not verified here.
- Databricks did not disclose the models or stages behind `ai_parse_document`.

---

## Q2. What is the consensus "standard" sequence in 2025–2026, and where do practitioners disagree?

### Takeaway
The consensus is **"layout first, then region-level recognition, grounded in OCR or the text layer where possible."** Even the leading VLM parsers converged on this in late 2025: PaddleOCR-VL and MinerU2.5 both detect layout and reading order first, then run a small VLM on crops. Whole-page end-to-end VLMs (olmOCR 2, dots.ocr, DeepSeek-OCR, Chandra) win or tie on some benchmarks but carry hallucination and repetition-loop risk. Disagreement centres on four questions: (1) pipeline vs end-to-end; (2) whether to trust the PDF text layer; (3) whether CER/benchmark gains reflect semantic fidelity; (4) how much classical image preprocessing is still needed.

### Cited Findings

**The canonical stage order, as described by systems that publish it**

1. **Triage / text-layer check.** Marker checks each page for usable embedded text and sends garbled or scanned pages to OCR, with page-level or block-level re-OCR ([Marker README](https://github.com/datalab-to/marker)). Docling runs OCR only where layout finds scanned pages or bitmap regions ([arXiv:2501.17887](https://arxiv.org/html/2501.17887v1)). Unstructured's `auto` picks between `fast` (text layer) and model-based strategies ([Unstructured docs](https://docs.unstructured.io/open-source/concepts/partitioning-strategies)).
2. **Render pages to images.** olmOCR 2 renders at 1288 px on the longest side ([arXiv:2510.19817](https://arxiv.org/html/2510.19817v1)). PaddleOCR-VL uses a native dynamic-resolution encoder to avoid distorting images, and MinerU2.5 does layout on a downsampled page but recognition on native-resolution crops ([arXiv:2510.14528](https://arxiv.org/html/2510.14528v4); [arXiv:2509.22186](https://arxiv.org/abs/2509.22186)).
3. **Layout detection.** RT-DETR-family detectors are the de facto standard: Docling (RT-DETR on DocLayNet), PaddleOCR-VL (PP-DocLayoutV2 = RT-DETR), and Marker (rf-detr). Sources: [Docling](https://arxiv.org/html/2501.17887v1), [PaddleOCR-VL](https://arxiv.org/html/2510.14528v4), [Marker](https://github.com/datalab-to/marker).
4. **Reading order.** Docling uses post-processing rules ([Docling](https://arxiv.org/html/2501.17887v1)). PaddleOCR-VL uses a learned pointer network ([PaddleOCR-VL](https://arxiv.org/html/2510.14528v4)). End-to-end VLMs emit reading order implicitly.
5. **Region recognition.**
   - Text: OCR or the text layer.
   - Tables: TableFormer matched to text cells ([Docling](https://arxiv.org/html/2501.17887v1)), or heuristics with a VLM fallback ([Marker](https://github.com/datalab-to/marker)), or a VLM on the crop ([PaddleOCR-VL](https://arxiv.org/html/2510.14528v4)).
   - Formulas: VLM to LaTeX.
   - Figures: VLM/LLM captions or "verbalisation" ([Google](https://docs.cloud.google.com/document-ai/docs/layout-parse-chunk), [Azure](https://learn.microsoft.com/en-us/azure/search/cognitive-search-skill-document-intelligence-layout), [Databricks](https://www.databricks.com/blog/pdfs-production-announcing-state-art-document-intelligence-databricks)).
6. **Furniture removal.** Page headers and footers are detected as their own classes and kept out of the body text ([Docling "furniture"](https://arxiv.org/html/2501.17887v1); [Google PDF elements](https://docs.cloud.google.com/document-ai/docs/layout-parse-chunk)).
7. **Assembly to a structured document.** This builds the section hierarchy, page provenance, and bounding boxes, then exports Markdown/HTML/JSON ([DoclingDocument](https://arxiv.org/html/2501.17887v1); [Marker JSON](https://github.com/datalab-to/marker); [Azure locationMetadata](https://learn.microsoft.com/en-us/azure/search/cognitive-search-skill-document-intelligence-layout)).
8. **Layout-aware chunking.** Chunks follow heading or layout-element boundaries and carry ancestor headings ([Google](https://docs.cloud.google.com/document-ai/docs/layout-parse-chunk); [Azure markdownHeaderDepth](https://learn.microsoft.com/en-us/azure/search/cognitive-search-skill-document-intelligence-layout)).

**Arguments for two-stage / pipeline**
- PaddleOCR-VL's authors say end-to-end VLMs rely on long autoregressive sequences. These raise latency and memory, and the models "are more prone to unstable layout analysis and hallucinations," especially on multi-column and mixed text-graphic pages. A separate layout model needs lower resolution and fewer parameters and is easier to extend to new classes. (opened) — [arXiv:2510.14528](https://arxiv.org/html/2510.14528v4)
- Docling's authors argue that keeping text from the PDF or OCR, with models recovering only structure, avoids generative hallucination. (opened) — [arXiv:2501.17887](https://arxiv.org/html/2501.17887v1)
- Google says OCR grounding reduces hallucination in its Gemini parser. (opened, vendor) — [Google docs](https://docs.cloud.google.com/document-ai/docs/layout-parse-chunk)
- A Harvard LIL / Boston Public Library pipeline (Aug 2026) **segments scans into type-agnostic crops before OCR**. Each crop then goes through OCR, text analysis, type classification, reading order detection, NER, subject classification, language detection, and embeddings. The pipeline runs on workstation-level hardware. (opened, abstract) — [Institutional Newspapers Pipeline, arXiv:2608.18972](https://arxiv.org/abs/2608.18972)
  - A search summary said the authors chose crops because large regions sent to a VLM cause degenerate repetition loops on historical pages. (snippet-only; full PDF could not be read)

**Benchmark state (all OmniDocBench and olmOCR-Bench numbers are author-reported unless noted)**
- **OmniDocBench v1.5 overall:**

  | System | Score |
  |---|---|
  | PaddleOCR-VL | 92.86 |
  | MinerU2.5 | 90.67 |
  | dots.ocr | 88.41 |
  | Gemini-2.5 Pro | 88.03 |
  | GPT-4o | 75.02 |
  | Marker-1.8.2 | 71.30 |

  On OmniDocBench v1.0, Docling's overall edit distance was 0.749 vs PaddleOCR-VL's 0.115 (lower is better). — [PaddleOCR-VL paper](https://arxiv.org/html/2510.14528v4) (self-reported by a competitor of the listed systems)
- **olmOCR-Bench, in the olmOCR 2 paper:**

  | System | Score |
  |---|---|
  | Chandra 0.1.0 | 83.1 |
  | Infinity-Parser 7B | 82.5 |
  | olmOCR 2 | 82.4 |
  | PaddleOCR-VL | 80.0 |
  | dots.OCR | 79.1 |
  | Marker 1.10.1 | 76.1 |
  | DeepSeek-OCR | 75.7 |
  | MinerU 2.5.4 | 75.2 |
  | Mistral OCR API | 72.0 |
  | GPT-4o | 68.9 |
  | Gemini Flash 2 | 57.8 |

  Several of these are "author-reported." — [arXiv:2510.19817](https://arxiv.org/html/2510.19817v1)
- **olmOCR-Bench, in Marker's README (Nov 2026 version, self-reported):**

  | System | Overall | Digital-only | Throughput |
  |---|---|---|---|
  | Chandra 2 (hosted) | 85.8 | — | — |
  | Gemini Flash 3.5 API | 76.4 | — | — |
  | Marker balanced | 76.0 | 83.5 | 2.9 pg/s |
  | MinerU pipeline | 72.7 | — | 0.54 pg/s |
  | Marker fast | 66.6 | — | — |
  | Docling | 50.3 | — | 2.1 pg/s |

  — [Marker README](https://github.com/datalab-to/marker)
- Rankings flip depending on the benchmark and on who runs it. For example, PaddleOCR-VL tops OmniDocBench in its own paper but trails Chandra and olmOCR 2 on olmOCR-Bench. Docling scores far lower in competitors' tables. (Derived from the two tables above.)

**Arguments against trusting CER / benchmark wins (independent academic evidence)**
- On Uruguayan dictatorship-era microfilm, "VLMs consistently outperform traditional methods" on CER/WER. Qualitative analysis, however, shows spelling normalisation, generated content not present in the source, and fluent word substitutions that change meaning. Named-entity errors distort meaning while barely moving CER. The authors call for semantic-reliability metrics. (opened, abstract; arXiv Jul 2026, v3 Sep 2026) — [When Low CER is Not Enough, arXiv:2607.24077](https://arxiv.org/abs/2607.24077)
- An Arabic manuscript study reported VLM omission of 11.9% vs Tesseract's 47.7%, with more hallucinated text from VLMs: a coverage-precision trade-off. (snippet-only) — [When Do VLMs Help Arabic Manuscript OCR?, arXiv:2608.22366](https://arxiv.org/pdf/2608.22366)

### Inferences
- The 2026 "standard" is no longer "Tesseract + rules" nor "send the page to GPT." It is **a layout detector plus reading order, then specialised recognisers or a small VLM per region, with an LLM only for figure/table verbalisation and hard cases.** End-to-end page VLMs are a legitimate alternative, mainly for bulk conversion (e.g. LLM training data, which is olmOCR's origin), where occasional hallucination is tolerable.
- For legal or regulatory text (relevant to a KG over legal documents), the semantic-error findings argue for: preferring the text layer on born-digital pages; OCR-grounded or crop-level recognition on scans; and verification of named entities, numbers, and article references rather than relying on CER.
- Classical image preprocessing (deskew, denoise, binarisation) is barely mentioned by any modern system I opened. VLM parsers instead handle resolution choice (1288 px longest edge, native-resolution crops) and **rotation** (olmOCR 2 emits a rotation-correction field). Binarisation appears to be a legacy-OCR concern. This is an inference from absence; see Gaps.

### Gaps
- I found no 2025–2026 primary source that specifies deskew, denoise, or binarisation as a required stage before VLM parsers. PaddleOCR's PP-StructureV3 is commonly said to include document-orientation classification and unwarping (UVDoc) modules, but I did not open a page confirming this. The PaddleOCR-VL paper I read describes no such modules.
- Rendering DPI: only olmOCR's pixel-based setting was confirmed (1288 px longest edge). No vendor DPI recommendation (e.g. 300 DPI for OCR) was opened.
- Deduplication and file-type detection: no opened source covers these in a parsing reference architecture. They remain unsourced here.
- Stamps, signatures, and handwriting regions: no opened source describes dedicated layout classes for them. Reducto's "Agentic OCR" handwriting claim is snippet-only. Azure's handwriting style detection was not verified.

---

## Q3. Concrete engineering write-ups at scale, with numbers; confidence, retries, and fallbacks

### Takeaway
Hard production numbers in public are mostly throughput and cost figures from tool authors. The large-scale independent write-up I found is Harvard LIL/BPL's newspaper pipeline: 1.47M scans, 83.1M crops, 16.3B tokens. Fallback patterns are consistent across sources. Systems route per page or per block based on text-layer quality, fall back to a VLM on low-confidence tables, raise temperature to escape repetition loops, and send low-confidence OCR pages to a VLM.

### Cited Findings
- **Harvard LIL + Boston Public Library (Aug 2026):** 1,473,635 public-domain newspaper scans (1795–1930) were turned into **83.1M crops and 16.3B o200k tokens**. The modular pipeline runs crop segmentation, OCR, type classification, reading order, NER, language ID, and embeddings, on workstation-level hardware. The abstract gives no cost. (opened, abstract) — [arXiv:2608.18972](https://arxiv.org/abs/2608.18972)
- **Throughput:**
  - PaddleOCR-VL: 1.62 pages/s on one A100 with FastDeploy (1.35 with vLLM).
  - MinerU2.5: 1.06 pages/s.
  - dots.ocr: 0.35 pages/s.

  These are vendor measurements on OmniDocBench, batches of 512 PDFs. — [arXiv:2510.14528](https://arxiv.org/html/2510.14528v4)
- **Throughput, Marker:** 23.7 pages/s in fast mode without OCR on CPU, 7.4 pages/s in fast mode, and 2.9 pages/s in balanced mode, on one B200 host (vendor). — [Marker README](https://github.com/datalab-to/marker)
- **Throughput, Docling:** 0.48 s per page on average on an L4 (vendor). OCR is the dominant cost when triggered. — [arXiv:2501.17887](https://arxiv.org/html/2501.17887v1)
- **Cost, olmOCR:** under $200 per million pages (README); about $350 per million by an independent reviewer's estimate. (snippet-only) — [dev.to review](https://dev.to/andrew-ooo/olmocr-review-allenais-vlm-beats-mistral-marker-on-pdfs-4cci)
- **Retries / fallbacks in published systems:**
  - olmOCR 2 raises sampling temperature from 0.1 toward 0.8 when no EOS is produced (repetition loop) ([arXiv:2510.19817](https://arxiv.org/html/2510.19817v1)).
  - Marker falls back to the VLM on low-confidence tables and re-OCRs pages or blocks with bad text ([Marker](https://github.com/datalab-to/marker)).
  - Databricks relies on Lakeflow retries and checkpointing for incremental, at-scale runs ([Databricks blog](https://www.databricks.com/blog/pdfs-production-announcing-state-art-document-intelligence-databricks)).
  - Azure's Document Layout skill times out above 5 minutes of processing per document, and you are still billed ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/search/cognitive-search-skill-document-intelligence-layout)).
- **Practitioner hybrid routing:**
  - One write-up runs Tesseract first, sends low-confidence or near-empty pages to a VLM, and uses a character-count floor. It estimates the hybrid at about $2,500 vs $10,000 per month for pure VLM. (snippet-only, single author) — [dev.to: Vision models for OCR, when they beat Tesseract](https://dev.to/gabrielanhaia/vision-models-for-ocr-when-they-beat-tesseract-and-when-they-dont-54a6)
  - A 2026 arXiv microservice paper describes an OCR-first design chosen for cost, auditability, and page-level intermediate artifacts, and reports that OCR dominates end-to-end latency. (snippet-only) — [arXiv:2605.18818](https://arxiv.org/pdf/2605.18818)

### Inferences
- A defensible production design for scanned legal or administrative documents in 2026:
  1. Triage per page: text layer present and good → extract directly; otherwise → render.
  2. Layout + reading order (RT-DETR-class detector or two-stage VLM).
  3. Region-level recognition (OCR or small VLM).
  4. VLM/LLM fallback for low-confidence regions, tables, and figures.
  5. Loop and empty-output detection with retry (temperature or engine switch).
  6. Emit JSON with page and bbox provenance plus Markdown with a heading hierarchy for chunking.

  This combines patterns that individual sources document; no single source prescribes all of it.
- Confidence scores come from classical OCR engines and layout detectors. Generative VLMs give none natively, which is why sources rely on proxies: EOS/repetition detection, character-count floors, and cross-engine agreement.

### Gaps
- I found no public, opened write-up from a large enterprise, such as a bank or law firm, reporting pages per day, error rates, and costs for a VLM-based ingestion pipeline. The Databricks "millions of documents" claim has no attributable numbers.
- The cross-engine consensus approach (running multiple OCR engines and flagging disagreement) was snippet-only, from a vendor-oriented guide, and is unverified.
- I did not verify Textract/Azure per-word confidence semantics or how BDA exposes confidence.
