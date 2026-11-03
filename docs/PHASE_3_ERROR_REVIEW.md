# Bounded inspection of weak-label disagreements

Inspected six seed-42 disagreement samples per completed model (18 model/sample observations) on 2026-11-03. The queues contain up to 12 disagreements per model in ignored `data/interim/phase3_errors_*.json`. Contact-pattern-redacted excerpts were inspected locally; no real review excerpt or identifying record is published here. Overlap across model samples is possible, so 18 observations are not asserted to be 18 distinct reviews.

Observed patterns:

- Some three-star/neutral references contain predominantly favorable language. A positive model prediction can disagree with the weak star label without being a clear linguistic error.
- Several reviews mix overall approval with battery, coverage, charging or other complaints. Overall weak labels and lexical predictions cannot resolve aspect-level opinions; this motivates genuine ABSA annotation.
- Some negative-reference reviews expressing explicit problems were predicted positive or neutral. Negation, nonstandard spacing/spelling and long contrastive reviews remain plausible model weaknesses.
- Very short or specification-only text supplies little overall-sentiment evidence. A categorical prediction is not proof of sufficient information or confidence.
- The small sample did not provide an independently labeled sarcasm benchmark. No conclusion about sarcasm understanding, Hindi performance or robust Romanized-Hindi handling is supported.

These are diagnostic observations rather than human-verified relabeling, a measured error taxonomy or population prevalence estimates. No source labels were changed. Quantitative error-slice scores in the model results use explicit marker rules and weak labels; they are not phenomenon-specific human accuracy metrics.

Recommended next steps are blinded annotation/adjudication, an explicit mixed/uncertain label policy, catalog-linked independent holdouts, supervised aspect annotations, and evaluation by class/category/language with enough independent evidence. The annotation guide describes how to build that benchmark without deriving aspect labels from stars.
