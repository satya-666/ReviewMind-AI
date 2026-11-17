# ReviewMind AI

ReviewMind AI prepares real technology-product reviews for review intelligence research in the Indian market. Phase 1 collects and prepares data; Phase 2 performs EDA; Phase 3 adds weakly supervised sentiment experiments and rule-based aspect analysis. Phase 3.5 connects the supplied frontend to real FastAPI inference and persistent feedback. Product recommendations remain unavailable.

## Phase 3.5 web application

Deployment visibility check (2026-11-11): GitHub reports this repository as **private**. The bundled model is accessible to anyone with repository or image access; an image is not a confidentiality boundary. Do not make the repository or image public without an explicit rights and publication review.

From the project root, with the existing Phase 3 model available:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cp backend/model_metadata.json models/phase3/full/baseline/logistic_regression.metadata.json
.venv/bin/python scripts/verify_serving_model.py
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
```

Open http://127.0.0.1:8000. The selected checkpoint is `models/phase3/full/baseline/logistic_regression.joblib`; this specific 2.9 MiB checkpoint is included in the private deployment repository and bundled into Docker at `/app/runtime/model.joblib`. No external model storage or `MODEL_ARTIFACT_URL` is needed. Build and startup verify its pinned SHA-256 and metadata before inference.

The application now offers contextual chat with a dedicated ReviewMind agent and server-side tool routing. Reviews use the unchanged trained sentiment classifier; ordinary questions and follow-ups can use **Gemini 3.1 Flash-Lite** when the backend key is configured and the visitor opts in. With Gemini enabled, typos, short replies and buying preferences go to the actual conversational model. Provider failures show a specific error and Retry rather than a repeated generic guide; consent notices remain clearly labeled. Product recommendations, current prices and verified comparisons remain unavailable.

Set `GEMINI_API_KEY` only in backend secrets, never the static frontend. Keep `FRONTEND_API_URL=https://reviewmind-api.onrender.com` on the frontend. No local LLM or new paid hosting resource is needed. A free-capable model does not control account billing—keep the Google project on its Free tier for free-only usage.

The chat UI includes New Chat, local history, working device settings, Help, mobile themes, bounded loading/retry and prediction feedback with a visible submit footer. Enter sends; Shift+Enter creates a new line. Model details are expandable. History remains opt-in and compatible with existing saved messages.

See [chat architecture, privacy, test evidence and exact Render release steps](docs/CHAT_INTEGRATION.md) and [Phase 3.5 deployment details](docs/PHASE_3_5.md). Both Render services must track `phase-3.5/web-integration`; the owner's earlier screenshot showed the frontend tracking phase-1. Both existing Render services have been updated to the deployment branch, and live Gemini plus real classifier inference were verified. The old static-site branch/timeout issue is resolved. See [the agent routing repair, memory policy and tests](docs/AGENT_INTEGRATION.md) for the current revision; historical live evidence remains in `reports/phase3_5_chat_live_verification.json`. No account, billing or resource-plan changes are made by this code.

## Scope and development roadmap

The pipeline supports smartphones, laptops, audio devices, wearables, TVs/monitors, computer accessories, tablets, networking devices, and chargers/power banks. Supported categories are distinct from acquired coverage; two categories currently have no usable records.

The roadmap distinguishes implemented research work from future milestones. Phases 4–7 are proposed plans, not implemented features or a finalized research plan.

1. Dataset collection and preparation — implemented and validated; collection coverage remains partial.
2. Exploratory Data Analysis (EDA) — implemented and executed on the available Phase 1 data; unavailable analyses documented below.
3. Sentiment and aspect analysis — classical/compact-transformer training executed; overall phase partial without independent sentiment/ABSA annotations.
   Phase 3.5 — supplied frontend integrated with real inference and persistent feedback; deployment prepared, public launch pending approval and rights review.
4. Multilingual NLP evaluation and adaptation — proposed.
5. Product intelligence and reliability analysis — proposed.
6. Preference-based recommendations and evaluation — proposed.
7. Further application capabilities and production deployment — proposed; Phase 3.5 supplies an initial analysis-only integration.

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

Phase 1 software and available-data execution are implemented; collection remains partial against the 50,000-review goal and nine-category multilingual coverage. More independently licensed catalog-linked data, smartphone/TV coverage, recent reviews and manually verified Indian-language evaluation are needed.

