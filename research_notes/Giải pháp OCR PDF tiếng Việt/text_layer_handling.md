# Text-layer handling for born-digital and corrupted PDFs (as of November 2026)

Scope note. Sources were opened unless marked "search snippet, not opened". Figures labelled "local simulation" were computed in this session from the vietunicode table and the repo's cleaned corpus. They are not third-party results. No source PDF was available locally (`data/raw/pdf` is referenced by `data/manifest.jsonl` but absent), so nothing here was tested on the team's real PDFs.

**Most important finding for the team (detail under the third question).** The garbage quoted in the repo does not look like VNI/TCVN3 output. Legacy fonts give `nghÞ ®Þnh sè` or `nghò ñònh soá`, not `Ngh/ d/nh sO'`. The same words also come out differently (`DI HOC` and `031 HQC`), which looks like an old OCR layer from an engine without Vietnamese. This is an inference, and it can be tested per file in minutes.

## Which extractors are best now, and what do benchmarks show on accuracy, speed, reading order, two-column layouts and tables?

### Takeaway
For plain text from a healthy layer, PyMuPDF and pypdfium2 tie at the top of the only benchmark covering the low-level libraries, while pdfplumber is the slowest and lowest. For reading order the structured parsers sit in a narrow band (about 0.86-0.93 NID), and tables separate them far more (TEDS about 0.40-0.93). No benchmark found tests Vietnamese or legacy-font PDFs, and most are vendor-run, so a better extractor alone will not fix this corpus.

### Cited Findings

