# Reproducible portfolio evaluation

Run `.venv/bin/python scripts/evaluate_portfolio.py` after dataset preparation. This evaluates the existing serving checkpoint and a train-majority baseline on identical held-out rows. A frozen clone refitted only on train reproduces TF-IDF vocabulary, IDF and all test predictions. It does not retune on test.

Labels come from stars (1–2 negative, 3 neutral, 4–5 positive), not independent sentiment annotations. The test has already been inspected in earlier phases; it is not a fresh final holdout. Smartphone and Hindi training coverage is absent.

| Model | Test reviews | Macro F1 |
|---|---:|---:|
| Train-majority | 2451 | 0.2817 |
| TF-IDF + logistic regression | 2451 | 0.6728 |

| Class | Train | Test | Precision | Recall |
|---|---:|---:|---:|---:|
| negative | 2073 | 474 | 0.8103 | 0.8650 |
| neutral | 1144 | 184 | 0.2286 | 0.3043 |
| positive | 15150 | 1793 | 0.9459 | 0.8968 |

Confusion matrix: rows = true rating label, columns = prediction, order negative / neutral / positive.

```json
[[410, 42, 22], [58, 56, 70], [38, 147, 1608]]
```

Duplicate audit: 0 detected cross-split groups. All retained rows: exact casefold text plus seeded 128-permutation MinHash candidates; character 5-gram Jaccard >=0.90 for text >=80 characters. Approximate candidate search is not proof of universal absence.

Mixed and negation slices are lexical markers with rating labels, not labeled mixed/negation understanding. Per-slice metrics and sample counts are in [the JSON](portfolio_evaluation.json). Hinglish is too small for a reliable generalization claim.

Manual aspect diagnostics: 10 authored examples; detection precision 1.000, recall 1.000; matched-aspect polarity accuracy 0.833. Small developer-authored English/Hinglish diagnostic set, selected with knowledge of rules; no independent annotator or representative sampling; not a supervised ABSA benchmark.

Five real rating-label disagreements are identified in the JSON. Exact customer text is written locally to `data/interim/portfolio_errors.json` by the reproduction command and is excluded from Git. Inspect these alongside their rating labels; a disagreement can reflect an imperfect weak label.

Dataset: Nirali Vaghani, Flipkart Product reviews with sentiment Dataset v1 (Kaggle); archive hash and split hashes are in the JSON manifest. Attribution, source evidence, ODbL/DbCL notices and acquisition constraints are in [the dataset handoff](../docs/PHASE_1.md).
