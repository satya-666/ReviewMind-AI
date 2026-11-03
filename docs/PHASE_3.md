# Phase 3 — Weakly supervised sentiment and aspect baselines

## Scope and branch dependency

`phase-3/ml-models` builds on Phase 2 commit `2a2bded66e753d4ecb3a788fd13ef6e888562866`; no `main` merge existed at inspection. Existing Phase 1 transformations, Phase 2 analysis modules and original Parquet inputs are preserved. The notebook executor gains an optional `--phase 3`; its default Phase 2 behavior remains unchanged. The Phase 2 notebook test is scoped to its original four notebooks so adding three new notebooks does not break it.

The entire Phase 3 remains **partial** without independent human sentiment evaluation and genuinely annotated supervised ABSA. Completed numerical experiments are in `reports/phase3_results.json`; no missing model or metric is invented. No recommendation engine, frontend or Phase 4 work is included.

## Environment and execution

Use Python 3.14 and the pinned requirements. PyTorch, Transformers and MLflow Skinny with its SQLite dependencies extend the existing environment. This session used an Apple M3 with 8 GB RAM; MPS is available outside the restricted sandbox. Auto device selection prefers CUDA, then MPS, then CPU. Training uses a compact pretrained encoder to keep memory bounded. No large DistilBERT/XLM-R checkpoints are downloaded.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/cache_transformer.py
.venv/bin/python scripts/run_phase3.py --mode full
.venv/bin/python scripts/evaluate_models.py
.venv/bin/python scripts/execute_notebooks.py --phase 3
.venv/bin/python -m pytest -q
```

The cache script verifies the Apache-2.0 declaration and downloads only Google compact BERT weights/config/tokenizer files. Immutable source revision is recorded in `reports/phase3_transformer_source.json` and pinned in YAML. The initial execution resolved `main` to that same recorded immutable revision before fine-tuning; future cache commands use the pinned revision directly. Training itself reads local files only.

Modes:

- `--mode smoke`: two classical models with 120/60/60 stratified review caps and one hyperparameter setting. This is a quick pipeline check, **not** a full experiment or a transformer run. Results/artifacts are isolated under smoke-specific names.
- `--mode baseline`: full derived training/validation/test views; tunes the two classical models and reports weak-label scores, aspect-rule coverage and resource costs.
- `--mode full` (default): baseline work plus the feasible bounded pretrained-transformer experiment. Failure to train the transformer is recorded explicitly while completed baseline work remains usable.

The full transformer pilot caps training at 12,000 stratified records, sequence length 96, batch size 32, two gradient-accumulation batches, four configured epochs and a 900-second budget checked after each complete epoch. Validation macro F1 selects the saved checkpoint with patience two. Hardware/epoch counts/times are measured in JSON. Mixed precision is off for MPS/CPU and may be enabled only for CUDA. On a suitable GPU machine, change the YAML device/batch/budget and set `max_train_reviews: null` to use the full derived training view; treat that as a new experiment rather than overwrite claims about this pilot.

## Leakage and labels

Phase 2 found 13 shared token-canonical phrase groups. Phase 3 derives views that keep train before validation before test and exclude conflicting lower-priority rows, without moving test records into training or modifying originals. The current derived sizes are 18,367 / 2,489 / 2,451. All original training rows remain available to classical models. Input checksums, retained-ID digests and canonical/source-ID/exact-name/recorded-duplicate group checks are recorded. This screen can overmerge common phrases and cannot certify semantic or catalog-identity disjointness.

Only `cleaned_text` is a model input. Ratings supply **weak overall** negative/neutral/positive labels (1–2/3/4–5); no rating or product field enters TF-IDF/tokenizer features. All direct model comparisons use the same derived test rows after validation-only model/hyperparameter/checkpoint selection. The transformer uses a smaller training budget than the classical models, so this is not an equal-budget architecture study. Macro metrics always include all three classes; per-class supports make absent/rare classes explicit.

The original test distributions were already inspected in Phase 2. These are exploratory development holdouts, not fresh confirmatory benchmarks. Independent human sentiment labels are absent. `docs/ANNOTATION_GUIDE.md` and an ignored seeded queue of 180 actual reviews establish a blinded human-labeling workflow, not fabricated annotations. Annotation work is preserved on reruns and is not automatically trusted by the training pipeline.

## Models, inference and uncertainty

Classical baselines combine word (1,2) and character-within-word (3,5) TF-IDF features with Logistic Regression or Linear SVM. C and class weighting are tuned only on validation macro F1, with fixed seeds and all trials logged. The transformer is Google's two-layer/128-dimensional English BERT miniature with a genuinely fine-tuned three-class head, not a random prediction placeholder. Recorded completed-run results determine which model actually succeeded.

```sh
.venv/bin/python scripts/predict_review.py \
  --model models/phase3/full/baseline/logistic_regression.joblib \
  --text "The sound is clear but the battery is poor" --category audio_devices

