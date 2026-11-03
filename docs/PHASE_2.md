# Phase 2 — Exploratory Data Analysis

## Scope and Git dependency

Phase 2 extends the existing repository without changing Phase 1 transformations or datasets. Branch `phase-2/eda` is based on `phase-1/data-pipeline` commit `26b7ea014f03542a4b5b3bfdd4dd8e52613bbdf4`. At inspection, GitHub had only that Phase 1 branch; no `main` merge existed. No merge or history rewrite is performed.

The EDA implementation executes on existing `data/splits/{train,validation,test}.parquet`. `scripts/run_phase2.py` orchestrates reusable modules in `src/analysis/` for dataset overview, ratings, languages, categories, text, product evidence, bias/leakage, charts and the Markdown report. No new dataset or model is downloaded and no classifier is trained.

## Execution

Use Python 3.14 and the pinned requirements, after Phase 1 preparation:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/run_phase2.py
.venv/bin/python scripts/execute_notebooks.py
.venv/bin/python -m pytest -q
```

`--config PATH` selects an alternate Phase 2 YAML config. Missing data/schema inconsistencies generate explicit errors; the script does not silently download or repair data. An all-empty set of splits produces an explicit no-records error instead of invented charts. Individual analysis functions and plotting also handle empty inputs for tests. Existing inputs are hashed before and after EDA to check they remain unchanged.

The notebooks use the executor's active Python executable. Each gets a fresh kernel and no shared state. Aggregate results and external PNG links remain in small executed notebooks; reviews and base64 image outputs are not embedded. Localhost ports are required for Jupyter kernels. A fresh temporary virtual environment installed only from requirements.txt is used for the separate clean-environment verification; machine paths are omitted from committed evidence.

## Measurement definitions

- Analysis unit: a retained review record, not necessarily a distinct customer. Dataset contains 23,322 reviews, 75 exact-name product groups, seven represented categories and one source.
- Product identity: `product_group` from Phase 1 is an exact-name proxy. All `product_id` fields are missing, so true unique-product count is unknown, not 75 verified products.
- Usable percentage: nonempty usable source text plus an available rating, divided by analyzed split records. This does not certify labels, customer independence or provenance rights.
- Ratings: documented integer stars 1–5. Weak overall sentiment maps 1–2/3/4–5 to negative/neutral/positive only in derived EDA summaries. Source datasets are unchanged.
- Missingness: null or blank schema fields for overview; category missing-cell rates count null schema cells. Null metrics for empty groups serialize to JSON null rather than NaN or invented zero averages.
- Text length: Unicode character counts and whitespace-separated words. Terms use NFC/casefolded Unicode letters/marks/numbers, no universal English stopword filter, and per-review document frequencies. Contact-like patterns are redacted and public terms require at least ten supporting reviews. Frequent terms are not validated aspects.
- Provisional evidence thresholds in YAML flag low coverage, short/long reviews and uncertain language. They are research diagnostics rather than universal scientific cutoffs. The suggested floor of 20 product reviews must be validated against independent-customer evidence and uncertainty.

## Validation and leakage methodology

Structural checks cover required fields, nonempty IDs/text, unique source IDs, allowed categories/languages, valid ratings/dates, exact-name group consistency and cross-split ID/group overlap. Existing candidate records and the Phase 1 seed/config reproduce retained IDs and split labels. Recorded input checksums are checked separately. A structural pass does not prove semantic leakage absence.

Full retained text is screened for exact case/whitespace-normalized overlap. A secondary token-canonical screen removes punctuation, emojis and one-character/numeric-only tokens: 13 shared phrase groups span splits and affect 1,766 rows. Such normalization can overmerge generic expressions, so results are potential leakage warnings, not proof of shared reviewer identity.

A second, independent long-text screen samples at most 2,500 eligible reviews per split after sorting IDs (seed 42). It screened 5,673 records with MinHash LSH candidate retrieval and exact character-five-gram Jaccard verification at 0.90. No candidate cross-split pair met the retrieval screen in the actual run. This bounded procedure avoids all-pairs work and cannot rule out unobserved overlaps, short-text variants or semantic paraphrases.

Known exact/group checks pass; broader similarity and catalog-variant risks remain. No splits were rewritten. Because all splits are inspected during EDA, reserve a fresh independent final holdout for later confirmatory evaluation.

## Main findings and limits

The mean rating is 4.205 and median is 5; 80.93% are high-rated. The top ten groups hold 49.62% of reviews. Category and class imbalance, repeated phrases, and uneven product evidence limit generalization. No smartphone/TV records or Hindi examples exist, and Hinglish labels number only 23. Tablet records are confined to training.

Confidence estimates are uncalibrated; the seed-42 private diagnostic sample of 18 uncertain/non-English-labeled records was inspected without publishing text. Apparent English reviews among the `other` samples indicate language-label noise. The aggregate inspection notes are in `PHASE_2_LANGUAGE_REVIEW.md`; this is not an accuracy evaluation or a relabeling exercise.

Dates, verified catalog IDs, purchase verification and helpful votes are missing throughout. Individual customer country and independent reviewer identity are unverified. Review-time drift, true product disjointness and human-verified sentiment/language accuracy therefore remain unavailable. No statistical-significance, causal-quality or definitive-fraud claims are made. ODbL/DbCL publisher-declared licensing and underlying-rights limitations from Phase 1 still apply.

## Outputs and checks

- `reports/phase2_metrics.json`: numeric summaries, thresholds, versions and input/code hashes.
- `reports/phase2_validation.json`: structural/reproduction checks and similarity warnings.
- `reports/phase2_eda_report.md`: descriptive research report with all 15 figures and Phase 3 recommendations.
- `reports/figures/`: 15 small PNGs, visually inspected as a contact sheet; no raw review texts or product names disclosed.
- `notebooks/01_dataset_overview.ipynb` through `04_category_analysis.ipynb`: executed aggregate notebooks.
- `reports/phase2_notebook_execution.json`, `phase2_test_results.txt`, `phase2_verification.json`: execution, tests and reproducibility evidence.
- Ignored `data/interim/phase2_language_sample.json`: local diagnostic sample only; never staged.

The tests cover loading/schema errors, rating arithmetic, category/product/language metrics, Unicode lengths, missing values, duplicates, split overlap, chart creation, JSON serialization, empty inputs, same-input reproducibility and actual-artifact accounting. The full suite includes Phase 1 regressions. Same-input EDA reruns are compared and input hashes must remain unchanged. Completion/test counts are recorded only after successful execution in the verification artifacts.

Implementation and available-data execution are complete. Analyses requiring absent metadata or independently verified labels remain incomplete. Phase 3 recommendations are a plan, not implementation; no model fitting or Phase 3 work is included.
