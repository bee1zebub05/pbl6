# OCR / document-parsing engines for scanned PDFs with no text layer (as of 9 Nov 2026)

Context: the team's current step is EasyOCR at 150 DPI, then Gemma vision on poor pages, on a CPU machine ([ocr_local.py](../../src/vanban/clean/ocr_local.py), [recitation.md](../../docs/recitation.md)). The corpus is Vietnamese legal documents.

Source labels:
- **[opened]** is the default: the page was opened and the number read from it.
- **[snippet only]** means the number came from a search result and the page could not be opened. Treat it as unverified.
- **[measured]** means this research session downloaded the file and checked it directly.

Page fetches went through a summariser, so table values were cross-checked where a conflict appeared.

## What are the leading options now?

### Takeaway
The field moved a lot in 2026. Small specialised models of about 1B parameters (OXR-1.0, TeleOCR, OvisOCR2, PaddleOCR-VL-1.6, LightOnOCR-3, Chandra 2, dots.mocr) now score above Gemini 3 Pro on OmniDocBench and olmOCR-Bench, though a maker-run Elo comparison still ranks Gemini 3 Pro first. On Vietnamese, the only public multi-engine benchmark found has Gemini 3 Pro, Chandra 2, kimi-K2.5, olmOCR 2 and MonkeyOCRv2 on top. PP-OCRv5 and PP-OCRv6 are not usable for Vietnamese as shipped: their dictionaries lack most tone-marked vowels.

### Cited Findings