.venv/bin/python scripts/predict_review.py \
  --model models/phase3/full/sentiment \
  --text "The battery is not good" --category smartphones
```

These inputs are synthetic API demonstrations, not benchmark records. `ReviewPredictor.single` and `.batch` reload real local checkpoints, validate input strings, return class scores/version identifiers and optionally category-specific aspect rules. Logistic probabilities and transformer softmax scores are explicitly **uncalibrated**. SVM decision margins are not probabilities and have no confidence probability. Empty batches are accepted; empty/malformed individual reviews raise errors. Hindi/Hinglish input handling tests do not establish language accuracy.

## ABSA boundaries and annotation needs

Nine category-aware taxonomies are configured in `configs/aspect_taxonomy.yaml`. Alias extraction and nearest clause-local lexical cues implement a rule baseline with limited negation handling and unknown/mixed output. Rule coverage is measured on real reviews. It is not independently labeled precision/recall/F1 or a trained supervised ABSA model; whole-review ratings never supervise individual aspects.

SemEval laptop ABSA was inspected, but unrestricted underlying-review reuse was not verified from official fair-use/provider terms; a mirror was inaccessible. No unclear-license annotated data was silently downloaded. Supervised aspect extraction and aspect-sentiment metrics remain null until genuine independently licensed labels and a finalized evaluation policy exist. See `ANNOTATION_GUIDE.md` for spans, annotator blinding, adjudication and mixed sentiment.

Hindi coverage is zero and Hinglish is too sparse for meaningful multilingual fine-tuning. XLM-R, IndicBERT and MuRIL experiments are not claimed. Per-language weak metrics use an explicit minimum sample threshold; small groups report counts and an unavailable status rather than unstable capability claims.

## Tracking, evaluation and artifacts

MLflow uses local SQLite `models/phase3/mlflow.db`, with a parent run and per-model child records. It stores architecture, seed, dataset/split identifiers, actual hyperparameters, hardware, validation/test metrics, times and artifact references. The trained sklearn preprocessing/classifiers, transformer tokenizer/weights and metadata remain under ignored `models/phase3/{mode}/`.

Evaluation reports accuracy, macro precision/recall/F1, weighted F1, per-class supports/F1 and confusion matrices; per-category/per-language slices; warmed batched inference throughput; model size; and product-group bootstrap macro-F1 intervals. These intervals are exploratory and conditional on uncertain product grouping/weak labels. Latency is not a single-request tail-latency benchmark. Error slices use heuristic markers, not genuine sarcasm/negation annotations. Actual disagreement samples stay in ignored `data/interim`; aggregate inspection notes go in `PHASE_3_ERROR_REVIEW.md`.

`evaluate_models.py` reloads completed checkpoints on CPU and checks predictions against the recorded held-out confusion matrices. It does not retune models or change selection. Reproducibility uses fixed seeds, version pins, source/split hashes and saved artifacts. PyTorch warned that MPS embedding backward is not fully deterministic; deterministic-algorithm warnings are retained locally, and GPU bitwise repeatability is not claimed.

## Tests, notebooks and output status

`tests/test_phase3.py` exercises label mapping, deterministic classical fitting, local tokenizer/configuration, checkpoint persistence, single/batch inference, taxonomy and scoped aspect cues, metrics/bootstrap, invalid/empty input and actual-artifact leakage checks. Previous-phase tests remain in the complete suite. Configuration-only randomly initialized test models are explicitly not research experiments. Executed counts and reload verification are recorded in `reports/phase3_verification.json` after the checks run.

Notebooks 05–07 load aggregate completed results and validate real saved artifacts. Expensive training is reproduced through the entry point rather than silently retriggered in a notebook. Outputs stay small, use external PNG links and contain no real review excerpts. All figures derive from actual completed runs; loss curves appear only when completed transformer epochs exist.

Expected research outputs: `reports/phase3_results.json`, `reports/phase3_model_report.md`, `reports/phase3_reevaluation.json`, `reports/figures/phase3_full_*.png`, executed notebooks and verification evidence. Models, tokenizer caches, raw annotation/error text, secrets and MLflow databases are excluded from Git. No project code license is introduced.

## Readiness

This is a weak-supervision research prototype. Independent sentiment benchmarks, genuine supervised ABSA labels, catalog-linked holdouts, robust multilingual evaluation and calibration are essential unfinished components. Do not treat the entire phase as complete or start a production recommendation stage from these scores. Phase 4 remains unimplemented.
