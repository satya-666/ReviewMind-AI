# Phase 1 — Dataset preparation handoff

The existing Phase 1 implementation is preserved in `scripts/`. Publication preparation on 2026-11-03 adds documentation and stronger Git exclusions; it does not train models, change dataset transformations, or start EDA.

## Verified dataset results

The original starter contained downloader scripts and source notes, not customer reviews. The executed pipeline acquired the suggested Flipkart Kaggle version-1 archive and preserved it unchanged. Recorded acquisition date: 2026-10-31.

| Measurement | Actual |
|---|---:|
| Raw reviews, all domains | 205,052 |
| Cleaned reviews, all domains | 205,050 |
| Technology candidates | 26,605 |
| Training-ready records | 23,322 |
| Training | 18,367 |
| Validation | 2,492 |
| Test | 2,463 |

Category and language counts, exclusions, missingness, rating distribution, source restrictions and biases are recorded in `reports/data_quality.json` and `reports/phase1_report.md`. The 50,000-review technology target remains unmet; smartphones and TVs/monitors have no acquired coverage. The observed labels include only 23 Hinglish candidates and no Hindi records; they are weak language estimates, not human annotations.

## Pipeline design

`scripts/run_pipeline.py` orchestrates the existing modules:

1. `download.py` reuses the versioned archive, verifies ZIP integrity/checksum and checks the publisher license declaration.
2. `inspect_data.py` inventories raw files without changing them.
3. `clean_data.py` supplies stable IDs, Unicode/whitespace normalization, usable-text checks and rating validation. Original source text is stored separately from cleaned text.
4. `categorize.py` uses product-name rules; unrelated/uncertain products are excluded from technology splits.
5. `detect_language.py` uses seeded language detection and conservative script/Roman-Hindi heuristics, with uncertainty flags.
6. `deduplicate.py` groups exact text and verified high-similarity MinHash candidates. Similar phrases alone do not prove two customer records are identical.
7. `split_dataset.py` assigns exact-name product groups toward 70/15/15 and quarantines detected cross-split duplicate text. Final proportions are approximately 79/11/11 after quarantine.
8. `generate_report.py` writes measured quality reports and source provenance.

The requested schema and additional provenance/quality columns are saved as Parquet. The acquired source lacks trustworthy product IDs, review dates, purchase verification and helpful votes; those fields remain null. Exact-name hashes are only product-group proxies. No fuzzy catalog merging or fabricated aspect labels occur.

## Validation and reproduction

From the repository root, follow the setup commands in `README.md`, then run:

```sh
.venv/bin/python scripts/run_pipeline.py
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
```

The full suite has 41 tests covering schema, ratings, missing values, categories, language heuristics, duplicate grouping, stable IDs, split reproducibility, source provenance and detected leakage. Full tests require local datasets; the README also documents the dataset-free unit-test command. `reports/test_results.txt` records the original successful run, and `reports/publication_validation.txt` records checks for publication preparation.

The earlier complete offline pipeline rerun produced identical SHA-256 checksums for training-ready and split Parquet artifacts, recorded in `reports/reproducibility.json`. Publication preparation reuses these existing artifacts and validates their checksums; it does not redownload or regenerate data unnecessarily.

## Licensing and publication boundaries

The Flipkart publisher declares ODbL/DbCL licensing. Attribution, applicable database share-alike and notice requirements remain relevant. Underlying author/marketplace rights were not independently cleared. Amazon is excluded pending explicit license clearance; the original downloader's assumed review-Parquet paths were also unavailable.

Raw/interim/processed/split datasets, archives, virtual environments, credentials and model artifacts are excluded from Git. Small aggregate reports, license evidence, source manifests, code, configuration and tests can be reviewed independently of the review records. No source-code license is added without the owner's approval.

## Limits and next phase

Phase 1 software and available-data execution are validated; collection remains partial. Product identity is inferred only through exact names, MinHash retrieval is approximate, short texts often have unknown language, and evaluation quarantine changes language/category balance. All tablet records currently fall in training, so tablet evaluation is unavailable in these splits.

Phase 2 is **Exploratory Data Analysis**. Existing Parquet artifacts and measured quality reports provide its inputs; missing category/language coverage and product-identity limitations must remain visible. No Phase 2 implementation is included here.
