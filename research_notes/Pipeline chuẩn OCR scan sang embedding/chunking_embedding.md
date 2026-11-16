# From parsed OCR text to vector index: cleaning, chunking, metadata, embedding, visual retrieval, OCR-noise effects (as of Nov 2026)

Source-handling note: every number below comes from a page opened during this session, unless it is marked **[snippet-only]**. Sources from before 2025 are marked **[older]**. Vietnamese-specific evidence is grouped under "Vietnamese" headings.

## Q1. What is the consensus 2025-2026 sequence from parsed text to vector index, and what is debated?

### Takeaway
The working consensus runs: parse (layout-aware) → light cleaning and normalisation → structure-aware chunking of a few hundred tokens with document/section context attached → metadata (doc ID, section path, page) → multilingual dense embedding plus BM25/sparse hybrid → rerank the top ~100-150 → top-k to the LLM. Four points are still debated: whether semantic or late chunking is worth its cost (mostly no), whether to skip OCR for scanned pages and use visual retrievers (strong on visual benchmarks, but a reranked text pipeline can match or beat them), whether aggressive cleaning helps (no rigorous evidence), and which embedding model to use (the leaderboard turns over every few months).

### Cited Findings

**Sequence and the effect of context-augmented chunks plus hybrid plus rerank (the most cited recipe)**
- Anthropic Contextual Retrieval **[older, Sep 2024]**: an LLM prepends a short chunk-specific context, drawn from the whole document, to each chunk before it is embedded and BM25-indexed. On top-20 retrieval failure rate (baseline 5.7%), contextual embeddings alone gave −35% (→3.7%). Adding contextual BM25 gave −49% (→2.9%), and adding reranking (top-150 → top-20) gave −67% (→1.9%). Chunks were "usually no more than a few hundred tokens", and the cost example assumes 800-token chunks. Top-20 beat top-5 and top-10. Gemini Text 004 and Voyage were the best embedders tested. With prompt caching, the one-time cost is about $1.02 per million document tokens. — [Anthropic](https://www.anthropic.com/news/contextual-retrieval)
- An independent comparison (Merola & Singh, Apr 2025) on NFCorpus with Jina-v3 scored NDCG@10 as follows: early fixed chunking 0.291, late chunking 0.294, contextual fixed chunks with rank-fusion and rerank 0.308, contextual semantic chunks 0.309. Contextual retrieval was best overall but needed up to about 20 GB VRAM on long documents, so only a 20% subset was run. Differences in generation were "not notable". — [arXiv 2504.19754](https://arxiv.org/html/2504.19754v1)

**Chunking (debated: semantic and late chunking vs simple)**
- "Is Semantic Chunking Worth the Computational Cost?" (Vectara; Oct 2024, NAACL 2025 Findings) tested document retrieval, evidence retrieval and answer generation. Its conclusion: "the computational costs associated with semantic chunking are not justified by consistent performance gains" over fixed-size chunking. Only the abstract was read, so the paper's numbers are not captured here. — [arXiv 2410.13070](https://arxiv.org/abs/2410.13070)
- Late chunking (embed the whole document with a long-context model, then mean-pool per chunk) gave mixed results:
  - It helped Jina-v2 (NDCG@10 0.237→0.255) and Jina-v3 (0.346→0.354) on NFCorpus.
  - It collapsed BGE-M3 (0.225→0.067).
  - It hurt Stella-v5 on MS MARCO (0.632→0.505).
  - LLM-based "dynamic" segmentation cost 2-4× the embedding time.
  - Recursive chunking was not evaluated.
  - So late chunking depends on the model: it only helps models trained for it. — [arXiv 2504.19754](https://arxiv.org/html/2504.19754v1)
- The original Jina late-chunking paper reports average nDCG@10 for 256-token chunks rising from 52.2 to 54.0 with late chunking. **[snippet-only, via search; paper not opened; arXiv 2409.04701, older]**
- Conflicting chunking benchmarks in vendor and blog sources **[snippet-only, unverified]**:
  - A Vecta/FloTorch benchmark had semantic chunking with the best recall (92% vs 88% for recursive) but recursive with the best end-to-end accuracy (69% vs 54%).
  - A Portuguese-corpus study had recursive at 61.0% recall vs 82.1% for semantic.
  - A RPI thesis found recursive and semantic beat the alternatives on noisy corpora, with recursive gaining most on the noisiest data, and found that late chunking needed boilerplate mitigation.
  - Sources for these three claims: [PremAI blog](https://blog.premai.io/rag-chunking-strategies-the-2026-benchmark-guide), [RPI dspace](https://dspace.rpi.edu/items/b010d6e2-6ec4-4f44-9bd9-6faa3d2535cb).
- On ViDoRe V3, chunking within pages and adding image descriptions to OCR Markdown did *not* improve text retrieval, so the authors reported the simplest pipeline (page-level). — [ViDoRe V3, arXiv 2601.08620v2](https://arxiv.org/html/2601.08620v2)

**Text cleaning and normalisation**
- No controlled RAG benchmark was found that isolates header/footer removal, dehyphenation or Unicode normalisation on OCR text.
  - The closest classical IR evidence **[older, 2004 SPIE]** found that removing running headers and footers did not improve retrievability for proximity search. ISRI's many experiments found OCR errors "do not significantly affect retrievability" for classic search engines.
  - Web2Text **[older, arXiv 1801.02607]** reports that HTML boilerplate removal improves retrieval on ClueWeb12.
  - Both claims are **[snippet-only]**, from [search results](https://arxiv.org/abs/1801.02607v1).
- A practitioner claim that preprocessing raises RAG accuracy by "30-40%" cites no evaluation, so it is unreliable. — [Galileo blog (snippet-only)](https://galileo.ai/blog/data-processing-steps-rag-precision-performance)

**Hybrid dense + BM25 and reranking**
- ViDoRe V3, text pipeline (NeMo Retriever extraction to Markdown, then Jina-v4): NDCG@10 rose from 50.4 to **63.6** with the zerank-2 text reranker (+13.2). The reranked text pipeline had "the highest overall retrieval performance", above the best visual retriever (ColEmbed-3B-v2, 59.8). A visual reranker (jina-reranker-m0) added only +0.2 and degraded four datasets. — [arXiv 2601.08620v2](https://arxiv.org/html/2601.08620v2)

**Visual (OCR-free) retrieval vs OCR-then-embed**
- ViDoRe V3 (Illuin/NVIDIA; v2 dated 21 Apr 2026) covers about 26k pages, 3,099 queries in 6 languages and 10 industry corpora.
  - Without reranking, the best visual retriever is ColEmbed-3B-v2 at **59.8** NDCG@10, against **51.0** for the best text model (Qwen3-8B) and 50.4 for Jina-v4 text.
  - Cross-lingual retrieval is 2-3 points below monolingual.
  - In generation with Gemini 3 Pro, a hybrid text+visual pipeline scored best on hard queries (54.7%, vs 52.1% text and 54.5% visual). Its non-oracle global score of 65.7% was the best overall.
  - Source: [arXiv 2601.08620v2](https://arxiv.org/html/2601.08620v2)
- "Lost in OCR Translation?" (May 2025): ColPali "performs well on documents it has been fine-tuned on", but OCR (Nougat) plus a text pipeline "generalizes better to unseen documents of varying quality". The abstract gives no numbers. — [arXiv 2505.05666](https://arxiv.org/abs/2505.05666)
  - A search snippet attributes these figures to it: ColQwen2 NDCG@5 0.6027 vs 0.3373 for Nougat-OCR text on the ViDoRe V1 DocVQA subset, with the gap blamed on semantic alignment rather than OCR quality. **[snippet-only]**
- OHRBench appendix, VisRAG (no OCR) with a Qwen2-VL-7B generator, overall F1:
  - VisRAG scored 40.2, vs 46.8 for ground-truth text, 37.9 for MinerU and 40.6 for Qwen2.5-VL-OCR.
  - It was much better on charts (30.6 vs 10.7 for MinerU).
  - It was worse on plain text (50.7 vs 57.7) and reading order (15.6 vs 29.8).
  - Source: [arXiv 2412.02592v4](https://arxiv.org/html/2412.02592v4)

**Embedding models (leaderboard state)**
- Qwen3-Embedding-8B model card, MTEB Multilingual, using leaderboard values from May/Jun 2025:

  | Model | Mean (task) | Retrieval |
  |---|---|---|
  | Qwen3-Embedding-8B | 70.58 | 70.88 |
  | Qwen3-Embedding-4B | 69.45 | – |
  | gemini-embedding-exp-03-07 | 68.37 | 67.71 |
  | multilingual-e5-large-instruct | 63.22 | 57.12 |
  | BGE-M3 | 59.56 | 54.60 |
  | text-embedding-3-large | 58.93 | 59.27 |
  | Cohere multilingual v3 | 61.12 | – |

  The model also supports 32K context, MRL output dimensions from 32 to 4096, and instructions (+1-5%). — [HF Qwen3-Embedding-8B](https://huggingface.co/Qwen/Qwen3-Embedding-8B)
- Microsoft harrier-oss-v1 (MIT licence, 32k context, Vietnamese listed) scores on MTEB v2 Multilingual:
  - 74.3 for the 27B model, 69.0 for 0.6B and 66.5 for 270M.
  - Microsoft says the family ranked #1 on the multilingual MTEB-v2 as of 6 Apr 2026.
  - Queries require task instructions.
  - These numbers are vendor-reported, from the [HF model card](https://huggingface.co/microsoft/harrier-oss-v1-27b) and [Bing blog](https://blogs.bing.com/search/April-2026/Microsoft-Open-Sources-Industry-Leading-Embedding-Model), seen via search **[snippet-only]**.
- A Sept 2026 roundup lists the MTEB(Multilingual v2) top as harrier-27b 74.31, KaLM-Embedding-Gemma3-12B 72.32 and Qwen3-Embedding-8B 70.75. It also warns that some frontier models train on data overlapping MTEB. — [ailog blog (snippet-only)](https://app.ailog.fr/en/blog/news/embedding-models-leaderboard-2026)

**Vietnamese**
- VN-MTEB (EACL 2026 Findings; 41 datasets machine-translated from MTEB, 18 models):
  - Overall: m-e5-large-instruct 67.99, e5-Mistral-7B 67.67, gte-Qwen2-7B 65.84.
  - Retrieval: gte-Qwen2-7B **46.05**, gte-Qwen2-1.5B 42.01, e5-Mistral 41.73, m-e5-large-instruct 40.88.
  - Vietnamese-specific models trail; for example, Vietnamese-Embedding scores 63.34 overall.
  - RoPE/decoder models beat APE models such as bge-m3 and m-e5, and instruction tuning helps.
  - Qwen3-Embedding and harrier were not evaluated.
  - Source: [arXiv 2507.21500](https://arxiv.org/html/2507.21500v1)
- ViRE (EACL 2026 Findings, "Which Works Best for Vietnamese?"), MRR@10 as BM25 / best dense / best hybrid:
  - ALQAC (legal): 92.20 / 94.14 / **96.66**
  - UIT-ViQuAD2: 78.09 / 89.29 / 93.62
  - ViMedAQA: 71.36 / 87.94 / 88.82
  - Hybrid beat standalone dense on all 10 datasets.
  - The best fusion weight was α≈0.6-0.8 dense; 0.7 was used.
  - Source: [ViRE GitHub](https://github.com/longstnguyen/ViRE)
- Vietnamese legal retrieval (VLSP 2025 DRiLL, statute-article retrieval, over 3,000 questions; the underlying VLQA has 59,636 articles):
  - Teams chunked by article and prepended document titles (FPT, "document-based chunking with titles").
  - Others used hierarchical chunking with BGE-M3, or clause segmentation plus LLM-generated article descriptions.
  - Pipelines were BM25 + dense + reranker.
  - Many articles exceed the 256-token limit of Vietnamese embedding models.
  - Source: [VNU JCSCE overview](https://jcsce.vnu.edu.vn/index.php/jcsce/article/view/6463/228), [VLSP 2025 papers](https://preview.aclanthology.org/anlp-naacl/2025.vlsp-1.18.pdf) **[snippet-only]**

### Inferences
- The defensible default is structure-aware chunking (Điều/Khoản for legal text) with the heading path prepended, which is a cheap substitute for Anthropic-style contextualisation. Add hybrid BM25 plus a dense multilingual model, then a cross-encoder reranker. Semantic and late chunking are optional and should be tested on your own data before adopting them.
- For scanned text-heavy legal documents, the evidence (OHRBench plain-text results; ViDoRe V3 after reranking; "Lost in OCR") favours OCR-then-text, possibly hybridised with a visual retriever. Visual retrievers win mainly on charts, tables and visually rich pages.
- Article-level chunking with titles is the practical norm in Vietnamese legal IR, but no study found here compares it against fixed or recursive chunking with numbers.

### Gaps
- No controlled measurement was found of the effect on retrieval of NFC normalisation, dehyphenation or header/footer removal on OCR text, in any language.
- There are no head-to-head numbers for parent-child (small-to-big) retrieval; framework docs were not consulted for this.
- Metadata enrichment (generated questions, summaries, entity extraction, bounding-box provenance) was not covered by any measured study found in this session.
- VN-MTEB does not include Qwen3-Embedding, harrier or Gemini embedding, so it is unknown whether they lead on Vietnamese retrieval.
- The live MTEB/ViDoRe leaderboards were not opened directly; leaderboard figures above come from model cards and blogs.

## Q2. Which choices have measured evidence, with numbers? (OCR-noise effects in particular)

### Takeaway
OCR noise measurably harms both retrieval and RAG. On OHRBench, even the best OCR output loses about 15% of retrieval quality and 14% of end-to-end F1 against clean text. Severe semantic noise (wrong characters or words) roughly halves performance for both BM25 and dense BGE-M3, so dense embeddings are *not* robust to character-level noise. Vietnamese diacritic-error robustness has not been measured in any study found.

### Cited Findings
- OHRBench (ICCV 2025; v4 Aug 2025; 8,561 page images, 8,498 QA pairs, 7 domains), averaged over retrievers and generators. Columns: retrieval LCS / generation F1 / overall F1.

  | Source | Retrieval LCS | Generation F1 | Overall F1 |
  |---|---|---|---|
  | Ground truth | 70.0 | 43.9 | 36.1 |
  | Qwen2.5-VL-72B | 59.2 | 37.5 | 31.1 |
  | Marker | 56.6 | 35.9 | 29.5 |
  | InternVL2.5-78B | 55.8 | 35.8 | 29.6 |
  | MinerU | 50.1 | 36.7 | 30.0 |
  | GOT | 45.4 | 27.8 | 24.6 |
  | Nougat | 40.9 | 25.5 | 14.5 |

  Source: [arXiv 2412.02592v4](https://arxiv.org/html/2412.02592v4)
- OHRBench: going from mild to severe semantic noise (r_noise > 0.6) causes "nearly a 50%" decline for most retrievers and LLMs. BM25 and BGE-M3 degrade alike. Formatting noise mainly hurts table, formula and chart questions (max −12.7% for BGE-M3 retrieval, −9.1% for Llama3.1-8B generation), while plain-text questions are largely unaffected. Larger LLMs are more robust (Qwen2-72B shows about −7%). — [arXiv 2412.02592v4](https://arxiv.org/html/2412.02592v4)
- OHRBench: Azure OCR (commercial) was the best source with strong generators but fell below MinerU with Llama3.1-8B. The authors conclude no current OCR is "competent for constructing high-quality knowledge bases". — [arXiv 2412.02592v4](https://arxiv.org/html/2412.02592v4)
- Reranking: +13.2 NDCG@10 for text retrieval on ViDoRe V3 (50.4→63.6). — [arXiv 2601.08620v2](https://arxiv.org/html/2601.08620v2)
- Contextual chunks + BM25 + rerank: −67% retrieval failures. — [Anthropic](https://www.anthropic.com/news/contextual-retrieval) **[older]**
- Hybrid over dense in Vietnamese: +0.9 to +4.3 MRR@10 across datasets (e.g., UIT-ViQuAD2 89.29→93.62; ALQAC 94.14→96.66). — [ViRE](https://github.com/longstnguyen/ViRE)
- Vietnamese OCR diacritic issues are documented qualitatively but not linked to retrieval:
  - OCR often recognises base characters but misses, confuses or misplaces diacritics, which changes meaning ([Research Square preprint, snippet-only](https://www.researchsquare.com/article/rs-10241038); [Vietnamese DAR survey 2025, snippet-only](https://arxiv.org/pdf/2506.05061)).
  - LLM reference-based post-OCR correction for diacritics has been proposed ([AAAI 2025, snippet-only](https://ojs.aaai.org/index.php/AAAI/article/view/35012)).

### Inferences
- Because semantic OCR noise hurts dense and BM25 retrieval about equally, OCR quality (including diacritic accuracy) and LLM post-OCR correction probably matter more for Vietnamese scans than the choice of embedding model. This is inferred from OHRBench, which has no Vietnamese data.
- Hybrid retrieval and reranking are the best-evidenced add-ons, with double-digit gains. Chunking variants show differences of about ±0.02 NDCG and swing in either direction.

### Gaps
- No study was found that measures embedding or retrieval robustness to stripped or swapped Vietnamese diacritics. ViRE's `--normalize-all` option exists, but it reports no results.
- No OHRBench-style benchmark exists for Vietnamese scanned documents, and ViDoRe V3 covers 6 languages, apparently not including Vietnamese (the language list was not verified).
- The full numbers in the semantic-chunking paper (2410.13070) and the newer 36-method chunking study (Shaukat et al., March 2026) were not read.
