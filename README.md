# ReviewMind AI

Phase 1 prepares real technology-product reviews for later review intelligence research in the Indian market. It collects, standardizes, cleans, categorizes, labels language, groups duplicates and writes reproducible dataset splits. No model training, recommendation engine or frontend is included.

The workspace itself is the project root. The original starter ZIP contained scripts and notes, **no reviews**. It was extracted intact into `starter/reviewmind_starter/`; the replacement downloader fixes the obsolete Amazon review-Parquet assumption by using the licensed, versioned Flipkart source instead.

## Scope and development roadmap

The pipeline supports smartphones, laptops, audio devices, wearables, TVs/monitors, computer accessories, tablets, networking devices, and chargers/power banks. Supported categories are distinct from acquired coverage; two categories currently have no usable records.

The seven-phase planning roadmap below records Phase 2 as the next step. Phases 3–7 are proposed milestones, not implemented features or a finalized research plan.

1. Dataset collection and preparation — implemented and validated; collection coverage remains partial.
2. Exploratory Data Analysis (EDA) — next, not started.
3. Sentiment and aspect analysis — proposed.
4. Multilingual NLP evaluation and adaptation — proposed.
5. Product intelligence and reliability analysis — proposed.
6. Preference-based recommendations and evaluation — proposed.
7. Application integration and deployment — proposed.

See [docs/PHASE_1.md](docs/PHASE_1.md) for the Phase 1 handoff. Repository source-code licensing has not been selected; dataset licenses do not license this project's code.

## Setup and execution

