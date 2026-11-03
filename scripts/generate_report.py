"""Write actual measurements and explicit limits; never substitute targets for results."""
import json
import pandas as pd
from download import ROOT
from categorize import CATEGORIES
from clean_data import SCHEMA

LIMITATIONS = [
 'Source lacks catalog IDs, customer IDs, original review IDs, review dates, purchase verification and helpful votes. Nulls are preserved.',
 'Exact full product names are leakage proxies, not verified product identities. Different spellings/variants can still leak; similar names are never merged.',
 'Flipkart is India-marketplace coverage; individual customer residence is unverified. No Indian-customer claim is supported.',
 'Publisher reports prior text cleaning and scraping in December 2022. Originals mean the downloaded source strings, not recoverable marketplace originals.',
 'Publisher-declared ODbL/DbCL permits reuse subject to attribution and database share-alike obligations. Underlying third-party rights are not independently established; no datasets are committed or redistributed.',
 'Amazon Reviews 2023 has no license declaration in the inspected current card/API and is excluded pending manual clearance. Its starter review Parquet paths are absent.',
 'Language labels are weak, uncalibrated estimates, not multilingual ground truth. Roman Hindi lexicon is incomplete; Devanagari is shared across languages. Short phrases often remain unknown.',
 'MinHash LSH is approximate candidate retrieval (128 permutations, retrieval threshold 0.75), verified at 0.90 character-five-gram Jaccard for texts >=40 characters. Undetected similarities and semantic paraphrases remain possible. Short text uses exact matches only.',
 'Generic repeated phrases are legitimate potential customer records, so they remain within a split. Ambiguous identical source rows are counted but not automatically deleted without author/record identity evidence.',
 'To prevent detected leakage without merging products, text groups spanning proposed splits retain train first, then validation, then test. Conflicting evaluation rows are quarantined. This makes evaluation less representative and changes ratios.',
 'Small numbers of products, category imbalance, source selection, historical collection, prior cleaning and short reviews limit generalization. Category/language proportions cannot all be preserved under product grouping.',
 'Unknown/out-of-scope products are retained in standardized/excluded artifacts and excluded from technology training-ready splits. Missing or invalid ratings remain null; no aspect labels or sentiment ground truth are created.',
 'Hinglish/Hindi/general sentiment discovery datasets were not ingested: no independently licensed electronics-specific source was established. No model or frontend was built.',
]

def counts(frame,key):
    return {str(k):int(v) for k,v in frame[key].value_counts(dropna=False).items()}

