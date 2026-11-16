# Vietnamese OCR models and services: what extends the earlier notes (as of 10 Nov 2026)

Scope: these notes add to `../Giải pháp OCR PDF tiếng Việt/scan_ocr_engines.md` and `vietnamese_hard_cases.md`. Facts already established there are **not repeated**, only referenced as "(earlier notes)". Those facts include the MDPBench VI table, SEA-Vision VI table, VMMU CER table, the SenOCR-Vi and Xiaomi-OCR-0-vi cards, the PP-OCR dictionary gap, Document AI, Azure and Textract language and price rows, and LLM token prices.

Labels:
- **[opened]**: the page was fetched and the figure read from it. This is the default and is not written out.
- **[snippet only]**: seen in a search result only.
- **[self-reported]**: produced by the model or service's own authors.

Every page was read through a summarising fetcher, so exact table cells should be spot-checked before quoting them in a final report.

## Vietnamese-specific models: what exists, licence, size, hardware, measured results

### Takeaway
Most new Vietnamese OCR releases from 2026 are **line-level recognisers** or **LoRA fine-tunes of PaddleOCR-VL-1.6 / MinerU2.5-Pro**. Every accuracy number for them is self-reported, on small or unnamed sets. For full scanned pages, the only Vietnamese-specific page-level candidates remain SenOCR-Vi (Apache-2.0) and Xiaomi-OCR-0-vi (non-commercial), both covered in the earlier notes. Two CPU-friendly additions are new here:
- tieubaoca's PaddleOCR-VL-1.6-Vietnamese GGUF, a Vietnamese line recogniser for llama.cpp, Apache-2.0;
- AsterNet, an MIT-licensed, 10.6M-parameter CTC line recogniser at about 60 ms per line on one Intel core.

Both need a separate text detector. No new Vintern release from 2026 was found.

### Cited Findings

**New since the earlier notes**