**Releases, newest first**
- PaddleOCR news [opened](https://github.com/PaddlePaddle/PaddleOCR):
  - HPD-Parsing, 22 Jul 2026, claims a peak of 4,752 tokens/s.
  - PP-OCRv6 in PaddleOCR 3.7.0, 11 Jun 2026.
  - PaddleOCR-VL-1.6 in 3.6.0, 28 May 2026.
  - PaddleOCR-VL-1.5 in 3.4.0, 29 Jan 2026.
  - PaddleOCR-VL in 3.3.0, 16 Oct 2025.
- OXR-1.0 (SoMark), 2026. The card gives no date; press coverage is from Oct 2026 — [QbitAI](https://qbitai.com/2026/10/505635.html) [snippet only]. The README says 1.3B parameters, while Hugging Face metadata shows 2B — [model card](https://huggingface.co/somarkai/oxr-1.0).
- TeleOCR (StarDoc-AI, formerly NaviDC-OCR): weights released 17 Aug 2026, about 1.2B parameters, Apache-2.0. The card names only Chinese and English — [model card](https://huggingface.co/StarDoc-AI/TeleOCR).
- OvisOCR2, Jul 2026, 0.8B, Apache-2.0 — [Docsumo roundup, 30 Sep 2026](https://www.docsumo.com/blog/best-ocr-models).
- Mistral OCR 4.1, page dated 16 Jul 2026, GA, adds paragraph-level bounding boxes and block confidence — [Mistral model card](https://docs.mistral.ai/models/model-cards/ocr-4-1). Mistral OCR 4 launched 23 Jun 2026 — [Tech Insider](https://tech-insider.org/mistral-ocr-4-launch-2026/).
- MinerU 4.x with four tiers (flash, basic, standard, advanced), and MinerU2.5-Pro — [MinerU README](https://github.com/opendatalab/MinerU). Docsumo dates MinerU2.5-Pro to May 2026.
- Surya 2.5: one VLM of about 689M parameters for layout, OCR and tables — [Surya README](https://github.com/datalab-to/surya).
- Chandra 2, Mar 2026 — [Chandra README](https://github.com/datalab-to/chandra). dots.mocr (the rebranded dots.ocr-1.5), 19 Mar 2026 — [dots.ocr README](https://github.com/rednote-hilab/dots.ocr).
- GLM-OCR: 0.9B, arXiv 11 Mar 2026 — [arXiv](https://arxiv.org/abs/2603.10910). DeepSeek-OCR 2: Apache-2.0, arXiv ID suggests Jan 2026 — [GitHub](https://github.com/deepseek-ai/DeepSeek-OCR-2).
- LightOnOCR-3 (0.8B and 4B), Apache-2.0. The card gives no exact date for the 4B — [model card](https://huggingface.co/lightonai/LightOnOCR-3-4B).
- Others seen on leaderboards but not investigated: Infinity-Parser2-Pro, ProKope-4B-Eagle-Eye, Unlimited-OCR, Youtu-Parsing, MonkeyOCRv2, HunyuanOCR-1.5, Qianfan-OCR, Falcon-OCR, SenOCR-Vi — [Ai2 dataset page](https://huggingface.co/datasets/allenai/olmOCR-bench), [OmniDocBench](https://github.com/opendatalab/OmniDocBench), [MDPBench](https://huggingface.co/datasets/Delores-Lin/MDPBench/blob/main/README.md).

**Older or stagnant engines**
- EasyOCR's latest release is v1.7.2, 24 Sep 2024, with no Vietnamese-specific note — [releases](https://github.com/JaidedAI/EasyOCR/releases). No olmOCR-Bench, OmniDocBench or MDPBench entry for EasyOCR appeared in any table opened.
- Tesseract 5.5.4: a security release fixing 17 advisories, dated "28 Oct" with no year shown — [releases](https://github.com/tesseract-ocr/tesseract/releases). Docsumo lists 5.5.3 as Jul 2026, so 5.5.4 is presumably Oct 2026. No leaderboard entry was found.
- GOT-OCR2: papers date from 2024 (older), Apache-2.0, 0.7B — [model card](https://huggingface.co/stepfun-ai/GOT-OCR2_0). It scored 48.3 in Ai2's 2025 table — [Ai2](https://huggingface.co/datasets/allenai/olmOCR-bench).
- Granite-Docling-258M: 17 Sep 2025, Apache-2.0. Languages are English plus experimental Japanese, Arabic and Chinese; **Vietnamese is not listed**. Full-page OCR edit distance is 0.45 — [model card](https://huggingface.co/ibm-granite/granite-docling-258M).

**Vietnamese-specific**
- **PP-OCRv6 conflict.** The paper's language appendix lists Vietnamese as supported for all three tiers — [arXiv 2606.13108](https://arxiv.org/html/2606.13108).
- A dictionary check contradicts this in practice. Counting 67 lowercase Vietnamese non-ASCII letters across the shipped `inference.yml` files, with no combining marks in any file [measured]:

  | Model | Letters present | Examples missing |
  |---|---|---|
  | [PP-OCRv6_medium_rec](https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec/resolve/main/inference.yml) | 23/67 | ệ, ộ, ắ, ữ, ấ |
  | [PP-OCRv5_server_rec](https://huggingface.co/PaddlePaddle/PP-OCRv5_server_rec/resolve/main/inference.yml) | 19/67 | same |
  | [latin_PP-OCRv5_mobile_rec](https://huggingface.co/PaddlePaddle/latin_PP-OCRv5_mobile_rec/resolve/main/inference.yml) | 22/67 | same |

  A CTC-style recogniser cannot emit a character missing from its dictionary, so these models cannot write ệ or ộ. That is why Vietnamese text comes out without tone marks.
- A third-party repo reached the same result independently: "Nội dung" became "Ni Dung". CER was 15.90% on printed samples for base `en`, 15.55% for `latin_PP-OCRv5`, and 0.35% for an unlicensed `tieubaoca` finetune. This is a small sample in a closed draft PR dated 9 Nov 2026 — [PR #14](https://github.com/quynhonsemiconductor/ai-services/pull/14).
- SenOCR-Vi (VietAlpha, 31 Aug 2026) is a PaddleOCR-VL-1.6 finetune for Vietnamese, Apache-2.0, 0.959B. It reports 82.83 composite on 160 Vietnamese pages (self-reported, Vietnamese MDPBench composite) and text 1−edit distance of about 86.7%. Tables (TEDS 70.7) and formulas (CDM 72.5) are much weaker, and its three-language macro is slightly below the base model. The authors disclose a scorer defect that added 3 rows and re-aggregated without them — [VietAlpha](https://www.vietalpha.org/research/senocr-vi).
- VMMU (ACL Findings 2026) finds closed-source VLMs already do well on Vietnamese OCR — [ACL Anthology](https://aclanthology.org/2026.findings-aacl.44/) [snippet only]. No scores were read.

### Inferences
- The team's EasyOCR dates from 2024, so age alone makes it worth re-testing. There is no public number that says how far behind it is on Vietnamese.
- Moving to PP-OCRv5 or v6 "because it is newer" would be a regression for Vietnamese unless a licensed finetuned recogniser is found.
- A high OmniDocBench rank tells little about Vietnamese, because OmniDocBench is not language-specific to it. PaddleOCR-VL-1.6 is 4th there but scored 79.3 in MDPBench's Vietnamese column, below Chandra 2's 85.6.

### Gaps
- No page confirms TeleOCR, OXR, OvisOCR2 or LightOnOCR-3 on Vietnamese. The LightOn and OXR cards give no language list; the TeleOCR card names only Chinese and English.
- Qwen licence terms by variant were not checked beyond Docsumo's note that Qwen3-VL-235B is Apache-2.0.
- No licensed Vietnamese finetune for PP-OCR was verified. VietOCR's accuracy against modern VLMs was not found; [AsterNet's card](https://huggingface.co/asterxlabs/asternet-vietnamese-ocr) compares against it but its numbers were not read.

## What do independent benchmarks show?

### Takeaway
Almost nothing here is truly independent. Most numbers are self-reported or run by parties with a stake. The closest to useful for this team is MDPBench, the only benchmark found with a Vietnamese column. On it, Gemini 3 Pro (85.9), kimi-K2.5 (86.2) and Chandra 2 (85.6) lead Vietnamese, in a tight band with olmOCR 2 (84.0) and MonkeyOCRv2-B (83.2). None of these benchmarks tests scanned Vietnamese legal documents specifically. The team needs its own small test.

### Cited Findings

**Who runs what, and the conflicts of interest**

| Benchmark | Run by | Conflict or weakness |
|---|---|---|
| olmOCR-Bench | Ai2. 1,403 PDFs, 7,010 pass/fail tests, English — [dataset](https://huggingface.co/datasets/allenai/olmOCR-bench) | Ai2 also ships olmOCR. Leaderboard entries are largely maker-reported. LlamaIndex (a competitor) criticises limited diversity and coarse binary tests — [post, Dec 2025](https://www.plushcap.com/content/llamaindex/blog/llamaindex-olmocr-bench-review-insights-and-pitfalls-on-an-ocr-benchmark) |
| OmniDocBench | OpenDataLab. v1.6 from 10 Apr 2026; latest results 11 Sep 2026 — [README](https://github.com/opendatalab/OmniDocBench) | Same GitHub org as MinerU. Overall = mean of text, table and formula scores, so text-only users should read Text Edit instead |
| MDPBench | Huazhong University of Science and Technology and Kingsoft Office. 3,400 images, 17 languages — [arXiv, 30 Mar 2026](https://arxiv.org/abs/2603.28130) | Digital and photographed pages, not specifically scans |
| ParseBench | LlamaIndex. About 2,000 enterprise pages, 167k rules — [arXiv, Apr 2026](https://arxiv.org/abs/2604.08538) | Vendor's own LlamaParse Agentic wins at 84.9% |
| IDP Leaderboard | Hosted at [Nanonets' domain](https://benchmarking.nanonets.com/benchmarks/olmocr) | Nanonets OCR-3 is #1. The page does not say who ran the scores or with what settings |
| DP-Bench | Upstage. 200 documents — [dataset](https://huggingface.co/datasets/upstage/dp-bench) [snippet only] | Only Upstage's own undated TEDS 93.48 was found — [Upstage](https://upstage.ai/products/document-parse) [snippet only]. No 2026 third-party results found |

**Benchmark that includes Vietnamese: MDPBench**
Figures below are from the [dataset README](https://huggingface.co/datasets/Delores-Lin/MDPBench/blob/main/README.md).

| Model | Overall | VI |
|---|---|---|
| kimi-K2.5 | 77.5 | 86.2 |
| Gemini-3-pro-preview | 86.4 | 85.9 |
| chandra-ocr-2 | 79.7 | 85.6 |
| olmOCR2 | 70.4 | 84.0 |
| MonkeyOCRv2-B-Parsing | 83.3 | 83.2 |
| Claude-Sonnet-4.6 | 73.1 | 83.1 |
| HunyuanOCR-1.5 | 76.8 | 82.4 |
| ChatGPT-5.2 | 68.6 | 82.1 |
| dots.mocr | 80.5 | 79.9 |
| PaddleOCR-VL-1.6 | 75.0 | 79.3 |
| PaddleOCR-VL-1.5 | 78.3 | 78.9 |
| LightOnOCR-2-1B | 63.9 | 74.9 |
| MinerU-2.5-Pro | 71.0 | 74.2 |
| Qwen3.5-9B / Qwen3-VL-8B | 65.7 / 68.3 | 74.0 / 73.4 |
| GLM-OCR | 67.3 | 69.2 |
| DeepSeek-OCR | 51.8 | 54.1 |
| PP-StructureV3 (pipeline) | 45.4 | 52.7 |
| MinerU-2.5-VLM | 46.3 | 46.0 |
| MinerU-2.5-pipeline | 33.5 | 27.6 |

Reliability notes on this table:
- The VI column position was checked against the raw rows of [arXiv Table 2](https://arxiv.org/html/2603.28130v1), reading header order `...NL PT VI`. A first automated reading wrongly gave Gemini 91.4, which is actually PT.
- Oddly, VL-1.6 scores below VL-1.5 overall here (75.0 vs 78.3), although it leads VL-1.5 on OmniDocBench.
- VietAlpha quotes the VL-1.6 Vietnamese score as 80.90 and README shows 79.3, an unresolved conflict. Its other quoted values match ([VietAlpha](https://www.vietalpha.org/research/senocr-vi)).
- Photographed pages drop an average of 17.8% — [arXiv](https://arxiv.org/html/2603.28130v1).

**Other Vietnamese numbers (self-reported, different test)**
- Datalab's own multilingual benchmark gives Gemini 2.5 Flash 89.5, Datalab API 85.0, GPT-5 Mini 83.6, Chandra 1 81.6, Chandra 2 80.4 on Vietnamese. That is, Datalab's own test puts Gemini ahead of its model on Vietnamese — [Chandra README](https://github.com/datalab-to/chandra).
- Surya 2.5 scores 63.6% on Vietnamese (self-reported) — [Surya README](https://github.com/datalab-to/surya).

**olmOCR-Bench (English)**

| System | Overall | Old Scans | Source and who ran it |
|---|---|---|---|
| OXR-1.0 | 87.84 | 59.32 | Self-reported. [Community rerun](https://huggingface.co/npario/OXR-1.0-mlx-8bit): 87.6 ± 1.0, Old Scans 58.9, official evaluator 0.4.27, bf16 weights, MLX backend — the only independent reproduction found |
| Infinity-Parser2-Pro | 87.6 | n/a | Leaderboard entry — [Ai2 dataset](https://huggingface.co/datasets/allenai/olmOCR-bench) |
| Nanonets OCR-3 | 87.4 | 49.6 | Vendor's own board — [IDP](https://benchmarking.nanonets.com/benchmarks/olmocr) |
| LightOnOCR-3-4B | 86.3 | n/a | Maker — [card](https://huggingface.co/lightonai/LightOnOCR-3-4B) |
| Chandra 2 | 85.8 ± 0.8 | 51.1 | Maker — [README](https://github.com/datalab-to/chandra) |
| Mistral OCR 4 | 85.20 | n/a | Maker claim, via [Tech Insider](https://tech-insider.org/mistral-ocr-4-launch-2026/) |
| dots.mocr | 83.9 ± 0.9 | 48.2 | Maker. Header and footer cells deleted before scoring, per [CodeSOTA](https://www.codesota.com/ocr/benchmark/olmocr-bench) |
| Surya 2.5 | 83.7 | n/a | Maker — [README](https://github.com/datalab-to/surya) |
| olmOCR 2 v0.4.0 | 82.4 ± 1.1 | 47.7 | Ai2 — [README](https://github.com/allenai/olmocr) |
| GPT-5.4 | 81.0 | 43.9 | [IDP](https://benchmarking.nanonets.com/benchmarks/olmocr), H&F only 20.1 |
| PaddleOCR-VL | 80.0 ± 1.0 | 37.8 | Asterisked in [Ai2 README](https://github.com/allenai/olmocr); the page does not define the asterisk |
| Qwen3-VL-Plus | 77.9 | 51.0 | [IDP](https://benchmarking.nanonets.com/benchmarks/olmocr) |
| Gemini-3-Pro | 77.7 | 43.7 | [IDP](https://benchmarking.nanonets.com/benchmarks/olmocr), H&F 26.7 |
| Gemini Flash 3.5 (API) | 76.4 | n/a | Run by Datalab — [Marker README](https://github.com/datalab-to/marker) |
| DeepSeek-OCR | 75.7 ± 1.0 | 33.3 | [Ai2 README](https://github.com/allenai/olmocr) |
| Claude Sonnet 4.6 | 73.9 | 19.8 | [IDP](https://benchmarking.nanonets.com/benchmarks/olmocr) |
| Gemma-4-E4B | 47.0 | 28.3 | [IDP](https://benchmarking.nanonets.com/benchmarks/olmocr) |
| Gemma-4-E2B | 38.2 | 23.4 | [IDP](https://benchmarking.nanonets.com/benchmarks/olmocr) |
| Docling | 50.3 | n/a | Run by competitor Datalab — [Marker README](https://github.com/datalab-to/marker) |
| Tesseract, EasyOCR, Azure, Google Doc AI, Textract | not found | | No olmOCR-Bench entry in any table opened |

**Conflicts between sources**
- Marker: 76.0 balanced mode (run by Datalab, [Marker README](https://github.com/datalab-to/marker)) vs 83.2 "Datalab Marker" ([IDP](https://benchmarking.nanonets.com/benchmarks/olmocr)). The IDP page does not state the version or mode.
- GLM-OCR: 75.2 excluding H&F ([CodeSOTA](https://www.codesota.com/ocr/benchmark/olmocr-bench)) vs 68.4 ([IDP](https://benchmarking.nanonets.com/benchmarks/olmocr)).
- Comparability warning: LightOnOCR-2, GLM-OCR and FireRed exclude the H&F category, and dots.mocr deletes header/footer cells — [CodeSOTA](https://www.codesota.com/ocr/benchmark/olmocr-bench).
- Qianfan-OCR's 73.1 on Old Scans is an outlier, well above the rest, and its H&F score is 42 — [CodeSOTA](https://www.codesota.com/ocr/benchmark/olmocr-bench). It was not verified at source.
- Old provenance: OmniDocBench and IDP values for the same model differ across versions. The Ai2 2025 table (Mistral 72.0) is **older** and predates current versions.

**OmniDocBench v1.6_full** ([README](https://github.com/opendatalab/OmniDocBench), latest additions 11 Sep 2026):

| Model | Overall | Text Edit (lower better) | Table TEDS | Read Order Edit (lower better) |
|---|---|---|---|---|
| OXR-1.0 | 97.03 | 0.0244 | 96.61 | 0.1216 |
| TeleOCR | 96.91 | 0.0267 | 96.82 | 0.1184 |
| OvisOCR2 | 96.47 | 0.0265 | 94.58 | 0.1120 |
| PaddleOCR-VL-1.6 | 96.34 | 0.0326 | 94.76 | 0.1278 |
| MinerU2.5-Pro | 95.75 | 0.036 | 93.42 | 0.120 |
| GLM-OCR | 95.22 | 0.044 | 92.83 | 0.133 |
| Gemini 3 Pro | 92.91 | 0.064 | 89.15 | 0.165 |
| MinerU-Pipeline | 86.47 | | | |
| Marker | 78.44 | | | |

- Self-reports differ slightly from the board: TeleOCR 96.87 on [its card](https://huggingface.co/StarDoc-AI/TeleOCR), OXR 97.18 in [secondary coverage](https://letsdatascience.com/news/somark-open-sources-13b-oxr-10-document-parser-with-benchmar-903f39c6) [snippet only].
- Docsumo lists GPT-5.2 at 86.59 and Qwen3-VL-235B at 89.78 — [Docsumo](https://www.docsumo.com/blog/best-ocr-models).
- Mistral OCR 4 claims 93.07 — [Tech Insider](https://tech-insider.org/mistral-ocr-4-launch-2026/).
- The README does not say who produced each row, and its 30 Apr 2026 note mentions "v1.6 to v1.7", contradicting the table heading.

**Degraded inputs (closest to scans)**
- TeleOCR reports real-degraded 70.85 vs clean 86.90 on PureDocBench, and scanning 92.33 on Real5-OmniDocBench (self-reported) — [card](https://huggingface.co/StarDoc-AI/TeleOCR).
- Docsumo reports PaddleOCR-VL at 91.93 clean vs 72.19 photos on Wild-OmniDocBench — [Docsumo](https://www.docsumo.com/blog/best-ocr-models).
- Note the olmOCR-Bench Old Scans column above: the best verified score is about 59, and most fall under 52.

**ParseBench (LlamaIndex)**
- 14 methods. "No method is consistently strong across all five dimensions" — [arXiv](https://arxiv.org/abs/2604.08538).
- Content faithfulness tops out at about 90% for unnamed best methods; semantic formatting ranges from Docling 1.0% to LlamaParse Agentic 85.2% — [LlamaIndex](https://www.llamaindex.ai/blog/parsebench).
- Model-card means: LightOnOCR-3-4B 75.1 — [card](https://huggingface.co/lightonai/LightOnOCR-3-4B); TeleOCR 58.67 — [card](https://huggingface.co/StarDoc-AI/TeleOCR).
- Per-method tables in the PDF could not be extracted.

**Elo comparison (maker-run, judged by Gemini 3 Flash)**
Averages across olmOCR-Bench, OmniDocBench v1.5 and XDocParse: Gemini 3 Pro 1210.7, dots.mocr 1124.7, dots.ocr 1086.2, HunyuanOCR 984.2, PaddleOCR-VL-1.5 920.5, GLM-OCR 892.5, MonkeyOCR-pro-3B 781.1. This conflicts with the OmniDocBench edit-distance ranking, where Gemini 3 Pro sits below the specialised models. The judge is itself a Gemini model — [dots.ocr README](https://github.com/rednote-hilab/dots.ocr).

**In-house vendor claim, worth treating sceptically**
PP-OCRv6's paper reports its medium model beating VLMs on recognition (83.2 vs Qwen3-VL-235B 74.9, Gemini-3.1-Pro 71.4, GPT-5.5 64.2). All come from in-house benchmarks, and prompts and versions are unnamed — [arXiv](https://arxiv.org/html/2606.13108).

### Inferences
- General VLMs' low H&F scores on the IDP board (20–37) mostly reflect not removing headers and footers, a test convention. For legal documents, keeping such text may even be desired, so the macro score understates them. Read per-category columns instead.
- For a Vietnamese scanned corpus, the Vietnamese evidence points to a shortlist of Gemini (cloud), Chandra 2 and olmOCR 2 (GPU), and perhaps kimi-K2.5 and MonkeyOCRv2. It does not point to the OmniDocBench leaders, whose Vietnamese performance is mostly unmeasured.
- Differences of 1–3 points between leaders are within noise (± about 1 on olmOCR-Bench), and the same model varies more than that across boards.

### Gaps
- No benchmark found tests Tesseract or EasyOCR alongside modern VLMs on Vietnamese.
- No independent numbers for Vietnamese on Google Document AI, Azure, Mistral OCR 4/4.1 or Gemma 4 26B/31B (the variants the team actually uses, per [recitation.md](../../docs/recitation.md)). The IDP board has only E2B and E4B, which should not be extrapolated to 26B.
- MDPBench is not split by document type, so "scan" results cannot be isolated.
- [LLM Reference](https://www.llmreference.com/benchmark/omnidocbench) and the live OmniDocBench and MDPBench leaderboards were not opened. Newer rows may exist.
- Who produced OmniDocBench rows, and how the IDP board ran its models, could not be established.

## Licence, cost, hardware, speed, output, tables and reading order

### Takeaway
On a CPU-only machine, only the lightweight engines and a few llama.cpp or ONNX paths run at all, with little published x86 timing. The realistic options are:
- cloud API at about $1.50–5 per 1,000 pages;
- a Google Document AI free allowance of 1,000 pages;
- a batch GPU job on a free notebook (T4 16 GB is not a fit for vLLM paths, per PaddleOCR's own docs).

AWS Textract is out because it does not support Vietnamese.

### Cited Findings

**Open-weight engines**

| Engine | Licence | Hardware | Speed (published) | Output | Tables / reading order |
|---|---|---|---|---|---|
| [PaddleOCR-VL-1.6](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL.html) (0.9B) | Apache-2.0 | x64 CPU supported through PaddlePaddle, Transformers and llama.cpp. NVIDIA CC ≥ 7.0 for Paddle/Transformers, ≥ 8.0 for vLLM. vLLM on T4/V100 is "prone to timeouts or OOM". No VRAM figure | A100: 1.1–1.6 pages/s, [arXiv v3, Nov 2025](https://arxiv.org/html/2510.14528v3), first version. No CPU figure in docs | JSON, Markdown, DOCX, HTML/XLSX tables | Cross-page table merge, reading order; RO edit 0.1278 |
| [SenOCR-Vi](https://www.vietalpha.org/research/senocr-vi) | Apache-2.0 | No inference figures | none | as VL | TEDS 70.7 |
| [Chandra 2](https://github.com/datalab-to/chandra) (5B) | Code Apache-2.0. Weights modified OpenRAIL-M: free for research, personal use and startups under $2M | H100 only listed; no VRAM figure | H100 80GB: 1.44 pages/s, 60 s avg latency, 0% failures | Markdown, HTML, JSON with layout | Strong on tables (92.1 olmOCR) |
| [olmOCR 2](https://github.com/allenai/olmocr) (7B) | Apache-2.0. Docsumo notes Ai2 card says research/educational use, unverified | NVIDIA ≥ 12 GB, 30 GB disk, or remote `--server` | Claims < $200 per million pages, no methodology | Markdown, Dolma; strips H&F | Tables 84.9 |
| [dots.mocr](https://github.com/rednote-hilab/dots.ocr) (3B) | MIT in sidebar, plus a separate licence agreement file not reviewed | GPU examples; CPU only via a linked issue | dots.ocr 0.35 pages/s on A100, [PaddleOCR-VL paper](https://arxiv.org/html/2510.14528v3) (older) | JSON with bboxes, Markdown, `_nohf.md` | RO edit 0.029 on OmniDocBench, maker-reported |
| [OXR-1.0](https://huggingface.co/somarkai/oxr-1.0) (1.3B/2B) | Custom on Apache-2.0: free below $2M funding and $2M revenue, attribution for services, no competing APIs — [mirror summary](https://huggingface.co/npario/OXR-1.0-mlx-8bit) | **Min 24 GB VRAM single GPU, 48 GB recommended, Linux** | No figures | Markdown, JSON with bboxes, 13 element types | Tables 93.05 |
| [TeleOCR](https://huggingface.co/StarDoc-AI/TeleOCR) (1.2B) | Apache-2.0 | vLLM/SGLang; GGUF for llama.cpp, Ollama, LM Studio; no VRAM figure | No figures | Not specified on card | TEDS 96.82 |
| [LightOnOCR-3](https://huggingface.co/lightonai/LightOnOCR-3-4B) (0.8B/4B) | Apache-2.0 | GPU examples; no VRAM figure | 1,158 output tokens per page on average; no pages/s | Markdown; grounding mode with bboxes (0–1000) | Labels table, formula, etc. |
| [MinerU 4.x](https://github.com/opendatalab/MinerU) | Custom on Apache-2.0. Commercial licence above 100M MAU or $20M monthly revenue; services must disclose use — [Docsumo](https://www.docsumo.com/blog/best-ocr-models) | **CPU works:** basic ONNX 2 GB RAM; standard/advanced ONNX + llama.cpp 8 GB RAM. Full GPU: 8 GB+ VRAM, 16 GB RAM | No pages/s; flash fastest, advanced slowest | 9 targets incl. Markdown, HTML, DOCX, Content List | See OmniDocBench scores above |
| [Surya 2.5](https://github.com/datalab-to/surya) (689M) | Code Apache-2.0. Weights modified OpenRAIL-M, free under $5M | **CPU via llama.cpp**; peak RSS about 4.8 GB | M4 Max Metal 96 DPI: 0.19 pages/s. H100 192 DPI: 4.5 pages/s | HTML tables without row/column geometry | Layout included |
| [Marker](https://github.com/datalab-to/marker) | Same terms as Surya | "GPU, CPU, or MPS" | 23.7 pages/s fast no-OCR only (not relevant to scans) | Markdown, HTML, JSON polygons, chunks | Tables; `--use_llm` fallback supports Ollama |
| [Docling](https://github.com/docling-project/docling) | MIT; model licences separate | Local on x86/arm; no CPU timing | none | Markdown, HTML, DocTags, JSON | Reading order and table structure |
| [DeepSeek-OCR 2](https://github.com/deepseek-ai/DeepSeek-OCR-2) (3B per Docsumo) | Apache-2.0 | CUDA 11.8+ env; no VRAM figure | No figures | Markdown | |
| [GLM-OCR](https://arxiv.org/abs/2603.10910) (0.9B) | MIT per [Docsumo](https://www.docsumo.com/blog/best-ocr-models) | vLLM, SGLang, Ollama, MLX | 1.86 pages/s, hardware unnamed, per Docsumo | | TEDS 92.83 |
| [PP-OCRv6](https://arxiv.org/html/2606.13108) | Apache-2.0 | CPU fine | Xeon 8350C OpenVINO: tiny 0.20 s/image, medium 1.40 s/image, end to end | Text and boxes | **Cannot output most Vietnamese tones** (see first section) |
| EasyOCR | License not re-checked | Current baseline | Team measured locally | Text and boxes | None |
| Tesseract 5.5.4 | Apache-2.0 per [Docsumo](https://www.docsumo.com/blog/best-ocr-models) | CPU | no 2026 timing found | Text, hOCR, PAGE XML | Limited |

Windows note: vLLM, SGLang and FastDeploy do not run natively on Windows; PaddleOCR recommends Docker — [PaddleOCR docs](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL.html). The team's machine is Windows 10.

**CPU timing evidence is thin**
- PaddleOCR-VL at 32.65 s/page on CPU, one synthetic page — [ThakiCloud](https://thakicloud.github.io/en/research/paddleocr-vl-09b-multilingual-document-parsing/) [snippet only, page returned 404].
- Surya 2 on Intel N100 4-core: about 137.84 s, unit unclear — [wikidocs](https://wikidocs.net/441138) [snippet only, 403].
- PP-OCRv6 small/tiny at about 5 s/image on 4-core CPU, Korean documents — [wikidocs](https://wikidocs.net/441124) [snippet only, fetch failed].
- Treat these as orders of magnitude only. No x86 CPU seconds-per-page figure was opened for any VLM.

**Cloud engines**

| Service | Price per 1,000 pages | Free | Vietnamese | Output |
|---|---|---|---|---|
| [Google Document AI](https://cloud.google.com/document-ai/pricing) Enterprise OCR | $1.50 up to 5M, then $0.60 [measured from page HTML] | First 1,000 count free, as displayed in the pricing table | [Yes, including handwriting](https://docs.cloud.google.com/document-ai/docs/languages) | Layout, quality score |
| Google Layout Parser / Form Parser | $10 / $30 | | | Structure |
| [Azure Read / Layout](https://azure.microsoft.com/en-us/pricing/details/ai-document-intelligence/) | $1.50 / $10, per [third party, 4 Nov 2026](https://www.activepieces.com/blog/azure-document-intelligence-pricing-per-model-in-2026); official page rendered prices as "$-" | F0: 500 pages per month | [Printed yes, handwritten no](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/language-support/ocr) | Words, boxes, tables |
| [AWS Textract](https://aws.amazon.com/textract/pricing/) | $1.50 detect, $15 tables, $50 forms | 1,000 pages per month for 3 months | **No.** [Only English, Spanish, German, Italian, French, Portuguese](https://docs.aws.amazon.com/textract/latest/dg/textract-best-practices.html) | Confidence scores |
| [Mistral OCR 4.1](https://docs.mistral.ai/models/model-cards/ocr-4-1) | $4; $5 annotated. Batch $2 per [secondary](https://tech-insider.org/mistral-ocr-4-launch-2026/). Older OCR 3 was $2 — [tracker](https://www.usagepricing.com/blueprint/activity/mistral-ai-2026-07-06-api-rate-increase) [snippet only] | | Not stated | Markdown/JSON, boxes, confidence; self-host container |

**Vision LLM token prices** (per 1M tokens)
- [Gemini](https://aistudio.google.com/docs/pricing): 3.1 Flash-Lite $0.25/$1.50; 3.5 Flash-Lite $0.30/$2.50; 3.8 Flash $0.75/$3.75, **doubling on 1 Jan 2027**; 3.1 Pro $2/$12, no free tier. Batch is 50% off.
- Gemma 4: free tier only, paid not available. Free-tier data is used to improve products ([same page](https://aistudio.google.com/docs/pricing)).
- [Claude](https://claude.com/pricing): Haiku 5.5 $0.10/$0.50, Sonnet 5.5 $2/$10, Opus 5.5 $4/$20. Batch is 50% off.
- [OpenAI](https://developers.openai.com/api/docs/pricing): gpt-5.4 $2.50/$15, gpt-5.4-mini $0.75/$4.50, gpt-5-mini $0.25/$2, gpt-5.4-nano $0.20/$1.25. Batch is 50% off.
- Gemini counts each PDF page as 258 tokens, and scales pages between 768 and 3072 px; Google says higher resolution does not improve results — [docs](https://aistudio.google.com/docs/document-processing). Free-tier RPM and RPD are not published on the rate-limit page; they appear per project in AI Studio — [docs](https://aistudio.google.com/docs/rate-limits).

**Free GPU**
- Kaggle's weekly GPU quota is commonly reported at about 30 hours on T4 or P100, but Kaggle's docs give no number. Colab limits are unpublished, with sessions up to 12 hours and T4 when available. These come from search snippets — [gpuperhour](https://gpuperhour.com/blog/free-cloud-gpus-and-credits) [snippet only; fetch failed] and [AgentDeals](https://agentdeals.dev/vendor/kaggle) [snippet only].
- Granite-Docling warns that T4-class GPUs without bfloat16 can produce garbled output — [card](https://huggingface.co/ibm-granite/granite-docling-258M). This may affect other BF16 models on T4 too (inference).

### Inferences
- **LLM cost per 1,000 pages (my estimate).** Assumes 258 input tokens and 1,200 output tokens per page, borrowing LightOn's 1,158 average; a dense Vietnamese page may differ, and thinking tokens would add to it.

  | Model | Standard | Batch |
  |---|---|---|
  | Gemini 3.1 Flash-Lite | about $1.9 | about $0.9 |
  | Gemini 3.5 Flash-Lite | about $3.1 | about $1.5 |
  | Gemini 3.8 Flash | about $4.7 (about $9.4 from 2027) | half of standard |
  | Gemini 3.1 Pro | about $15 | half of standard |
  | Output only, excluding image input: Haiku 5.5 / gpt-5.4-mini / Sonnet 5.5 | $0.6 / $5.4 / $12 | half of standard |

- At these rates a corpus of tens of thousands of pages costs tens of dollars, so cost matters less than Vietnamese accuracy and blocked pages.
- On T4, Paddle or Transformers backends are more plausible than vLLM. OXR's 24 GB floor rules it out.
- Google Document AI Enterprise OCR is the cheapest way to get a verified-Vietnamese commercial engine. It is not a generative model, so a RECITATION-type block seems unlikely, but this was not confirmed by a source. Its Vietnamese accuracy is unmeasured.
- Licences are not blocking for a student project, including Chandra and OXR (research/personal or under $2M). Check them again if the project is commercialised.
- CPU-only VLM throughput is probably tens of seconds to minutes per page at best. A corpus-wide run would be slow, but rescuing only poor pages may be feasible. This needs measuring, with no reliable number available.

### Gaps
- No verified VRAM numbers for PaddleOCR-VL-1.6, Chandra 2, TeleOCR, LightOnOCR-3 or dots.mocr. [wikidocs 441137](https://wikidocs.net/441137) on RTX 3060 12 GB likely has one but returned 403.
- No primary x86 CPU page timing for any VLM, TeleOCR GGUF, or MinerU's llama.cpp tier.
- EasyOCR and Tesseract's current `vie` accuracy have no 2025–2026 public figures found. Tesseract output-format details are based on release notes mentioning PAGE XML; hOCR is unverified general knowledge.
- Azure's official price could not be read; values are third-party. Mistral OCR Vietnamese support is not stated.
- Whether Gemma 4 26B via API can be relied on long-term, and its exact free-tier limits, could not be determined from public pages.
- A cloud-OCR 150 vs 300 DPI effect was not found. The team's own test shows EasyOCR's score barely changes over 120–300 DPI ([ocr_local.py](../../src/vanban/clean/ocr_local.py)), and that finding should not be assumed to transfer to other engines.

## Known failure modes of vision LLMs and how they are detected

### Takeaway
Failures fall into four groups: runaway repetition, hallucination, omission, and provider-side blocks. Blocks and runaways are easy to detect from `finish_reason` and token counts. Hallucination and omission are silent and need a second signal such as comparison with another engine, or a Vietnamese diacritic check. No rigorous 2025–2026 study was found on dropped repeated text specifically.

### Cited Findings

**Repetition loops**
- The mechanism: the model conditions on its own output and self-reinforces, rarely stopping before the token cap. Mitigations listed are hard token and time caps, stream termination, and fallback. LlamaIndex rejects presence/frequency penalties because faithful transcription can legitimately repeat. Vendor blog, 8 Apr 2026 — [LlamaIndex](https://llamaindex.ai/blog/engineering-insights-failure-modes-that-break-vlm-powered-ocr-in-production).
- Signals: OpenAI `finish_reason: "length"`, Gemini `MAX_TOKENS`, Anthropic output limit reached — [same](https://llamaindex.ai/blog/engineering-insights-failure-modes-that-break-vlm-powered-ocr-in-production).
- PaddleOCR-VL looped forever on some forms and a lab table — [HF discussion #73, from 13 Nov 2025](https://huggingface.co/PaddlePaddle/PaddleOCR-VL/discussions/73):
  - A maintainer suggested `repetition_penalty ≥ 1.05`.
  - One user found `frequency_penalty ≥ 0.1` stopped loops but lowered quality.
  - Another still saw repetition at 1.1 on 3 Mar.
- OCR VLMs often loop on sparse tables and forms; Tensorlake describes a streaming detector — [Tensorlake](https://tensorlake.ai/blog/vlm-pipeline-improvement) [snippet only, page 404].

**Hallucination**
- MDPBench: "even Gemini-3-Pro can still produce errors such as missing content, incorrect reading order, and hallucinated outputs", and models "often hallucinate spaces within continuous text" — [arXiv](https://arxiv.org/html/2603.28130v1).
- PaddleOCR warns that running the VLM alone without layout analysis can produce poor results, including excessive hallucinated text — [docs](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL.html).
- olmOCR v0.3.0 (Aug 2025) fixed hallucinations on blank documents, showing this is a recognised category — [README](https://github.com/allenai/olmocr).
- Granite-Docling's card warns that smaller models may be more prone — [card](https://huggingface.co/ibm-granite/granite-docling-258M).
- PP-OCRv6's in-house hallucination set gives Kimi-K2.6 85.00, Qwen3-VL-235B 80.56, GPT-5.5 78.00, MiniMax-M3 72.60, PP-OCRv6_medium 93.20. These are vendor-run — [arXiv](https://arxiv.org/html/2606.13108).
- A closely related arXiv paper on hallucination reduction noted more lexical repetition as a side effect, in captioning rather than OCR — [arXiv 2604.20366](https://arxiv.org/html/2604.20366v1) [snippet only].

**Omission and dropped repeated text**
- ParseBench has a dedicated content-faithfulness dimension of 141,322 rules across 506 pages, covering omissions, hallucinations and reading-order violations — [HF dataset](https://huggingface.co/datasets/llamaindex/ParseBench) [snippet only]. Best methods reach about 90% — [LlamaIndex](https://www.llamaindex.ai/blog/parsebench).
- No study specifically on dropped repeated lines was found. Mechanistic link: the penalties used to stop loops penalise repeated tokens ([PaddleOCR-VL thread](https://huggingface.co/PaddlePaddle/PaddleOCR-VL/discussions/73)), and LlamaIndex rejects them for that reason. Whether they remove real repeated cells is **an inference**, not a measured result.

**Provider blocks: RECITATION**
- Google's reference defines `RECITATION` as content "flagged for recitation reasons", and `citationMetadata` can carry recitation information. Sibling reasons include `SAFETY`, `BLOCKLIST`, `PROHIBITED_CONTENT`, `SPII`, `MAX_TOKENS` — [Gemini API reference](https://aistudio.google.com/api-reference/generate-content).
- A public report on `gemini-3-flash-preview` in batch mode, OCRing centuries-old public-domain books: false positives rose from 1/2000 to 1/50. Stating public-domain status in the prompt did not help, reruns still failed about 90% of the time, and raising temperature was ruled out for fidelity. No staff response; auto-closed — [Google forum, 28 Apr 2026](https://discuss.ai.google.dev/t/new-recitation-false-positives-in-public-domain-works/142749).
- LlamaIndex says public laws and standards are typical triggers, suggests higher temperature retries, and says blocked calls are still billed (unverified). OpenAI signals with `content_filter` — [LlamaIndex](https://llamaindex.ai/blog/engineering-insights-failure-modes-that-break-vlm-powered-ocr-in-production).
- The team's own measurements are the most directly applicable evidence, and match the above — [docs/recitation.md](../../docs/recitation.md):
  - Blocks are deterministic and retries are useless.
  - On one file, Gemini Flash-Lite still blocked all 5 pages one by one, while `gemma-4-26b-a4b-it` passed 5/5.
  - 11 stubborn pages, mostly scoring tables and appendix forms, needed cutting into 2×2 crops, which passed 10/10 but splits table rows.

**Silent PDF failures**
- A forum thread describes checking `usage_metadata.prompt_token_count` to catch PDFs that were not processed by Gemini 3.x — [Google forum](https://discuss.ai.google.dev/t/consistent-pdf-upload-processing-failure-with-gemini-3-x-models-in-google-ai-studio-affects-python-sdk-too/146407.md) [snippet only].

**Detection methods with research support**
- Latent Representation Probing improves abstention accuracy by 7.6% over best baselines, using hidden states rather than output probabilities. It was tested on scene-text VQA, not page OCR, and needs model internals — [arXiv 2511.19806, Nov 2025](https://arxiv.org/abs/2511.19806).
- Engine confidence scores exist in Mistral OCR 4.1 (block-level) — [card](https://docs.mistral.ai/models/model-cards/ocr-4-1) — and Textract — [docs](https://docs.aws.amazon.com/textract/latest/dg/textract-best-practices.html). Their calibration on Vietnamese is unverified.
- Grounding output with bounding boxes is available from LightOnOCR-3, dots.mocr, Chandra and OXR, as cited in the table above.

### Inferences
Suggested checks for this pipeline, as inferences not drawn from a validated study:
- Log `finish_reason` and output token count per page; treat `RECITATION`, `MAX_TOKENS` or empty output as failure, as the team already does for RECITATION.
- Flag repeated n-grams, and output length that is far off a cheap reference such as EasyOCR's character count. Be careful with forms, which repeat legitimately.
- Compare a VLM result with the local OCR result after diacritics are stripped. A large mismatch suggests hallucination or omission. Keeping the team's diacritic-ratio check catches engines that lose tones, which alone would have flagged PP-OCR.
- For legal documents, verify structured fields against the image with a second pass: số hiệu, dates, signers, article numbering.
- Self-hosted open-weight models have no provider recitation filter of this kind, so they could serve as the fallback for blocked pages, replacing 2×2 cropping. Their loops and hallucination remain, and this should be confirmed by testing those 11 known-bad pages.

Decision implied by the evidence, for the report writer:
- Do not replace on the basis of leaderboards alone.
- Run a small labelled bake-off on the team's own scanned pages (for example 50–100 pages, including the 11 RECITATION pages and known-poor scans), scoring CER with diacritics kept, omission rate, block rate, seconds per page and cost.
- Candidates supported by these notes:
  - current EasyOCR plus Gemma as the baseline;
  - Google Document AI Enterprise OCR;
  - Gemini Flash-Lite;
  - Chandra 2 and PaddleOCR-VL-1.6 or SenOCR-Vi on a free GPU;
  - PaddleOCR-VL-1.6 or MinerU's llama.cpp tier on the CPU, for timing.

### Gaps
- No quantitative rates found for hallucination or omission on scanned Vietnamese pages, or for RECITATION across engines. The only rates are one forum report and the team's own.
- ParseBench's per-method omission and hallucination tables could not be read from the PDF.
- No dots.ocr-specific loop report was found. No confirmed evidence on whether Google's traditional OCR or Mistral OCR ever block text.
- Whether Claude or GPT block OCR of public Vietnamese legal text was not tested or found. Only general signals are documented.