## Phase 2 — Exploratory Data Analysis

Phase 2 reads existing split Parquet files without changing them. It validates the schema, reproduces the Phase 1 split mapping, checks input checksums, calculates descriptive rating/category/language/text/product statistics, audits leakage and creates 15 Matplotlib PNG figures. Rating-derived overall sentiment is an explicitly weak exploratory label, not human or aspect ground truth. No model is trained.

Install the pinned `requirements.txt` as above (including Matplotlib, nbformat, nbclient and ipykernel), prepare Phase 1 data if necessary, then run:

```sh
.venv/bin/python scripts/run_phase2.py
.venv/bin/python scripts/execute_notebooks.py
.venv/bin/python -m pytest -q
```

Configuration is in `configs/phase2_config.yaml`. The first command generates `reports/phase2_metrics.json`, `reports/phase2_validation.json`, `reports/phase2_eda_report.md` and `reports/figures/*.png`. It uses a reproducible bounded MinHash sample rather than an all-pairs comparison. An alternate config can be passed with `--config PATH`.

Four notebooks in `notebooks/` load actual data through reusable `src/analysis/` functions. The executor starts a fresh kernel for each notebook using its active Python environment, runs every code cell and keeps only small aggregate outputs and external figure links. Run EDA before notebooks; localhost kernel ports must be allowed. No raw excerpts or embedded datasets are committed. The environment used for clean-environment verification is documented in `reports/phase2_verification.json`.

Measured findings:

- 23,322 reviews, 75 exact-name product groups, seven represented categories; true unique catalog-product count is unavailable.
- Mean rating 4.205/5; 80.93% of ratings are four or five stars.
- Top ten product-name groups account for 49.62% of reviews.
- No exact normalized-text or recorded product-group overlap across splits. A broader token-normalization screen flags 13 shared phrase groups involving 1,766 rows; these are potential leakage warnings, not proven duplicate customer identities.
- A bounded independent long-text check sampled 5,673 records and found no cross-split pairs above its threshold. Sampling/LSH does not establish universal leakage absence.
- Hindi data is absent, Hinglish labels number 23, and the private diagnostic sample shows apparent English text among `other` labels. Multilingual labels need human verification.

EDA implementation, figures and notebooks are complete for available data. Temporal drift, verified catalog identity, customer geography and language-label accuracy remain unassessable; collection is still partial. Whole-dataset EDA exposes holdout distributions, so future confirmatory experiments need a fresh independent final holdout. See [docs/PHASE_2.md](docs/PHASE_2.md) and the research report for methods, bias assessment and test evidence.

Validation: **52 tests passed**, including all 41 Phase 1 tests. All four notebooks executed in fresh kernels in a separate virtual environment installed from the pinned requirements. Repeated EDA runs produced identical metrics, reports, validation summaries and all 15 PNG checksums, while Phase 1 input hashes remained unchanged. Evidence is in `reports/phase2_verification.json`.

The original Phase 2 recommendations inform the Phase 3 experiments below. Whole-dataset EDA and weak supervision remain limitations even after model training.

## Phase 3 — Sentiment training and aspect rules

Phase 3 is **partially complete**. Two real TF-IDF models and a compact pretrained English BERT model were trained, saved, reloaded and evaluated. Independent human sentiment evaluation, supervised ABSA and credible multilingual model evaluation remain unavailable. No Phase 4 work is included.

Install the pinned requirements (including PyTorch, Transformers and local MLflow/SQLite dependencies), then run:

```sh
.venv/bin/python scripts/cache_transformer.py
.venv/bin/python scripts/run_phase3.py --mode full
.venv/bin/python scripts/evaluate_models.py
.venv/bin/python scripts/execute_notebooks.py --phase 3
.venv/bin/python -m pytest -q
```

`--mode baseline` runs full classical experiments; `--mode smoke` performs a small, explicitly separate pipeline check. Configuration is in `configs/phase3_config.yaml`; taxonomies and label IDs are in `configs/aspect_taxonomy.yaml` and `configs/label_mapping.json`. All full tests now require locally prepared Phase 1 data plus cached/trained Phase 3 artifacts; these are excluded from Git except the explicitly approved small serving baseline. The documented download/preparation/training commands produce them. Existing Phase 2 notebook execution still defaults to its original four notebooks.