| Model | Licence | Size | Input | Hardware | Measured result (who, dataset) |
|---|---|---|---|---|---|
| [tieubaoca/PaddleOCR-VL-1.6-Vietnamese-GGUF](https://huggingface.co/tieubaoca/PaddleOCR-VL-1.6-Vietnamese-GGUF) | Apache-2.0, gated | Card says 0.5B. LM Q8_0 498 MB, BF16 936 MB, plus mmproj 882 MB | **Cropped lines or regions only**, with the fixed prompt `OCR:`. No detection | llama.cpp (`llama-cli`/`llama-server`). Windows, Linux, macOS and Docker install shown. No speed or RAM figure | [self-reported] 160 local validation samples, 32 from each of 5 sources, BF16 before quantisation. Base PaddleOCR-VL-1.6 CER **0.234** vs merged Vietnamese **0.066**; exact match 0.1375 → 0.5125. Per-source CER 0.016–0.096. Card warns Q8_0 may differ, and that the model can hallucinate, omit or duplicate characters. No date; citation says 2026 |
| [asterxlabs/asternet-vietnamese-ocr](https://huggingface.co/asterxlabs/asternet-vietnamese-ocr) v1.0 | MIT, commercial use allowed | 10.65M params, 41 MB ONNX | Line strips 32 px high, CTC over 227 characters | **CPU**: i7-13700H, 1 thread, 60.2 ms per line (16.6 FPS). Ryzen 7840HS 54 ms. AWS c6i.large 63 ms. T4/3060 batch 16: 5.8 ms. Measured on 100 lines | [self-reported, dataset unnamed and unsized] vs VietOCR: exact sentence 86.0% vs 76.0%; CER 3.45% vs 3.85%; **WER 9.01% vs 8.23% (worse)**; latency 60 ms vs 766 ms. Trained on 1.56M "unified Vietnamese document samples". Node and C++ samples are stubs |
| [Faust345/MinerU2.5-Pro-1.2B-vi-ocr-v2](https://huggingface.co/Faust345/MinerU2.5-Pro-1.2B-vi-ocr-v2) | **CC-BY-NC-4.0**, inherited from data. Gated | 1.2B LoRA on MinerU2.5-Pro-2604 | Handwriting lines, prompt `\nText Recognition:` | Trained on 1×A100-40GB | [self-reported] 5CD-AI Viet-Handwriting-OCR-v2 test set, n=300. CER 0.608 → **0.218**, WER 0.990 → 0.468, exact match only 0.053 |
| [truonggiabao7/ocrdoc-models](https://huggingface.co/truonggiabao7/ocrdoc-models) | Apache-2.0 per search summary | ONNX | PP-OCRv6 recogniser fine-tuned for Vietnamese ID cards and passports | | [snippet only]. Not opened. Domain is IDs, not legal text |
| [Sino-Vietnamese PaddleOCRv5 fine-tune, arXiv 2510.04003](https://arxiv.org/html/2510.04003v1) | | | Hán-Nôm texts | | [snippet only] Exact accuracy 37.5% → 50.0%. Not relevant to modern quốc ngữ legal text |

**Vintern**
- The newest found is still Vintern-1B-v3.5. It is fine-tuned from InternVL2.5-1B and its card claims strong OCR on Vietnamese documents ([card](https://huggingface.co/5CD-AI/Vintern-1B-v3_5)). Its VQA-type scores are in the earlier notes.
- Search found **no Vintern 3B or 2026 Vintern release** ([search, 10 Nov 2026]; [arXiv 2408.12480](https://arxiv.org/html/2408.12480v2) is the 2024 paper).
- A 2024 user thread reports Vintern-1B-v2 OCR doing poorly on day/month/year — [discussion #4](https://huggingface.co/5CD-AI/Vintern-1B-v2/discussions/4) [snippet only, title read].

**Already covered in the earlier notes, not repeated**
- SenOCR-Vi (Apache-2.0, 0.96B, MDPBench-VI 82.83, self-reported).
- Xiaomi-OCR-0-vi (CC-BY-NC, 0.8B, the only công văn header-order test).
- VietOCR (Apache-2.0; nom-vn synthetic CERs).
- VieSVTR (CC BY-NC).
- The VietOCR handwriting fine-tune.

**Searched and not found**
- No Vietnamese fine-tune of Qwen-VL, dots.ocr, olmOCR or Chandra with a model card and Vietnamese metric appeared in searches on 10 Nov 2026. That only means none was found. It does not prove none exists.

### Inferences
- **The line-level models fit the team's current pipeline shape.** EasyOCR detection plus recognition is a CPU pipeline, so swapping in a better Vietnamese recogniser is the cheapest CPU upgrade. The options are AsterNet (MIT, ONNX, about 60 ms per line) or the PaddleOCR-VL-1.6-Vietnamese GGUF (Apache-2.0, llama.cpp). Using EasyOCR or PP-OCR *detection* boxes with one of these recognisers avoids the PP-OCR dictionary gap.
- **Scale estimate, my own arithmetic.** At about 40 lines per page, AsterNet would take about 2.4 s per page on one core, roughly 7–8 hours for 11,000 pages before detection time. The VLM GGUF will be much slower, with no published speed.
- **None of the numbers is independent or measured on legal scans.** AsterNet's benchmark is unnamed. The GGUF's 160 samples are the author's own. Treat both as candidates for the team's own bake-off, not as rankings.
- Non-commercial licences (Xiaomi-OCR-0-vi, MinerU vi-ocr-v2, VieSVTR, VietHTR-Line data) are acceptable for a student project, but not if the project is later commercialised.

### Gaps
- The CPU speed of the GGUF model per line or per page is not published. SenOCR-Vi has no inference timing.
- AsterNet's evaluation set and its date are unstated. No independent comparison of AsterNet, the VietOCR fine-tunes and the GGUF model was found.
- No Vietnamese model was found that measures stamps, signatures or Công báo pages, beyond Xiaomi's 32-page header test (earlier notes).

## International services and frontier models: Vietnamese support, evidence, price per 1,000 pages, handwriting

### Takeaway
Language support for Vietnamese **printed** text is now confirmed by official pages for Google Document AI (earlier notes), Google Cloud Vision, Azure (earlier notes) and **Mistral OCR**, which is new here. Vietnamese **handwriting** is:
- supported by Document AI (earlier notes);
- **experimental** in Cloud Vision;
- not supported by Azure (earlier notes);
- not mentioned by Mistral.

No independent accuracy result for Vietnamese exists for Document AI, Vision, Azure or Mistral OCR. The only Vietnamese numbers for services are for LLMs (Gemini, Claude, GPT, kimi-K2.5), from MDPBench and VMMU (earlier notes). Moonshot now lists kimi-k2.5 as **deprecated** on its own platform.

### Cited Findings

**Language support (official pages)**
- **Google Cloud Vision.** `TEXT_DETECTION` and `DOCUMENT_TEXT_DETECTION` support Vietnamese: "Tiếng Việt | Vietnamese | vi | Latn". The handwriting scripts table says "vi | Vietnamese | **Experimental**". No last-updated date is shown — [Vision languages](https://docs.cloud.google.com/vision/docs/languages).
- **Mistral OCR.** The OCR section of Mistral's languages page lists, under Southeast Asian, "Indonesian, Tagalog, Thai, **Vietnamese**". Handwriting is not mentioned and no model version is given — [Mistral languages](https://docs.mistral.ai/resources/languages). This closes the earlier gap "Mistral OCR Vietnamese support is not stated".
- Mistral OCR 4 is marketed as covering 170 languages in 10 language groups, with a "72% win rate in blind tests". This is a vendor claim reported second-hand — [CryptoBriefing](https://cryptobriefing.com/mistral-ai-ocr-4-launch/) [snippet only].
- **Kimi.** Moonshot's pricing page lists `kimi-k2.5` under "Deprecated models" — [Kimi platform](https://platform.kimi.ai/docs/pricing/chat-k25). Third-party trackers quote about $0.60 input and $2.50–3.00 output per 1M tokens, and K2.6 at $0.95/$4.00. These figures conflict and are unverified — [BenchLM](https://benchlm.ai/moonshot/api-pricing) [snippet only].
- **Gemini, Claude and GPT.** No official Vietnamese OCR or handwriting statement was found. The only measured evidence is MDPBench and VMMU (earlier notes). A Vietnamese diploma study claims Gemini handles handwriting "with high accuracy" but gives no numbers (earlier notes).

**Price per 1,000 pages (new rows; the earlier notes cover Document AI, Azure, Textract, Mistral and token prices)**

Datalab (the company behind Chandra), from the [Datalab pricing page](https://www.datalab.to/pricing). No effective date is shown beyond "© 2026".

| Mode | Price per 1,000 pages |
|---|---|
| Convert lite ("fast CPU OCR") | $0.50 |
| Convert fast / balanced | $4 |
| Convert accurate | $10 |

- No separate Chandra price is listed.
- There is no batch discount.
- Free credit is $20 per month for a work email and $10 for a personal email, reset every 30 days — [Datalab billing docs](https://documentation.datalab.to/platform/billing.md).
- Datalab's own multilingual benchmark (earlier notes) does not say which API mode scored 85.0 on Vietnamese.

Google Cloud Vision: the price per 1,000 units was **not opened** in this session (gap).

**Already established, not repeated:** Document AI ($1.50, first 1,000 free), Azure Read ($1.50, third-party price), Mistral OCR 4.1 ($4, or $2 batch per a secondary source), Gemini, Claude and OpenAI token prices, and Textract (no Vietnamese).

### Inferences
- **Lowest-cost verified-Vietnamese engines for 11,000 pages, my arithmetic on list prices:**

  | Engine | Approx. cost for 11,000 pages | Notes |
  |---|---|---|
  | Document AI Enterprise OCR | about $15 | 10,000 billable pages × $1.50 |
  | Azure Read | about $16 | Printed text only, third-party price |
  | Gemini Flash-Lite batch | about $10 | Earlier notes' token estimate |
  | Mistral OCR 4.1 | $22–44 | Batch vs standard |
  | Datalab balanced | about $44 | |
  | Datalab lite | about $5.50 | Vietnamese quality and underlying engine unknown |

  All of these are small, so the choice should rest on accuracy and failure behaviour.
- **RECITATION and hallucination risk by engine class.**
  - Classic OCR APIs (Document AI, Vision, Azure Read) return recognised text with boxes and confidence. They are not generative, so a RECITATION-type block or invented sentences are structurally unlikely. Errors will be character-level. This is inference; no source states it.
  - Mistral OCR and Datalab are VLM-based. They can hallucinate, but no RECITATION-style filter is documented for them. That absence of evidence is not proof that no filter exists.
  - Gemini has the documented RECITATION false positives (earlier notes).
  - With kimi-K2.5 deprecated, its MDPBench lead is of limited practical use.
- Vietnamese handwriting (handwritten số or dates): Document AI is the only commercial service with official non-experimental Vietnamese handwriting support found.

### Gaps
- No independent Vietnamese accuracy figure for Document AI, Cloud Vision, Azure, Mistral OCR 4/4.1 or Datalab API modes.
- Cloud Vision's current price, and whether Mistral, Claude or GPT block legal text, were not verified.
- Kimi K2.6/K3 Vietnamese OCR results: none found. Kimi-K3 appears on the MDPBench leaderboard with no VI score (see below).

## New Vietnamese OCR benchmarks after March 2026; MDPBench and SEA-Vision updates

### Takeaway
No new **Vietnamese-specific page-level OCR benchmark or leaderboard** was found after March 2026. The new Vietnamese data is handwriting lines (5CD-AI VietHTR-Line, 60k pairs, no baselines). The MDPBench Hugging Face leaderboard has added three overall-only rows with **no Vietnamese score**, and its VI table is unchanged. No SEA-Vision update was found.

### Cited Findings
- **MDPBench Hugging Face page** — [dataset](https://huggingface.co/datasets/Delores-Lin/MDPBench):
  - The leaderboard now includes FINAL-Bench/Darwin-180B-RSI (83.65, asterisk not explained), moonshotai/**Kimi-K3** (83.6) and MinerU2.5-Pro-2605-1.2B (71). These are overall only; none has a VI cell.
  - The page has no dated news.
  - The private test set is not released; evaluation requires contacting the authors.
  - The page says 17 languages while its abstract lists 16, and Dutch appears in the table.
  - No per-language sample count is given, so the 160 vs 39+39 page conflict in the earlier notes is not resolved.
- MDPBench is reported as released in Apr 2026 and accepted to the NeurIPS 2026 Datasets & Benchmarks track, per the OCRBench repo listing — [MultimodalOCR repo](https://github.com/yuliang-liu/multimodalocr) [snippet only; not on the MDPBench page itself].
- **VietHTR-Line** (5CD-AI) — [dataset](https://huggingface.co/datasets/5CD-AI/VietHTR-Line):
  - 60,247 human-verified handwritten line pairs (about 2.74M characters) from "real-world document pages".
  - 59,247 train and 1,000 test, with no shared pages.
  - **CC BY-NC-ND 4.0**, gated.
  - **No baseline results.** Document types are unnamed.
  - The year 2026 comes from the citation and an AIIA 2026 award.
- 5CD-AI also released Viet-Handwriting-OCR-v2, used by the MinerU fine-tune above — [card](https://huggingface.co/Faust345/MinerU2.5-Pro-1.2B-vi-ocr-v2).
- Multilingual benchmarks seen but not opened for Vietnamese content:
  - GlotOCR Bench, Apr 2026 — [arXiv 2604.12978](https://arxiv.org/pdf/2604.12978) [snippet only].
  - Dr. DocBench, Jun 2026 — [arXiv 2606.01393](https://arxiv.org/pdf/2606.01393) [snippet only].
  - SoMark DocParsingBench, with a legal domain — [HF](https://huggingface.co/datasets/SoMarkAI/DocParsingBench) [snippet only].

  Whether any of them has a Vietnamese column is unknown.
- **SEA-Vision:** no post-March-2026 update found (one search; not checked on arXiv versions).

### Inferences
- MDPBench remains the only multi-engine page-level Vietnamese comparison. Its VI ranking (earlier notes) has not been extended to newer models such as Kimi-K3, OXR or TeleOCR.
- VietHTR-Line could be used to test handwriting on handwritten số and dates, but only line-level and only non-commercially.

### Gaps
- GlotOCR Bench and Dr. DocBench may include Vietnamese; neither was opened.
- No benchmark on Vietnamese legal or administrative scans exists beyond the 32-page header test.

## Which options can process about 11,000 pages cheaply with the least hallucination or RECITATION risk?

### Takeaway
Evidence-based ranking for this team (CPU only, scanned Vietnamese legal PDFs), as inference built on the cited facts:

1. **Google Document AI Enterprise OCR.** About $15. Official Vietnamese printed and handwriting support. Non-generative, so lowest block and hallucination risk. Vietnamese accuracy is unmeasured.
2. **A CPU line-recogniser swap** behind the existing detector (AsterNet, MIT, or the PaddleOCR-VL-1.6-Vietnamese GGUF, Apache-2.0). $0. Self-reported only.
3. **Self-hosted SenOCR-Vi or PaddleOCR-VL-1.6 on a free Colab or Kaggle GPU.** $0, with no provider filter.
4. **Gemini Flash-Lite batch.** About $10, but documented RECITATION false positives.
5. **Mistral OCR 4.1 or Datalab.** $22–44, VLM-based, Vietnamese listed or measured only by the vendor.

The cost differences are negligible, so a 50–100 page bake-off on the team's own scans should decide.

### Cited Findings
- Prices and language support: see the sections above and the earlier notes ([Datalab pricing](https://www.datalab.to/pricing); [Mistral languages](https://docs.mistral.ai/resources/languages); [Vision languages](https://docs.cloud.google.com/vision/docs/languages)).
- Hallucination warnings from the authors of the line-level models themselves — [GGUF card](https://huggingface.co/tieubaoca/PaddleOCR-VL-1.6-Vietnamese-GGUF).
- AsterNet's CPU latency, about 60 ms per line on 1 thread [self-reported] — [card](https://huggingface.co/asterxlabs/asternet-vietnamese-ocr).

### Inferences
- **Risk-ordered fallback design.**
  1. Run a non-generative engine first: Document AI, or local detection plus a Vietnamese recogniser.
  2. Send only low-confidence pages or low diacritic-ratio pages to a VLM.
  3. Use a self-hosted VLM (SenOCR-Vi or PaddleOCR-VL) for pages Gemini blocks, since self-hosted weights have no RECITATION filter.
- Avoid basing decisions on kimi-K2.5's MDPBench lead, since it is deprecated on Moonshot's platform.
- Free-GPU caveats: T4-class GPUs lack bfloat16, and PaddleOCR documents vLLM timeouts on T4 (earlier notes). Use the Transformers or Paddle backend there.

### Gaps
- No measured CPU throughput for any page-level Vietnamese VLM.
- No measured hallucination or omission rate for any engine on Vietnamese scans; the team must measure it.