Validated with Python 3.14 on macOS ARM64. Exact installed dependencies are pinned in `requirements.txt`.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/download.py
.venv/bin/python scripts/inspect_data.py
.venv/bin/python scripts/run_pipeline.py
.venv/bin/python -m pytest -q
```

Tests include checks against local acquired artifacts. On a fresh clone, run dataset preparation before the full test suite. For unit checks without downloading data, use:

```sh
.venv/bin/python -m pytest -q -k 'not actual and not report_accounting'
```

Run from this project directory. Internet is needed for first acquisition and dependency installation; sandboxed environments may require network permission. Subsequent runs reuse the local archive, verify its SHA-256 and run offline. Raw files are never rewritten. Remove no raw data when rerunning. A changed archive checksum or source schema stops execution.

`configs/dataset_config.yaml` records the source version, access date, known rating scale, 50,000-review collection target, seed 42, split targets and similarity settings. Changing the source requires an explicit schema/provenance adapter and license review; arbitrary files are not silently ingested. Language cache entries are invalidated when detector code changes. Reproducibility requires the same source archive, config, code and pinned dependencies.

## Data sources and terms

- **Used:** [Nirali Vaghani, Flipkart Product reviews with sentiment Dataset, version 1](https://www.kaggle.com/datasets/niraliivaghani/flipkart-product-customer-reviews-dataset). Publisher API declares “Database: Open Database, Contents: Database Contents.” Preserve attribution and comply with [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) and [DbCL 1.0](https://opendatacommons.org/licenses/dbcl/1-0/), including applicable database share-alike/notice obligations. Publisher states December 2022 scraping and prior text cleaning. Its supplied VADER/manual sentiment column is not treated as research ground truth or copied into training-ready labels.
- **Excluded:** [Amazon Reviews 2023](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023). Current publisher card/API lacked an explicit license. No training-ready records are included pending manual clearance. The original starter downloader was executed; its assumed review Parquet directories do not exist in the inspected inventory.
- Hindi/Hinglish discovery links contain no verified electronics dataset; nothing was fabricated or imported to fill language quotas.

Evidence is saved in `reports/evidence/`; provenance, restrictions and geography are in `reports/dataset_sources.csv`. Publisher licensing is documented, not a guarantee of underlying marketplace/author rights. No reviews are committed, published or pushed. Public database use/distribution needs the applicable notices and terms.

## Artifacts

```text
data/raw/             Versioned original ZIP, unchanged
data/interim/         Standardized rows, excluded rows, duplicate pairs, language cache
data/processed/       Cleaned technology candidates and training_ready.parquet
data/splits/          train.parquet, validation.parquet, test.parquet
scripts/              Downloader, inspection, pipeline and task-specific helpers
configs/              Dataset configuration
reports/              Sources, quality JSON, research report, evidence and execution logs
tests/                Unit and real-artifact integration tests
starter/              Original extracted starter, unchanged
```

Parquet includes all 15 requested schema fields plus cleaned text, original title/rating, archive hash, source version/row, language method/confidence/manual-review flag, quality flags, product-group proxy and duplicate group. `review_text` is the verbatim source `Summary`, falling back to verbatim `Review` title when the body is unusable. `cleaned_text` is separate. Marketplace originals before the publisher's cleaning cannot be recovered. IDs are deterministic SHA-256 values incorporating dataset, archive checksum and source row identity.

No trustworthy catalog ID, review date, verified purchase or helpful-vote field exists here; those fields remain null. `product_group` hashes an exact full product name for leakage control, **not** verified product identity. No fuzzy product merging occurs. India-marketplace provenance does not prove an Indian customer location.

## Cleaning, languages and splitting

NFC normalization and whitespace/control-character cleanup preserve punctuation, emojis, Devanagari and original text. Empty/unusable reviews are excluded. Short and spam-like reviews are flagged, not discarded for suspected fraud. Ratings outside the known 1–5 scale are nulled. Products are categorized from metadata only; uncertain or unrelated products remain `unknown` in standardized/excluded records.

Language uses seeded langdetect, script checks and a small Roman-Hindi lexicon. Labels are weak estimates; confidence is uncalibrated and heuristic confidence is null. Short or ambiguous text is marked for manual review. No translation or aspect-label generation occurs.

Exact normalized text is grouped across products. Longer near duplicates use 128-permutation MinHash LSH candidates with verified character-five-gram Jaccard >=0.90. This is approximate, not exhaustive semantic deduplication. Identical source rows without author IDs may represent different customers, so they are reported and retained rather than asserted to be the same review.

Exact-name product groups are assigned toward 70/15/15 with category/language balancing. If detected text groups cross splits, conflicting evaluation rows are quarantined, retaining train before validation before test. Tests ensure no overlap of retained source IDs, exact-name product groups, exact texts or detected near-duplicate groups. Final proportions can differ from targets, and generic evaluation phrases are underrepresented. Missing reliable product IDs prevents claiming verified catalog-disjoint evaluation.

## Results and remaining work

Executed results: **205,052** raw rows, **26,605** technology candidates, **23,322** training-ready reviews. Split sizes: **18,367 / 2,492 / 2,463** train/validation/test (78.75% / 10.69% / 10.56% after leakage quarantine). **41 tests passed**; logs are in `reports/test_results.txt`.

A complete offline rerun produced byte-identical SHA-256 checksums for training-ready and all three split Parquet files; evidence is in `reports/reproducibility.json`.

| Category | Usable reviews |
|---|---:|
| Audio devices | 7,680 |
| Chargers and power banks | 4,830 |
| Accessories | 3,617 |
| Laptops | 3,071 |
| Wearables | 1,905 |
| Networking devices | 1,176 |
| Tablets | 1,043 |
| Smartphones | 0 |
| TVs and monitors | 0 |

Language estimates: English 12,433; Hinglish 23; other 249; unknown 10,617; Hindi and other Indic 0. There are 75 exact-name product groups. These are record counts, not independently verified unique customers. Missing Hindi/TV/smartphone coverage is a collection gap, not a generated quota.

Actual measured results are in [reports/phase1_report.md](reports/phase1_report.md) and [reports/data_quality.json](reports/data_quality.json); executed test output is in `reports/test_results.txt`. Acquisition produced 205,052 source records across mixed domains, not 205,052 technology reviews. The pipeline selects actual technology reviews and reports the smaller usable total. Category/language/split distributions, all exclusion stages, missingness and limitations are generated from the retained artifacts.

Phase 1 software and available-data execution are implemented; collection remains partial against the 50,000-review goal and nine-category multilingual coverage. More independently licensed catalog-linked data, smartphone/TV coverage, recent reviews and manually verified Indian-language evaluation are needed. Phase 2 has not started.
