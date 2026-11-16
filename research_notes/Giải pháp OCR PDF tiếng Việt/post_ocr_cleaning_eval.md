# Post-OCR correction, cleaning and quality evaluation (state as of November 2026), with application to a 454-document Vietnamese legal corpus

Reading guide: "Cited Findings" were read on the linked page, except where marked otherwise. Percentages labelled "computed" are my arithmetic on the source's figures. "Inferences" are my reasoning, not published results. Items marked "older" pre-date 2024. **No study found measures post-OCR correction on Vietnamese legal text; every LLM/VLM CER figure below comes from other languages, mostly historical print.**

## 1. What post-OCR correction works best now: LLMs vs ByT5/mT5, multi-OCR consensus, confidence-guided, vision-grounded?

### Takeaway
The strongest measured result is vision-grounded correction (page image plus OCR text), which beat text-only LLMs and image-only re-OCR in the studies that tested it, though on few datasets and no Vietnamese. Fine-tuned text-only LLMs lead the one text-only competition. Zero-shot LLMs are inconsistent and can make text worse; ByT5 is a solid fine-tuned baseline but does not transfer across OCR engines. Multi-OCR consensus and confidence-guided correction have little CER evidence.

### Cited Findings

**Vision-grounded (image + OCR text)**
- Thomas et al., Findings of EMNLP 2026, BLN600 (19th-century English newspapers, test mean CER 8.22%, WER 25.77%, 120 test documents, 2,379 sequences). CER/WER reduction **with prompting only**: Llama 3.1 8B text 14.71/40.21%; Llama 3.2V 11B image+text 42.90/67.53%; Qwen 2.5 7B text 9.88/33.40%; Qwen 2.5 VL 7B image+text 45.34/64.58% — [PDF](https://aclanthology.org/2026.findings-emnlp.60.pdf)
- Same paper, **after QLoRA fine-tuning**: Llama 3.1 text 41.63/66.84%; Qwen 2.5 text 43.78/65.79%; Llama 3.2V image+text 92.03/91.40%, image-only 84.27/90.05%, text-only 43.42/61.79%; Qwen 2.5 VL image+text 89.27/90.28%, image-only 83.49/89.52% — [PDF](https://aclanthology.org/2026.findings-emnlp.60.pdf)
- Same paper: direct re-OCR with pretrained PaddleOCR-VL gave only 52.32/71.97%, well under image+OCR correction (Appendix C). Fine-tuning gains were reported as minimal when training data increased from a 70-document subset upward (Figure 2). LLM performance fell from 41.63% to 23.74% CER reduction as input grew from 1 to 9 merged sequences, while the VLM fell only from 92.03% to 86.74%. LLMs "often further degrade" even easy samples; VLMs "rarely degrade". Text-only LLMs hallucinate plausible corrections on illegible text. Folded or distorted pages still cause VLM errors. Note the paper did not test on a second dataset and deliberately excluded BART/ByT5 baselines — [PDF](https://aclanthology.org/2026.findings-emnlp.60.pdf)
- Greif et al. 2025, German city directories 1754–1870, 30 pages. Transkribus Print M1 alone: normalized CER 3.67%, strict CER 4.95%, normalized WER 24.26%. Print M1 then Gemini 2.0 Flash with image+OCR text: 0.84%, 1.91%, 5.55% (computed: 77% and 61% CER reduction). Print M1 then GPT-4o: 1.00%, 2.17%. Gemini 2.0 Flash image-only: 1.27%, 2.08%. GPT-4o image-only: 6.31%, 7.19%. A model re-correcting its own transcription gave no noteworthy gain. No text-only condition and no hallucination measurement. **Its "normalized" CER is ASCII-only and excludes non-ASCII characters, so that figure would hide Vietnamese diacritic errors entirely; only the strict figure is a relevant analogue** — [arXiv](https://arxiv.org/html/2504.00414)
- Against over-reading vision models: on spelling errors inside real images (Chinese and English, not OCR post-correction), token-correction F1 was GPT-4o 38.8, Qwen-32B 36.5; humans fully corrected 41 of 50 erroneous images, GPT-4o 16. Running OCR first raised Qwen-32B from 36.5 to 44.0 and Qwen-72B from 33.1 to 45.0, but hurt smaller models — [Vision Language Models Are Not (Yet) Spelling Correctors](https://arxiv.org/html/2509.17418)

**Text-only LLMs**
- ICDAR 2026 HIPE-OCRepair (English, French, German historical newspapers and books; text only; 50 runs from 4 teams; about 995k tokens; 740 test units). Overall cMER: BnF-Mistral run1 0.0050, BLOCR run1 0.0106, L3i run1 0.0176, uncorrected baseline 0.0226 (computed: 78%, 53%, 22% reduction). Preference score 0.90, 0.70, 0.36. The winner was Mistral Small 3 with continued pre-training, LoRA on about 10,000 samples, synthetic OCR pairs, a judge-and-retry loop and routing of CER >15% documents to a larger model. Zero-shot prompting came second (BLOCR, DeepSeek/Gemma 3, temperature 0.2). Zakaria-ENSIAS zero-shot on French was **worse** than baseline (0.0185 vs 0.0176). Scoring normalizes case and punctuation and is described as IR-oriented, so gains reflect searchability rather than diplomatic fidelity — [report](https://arxiv.org/html/2607.08143v1)
- HIPE by noise level (dta19, best system vs baseline): low noise 0.0040→0.0029; medium 0.0240→0.0054; high 0.0546→0.0082 (computed: 27.5%, 77.5%, 85%). Absolute gain at low noise is only 0.0011 — [report](https://arxiv.org/html/2607.08143v1)
- Kanerva et al. 2025, CER/WER relative improvement. English (18th-century ECCO): GPT-4o 58.1/59.1, Llama-3.1-70B 38.7/46.3, Gemma-2-27B 35.6/37.8, Gemma-2-9B 28.2/38.4, Mixtral −14.9/19.1. Finnish (19th/20th-century, 449 pages; models don't officially support Finnish): GPT-4o 11.9/33.5, Gemma-2-27B −19.1/0.0, Gemma-2-9B −24.0/−4.1, Mixtral −76.5/−40.5. All open-weight models degraded Finnish CER. Segments of 50–100 words were notably worse; gains flatten beyond 200–300 words. Removing overgenerated text was essential — [arXiv](https://arxiv.org/html/2502.01205v1)
- Gemini and Gemma specifically, zero-shot at temperature 0, handwriting OCR in Portuguese/French/English (baseline CER 6.60, WER 22.62; c. 2025). Gemini 2.0 Flash prompt 1: CER 5.54, WER 15.06; prompt 2: CER 7.76, WER 18.57. Gemma 3 27B: CER 7.14/6.93, WER 17.13/16.36. Most open models raised CER while lowering WER. So the same Gemini model flipped from best to worse than baseline on prompt alone. Granite, DeepSeek-R1 and Qwen 3 were dropped during screening for hallucination — [de Araújo et al., STIL](https://sol.sbc.org.br/index.php/stil/article/download/37859/37637)
- Boros et al. 2024: 14 foundation models across languages, periods and document types; LLMs were "anything but efficient" in zero-shot and few-shot settings — [ACL](https://aclanthology.org/2024.latechclfl-1.14/)
- Bourne 2024/2025 (CLOCR-C): best model over 60% CER reduction on NCSE newspapers; benefit carries over to NER; misleading prompts reduce performance — [arXiv](https://arxiv.org/abs/2408.17428)

**ByT5/seq2seq**
- Guan et al., EMNLP 2024: ByT5 with synthetic data at several noise levels, CER-threshold filtering and test-time adaptation reached 68.67% CER reduction without manually annotated data — [ACL](https://aclanthology.org/2024.emnlp-main.862/)
- Thomas et al. 2024: instruction-tuned Llama 2 54.51% vs fine-tuned BART 23.30% CER reduction on BLN600 — [ACL](https://aclanthology.org/2024.lt4hala-1.14/)
- ByT5-small trained on EasyOCR noise for Devanagari: EasyOCR CER clean 2.82→2.62, noise 2.97→2.73, but blur 3.05→3.50 and low-DPI 3.07→4.53. Transfer to other engines made them worse: Qwen 2.35→2.98, Unlimited 3.20→4.93, DeepSeek 3.58→5.62 — [Can OCR-VLMs Read Devanagari?](https://arxiv.org/html/2606.29213)
- Decoupled T5/ByT5/BART correctors trained on synthetic noise alone: T5-Base best on modern text, ByT5-Base best on historical text. The abstract gives no error rates — [arXiv](https://arxiv.org/abs/2603.28028)
- I found no 2024–2026 mT5 post-OCR result with measured CER, and no ByT5 entry among the HIPE 2026 teams — [HIPE report](https://arxiv.org/html/2607.08143v1)

**Multi-OCR consensus and confidence-guided**
- CE-OCR (multi-VLM agreement, revised 2026): consensus entropy routes uncertain inputs to a stronger model. OCRBench score 907 vs 888 best single model (+2.1%), 852 average single model (+6.5%), 7.3% routed at θ=0.5. OCRBench-V2 with GPT-4o rephrasing: +9.1% English, +8.6% Chinese overall. Error-detection F1 48.0–51.3 vs 36.1–40.0 for VLM-as-judge on 1,000 human-scored pages. These are benchmark scores, not CER — [arXiv](https://arxiv.org/html/2504.11101v3)
- Large char-n-gram seq2seq voting (older, 2021/2022): best on 5 of 9 ICDAR 2019 languages. This is ensembling of a single model's windows, not multiple engines — [arXiv](https://arxiv.org/abs/2109.06264)
- L3i's detection-augmented HIPE run underperformed its plain run; the team attributed this to too little training data — [HIPE report](https://arxiv.org/html/2607.08143v1)

### Inferences
- For the residual é problem, text-only re-correction has the weakest claim: the image holds the deciding evidence, and context alone cannot always separate two valid syllables. Image+OCR correction is the first candidate to test. It is unproven on Vietnamese diacritics, and the spelling-in-image study warns that vision models miss subtle character substitutions.
- The 90% figure should not be extrapolated. It needs fine-tuning, starts at 8% CER, works on line-sized sequences and is English. The prompt-only figure (43–45%) is the closer analogue for a team that does not fine-tune, and the starting CER on the 54 documents is likely lower. Absolute gains shrink at low noise.
- Crop size matters: send small image patches and short text units, but note the conflict that text-only LLMs did worse on short (50–100 word) segments in Kanerva and on long sequences in Thomas. Test unit size locally.
- A low-cost consensus check is possible without a new OCR run: two independent vision reads of a suspect token, using disagreement to route to human review. This adapts CE-OCR's logic and has not been evaluated in this form.

### Gaps
- No Vietnamese measurement of vision-grounded correction, or of LLM vs ByT5.
- No 2024–2026 study with CER for classic multi-engine alignment and voting, or LLM merging of several engines. A search snippet attributes "up to 15% WER improvement" to a 2021 multi-view paper, and LMV-RPA is reported at 99% vs 94% accuracy by a secondary review. I could not open either, so neither figure should be used.
- Confidence-guided token selection: only a Rostock thesis snippet says it mitigates hallucination; the [event page](https://www.informatik.uni-rostock.de/veranstaltungen/detailansicht-des-events/n/default-8eb5fab2bbde0a90019f3ad80bfdff7c) returned 404. No numbers.

## 2. Risk of over-correction and hallucination (numbers, legal citations, proper nouns), and guards

### Takeaway
Over-correction is documented and severe when the input is already good. The published guards are mostly length checks, retries, judge loops, masking and fallback to the original text. I found no published evaluation of numeric-token preservation or diff-constrained output on OCR correction, and none on legal citations, so the guard set below has to be validated locally.

### Cited Findings

**Size of the risk**
- Spanish historiographical sources with Latin and proper nouns, Qwen3 8B correction after each pipeline. Every LLM-augmented pipeline scored below its base. Character accuracy: Marker 98.70→82.82; Docling+Tesseract 89.06→78.77; Docling+EasyOCR 85.39→74.58; PyMuPDF 84.05→55.95. Marker on clean scans 99.56→51.66. For Marker, this means CER rose from 1.30% to 17.18% (computed). The LLM invented errors, returned explanations, normalized Latin into Spanish ("possessores"→"poseedores"), and left some non-dictionary errors unfixed. Outputs varied between runs. Authors note edit distance also penalizes some legitimate forms and recommend validating on representative samples before scale-up. Small local model, preprint — [Gómez Rey et al., 2026](https://arxiv.org/html/2608.24976v1)
- "Overcorrection on low-noise inputs emerges as a recurring challenge"; abstaining is competitive at low noise — [HIPE 2026](https://arxiv.org/html/2607.08143v1)
- Vision models can distort silently: Qwen CER 0.60% vs TrOCR 1.05% on the same historical lines, but Qwen more often replaces uncertain forms with plausible valid words ("silent semantic distortion", spelling regularization like "Antient"→"Ancient"). Hallucination itself was not quantified — [Vesalainen et al., 2026](https://arxiv.org/html/2602.14524v1)
- Catastrophic outliers exist under image degradation. DeepSeek-OCR under blur: median CER 1.50, mean 73.65, 2% catastrophic samples, output up to 71.6× reference length — [Devanagari study](https://arxiv.org/html/2606.29213)
- Hallucination at illegible points is plausible rather than random: LLMs often insert a synonym that keeps meaning but misses the ground truth — [Thomas et al. 2026](https://aclanthology.org/2026.findings-emnlp.60.pdf)

**Guards that are published**
- Two-sided length ratio accepting 0.35×–2.8× input length, up to two retries, then fallback to the original OCR, plus stripping echoed prompts and chain-of-thought (temperature 0.1) — [HIPE, Zakaria-ENSIAS](https://arxiv.org/html/2607.08143v1)
- Judge-and-retry loop reducing the flag rate from 42% to 6%, language-specific anti-hallucination prompts, routing by CER — [HIPE, BnF-Mistral](https://arxiv.org/html/2607.08143v1)
- Vietnamese reference-based pipeline: temperature 0; correct only words present in the input; sliding-window Levenshtein trim of text added beyond the input; for short or dangling text, reject unless similarity is high, length differs only slightly **and word count is unchanged** — [Do et al., AAAI 2025](https://arxiv.org/html/2410.13305v1)
- Line tags `<i.j.k>…</i.j.k>` to constrain output and allow regex extraction; an instruction "Do not correct numbers" appears in one prompt, but its effect was not reported separately — [de Araújo et al.](https://sol.sbc.org.br/index.php/stil/article/download/37859/37637)
- Vietnamese administrative text: Underthesea normalization and conservative detection, **entity masking for rigid identifiers**, BARTpho correction, detector-guided post-processing and iterative masked refinement. Authors report much less over-correction than baselines. I saw this through the search index abstract only; the journal site returned an expired-certificate error, so metrics were not read — [VNU JCSCE 2026](https://jcsce.vnu.edu.vn/index.php/jcsce/article/view/7020)
- Temperature alone is not a safeguard: over-correction and degradation appear in the temperature-0 and low-temperature runs above. Kanerva's tuned optimum was non-zero (0.26 English, 0.14 Finnish) — [arXiv](https://arxiv.org/html/2502.01205v1)

### Inferences
- The current length check is one-sided and tests only one failure. It catches truncation, but not added text or same-length wrong substitutions, which is the failure that matters for numbers and citations. Example: changing a document number digit leaves length unchanged. "No rejection" therefore says nothing about fidelity.
- Suggested layered guard, enforced in code after any LLM call. **None of this is published as a tested bundle; all of it needs local measurement:**
  1. Align output to input at token level and fall back to the original per token or paragraph, not per document.
  2. Hard invariants: the multiset of digit-bearing tokens is unchanged; legal citation regex matches (such as forms like `15/2020/NĐ-CP`, `Điều 5`, `khoản 2`) are identical; dates are identical. Any violation sends the span to a human, not to automatic acceptance. Real OCR errors in numbers will also be flagged, which is the intended behaviour.
  3. For the é pass specifically: **accept only edits where the accent-folded token is unchanged**, with `đ` kept distinct from `d`, and only for the ê/é family. This makes the edit space a closed allow-list: the model picks one of {é, ế, ề, ể, ễ, ệ, e…} and cannot rewrite the word. Structured output listing `{token_id, replacement}` is easier to validate than free-form regenerated text.
  4. Proper nouns and signers: mask or restrict to diacritic-only edits; compare to entities already known from the corpus's knowledge graph.
  5. Log edit-rate per document. An unusual edit rate, compared with the checker's estimated error rate, is a review trigger.
- Measure false-edit rate on text known to be correct: seed clean pages and count what changes.

### Gaps
- No measured study found on numeric-token preservation, grammar-constrained decoding or diff-only output for OCR correction. Structured output's benefit here is my reasoning, not evidence.
- No measured hallucination rate for digits, legal citations or Vietnamese proper nouns. The HIPE paper lists controlling over-correction and hallucination as future work rather than solved (per search-result excerpt).
- No production engineering write-up with measured guard results surfaced. Vendor claims encountered were unverified and are excluded.

## 3. Vietnamese-specific: diacritic restoration, spelling correction, syllable dictionaries, datasets

### Takeaway
Vietnamese evidence is thin and mostly about other tasks: typing errors, handwriting OCR, or historical books. No BARTpho or ViT5 post-OCR result with CER was found. A syllable checker will structurally miss many é-for-ê errors because they form valid syllables, so the current error rate is a lower bound.

### Cited Findings
- Survey (2025) results on line-level VNOnDB-OCR: AED baseline CER 4.67, WER 13.33; statistical language model 4.17/9.82; BLSTM NMT WER 11.5; unsupervised hill climbing 4.13/9.47. Competition best CER 1.02, WER 2.02 with a syllable trigram on VTB. These methods give small CER gains. The survey says lack of unified metrics and datasets makes comparison hard, and that Vietnamese lacks specialized document-analysis LLMs — [Le et al.](https://arxiv.org/html/2506.05061v1)
- Do et al., AAAI 2025 (VieBookRead; 25,585 pages; 1850–2003 books): reference-based GPT-4o mini correction scored mean 8.72 vs 7.03 for Tran et al. 2021 spelling correction in human grading (450 of 1,025 planned samples, 10-point scale). This is a human score, not CER, and needs an ebook reference that legal documents may or may not have. OCR-level CER/WER on this data: Azure DI 0.04/0.13, GPT-4o 0.05/0.11, Google Doc AI 0.07/0.14, fine-tuned Tesseract 0.09/0.18, base Tesseract 0.14/0.27, fine-tuned Donut 0.15/0.44, EasyOCR 0.25/0.59. The paper notes "con ga" alone yields 18×18 diacritic combinations. Encoding inconsistencies in older ebooks required re-encoding — [arXiv](https://arxiv.org/html/2410.13305v1)
- VSEC (older, 2021): Transformer spelling correction detected 86.8% and corrected 81.5% of 11,202 human-made misspellings across 9,341 sentences. Not OCR errors — [arXiv](https://arxiv.org/abs/2111.00640)
- Hierarchical Transformer (older, 2021): claims to beat contemporaries; abstract gives no figures — [arXiv](https://arxiv.org/abs/2105.13578)
- Diacritic restoration from accent-free text (older, 2017): phrase-based MT 97.32% accuracy, neural MT 96.15% — [arXiv](https://arxiv.org/abs/1709.07104)
- BARTpho's only OCR-adjacent use found is the 2026 two-stage administrative spelling pipeline above (metrics not read) — [VNU JCSCE](https://jcsce.vnu.edu.vn/index.php/jcsce/article/view/7020). Base model paper: [BARTpho](https://arxiv.org/pdf/2109.09701).
- A lightweight diacritic-aware Vietnamese baseline reports CER, WER, diacritic error rate and exact word accuracy, per search abstract. The page body would not load, so values and the metric definition are unknown — [Research Square preprint](https://www.researchsquare.com/article/rs-10241038)
- Syllable inventory: Hoàng Phê (1995) spelling dictionary, 6,760 syllables in writing and 6,616 in phonology, as cited in a 2000 ACL paper (older) — [P00-1076](https://aclanthology.org/P00-1076.pdf). Tools found, not evaluated: [ctnx syllable parser](https://chiecthuyenngoaixa.readthedocs.io/en/stable/generated/ctnx.syllable.html), [Rust `vi` validator](https://docs.rs/vi), [hunspell-vi](https://awesome.ecosyste.ms/projects/github.com%2F1ec5%2Fhunspell-vi).

### Inferences
- **The checker is partly blind to the exact residual error.** From my knowledge of Vietnamese orthography (please verify by running each substitution through the project's checker): `về→vé`, `kết→két`, `hết→hét`, `thể/thế→thé`, `hệ→hé`, `nghề→nghé`, `lệ→lé` yield valid syllables and pass. `tiếp→tiép`, `quyết→quyét`, `điều→điéu` and `mệnh→ménh` are not valid and get flagged. So detection covers mainly ê inside iê/uyê or before -nh/-ch. Reported rates are lower bounds, and the "about 54 documents" list may omit documents whose errors are mostly the valid-syllable kind. A quick test: enumerate all syllables with ê-family vowels, substitute é, and compute the share that passes. Then count real-word pairs by corpus frequency.
- Restoration models are the wrong tool at document level. A model with about 97% accuracy on stripped text would add errors if run over text already above 99% correct. Use one only at flagged positions and only with the folded-token guard above. Its older accuracy figure also came from accent-free input, a different task.
- Context language models can rank candidates cheaply: a syllable n-gram model built from the corpus's clean documents can score `về` vs `vé` at each suspect position, since legal language is repetitive. High-confidence, frequent pairs ("về việc") could be patched this way, leaving the rest for image review. The earlier "cannot be fixed mechanically" stands for ambiguous tokens, but the ambiguous share may be small. This is testable and I found no published number for it.
- VNOnDB is, from its name and competition context (VOHTR 2018), a handwriting dataset, so survey figures say little about printed legal scans.

### Gaps
- No Vietnamese legal OCR gold dataset or post-OCR benchmark found.
- No 2024–2026 peer-reviewed Vietnamese diacritic restoration accuracy figure opened; ViT5 spelling or OCR correction results not found.
- No Gemini or Gemma post-OCR CER on Vietnamese.
- No published measure of é vs ế/ề/ể/ệ confusion, or of how often Vietnamese syllable checkers miss real-word OCR errors.
- A [Vietnamese administrative spelling study using LLMs](https://www.vjol.info.vn/DHM-TPHCM/en/article/view/92989) exists, but the page could not be loaded (redirect loop).

## 4. Measuring quality without ground truth and building a small gold set

### Takeaway
GT-free signals can rank pages for triage but cannot deliver a trustworthy error rate: the best recent benchmark reaches only about ρ = 0.5. A stratified gold set of roughly 40–120 pages, with separate token-level audits for numbers and é-suspects, is enough for a go/no-go decision. Use NFC plus grapheme-aware scoring and report diacritic and base-letter errors separately.

### Cited Findings

**GT-free**
- Reference-free render-and-compare OCR metrics, 147 method implementations on 1,355 pages: naive CLIP ρ = 0.339, best composite ρ = 0.494, peak 0.605 on formula-only — [Singh, NeurIPS 2026 poster](https://neurips.cc/virtual/2026/poster/139231)
- Luxembourg National Library (BnL): text-only features (dictionary-match ratio, trigram rank similarity, garbage-token rules, publication year) drive a quality classifier and an improvement regressor (MAE 0.034; size-weighted 0.024) — [BnL paper](https://arxiv.org/html/2110.01661v5)
- Multi-model disagreement beats asking a model to judge: F1 48.0–51.3 vs 36.1–40.0 — [CE-OCR](https://arxiv.org/html/2504.11101v3)
- Valid-word errors from vision models are harder to detect — [Vesalainen et al.](https://arxiv.org/html/2602.14524v1)

**Tools**
- dinglehopper: CER and WER; reads ALTO, PAGE XML and plain text; word- and character-level diff reports — [GitHub](https://github.com/qurator-spk/dinglehopper). For plain strings it applies NFC, splits into grapheme clusters with `uniseg`, and computes d/n over clusters — [source](https://raw.githubusercontent.com/qurator-spk/dinglehopper/master/src/dinglehopper/character_error_rate.py)
- jiwer: WER, MER, WIL, WIP, CER. Its documentation page does not mention Unicode normalization or grapheme clusters — [docs](https://jitsi.github.io/jiwer/)
- ocreval: 17 tools, ISRI port with UTF-8 through utf8proc. Copyright notice through 2021 and old CI badge suggest low activity — [GitHub](https://github.com/eddieantonio/ocreval)

**Metric practice**
- Report median and catastrophic rate alongside mean, use real scans rather than synthetic renders, apply NFC, use grapheme-aware scoring because code-point CER understates structural errors — [Devanagari study](https://arxiv.org/html/2606.29213)
- HIPE: cMER = (S+D+I)/(H+S+D+I), bounded in [0,1]; sign-based preference score (how consistently units improve vs degrade); 95% bootstrap CI over 10,000 resamples. Baseline-relative gains are more informative than absolute scores — [report](https://arxiv.org/html/2607.08143v1)
- Normalization changes conclusions: GPT-4o's Finnish gain would have been negative without it — [Kanerva et al.](https://arxiv.org/html/2502.01205v1). Best run: strict CER 1.91 vs normalized 0.84 — [Greif et al.](https://arxiv.org/html/2504.00414)
- Error reduction formula used at corpus level: (1 − ER_corrected/ER_original)×100 — [Thomas et al.](https://aclanthology.org/2026.findings-emnlp.60.pdf)

**Agreement and human noise floor**
- Yiddish OCR corpus (658 pages): 3 separately double-annotated pages; Krippendorff's alpha with CER as the distance (Levenshtein / max length): 0.977 with all diacritics, 0.992 with reduced diacritics. Diacritics visibly lower agreement. Three pages is a very small sample — [Jochre 3](https://arxiv.org/html/2501.08442)
- Double-keying audit (older, 2013): 7,208 pages, about 9.94M characters, 99.9909% accuracy, 830 transcription errors, 24 stratified categories — [Haaf et al.](https://journals.openedition.org/jtei/739)
- Rule of three: zero events in n trials gives a 95% upper bound of about 3/n — [Wikipedia](https://en.wikipedia.org/wiki/Rule_of_three_(statistics))

### Inferences

**Sample size (my calculations; normal approximation, z = 1.96, assumptions stated)**

| Goal | Formula inputs | Result |
|---|---|---|
| CER ≈ 1%, ±0.2% | independent characters | 9,508 chars |
| Same, clustered in pages | design effect 5 / 10 / 20 (assumed) | 47.5k / 95k / 190k chars |
| CER ≈ 1%, ±0.5% | design effect 5 / 10 / 20 | 7.6k / 15k / 30k chars |
| CER ≈ 0.3%, ±0.1% | design effect 5 / 10 / 20 | 57k / 115k / 230k chars |
| Share of flagged docs (N=54), ±15% / ±10%, p=0.5, finite correction | documents | 24 / 35 |
| Share of remaining docs (N≈400), ±15% / ±10% | documents | 39 / 78 |
| Rare class in remaining docs, p≈10%, ±5% | documents | 103 |
| Zero wrong tokens in 500 / 1,000 / 3,000 audited | rule of three | <0.6% / <0.3% / <0.1% |

The design effect is a guess; errors cluster by page and document, so estimate it from the pilot rather than trusting independent-character counts. At an assumed 2,500 characters per page, 95k characters is about 40 pages.

**Practical design**
1. **Strata**: flagged (≥1%, 54 documents), borderline (0.3–1%), apparently clean. Add a stratum for any layout or source that differs: tables, signature blocks, annexes.
2. **Pilot gold set (about 40 pages)**: 20 flagged, 10 borderline, 10 clean, one or two pages per document, chosen at random. Scale to about 120 pages only if the decision stays unclear.
3. **Transcribe from the page image, double-key about 10–20% of pages independently**. Editing OCR text is faster but can anchor annotators to its errors, especially where é and ế look alike. Write a short guideline covering tone mark placement (`hoà` vs `hòa`), line breaks and tables before starting.
4. **Agreement**: report inter-annotator CER, and alpha with CER as the distance as in the Yiddish corpus, separately for all characters and diacritic-folded. Adjudicate differences. If annotators disagree at the level of the OCR error you are measuring, the gold set cannot settle the question.
5. **Metrics per stratum**, with bootstrap CIs by document: strict CER (NFC, graphemes); base-letter CER after folding; diacritic error rate as the difference or as errors on aligned same-base characters; WER; syllable real-word error rate; an ê-family confusion matrix; median and worst page.
6. **Field-level audits**, independent of the page sample: 500–1,000 digit tokens and citations, drawn randomly and from flagged spans, checked against the image; document number, date, issuing body and signer per sampled document; 300 random é-suspects to establish how many are errors. Compare with the official text where one exists.
7. **Before/after evaluation must be on held-out pages**: paired by document, with the preference score. Count *new* errors introduced, separately from errors fixed. The team's correction step can be evaluated retrospectively if raw OCR was kept.
8. **Calibrate the checker**: regress gold CER on checker rate. This turns the syllable checker into an estimator with known bias across all 454 documents and gives an estimate of what it misses.

### Gaps
- No published sample-size guidance specifically for OCR gold sets was found. The table above is my standard-statistics derivation.
- No published Vietnamese diacritic-sensitive CER standard; the Research Square definition was not readable.
- No typical inter-transcriber CER across collections, and no published field-level OCR accuracy benchmark for legal citations.
- jiwer's and dinglehopper's handling of Vietnamese was not tested. Recommendation: run a small unit test, such as NFC vs NFD input for `ế`, before relying on them.

## 5. Cost/benefit: re-OCR vs post-correction; subset vs whole corpus

### Takeaway
No published threshold fits this case, and I found no comparable cost data. The evidence favours targeted reprocessing at page or token level: low-noise text gains little and carries over-correction risk, and image-grounded correction beat image-only re-OCR in both studies that compared them. Whole-corpus re-cleaning looks hard to justify unless the gold set shows that the checker is seriously undercounting errors.

### Cited Findings
- Image+OCR correction beats re-transcription: 92.03/89.27% vs 83.49–84.27% image-only for the same fine-tuned VLMs, vs 52.32% for pretrained PaddleOCR-VL — [Thomas et al. 2026](https://aclanthology.org/2026.findings-emnlp.60.pdf). Gemini strict CER 1.91 with OCR vs 2.08 image-only (a small gap); GPT-4o 2.17 vs 7.19 (a large gap) — [Greif et al.](https://arxiv.org/html/2504.00414). The advantage clearly depends on the model.
- If the engine differs, re-OCR choice matters: Azure DI 0.04, Tesseract 0.14, EasyOCR 0.25 CER on Vietnamese books — [Do et al.](https://arxiv.org/html/2410.13305v1)
- Selective re-OCR at scale (older, 2021, revised later): BnL reprocesses a block if predicted improvement ≥ θ, with θ between 0 and 0.05 recommended for its data. A higher θ cuts degradation risk but selects fewer blocks. Assessment took under 5% of OCR compute; first run was 566,000 pages in about 15 days using a classifier at θ=0.95. Stated goal is both lower compute and lower degradation risk — [BnL](https://arxiv.org/html/2110.01661v5)
- Gain scales with noise: 27.5% at low noise vs 85% at high noise in HIPE (computed) — [HIPE](https://arxiv.org/html/2607.08143v1). An already accurate pipeline lost heavily from LLM correction (Marker on clean scans 99.56→51.66) — [Gómez Rey et al.](https://arxiv.org/html/2608.24976v1). BnF-Mistral routes only CER >15% to a larger model — [HIPE](https://arxiv.org/html/2607.08143v1)
- Downstream: in OHRBench (8,561 images in seven domains including Law; 8,498 Q&A), semantic OCR noise had the largest impact. Under severe perturbation (ratio >0.6), performance dropped nearly 50% for most retrievers and LLMs. Best OCR F1 31.1 vs 36.1 with ground-truth structure. This addresses severe noise, not 1% CER — [Zhang et al.](https://arxiv.org/html/2412.02592)
- Error structure matters: aggregate accuracy hides downstream risk, so model choice should follow explicit error-risk analysis — [Vesalainen et al.](https://arxiv.org/html/2602.14524v1)
- Validate on representative samples before large-scale use — [Gómez Rey et al.](https://arxiv.org/html/2608.24976v1)

### Inferences

**First, a low-cost diagnostic:** check whether é errors cluster by source file, scan batch, font or OCR engine. Heavy clustering suggests a systematic source (engine weakness, low resolution, font, legacy encoding), so re-OCR or a different engine for that batch is likely better than correcting tokens. Scattered errors favour token-level image review. Also check whether any flagged PDFs have a usable text layer or an official digital copy; replacing a document with an authentic source beats either method.

**Decision criteria (suggested starting values, not published thresholds; set final values from the gold set):**

| Situation found on gold set/diagnostic | Action |
|---|---|
| Strict CER <0.3% and no digit or citation errors in the audit | Leave alone; LLM pass has more downside than upside |
| Errors are mostly é-family, scattered, diacritic-only | Token-level patch: n-gram for confident cases, image+OCR on suspects, folded-token guard, human review for the remainder |
| CER ≥ about 1%, mixed errors, clustered by batch or engine | Re-OCR those pages with the best engine shown by a pilot, then compare per page and keep the better result |
| Digit or citation errors found at any material rate | Priority on those documents regardless of CER; verify against official sources |
| Gold CER far above checker rate in "clean" stratum (undercount) | Widen scope beyond the 54; expand gold set before re-cleaning everything |
| New pipeline introduces more errors than it fixes on held-out pages, or any invariant failure gets through | Do not ship |

**Whether to proceed:** measure retrieval and citation effects as well. Run a set of real queries and test questions over raw and corrected versions of the flagged documents. If the eval doesn't move, a re-clean is justifiable mainly on text accuracy and citation trust. In a legal corpus that can still be sufficient, especially when text is displayed to users, but it should be a conscious decision. Errors on high-frequency function words like `về` may not affect retrieval much, whereas errors in citation numbers or names would.

**Default recommendation given current evidence:**
1. Keep the existing output as baseline and do not re-run the whole corpus.
2. Week-scale pilot: the 40-page gold set, checker calibration, digit/citation audit and é-suspect audit.
3. Run guarded image+OCR correction only on suspect spans of the 54 documents, plus any others the calibration implicates.
4. Evaluate on held-out pages. Promote changes per page only when they pass. Keep versioned raw, corrected and diff, so any change can be rolled back and audited.

### Gaps
- No published dollar or time cost comparison of re-OCR vs correction per page; budget must come from a local pilot with current Gemini pricing, which was outside this research.
- No published OCR-quality threshold at which legal retrieval or RAG suffers. OHRBench addresses severe perturbation only. The effect of about 1% diacritic-only CER on Vietnamese embedding retrieval is unmeasured as far as I could find.
- No head-to-head study of re-OCR vs image-grounded correction on Vietnamese.
