# ReviewMind AI — Phase 1 report

Pipeline executed on real source records. Collection is partial relative to the 50,000 technology-review target; no synthetic reviews are included. Automated test results are recorded separately in reports/test_results.txt.

Access date: 2026-10-31. Seed: 42. Source: Flipkart Kaggle version 1, Nirali Vaghani.

| Measurement | Actual |
|---|---:|
| Raw rows found and downloaded | 205,052 |
| Cleaned rows, all domains | 205,050 |
| Technology candidates | 26,605 |
| Training-ready reviews | 23,322 |
| Train / validation / test | 18367 / 2492 / 2463 |

The publisher description says 205,053 rows; the downloaded CSV has 205,052 data rows plus its header. The raw file is not altered.

## Category counts

| Category | Reviews |
|---|---:|
| smartphones | 0 |
| laptops | 3,071 |
| audio_devices | 7,680 |
| wearables | 1,905 |
| tvs_monitors | 0 |
| accessories | 3,617 |
| tablets | 1,043 |
| networking_devices | 1,176 |
| chargers_power_banks | 4,830 |
| unknown | 0 |

## Language counts

| Language | Reviews |
|---|---:|
| english | 12,433 |
| hindi | 0 |
| hinglish | 23 |
| other_indic | 0 |
| other | 249 |
| unknown | 10,617 |

## Cleaning and exclusions

| Stage | Input | Removed | Remaining |
|---|---:|---:|---:|
| empty_or_unusable_text | 205052 | 2 | 205050 |
| duplicate_source_record_id | 205050 | 0 | 205050 |
| unknown_or_out_of_scope_product | 205050 | 178445 | 26605 |
| license_not_cleared | 26605 | 0 | 26605 |
| cross_split_duplicate_text_group | 26605 | 3283 | 23322 |

## Duplicates and splitting

{
  "exact_text_pairs": 11967,
  "near_text_pairs": 4,
  "identical_full_source_rows": 34375,
  "policy": "Retain ambiguous identical rows and customer phrases; quarantine evaluation rows sharing a detected text group with higher-priority train/validation split."
}

Products are assigned greedily to 70/15/15 targets using row counts and category-language strata; deterministic ties use seed 42. Exact full-name groups are indivisible. Detected text conflicts are quarantined from lower-priority splits; they remain available in excluded.parquet. This is a defensible fallback, not verified catalog-product disjointness.

Final percentages: {'train': 78.754, 'validation': 10.685, 'test': 10.561}. Proposed sizes before quarantine: {'train': 18367, 'validation': 4182, 'test': 4056}.

Detected cross-split conflicts remaining: {'review_id': 0, 'product_group': 0, 'duplicate_group': 0}.

## Rating distribution

{
  "5.0": 14569,
  "4.0": 4306,
  "1.0": 2387,
  "3.0": 1490,
  "2.0": 570
}

Source Rate has numeric values 1–5, consistent with the Flipkart star scale. Three malformed shifted rows have product strings in Rate; ratings are nulled. No rating-derived aspect or sentiment labels are created.

## Missing percentages

| Field | Missing % |
|---|---:|
| review_id | 0.0 |
| product_id | 100.0 |
| product_name | 0.0 |
| product_category | 0.0 |
| source_platform | 0.0 |
| source_dataset | 0.0 |
| review_text | 0.0 |
| rating | 0.0 |
| review_date | 100.0 |
| language | 0.0 |
| verified_purchase | 100.0 |
| helpful_votes | 100.0 |
| market | 0.0 |
| source_record_id | 0.0 |

## Source and geography

{
  "niraliivaghani/flipkart-product-customer-reviews-dataset": 23322
}

India-marketplace records: 23,322; verified Indian customer locations: 0. Sources, access dates and restrictions are in dataset_sources.csv. Archive SHA-256 is in download_manifest.json.

## Quality flags

{
  "short_review": 7332,
  "spam_like": 5,
  "encoding_warning": 0,
  "rating_invalid": 0,
  "language_manual_review": 10640
}

Flags identify potential issues; they do not prove fraud. Short reviews, punctuation and emojis are retained. Language uncertainty does not make review content unusable.

## Licenses, biases and remaining gaps

- Source lacks catalog IDs, customer IDs, original review IDs, review dates, purchase verification and helpful votes. Nulls are preserved.
- Exact full product names are leakage proxies, not verified product identities. Different spellings/variants can still leak; similar names are never merged.
- Flipkart is India-marketplace coverage; individual customer residence is unverified. No Indian-customer claim is supported.
- Publisher reports prior text cleaning and scraping in December 2022. Originals mean the downloaded source strings, not recoverable marketplace originals.
- Publisher-declared ODbL/DbCL permits reuse subject to attribution and database share-alike obligations. Underlying third-party rights are not independently established; no datasets are committed or redistributed.
- Amazon Reviews 2023 has no license declaration in the inspected current card/API and is excluded pending manual clearance. Its starter review Parquet paths are absent.
- Language labels are weak, uncalibrated estimates, not multilingual ground truth. Roman Hindi lexicon is incomplete; Devanagari is shared across languages. Short phrases often remain unknown.
- MinHash LSH is approximate candidate retrieval (128 permutations, retrieval threshold 0.75), verified at 0.90 character-five-gram Jaccard for texts >=40 characters. Undetected similarities and semantic paraphrases remain possible. Short text uses exact matches only.
- Generic repeated phrases are legitimate potential customer records, so they remain within a split. Ambiguous identical source rows are counted but not automatically deleted without author/record identity evidence.
- To prevent detected leakage without merging products, text groups spanning proposed splits retain train first, then validation, then test. Conflicting evaluation rows are quarantined. This makes evaluation less representative and changes ratios.
- Small numbers of products, category imbalance, source selection, historical collection, prior cleaning and short reviews limit generalization. Category/language proportions cannot all be preserved under product grouping.
- Unknown/out-of-scope products are retained in standardized/excluded artifacts and excluded from technology training-ready splits. Missing or invalid ratings remain null; no aspect labels or sentiment ground truth are created.
- Hinglish/Hindi/general sentiment discovery datasets were not ingested: no independently licensed electronics-specific source was established. No model or frontend was built.

## Acquisition limitations

- Starter downloader executed: all five categories failed sandbox DNS; authoritative inventory then confirmed no raw_review_<category> Parquet paths. Computers is not a raw category.
- Amazon excluded on license grounds after successful card/API retrieval; no duplicate or full-corpus download attempted.

## Next collection needs

Collect independently licensed, recent, catalog-linked reviews for all nine categories, with a manually verified Hindi/Hinglish evaluation sample and product identity checks. Review licensing before public redistribution or commercial use. No Phase 2 work has started.