Training derives views of **18,367 train / 2,489 validation / 2,451 test** records, quarantining 15 lower-priority evaluation rows that share Phase 2 canonical phrase keys. Original Parquet files are unchanged. Models receive text only; ratings provide weak overall labels, never aspect ground truth. Hyperparameters/checkpoints and the selected model are chosen by validation macro F1 before test predictions. Prior EDA makes this an exploratory development benchmark, not an untouched final holdout.

| Actual model | Training reviews | Validation macro F1 | Weak test accuracy | Weak test macro F1 |
|---|---:|---:|---:|---:|
| TF-IDF + Logistic Regression | 18,367 | 0.6593 | 0.8462 | 0.6728 |
| TF-IDF + Linear SVM | 18,367 | 0.6488 | 0.8792 | 0.6667 |
| Google compact English BERT | 12,000 | 0.6547 | 0.8690 | 0.6988 |

**Logistic Regression is the validation-selected model**. BERT's higher observed test macro F1 does not justify changing that frozen selection using test feedback. The BERT pilot used four completed epochs, selected epoch 3 and an Apple M3 MPS device with 8 GB RAM. Measured classical search times were 28.92 and 24.32 seconds; transformer optimization/validation/checkpoint time was 116.72 seconds, excluding initial model loading/tokenization. These are different workloads, not controlled speed comparisons.

The nine-category aspect rule baseline found mentions in **1,094 of 2,451** held-out reviews. These are coverage counts, not extraction accuracy. No supervised aspect model or aspect F1 is claimed. There are no Hindi records and too few Hinglish examples to claim multilingual performance. A blank, private 180-review annotation queue and [annotation guide](docs/ANNOTATION_GUIDE.md) provide the next labeling workflow; no human labels were fabricated.

Local artifacts are in `models/phase3/full/baseline/` and `models/phase3/full/sentiment/`; MLflow tracking is in `models/phase3/mlflow.db`. All other models, tokenizer downloads, MLflow artifacts, raw annotation/error excerpts and credentials are ignored by Git. The approved Logistic Regression checkpoint is the sole deployment exception.

```sh
.venv/bin/python scripts/predict_review.py \
  --model models/phase3/full/baseline/logistic_regression.joblib \
  --text "The sound is clear but the battery is poor" --category audio_devices
```

This is a synthetic inference illustration, not benchmark evidence. Single/batch inference exposes model versions and explicitly uncalibrated probabilities/softmax scores; SVM margins are not probabilities. Category-aware aspect rules use clause-local cues and limited negation handling, with unknown/mixed outputs and no confidence claims.

Read [docs/PHASE_3.md](docs/PHASE_3.md), [the model report](reports/phase3_model_report.md), `reports/phase3_results.json`, and `reports/phase3_verification.json` for methods and executed checks. GPU bitwise repeatability is not guaranteed: PyTorch reports a nondeterministic MPS embedding-backward operation. Checkpoint-reloaded predictions and seeded classical fitting are verified separately. Human-annotated benchmarks, licensed supervised ABSA, reliable catalog identities, a fresh final holdout and multilingual annotation remain prerequisites for stronger Phase 4 readiness claims.

Validation completed: **61 tests passed**, all three Phase 3 notebooks executed, and CPU reloads of all three checkpoints reproduced their original test confusion matrices. A Phase 2 rerun retained byte-identical outputs; original Phase 1 artifact hashes still match. Eleven full-run research figures were generated and visually inspected. Full training/evaluation took about 192 measured seconds, excluding final plotting/report overhead; timings are machine-dependent.

### Product research and default conversation

Conversation now uses Gemini automatically after one-time permission, with persistent opt-out in Settings. Optional SerpApi India Shopping tools provide sourced product cards only when a backend key is configured and live retrieval succeeds. See [provider research, free-plan setup and limitations](docs/PRODUCT_RETRIEVAL.md). No trained model or paid infrastructure was changed.

Google sign-in is implemented for production, with backend ID-token verification and per-account optional device history. Activation requires the owner's Google OAuth web client ID before deploying the authentication gate. See [setup and verification](docs/GOOGLE_AUTH.md). Sample buying prompts have been removed from the customer interface.