**Low-level libraries (py-pdf/benchmarks: 14 PDFs, 425 pages; repo last commit 2026-11-06).** Speeds are normalised estimates, and the corpus is small — [py-pdf/benchmarks](https://github.com/py-pdf/benchmarks)

| Library | Version | Avg. time | Text score |
|---|---|---|---|
| pypdfium2 | 5.15.0 | 0.1 s | 95% |
| PyMuPDF | 2.1 | 0.1 s | 95% |
| pypdf | 7.0.0 | 1.8 s | 95% |
| Tika | 3.3.2 | 0.2 s | 94% |
| pdftotext (Poppler) | 24.02.0 | 0.3 s | 90% |
| pdfminer.six | 20260107 | 3.5 s | 89% |
| pdfplumber | 0.11.10 | 5.6 s | 74% |

- The benchmark's Poppler (24.02.0) is much older than the current release, 26.11.0 of 5 Nov 2026 — [Poppler releases](https://poppler.freedesktop.org/releases.html)
- pypdfium2 does no layout analysis (no words, lines or paragraphs), and PDFium usually emits CRLF line breaks. Docs show helpers 5.15.1 and PDFium 159.0.8138.0 — [pypdfium2 docs](https://pypdfium2.readthedocs.io/en/stable/python_api.html)

**Structured parsers (opendataloader-bench: 200 PDFs; the page gives no engine versions, hardware or date, only a "© 2026" footer).** — [opendataloader-bench](https://github.com/opendataloader-project/opendataloader-bench)

| Engine | Overall | Reading order (NID) | Tables (TEDS) | Headings (MHS) | s/page | License as listed |
|---|---|---|---|---|---|---|
| opendataloader [hybrid] | 0.907 | 0.934 | 0.928 | 0.821 | 0.463 | Apache-2.0 |
| nutrient | 0.885 | 0.925 | 0.708 | 0.819 | 0.008 | Commercial |
| docling | 0.882 | 0.898 | 0.887 | 0.824 | 0.762 | MIT |
| marker | 0.861 | 0.890 | 0.808 | 0.796 | 53.932 | GPL-3.0 |
| unstructured [hi_res] | 0.841 | 0.904 | 0.588 | 0.749 | 3.008 | Apache-2.0 |
| edgeparse | 0.837 | 0.894 | 0.717 | 0.706 | 0.036 | Apache-2.0 |
| opendataloader | 0.831 | 0.902 | 0.489 | 0.739 | 0.015 | Apache-2.0 |
| mineru | 0.831 | 0.857 | 0.873 | 0.743 | 5.962 | AGPL-3.0 |
| pymupdf4llm | 0.732 | 0.885 | 0.401 | 0.412 | 0.091 | AGPL-3.0 |
| unstructured | 0.686 | 0.882 | 0.000 | 0.388 | 0.077 | Apache-2.0 |
| markitdown | 0.589 | 0.844 | 0.273 | 0.000 | 0.114 | MIT |
| liteparse | 0.576 | 0.866 | 0.000 | 0.000 | 1.061 | Apache-2.0 |

- Marker and MinerU results on that leaderboard are preserved predictions, because their parser code was removed from the repo. pdfplumber, pypdfium2 and Poppler are not on it — [opendataloader-bench](https://github.com/opendataloader-project/opendataloader-bench)
- Corpus types include multicolumn policy reports, papers, legal and regulatory reports with styled tables, and sidebar handouts. TEDS is scored on 42 documents and MHS on 107. The share of scanned documents is not reported — [Nutrient](https://www.nutrient.io/blog/pdf-extraction-benchmark-opendataloader-bench.md)
- **Conflict.** The same pymupdf4llm version (1.28) scores 0.86 overall / 0.73 TEDS / 0.78 MHS in Nutrient's M3 Ultra run — [Nutrient](https://www.nutrient.io/blog/pdf-extraction-benchmark-opendataloader-bench.md). It scores 0.732 / 0.401 / 0.412 in LlamaIndex's table — [LlamaIndex, 22 Sep 2026](https://www.llamaindex.ai/blog/liteparse-updates-september-2026). Neither source explains the gap.
- Nutrient's run also gives Docling 2.110.0 about 0.89 overall and 0.93 TEDS, and Nutrient's own Standard engine 0.89 at 0.004 s/page. Nutrient is the benchmarked vendor, and its Vision result is "not independently verified" — [Nutrient](https://www.nutrient.io/blog/pdf-extraction-benchmark-opendataloader-bench.md)

**olmOCR-Bench (1,403 PDFs).**
- Marker's self-reported table — [Marker README](https://raw.githubusercontent.com/datalab-to/marker/master/README.md):

| System | Overall | Digital-only | Throughput |
|---|---|---|---|
| Chandra 2 (hosted) | 85.8 | not given | not given |
| Marker balanced | 76.0 | 83.5 | 2.9 pg/s GPU |
| MinerU pipeline | 72.7 | 83.3 | 0.54 pg/s GPU |
| Marker fast | 66.6 | 71.6 | 7.4 pg/s GPU |
| docling | 50.3 | 64.0 | 2.1 pg/s GPU |
| Marker fast, no OCR | 43.6 | 55.8 | 23.7 pg/s CPU |
| liteparse, no OCR | 20.4 | 25.0 | 1721 pg/s CPU |

- AI2's table shows the "Multi column" category: olmOCR v0.4.0 83.7, Chandra 0.1.0 81.2, Marker 1.10.1 80.0, PaddleOCR-VL 79.9, MinerU 2.5.4 78.2. Overall: Chandra 83.1, olmOCR 82.4, Marker 76.1, MinerU 75.2. Versions differ from Marker's table, and MinerU's overall differs (75.2 against 72.7) — [olmOCR README](https://github.com/allenai/olmocr)
- With OCR off, LlamaIndex reports pymupdf4llm 1.28 (layout on) at 37.3 overall and 60.3 on tables, LiteParse 2.14.6 at 39.6, pdf-inspector 1.19 at 33.7. Its markdown speeds are LiteParse 3.94, pdf-inspector 5.72, opendataloader 24.15, pymupdf4llm 140.80, markitdown 191.07 ms/page. These are the vendor's own figures, and on 200-document opendataloader-bench it reports LiteParse 2.14.6 at 0.886 with TEDS 0.818 — [LlamaIndex](https://www.llamaindex.ai/blog/liteparse-updates-september-2026)

**ParseBench (about 2,000 enterprise pages, 14 methods).** LlamaParse Agentic leads at 84.88 overall. Content Faithfulness: LlamaParse Agentic 89.68, Dots OCR 1.5 90.0, Reducto 86.4, Docling 66.9. Tables: LlamaParse Agentic 90.74, Docling 66.4. The authors use runllama.ai email addresses and rank their own product first, and no PyMuPDF-type extractor was tested — [ParseBench](https://arxiv.org/html/2604.08538)

**Independent academic check.** On Visigothic historiography PDFs (13 pipelines), Marker direct extraction reached 98.70% CER accuracy and 97.71% WER accuracy. Embedded-text extraction worked on digital PDFs but failed on scans, and LLM post-correction "often degraded accurate extractions". Abstract only; per-category figures not read — [arXiv 2608.24976](https://arxiv.org/abs/2608.24976)

**Current releases (GitHub API, checked 9 Nov 2026).** [Docling](https://github.com/docling-project/docling/releases) v2.149.0 (8 Nov 2026), [MinerU](https://github.com/opendatalab/MinerU/releases) 4.1.7 (4 Nov 2026), [Marker](https://github.com/datalab-to/marker/releases) v2.1.0 (29 Oct 2026), [olmOCR](https://github.com/allenai/olmocr/releases) v0.4.27 (12 Mar 2026). [pymupdf4llm](https://github.com/pymupdf/pymupdf4llm/releases)'s latest GitHub release is tagged v0.3.4 (14 Feb 2026), which does not match the "1.28" version quoted in benchmarks, and I did not resolve this.

**Licensing.** Marker's code is now described as Apache 2.0, with weights under a modified RAIL-M licence free for research, personal use and startups under $5M — [Marker README](https://raw.githubusercontent.com/datalab-to/marker/master/README.md). opendataloader-bench still lists it as GPL-3.0 — [opendataloader-bench](https://github.com/opendataloader-project/opendataloader-bench).

### Inferences
- Keep PyMuPDF for fast text and spans, since its 95% score equals pypdfium2 at the same speed. The AGPL licence matters only if the code is distributed or served. pdfplumber is worth using only for targeted table and form geometry.
- Reading-order spread is small, so reading order is a weak reason to switch parser. Table extraction is the strong reason (Docling or MinerU, per their TEDS). The Vietnamese legal header (issuing body left, national motto right) is a two-column block worth adding to a local evaluation.
- Marker's 53.9 s/page against 2.9 pg/s almost certainly reflects different hardware, but the leaderboard page does not state it, so the two numbers should not be compared.

### Gaps
- No benchmark found covers Vietnamese, legacy-font PDFs or corrupted layers. All numbers above describe healthy or English-dominant documents.
- No independent 2026 head-to-head was found with pdfplumber, pypdfium2 and Poppler alongside Docling, Marker and MinerU on one corpus.
- A dedicated two-column metric exists only in olmOCR-Bench. PyMuPDF `get_text()` ordering on Vietnamese two-block headers was not tested.

## How do modern tools detect a bad text layer and route per page, and which metrics are used?

### Takeaway
Tools mostly use language-agnostic structural signals (CID codes, U+FFFD, control or private-use characters, whitespace and letter ratios, vowel share). These catch unmapped fonts but explicitly miss "right alphabet, wrong letters", which is exactly the team's example. OCR-versus-layer comparison is the strongest signal seen, and Vietnamese needs a language-specific check on top, so the team's diacritic score remains useful but should run per page with extra checks.

### Cited Findings

**Docling**
- `replace_broken_text_layer` (off by default, CLI `--replace-broken-text-layer`) replaces flagged pages with OCR and leaves the others alone. The docs state it "cannot detect a page whose text uses the right alphabet but the wrong letters", for which they point to `mode=OcrMode.FULL_PAGE` — [Docling OCR docs](https://github.com/docling-project/docling/blob/main/docs/concepts/OCR.md)
- `is_broken_text_layer` thresholds: minimum 20 characters; junk (control, surrogate, private-use, U+FFFD) at 3% of characters or more; junk in at least max(3, 10% of) lines; for Latin text, at least 50 letters with accented share at 0.5 or more; or at least 200 word letters with vowel share under 0.25. It returns False when unsure — [text_quality.py](https://github.com/docling-project/docling/blob/main/docling/utils/text_quality.py)
- A low `parse_score` alone does not replace a page. `force_full_page_ocr` is deprecated in favour of `mode=OcrMode.FULL_PAGE`. `DEFAULT` runs `PDF_AWARE_LAYOUT_REGIONS` — [pipeline_options.py](https://raw.githubusercontent.com/docling-project/docling/main/docling/datamodel/pipeline_options.py)
- Issue #2963 (opened 8 Feb 2026) still shows as open without maintainer replies, even though the option above now exists. Community comments propose reason codes per page, flagging Caesar-shifted text, and an offset-inference repair said to recover about 99.4% of codes — [Docling #2963](https://github.com/docling-project/docling/issues/2963)

**Marker**
- It decides per page whether embedded text is usable. Balanced mode re-OCRs the whole page if any embedded text is bad. Fast mode repairs individual blocks and runs a full-page pass only on scanned or mostly bad pages. README recommends `--force_ocr` for garbled text — [Marker README](https://raw.githubusercontent.com/datalab-to/marker/master/README.md)
- `detect_bad_ocr` flags text as bad if whitespace ratio exceeds 0.7, newline ratio exceeds 0.6, alphanumeric ratio falls below 0.3, or invalid characters exceed max(6, 3% of length). A page with no text objects is also rejected — [marker/providers/pdf.py](https://raw.githubusercontent.com/datalab-to/marker/master/marker/providers/pdf.py)
- Flagged blocks are OCRed unless of a skipped type (Figure, Picture, Diagram, Table, Form, TableOfContents) — [marker/builders/ocr.py](https://raw.githubusercontent.com/datalab-to/marker/master/marker/builders/ocr.py)

**MinerU**
- In release 2.7.6, routing is per document: up to 10 sampled pages; OCR if under 50 cleaned characters per page, more than 5% `(cid:N)` per pdfminer, or high-image-coverage ratio of 0.8 or more; any exception defaults to OCR — [pdf_classify.py @ release-2.7.6](https://github.com/opendatalab/MinerU/blob/release-2.7.6/mineru/utils/pdf_classify.py)
- In current master that file is gone. Tests show `Document.classify()` used in `auto` mode with DocVortex — [test_docvortex_routing.py](https://github.com/opendatalab/MinerU/blob/master/tests/unittest/test_docvortex_routing.py). I did not verify whether the thresholds carried over.

**PyMuPDF4LLM**
- `analyze_page` computes per-page image, text and vector coverage plus the area of spans with bad characters. `BAD_CHAR_THRESHOLD` is 0.10, an ONNX `ocr_decision_model` decides, and `needs_ocr` is true at probability 0.93 or more (`PYMUPDF_OCR_MODEL_THRESHOLD`) — [analyze_page.py](https://github.com/pymupdf/pymupdf4llm/blob/main/src/ocr/analyze_page.py)
- `TEXT_USE_CID_FOR_UNKNOWN_UNICODE` is on by default, so PyMuPDF returns raw codes rather than U+FFFD. Turn it off to scan for U+FFFD — [PyMuPDF constants](https://pymupdf.readthedocs.io/en/latest/vars.html)

**olmOCR**
- The document filter is not a quality gate: it samples the first five pages via `pdftotext`, and keeps under 200 characters or under 50% letters as "may be OCR". It then applies Lingua language detection and SEO-spam checks (threshold 0.004), and removes fillable forms — [filter.py](https://raw.githubusercontent.com/allenai/olmocr/main/olmocr/filter/filter.py)
- It works from rendered page images, and `--target_anchor_text_len` (the embedded-text hint) is "not used for new models". Vietnamese is not mentioned, and it needs a GPU with 12 GB or more — [olmOCR README](https://github.com/allenai/olmocr)

**OCRmyPDF.** No quality metric is documented. Users choose a mode: `force` rasterises everything and is recommended "for fixing OCR text with a damaged character map"; `skip` leaves text pages; `redo` strips invisible text — [OCRmyPDF advanced](https://ocrmypdf.readthedocs.io/en/latest/advanced.html)

**Lighter routers and low-level signals**
- LiteParse `lit is-complex` reports per page whether it is scanned, text coverage, garbled status and whether OCR is needed, at about 3.5 ms/page (vendor figure) — [LlamaIndex](https://www.llamaindex.ai/blog/liteparse-updates-september-2026)
- pdf-inspector (MIT) reads `Tj`/`TJ` and `Do` operators without loading the whole document, returns `TextBased/Scanned/ImageBased/Mixed` and `pages_needing_ocr`, and flags broken font encodings. Claimed 10-50 ms classification — [pdf-inspector](https://github.com/firecrawl/pdf-inspector)
- PDFium has `FPDFText_HasUnicodeMapError`, marked "Get if a character in a page has an invalid unicode mapping" — [fpdf_text.h](https://pdfium.googlesource.com/pdfium/+/refs/heads/main/public/fpdf_text.h)
- Poppler `pdffonts` shows `uni` = "yes" when an explicit ToUnicode map exists, and a missing map does not necessarily mean text cannot be converted — [pdffonts man page](https://manpages.debian.org/testing/poppler-utils/pdffonts.1.en.html)

**Metrics beyond structure**
- *OCR versus layer.* cheapshot PR #3 keeps the layer only if no OCR line is missing. A line (4+ words) counts as missing when over 50% of its word pairs are absent from the layer, after folding accents. Good layers scored 0.4 or less, dropped lines 0.7-1.0. Word counts: garbled 328 to 2,917, control unchanged at 3,264 bytes-identical. Cost about 0.25 s/page; test PDFs unnamed, and a small project — [cheapshot PR #3](https://github.com/all-caps-dev/cheapshot/pull/3)
- *Dictionary or n-gram plausibility.* An extractous issue proposed word-plausibility by dictionary or n-gram. The merged version uses a unigram model only for constant-offset maps, and explicitly leaves out wrong-but-plausible text. Claimed recall 1.000 and no false triggers on its own scoreboard. Records `metadata.rejected_text_layers` with the reason — [extractous #29](https://github.com/stubbedev/extractous/issues/29)
- It also uses Tika's `pdf:unmappedUnicodeCharsPerPage`, `pdf:charsPerPage` and `pdf:containsDamagedFont` — [extractous #29](https://github.com/stubbedev/extractous/issues/29)

**The team's method** (`probe` reads up to 5 pages and scores them jointly; `VI_SCORE_OK = 0.15`; returns -1.0 under 200 letters) — [pdf_text.py](../../src/vanban/clean/pdf_text.py). Project measurements: clean about 0.25, broken 0.00-0.09; 27 good layers and 184 broken across 501 files — [PIPELINE_TU_DONG.md](../../docs/PIPELINE_TU_DONG.md)

**Local simulation (not third-party).** 150 documents from `data/clean/text_final` (first 6,000 characters each), encoded with the [vietunicode table](https://vietunicode.sourceforge.net/charset/) and read as cp1252. TCVN3 text was lowercased first, because the table's capitals are only illustrative. "Syllable hit" uses a 1,457-token lexicon built from half the sample and scored on the held-out half, so it is an indication only.

| Text | `vietnamese_score` median (min-max) | Syllable hit (median) | Accented share (median) | Vowel share (median) |
|---|---|---|---|---|
| Clean | 0.302 | 0.996 | 0.146 | 0.410 |
| VNI | 0.108 (0.087-0.143) | 0.150 | 0.273 | 0.528 |
| VPS | 0.102 (0.079-0.132) | 0.552 | 0.251 | 0.369 |
| VISCII | 0.099 (0.073-0.125) | 0.544 | 0.222 | 0.322 |
| TCVN3 | 0.087 (0.064-0.117) | 0.387 | 0.174 | 0.313 |

- All-simulated legacy text scored under 0.15, so the threshold held, but VNI's maximum (0.143) is close. Mojibake scores above zero because Latin-1 letters such as á, ò, ù are in the Vietnamese set.
- Re-computing Docling's published accented, vowel and junk thresholds with my own code flagged 0/150 for VNI, VPS and VISCII, 1/150 for TCVN3, 0/150 for diacritic-stripped text. The repo sample is far too short for the minimum-letter gates (its 0.0 vowel share rests on two qualifying tokens), so it would not be judged at this length. I did not execute Docling's own module (blocked by a permission rule), and I did not reproduce its line-level check.
- The syllable hit is inflated for mojibake, because tokenising on non-letters splits words into short valid fragments. The repo's short sample scored 0.467 on the same measure.

### Inferences
- Docling's `replace_broken_text_layer` will likely not catch this corpus on its own. Use `FULL_PAGE` or the team's own router instead.
- A diacritic share alone has two blind spots: right-looking accents on wrong letters, and a whole document averaged across pages. The sampling of 5 pages also misses later pages with different fonts, so a per-page decision is safer.
- Suggested stack, cheapest first:
  1. Per-page structure: hidden-text share, image coverage, `pdffonts`-style font list, U+FFFD and control characters.
  2. Fingerprint legacy encodings (next question).
  3. Syllable hit and diacritic score per page, with a proper lexicon.
  4. For the uncertain band, and a sample of accepted pages, OCR the page and compare with the layer without folding accents. Folding as cheapshot does would hide exactly the Vietnamese failure.
  5. Record the reason per page, as extractous does.
- Protect digits and legal identifiers such as document numbers separately, because diacritic metrics say nothing about `2347/QĐ-ĐHBK`.

### Gaps
- Nobody found publishes a validated dictionary or language-model threshold for Vietnamese text layers. The 0.15 threshold and any syllable-hit threshold must be calibrated locally.
- The count of valid Vietnamese syllables and a citable lexicon were not found.
- Thresholds in Marker, Docling and PyMuPDF4LLM come from current source and may change. Their real recall on Vietnamese is unmeasured.

## Can legacy Vietnamese encodings be converted deterministically, and when is information already lost?

### Takeaway
Yes, if the extractor still gives the original font bytes or codes: the VNI, VPS, VISCII and TCVN3 tables are one-to-one in the table tested, and conversion is a lookup plus font-name handling for capitals. No, if the codes were never legacy bytes or diacritics have been lost, and the team's quoted samples look like that second case, so conversion should be tried only on pages whose fingerprint matches.

### Cited Findings

**Encoding facts (older standards)**
- The vietunicode reference lists Unicode, VNI, VPS, VISCII, TCVN3 and VIQR for 134 letters. Undated page. It notes TCVN3 capitals are in a separate font, so its capital codes are illustrative only — [vietunicode charset](https://vietunicode.sourceforge.net/charset/)
- Local parse of that table: all four encodings have 134 entries and 0 duplicate byte sequences. VNI has 116 two-byte entries (`ố` = 6F E1); VPS and VISCII are single-byte, but use 14 and 6 control bytes respectively. VISCII's are 0x02, 0x05, 0x06, 0x14, 0x19, 0x1E. The VPS entry for `Ạ` is marked oddly in the source, so check it manually — [vietunicode charset](https://vietunicode.sourceforge.net/charset/)
- VISCII (RFC 1456, May 1993) is 8-bit and moved six rarely used capitals into C0 control positions — [RFC 1456](https://www.rfc-editor.org/rfc/rfc1456.txt)
- TCVN 5712:1993: VSCII-3 (TCVN3) keeps ASCII, adds 75 characters, and handles toned capitals "by switching to an all-capital font". VN1 uses 12 control codes and has 140 non-ASCII characters — [Wikipedia: VSCII](https://en.wikipedia.org/wiki/VSCII)

**Fingerprints.** Local output from the table above, read as cp1252, for "nghị định số quyết định đại học đà nẵng":

| Encoding | Expected garbage |
|---|---|
| TCVN3 | `nghÞ ®Þnh sè quyÕt ®Þnh ®¹i häc ®µ n½ng` |
| VNI | `nghò ñònh soá quyeát ñònh ñaïi hoïc ñaø naüng` |
| VPS | `nghÎ ÇÎnh sÓ quy‰t ÇÎnh Çåi h†c Çà n¤ng` |
| VISCII | `ngh¸ ð¸nh s¯ quyªt ð¸nh ðÕi h÷c ðà nÇng` |

**The repo's real samples match none of these** — [PIPELINE_TU_DONG.md](../../docs/PIPELINE_TU_DONG.md), [pdf_text.py](../../src/vanban/clean/pdf_text.py)
- `DI HOC  DA NANG`, `TR1NG 031 HQC BACH KHOA`, `QUYET BNH`, `Ngh/ d/nh sO'`
- These are pure ASCII. `ĐẠI HỌC` appears as both `DI HOC` and `031 HQC`.
- `Ị` appears as `/`, `Ọ` as `Q`, `Ố` as `O'`: shapes resemble the printed characters.

**Tools**
- UnicodeConverter handles VNI, VPS, VISCII, TCVN3, VIQR/Vietnet and NCR, plus NFD to NFC, on text, RTF, HTML and Office files. Java, Windows and .NET versions; no PDF input listed — [vietunicode how-to](https://vietunicode.sourceforge.net/howto/unicodeconversion.html)
- TCVN3 gist (Python, last active May 2026): simple regex and dictionary, only lowercase accented forms, no tests, broken reverse function — [gist](https://gist.github.com/congkhoa/bcd46eea4972d01aad15f2c603b560c7)
- Other languages, search snippets, not opened: PHP [vi_encoder](https://github.com/vuthaihoc/ViEncoder), PHP [unicode-converter](https://packagist.org/packages/visualweber/unicode-converter), npm [vietnamese-conversion](https://www.pkgstats.com/pkg:vietnamese-conversion), R [vietnameseConverter](https://cran.r-project.org/web/packages/vietnameseConverter/refman/vietnameseConverter.html) (does not support VNI), PyPI [vietnamese](https://pypi.org/project/vietnamese/) (`normalize()`, encodings not listed).
- Local check on Python 3.12: built-in codec aliases include `cp1258` but none for VISCII or TCVN.

**PDF mechanics and glyph recovery**
- ISO 32000 9.10.2 order: ToUnicode CMap; then simple fonts with predefined encoding or standard Differences names, via Adobe Glyph List; then composite fonts via a predefined CMap (not Identity). If all fail, the code's meaning cannot be determined and the reader may pick its own value. Read via a Chinese translation mirror — [ISO 32000 mirror](https://hellowac.github.io/pdf-std-zh-cn/iso32000/c9/s10)
- pdf-glyph-mapping dumps glyph bitmaps, a human maps them, and it writes `ActualText`. "Mostly abandoned", tested on one PDF — [pdf-glyph-mapping](https://github.com/shreevatsa/pdf-glyph-mapping)
- PDFix Font Fix "uses OCR to recover the correct character for each unmapped glyph", free via Docker. No engine, accuracy or language list given; page updated July 2026 — [PDFix](https://pdfix.net/font-fix-pdfix/)
- pdf-fix-tuc fixes ToUnicode for CJK look-alike kanji, and conversion is irreversible — [pdf-fix-tuc](https://github.com/trueroad/pdf-fix-tuc)
- A community proposal in Docling recovers constant-offset maps, reportedly about 99.4% of codes; an English-text case — [Docling #2963](https://github.com/docling-project/docling/issues/2963)

### Inferences

**The hypothesis.** The repo's samples likely come from a hidden OCR layer, created by an engine without a Vietnamese model, not from a legacy font. A font map is deterministic, so the same glyphs in the same font cannot yield two outputs, and digits and `/` for accented letters are typical OCR confusions. The caveat is that different fonts or a lossy PDF producer could also explain this. Test before acting: `get_texttrace()` type 3 or opacity 0, `pdffonts` output, full-page image coverage. If confirmed, the repo comment attributing these to VNI/TCVN3 is wrong for those files, and conversion cannot help, so OCR is the right route.

The 184 "broken" files may be a mix, so measure before deciding whether a converter is worthwhile.

| Situation | What survives | Recoverable? |
|---|---|---|
| Legacy font, extractor returns bytes as WinAnsi or Latin-1 | Original codes | Yes, deterministic lookup after fingerprint match |
| TCVN3 with capital font (for example `.VnTimeH`) | Codes plus font name | Yes, but per span with font name; flat text loses the case signal |
| Legacy bytes read through a different code page or repaired incorrectly | Possibly | Often; reverse it per font and verify with syllable hit |
| Valid but wrong ToUnicode, while raw codes are in the content stream | Codes in the stream | Possibly; bypass ToUnicode and read codes per font |
| Subset CID font, Identity-H, no ToUnicode | Glyph shapes only | Only by per-glyph identification, one map per subset font |
| Constant-offset map | Codes | Yes, by inferring the offset, then verify |
| Extracted text already saved without diacritics | Nothing about tones | No from text; go back to the PDF or the page image |
| Hidden OCR text from an earlier scan | Page image only | No conversion; re-OCR |
| Text as outlines or images | Pixels only | OCR only |

- **Implementation sketch.** Work per span using PyMuPDF `dict` spans with `font`, not flat text. Detect family from font name (`.Vn*`, `VNI-*`, `VPS*`, etc.) and fingerprints. Apply the lookup longest match first. Normalise to NFC. Then validate by syllable hit and a sample comparison with OCR on the same page. If validation fails, OCR the page.
- **Do not restore diacritics from stripped text in a legal corpus.** One toneless form maps to several meanings, so this is prediction rather than recovery. The arXiv study above also found LLM correction often degrades accurate text.
- **Glyph-level recovery looks unattractive here.** With EasyOCR working at the team's measured rate of about 360 pages/hour ([PIPELINE_TU_DONG.md](../../docs/PIPELINE_TU_DONG.md)) and no maintained Vietnamese-capable tool found, OCR is simpler unless exact text with positions is needed.

### Gaps
- Whether real PDFs in this corpus hold legacy fonts is unverified: PDFs are not available locally, and the only local text is post-OCR.
- UniKey/UniConvert: I found no primary documentation or source for its conversion tables, only low-quality how-to pages (not opened). Its behaviour is unverified.
- No maintained Python package with full TCVN3, VNI, VPS and VISCII support and tests was confirmed. Package metadata for PyPI `vietnamese` was not opened.
- A claim that dictionary-based VietPad diacritic restoration reached only 60-85% appeared in a search snippet. I could not read the paper's PDF ([PACLIC 2020](https://aclanthology.org/2020.paclic-1.9.pdf)), so treat it as unverified. A 2026 paper on legal identifiers such as `15/2023/ND-CP` being mis-flagged also appeared only in a snippet.
- How diacritics that are separate positioned glyphs behave across extractors was not tested. VNI's two-byte form makes this worth one experiment.
- No source documents VNI, VPS or TCVN3 in PDF specifically. The mechanism here is derived from ISO 32000 and the encoding tables.

## How should PDFs with an invisible OCR layer, and pages mixing digital text with scanned stamps or handwriting, be handled?

### Takeaway
Treat a hidden layer as an untrusted old OCR result, and detect it per page first by render mode, opacity and font, and only then judge quality. For mixed pages, keep good visible text and OCR only image regions. OCRmyPDF `redo` and Docling's PDF-aware mode are the ready-made implementations, while handling of stamps and handwriting needs local testing.

### Cited Findings

**OCRmyPDF modes**
- It cannot tell a printable layer from hidden OCR on the "page already has text" check, and exits by default — [OCRmyPDF errors](https://ocrmypdf.readthedocs.io/en/latest/errors.html)
- `redo`: "Text is categorized as either visible or invisible. Invisible text (OCR) is stripped out." An image of each page is then created "with visible text masked out", so it can "locate the additional text in images without disrupting the existing text". Visible OCR text cannot be distinguished from real text, so it is not redone — [OCRmyPDF advanced](https://ocrmypdf.readthedocs.io/en/latest/advanced.html)
- `force`: rasterises all pages, discarding hidden OCR text, also rasterises printable text and flattens form fields. `skip`: copies pages with text unchanged — [OCRmyPDF advanced](https://ocrmypdf.readthedocs.io/en/latest/advanced.html)
- Printable vector text is excluded from OCR in `redo`, so it suits files mixing digital and scanned pages — [OCRmyPDF errors](https://ocrmypdf.readthedocs.io/en/latest/errors.html)

**Marker**
- `--strip_existing_ocr` keeps digital text and removes existing OCR — [Marker README](https://raw.githubusercontent.com/datalab-to/marker/master/README.md)
- When enabled, a page is rejected if any text is in an invisible or unknown render mode, if all fonts are non-embedded or "glyphless", or if an image covers at least 65% of the page — [marker/providers/pdf.py](https://raw.githubusercontent.com/datalab-to/marker/master/marker/providers/pdf.py)

**Docling**
- In PDF-aware mode, a layout cluster goes to OCR if it overlaps a bitmap, has no visible text, or has non-rule shapes its text does not account for. OCR merges with PDF cells, which have priority — [base_ocr_model.py](https://raw.githubusercontent.com/docling-project/docling/main/docling/models/base_ocr_model.py)
- In full-page OCR, OCR cells replace visible PDF cells but invisible PDF cells are kept and added back — [base_ocr_model.py](https://raw.githubusercontent.com/docling-project/docling/main/docling/models/base_ocr_model.py)

**PyMuPDF**
- `Page.get_texttrace()` reports span type 3 ("Ignored text – equivalent to 3 Tr (hidden text)") and opacity, where 0 is invisible — [PyMuPDF functions](https://pymupdf.readthedocs.io/en/latest/functions.html)
- PyMuPDF4LLM's `is_ocr_span` is true if the font is Tesseract's, alpha is 0, or neither stroked nor filled flags are set — [analyze_page.py](https://github.com/pymupdf/pymupdf4llm/blob/main/src/ocr/analyze_page.py)
- `get_textpage_ocr(full=...)` OCRs the full page or "only page areas that contain no legible text"; full-page results use `GlyphLessFont` — [PyMuPDF Page](https://pymupdf.readthedocs.io/en/latest/page.html)

**Other**
- pdf-inspector classifies from text and image operators, and its `Mixed` class needs the `Full` strategy for accuracy (the default samples 8 pages) — [pdf-inspector](https://github.com/firecrawl/pdf-inspector)
- Marker's fast mode skips Figure, Picture, Table, Form and similar blocks by default in block repair, so a stamp classified as a figure may not be read — [marker/builders/ocr.py](https://raw.githubusercontent.com/datalab-to/marker/master/marker/builders/ocr.py)

### Inferences
- The team's `probe` uses `get_text()` with no check on visibility, so a hidden layer is judged as if it were born-digital text. Add a per-page class first:
  - **Hidden layer over an image** — ignore the layer unless a quality check and OCR comparison pass; re-OCR. Good modern Vietnamese hidden layers can be retained.
  - **Visible digital text, good** — use it.
  - **Visible digital text with legacy fingerprint** — convert, then validate.
  - **Visible text, bad and not convertible** — full-page OCR.
  - **Visible text plus large images, stamps or signatures** — keep text and OCR image regions only.
  - **No text** — OCR.
- Docling keeping invisible cells during full-page OCR may matter here: check whether bad hidden text reaches the export before adopting it on this corpus.
- OCRmyPDF `--mode force` destroys vector text in the output. If the need is text rather than a searchable PDF, it is simpler to render and OCR directly, as the team already does.
- For legal documents, record stamp and signature presence as metadata rather than merging their OCR into the body, since stamp text can fall into the middle of a paragraph. Issue number and date fields should be validated against a clean region or manifest metadata.

### Gaps
- No source or benchmark was found on Vietnamese red stamps, signatures or handwriting mixed with digital text, or on how tools handle a stamp overlapping text.
- How OCRmyPDF `redo` classifies visible versus invisible text is described only as "detailed text analysis", with no algorithm given.
- The prevalence of hidden layers in this corpus is unknown. A single scan with `get_texttrace()` across the 501 files would settle both this and the encoding question.
