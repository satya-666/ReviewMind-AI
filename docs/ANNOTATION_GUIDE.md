# Independent sentiment and aspect annotation

Phase 3 creates a seeded local queue at `data/annotations/phase3_annotation_queue.json` from real retained reviews (up to 60 per derived split, stratified by weak class only to select the sample). Labels are **blank**, not fabricated. Ratings and model predictions are withheld from the labeling file to reduce anchoring. The language hint is explicitly uncertain and must not determine the content label. Do not publish the queue or free text.

Two independent annotators should label the original source text, then a third adjudicator resolves disagreements. Record annotator IDs/policy version and label provenance separately. Keep an immutable pre-adjudication copy, measure agreement, and document examples that are unresolvable. The automated sampler preserves a queue containing annotation work instead of overwriting it. The training pipeline does not automatically trust or ingest a filled JSON file as human ground truth.

## Overall labels

Use `negative`, `neutral`, `positive`, `mixed`, `uncertain`, or `not_applicable` based on the expressed opinion, not star ratings. Distinguish factual neutral statements from unclear/no usable opinion. Mixed reviews should remain mixed unless a documented three-class policy justifies an overall interpretation; never force them into a class solely to match training labels. Sarcasm and code-mixing require competent annotators. Preserve original Hindi/Hinglish scripts and expressions; do not automatically translate.

## Aspect annotations

Use the category taxonomy in `configs/aspect_taxonomy.yaml` as a starting policy, with explicit `other`/unmapped mentions recorded for adjudication. Each `aspects` entry must include:

```json
{"aspect": "battery", "term": "battery", "start": 0, "end": 7,
 "sentiment": "negative", "implicit": false}
```

This is a **schema illustration**, not an annotation of a real record. Spans use zero-based Python character offsets into the exact original `text`, with exclusive end. Validate that `text[start:end] == term`. Implicit aspects require a separate policy and should not be assigned fabricated explicit spans. Label aspect sentiment `positive`, `negative`, `neutral`, `mixed`, or `uncertain`; do not propagate the whole-review star label to each aspect.

## Evaluation design and completion requirements

Keep model training, validation and evaluation annotations separate by reliable product/catalog groups and duplicate-text groups. Existing test records were exposed during Phase 2 EDA, so a queue sampled from them supports a diagnostic benchmark, not a fresh confirmatory final holdout. Collect a newly licensed independent final test set before strong generalization claims.

Report overall human sentiment separately from rating-derived weak-label agreement. For genuine aspect labels, report extraction precision/recall/F1 under a stated exact/partial span policy, and aspect sentiment macro/per-class F1 on gold aspects separately from end-to-end predictions. Report label support and annotator agreement; reserve training-only/validation-only data for model development.

Current status: **zero independent human labels supplied; supervised ABSA and primary human sentiment evaluation incomplete**. A future supervised trainer needs adjudicated annotation files, verified reuse rights, a finalized taxonomy/mixed-label policy and a leakage-safe benchmark. No rule outputs are counted as human labels.

## Inspected external sources

- [SemEval-2014 ABSA task](https://alt.qcri.org/semeval2014/task4/) contains genuine laptop aspect terms/polarities, but its [data page](https://alt.qcri.org/semeval2014/task4/index.php?id=data-and-tools) refers to fair-use/provider conditions. Unrestricted reuse was not verified, so the data was not downloaded or used.
- Access to the SetFit ABSA laptop mirror could not be verified in this session. A mirror's accessibility alone would not establish rights to the underlying reviews.
- No general sentiment dataset was relabeled as technology-product ABSA. Dataset/model licenses remain separate; the downloaded Google compact BERT model declares Apache-2.0.