def generate_report(raw,processed,ready,stages,duplicates,config,cleaned_count,proposed):
    languages = ['english','hindi','hinglish','other_indic','other','unknown']
    quality = {
      'status':'phase1_pipeline_validated_collection_partial',
      'access_date':config['access_date'], 'target_reviews':config['target_reviews'],
      'total_raw_reviews_found':len(raw), 'total_successfully_downloaded':len(raw),
      'total_cleaned_reviews_all_domains':cleaned_count, 'technology_candidates':len(processed),
      'total_training_ready_reviews':len(ready),
      'category_distribution':{k:int(ready['product_category'].eq(k).sum()) for k in CATEGORIES},
      'language_distribution':{k:int(ready['language'].eq(k).sum()) for k in languages},
      'candidate_category_distribution':counts(processed,'product_category'),
      'candidate_language_distribution':counts(processed,'language'),
      'source_distribution':counts(ready,'source_dataset'),
      'rating_distribution':counts(ready,'rating'),
      'missing_percentages':{k:round(float(ready[k].isna().mean()*100),3) for k in SCHEMA},
      'cleaning_stages':stages, 'duplicates':duplicates,
      'split_sizes':{k:int(ready['split'].eq(k).sum()) for k in ['train','validation','test']},
      'proposed_split_sizes_before_quarantine':proposed,
      'split_percentages':{k:round(float(ready['split'].eq(k).mean()*100),3) for k in ['train','validation','test']},
      'split_distributions':{k:{c:counts(ready.loc[ready['split'].eq(k)],c) for c in ['product_category','language']} for k in ['train','validation','test']},
      'seed':config['seed'], 'requested_split_fractions':config['split_fractions'],
      'leakage_checks':{k:int(ready.groupby(k)['split'].nunique().gt(1).sum()) for k in ['review_id','product_group','duplicate_group']},
      'flags':{k:int(ready[k].sum()) for k in ['short_review','spam_like','encoding_warning','rating_invalid','language_manual_review']},
      'title_fallback_reviews':int(ready['text_origin'].eq('Review_title_fallback').sum()),
      'unique_product_name_groups':int(ready['product_group'].nunique()),
      'indian_marketplace_reviews':len(ready), 'verified_indian_customer_reviews':0,
      'known_limitations':LIMITATIONS,
      'acquisition_failures':[
          'Starter downloader executed: all five categories failed sandbox DNS; authoritative inventory then confirmed no raw_review_<category> Parquet paths. Computers is not a raw category.',
          'Amazon excluded on license grounds after successful card/API retrieval; no duplicate or full-corpus download attempted.',
      ],
    }
    (ROOT/'reports/data_quality.json').write_text(json.dumps(quality,indent=2,ensure_ascii=False)+'\n')
    sources = [
      {'dataset_name':config['source']['dataset'],'source_url':config['source']['url'],
       'license_information':'Publisher declares Database: Open Database, Contents: Database Contents (ODbL 1.0 + DbCL 1.0)',
       'license_evidence':'reports/evidence/flipkart_metadata.json; reports/evidence/odbl_1.0.html; reports/evidence/dbcl_1.0.html',
       'access_date':config['access_date'],'usage_restrictions':'Attribute Nirali Vaghani and source; database share-alike and notices on public use/distribution; do not assume independent clearance of third-party rights',
       'downloaded_review_count':len(raw),'training_ready_review_count':len(ready),
       'geographic_limitations':'Indian marketplace; customer country unverified','status':'used_publisher_license_verified','version':'1'},
      {'dataset_name':'Amazon Reviews 2023','source_url':'https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023',
       'license_information':'No explicit license found in current publisher README or cardData; manual review required',
       'license_evidence':'reports/evidence/amazon_README.md; reports/evidence/amazon_api.json',
       'access_date':config['access_date'],'usage_restrictions':'Excluded from training-ready data pending license clearance',
       'downloaded_review_count':0,'training_ready_review_count':0,'geographic_limitations':'International supplemental source; not India-specific',
       'status':'excluded_license_unverified','version':'2b6d039ed471f2ba5fd2acb718bf33b0a7e5598e'},
      {'dataset_name':'Hindi/Hinglish discovery','source_url':'https://huggingface.co/datasets?search=hinglish%20sentiment',
       'license_information':'Discovery only; no specific source licensed or acquired','license_evidence':'starter/reviewmind_starter/sources.csv',
       'access_date':config['access_date'],'usage_restrictions':'Do not treat general sentiment as electronics reviews',
       'downloaded_review_count':0,'training_ready_review_count':0,'geographic_limitations':'Language alone does not establish geography',
       'status':'not_acquired','version':''},
    ]
    pd.DataFrame(sources).to_csv(ROOT/'reports/dataset_sources.csv',index=False)
    pd.Series(quality['category_distribution'],name='reviews').rename_axis('category').to_csv(ROOT/'reports/category_distribution.csv')
    pd.Series(quality['language_distribution'],name='reviews').rename_axis('language').to_csv(ROOT/'reports/language_distribution.csv')
    lines = ['# ReviewMind AI — Phase 1 report','',
      'Pipeline executed on real source records. Collection is partial relative to the 50,000 technology-review target; no synthetic reviews are included. Automated test results are recorded separately in reports/test_results.txt.', '',
      f"Access date: {config['access_date']}. Seed: {config['seed']}. Source: Flipkart Kaggle version 1, Nirali Vaghani.", '',
      '| Measurement | Actual |','|---|---:|',
      f'| Raw rows found and downloaded | {len(raw):,} |',
      f'| Cleaned rows, all domains | {cleaned_count:,} |',
      f'| Technology candidates | {len(processed):,} |',
      f'| Training-ready reviews | {len(ready):,} |',
      f"| Train / validation / test | {' / '.join(str(v) for v in quality['split_sizes'].values())} |", '',
      'The publisher description says 205,053 rows; the downloaded CSV has 205,052 data rows plus its header. The raw file is not altered.','',
      '## Category counts','', '| Category | Reviews |','|---|---:|']
    lines += [f'| {k} | {v:,} |' for k,v in quality['category_distribution'].items()]
    lines += ['', '## Language counts','', '| Language | Reviews |','|---|---:|']
    lines += [f'| {k} | {v:,} |' for k,v in quality['language_distribution'].items()]
    lines += ['', '## Cleaning and exclusions','', '| Stage | Input | Removed | Remaining |','|---|---:|---:|---:|']
    lines += [f"| {s['stage']} | {s['input']} | {s['removed']} | {s['remaining']} |" for s in stages]
    lines += ['', '## Duplicates and splitting','',json.dumps(duplicates,indent=2),'',
      'Products are assigned greedily to 70/15/15 targets using row counts and category-language strata; deterministic ties use seed 42. Exact full-name groups are indivisible. Detected text conflicts are quarantined from lower-priority splits; they remain available in excluded.parquet. This is a defensible fallback, not verified catalog-product disjointness.','',
      f"Final percentages: {quality['split_percentages']}. Proposed sizes before quarantine: {proposed}.",'',
      f"Detected cross-split conflicts remaining: {quality['leakage_checks']}.",'',
      '## Rating distribution','',json.dumps(quality['rating_distribution'],indent=2),'',
      'Source Rate has numeric values 1–5, consistent with the Flipkart star scale. Three malformed shifted rows have product strings in Rate; ratings are nulled. No rating-derived aspect or sentiment labels are created.','',
      '## Missing percentages','', '| Field | Missing % |','|---|---:|']
    lines += [f'| {k} | {v} |' for k,v in quality['missing_percentages'].items()]
    lines += ['', '## Source and geography','',json.dumps(quality['source_distribution'],indent=2),'',
      f"India-marketplace records: {len(ready):,}; verified Indian customer locations: 0. Sources, access dates and restrictions are in dataset_sources.csv. Archive SHA-256 is in download_manifest.json.",'',
      '## Quality flags','',json.dumps(quality['flags'],indent=2),'',
      'Flags identify potential issues; they do not prove fraud. Short reviews, punctuation and emojis are retained. Language uncertainty does not make review content unusable.','',
      '## Licenses, biases and remaining gaps','']
    lines += ['- '+x for x in LIMITATIONS]
    lines += ['', '## Acquisition limitations',''] + ['- '+x for x in quality['acquisition_failures']]
    lines += ['', '## Next collection needs','',
      'Collect independently licensed, recent, catalog-linked reviews for all nine categories, with a manually verified Hindi/Hinglish evaluation sample and product identity checks. Review licensing before public redistribution or commercial use. No Phase 2 work has started.','']
    (ROOT/'reports/phase1_report.md').write_text('\n'.join(lines))

if __name__ == '__main__':
    raise SystemExit('Run python scripts/run_pipeline.py to regenerate reports from source data.')
