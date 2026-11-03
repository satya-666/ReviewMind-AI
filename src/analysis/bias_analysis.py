"""Bounded similarity checks distinguish detected overlap from proven identity leakage."""
import re
import pandas as pd
from datasketch import MinHash, MinHashLSH
from scripts.split_dataset import assign_splits, quarantine_leakage
from .dataset_analysis import percent
from .text_analysis import tokens
from scripts.categorize import CATEGORIES

def exact_text_audit(frame):
    keys = frame['cleaned_text'].fillna('').str.casefold().str.split().str.join(' ')
    groups = frame.groupby(keys)['split'].nunique()
    canonical = frame['cleaned_text'].fillna('').map(lambda s:' '.join(tokens(s)))
    valid = canonical.ne('')
    canonical_groups = frame.loc[valid].groupby(canonical.loc[valid])['split'].nunique()
    return {'normalized_text_repeated_rows':int(keys.duplicated().sum()),
      'normalized_text_cross_split_groups':int(groups.gt(1).sum()),
      'token_canonical_cross_split_groups':int(canonical_groups.gt(1).sum()),
      'token_canonical_cross_split_rows':int(canonical.loc[valid].isin(canonical_groups.index[canonical_groups.gt(1)]).sum()),
      'canonical_note':'Secondary screen drops punctuation, emojis, one-character and numeric-only tokens. It may group unrelated short phrases; overlap is not proof of the same customer review.'}

def bounded_near_audit(frame,config):
    # shortcut: sampling/LSH can miss overlap; expand the audit before freezing a final holdout.
    samples = []
    for _,g in frame.groupby('split',sort=True):
        eligible = g.loc[g['cleaned_text'].str.len().ge(config['near_duplicate_min_characters'])].sort_values('review_id')
        samples.append(eligible.sample(n=min(config['near_duplicate_sample_per_split'],len(eligible)),random_state=config['seed']))
    sample = pd.concat(samples).sort_values('review_id').reset_index(drop=True) if samples else frame.iloc[:0].copy()
    lsh = MinHashLSH(threshold=.75,num_perm=config['near_duplicate_permutations'])
    features = {}; splits = {}; candidate_count = 0; verified = 0
    for i,row in enumerate(sample.itertuples()):
        text = ' '.join(tokens(row.cleaned_text))
        grams = {text[j:j+5] for j in range(max(1,len(text)-4))}
        signature = MinHash(num_perm=config['near_duplicate_permutations'],seed=config['seed'])
        signature.update_batch([g.encode() for g in sorted(grams)])
        for key in sorted(lsh.query(signature),key=int):
            j = int(key)
            if splits[j] == row.split:
                continue
            candidate_count += 1
            union = grams | features[j]
            score = len(grams & features[j])/len(union) if union else 1.
            if score >= config['near_duplicate_jaccard']:
                verified += 1
        features[i] = grams; splits[i] = row.split; lsh.insert(str(i),signature)
    return {'sample_reviews':len(sample),'sample_by_split':sample['split'].value_counts().sort_index().to_dict(),
      'cross_split_candidate_pairs_checked':candidate_count,'verified_high_similarity_cross_split_pairs':verified,
      'seed':config['seed'],'jaccard_threshold':config['near_duplicate_jaccard'],
      'method':'Seeded per-split bounded sample; Unicode-token character-five-gram MinHash LSH (candidate threshold .75), then exact Jaccard. Independent normalization differs from Phase 1.',
      'limitation':'Sampling and LSH can miss overlaps; no semantic paraphrase or exhaustive all-pairs claim.'}

def verify_phase1_reproduction(root,frame):
    candidate = root/'data/processed/cleaned.parquet'
    config_path = root/'configs/dataset_config.yaml'
    if not candidate.exists() or not config_path.exists():
        return {'verified':False,'reason':'Phase 1 candidate artifact or config unavailable'}
    import yaml
    config = yaml.safe_load(config_path.read_text())
    candidates = pd.read_parquet(candidate)
    candidates['split'] = assign_splits(candidates,config['seed'],config['split_fractions'])
    expected,_ = quarantine_leakage(candidates)
    expected_map = expected.set_index('review_id')['split'].sort_index()
    actual_map = frame.set_index('review_id')['split'].sort_index()
    matched = expected_map.equals(actual_map)
    return {'verified':matched,'expected_rows':len(expected),'actual_rows':len(frame),'seed':config['seed'],
            'method':'Recompute original assignment and duplicate quarantine on existing Phase 1 candidates; compare all retained IDs and split labels'}

def bias_analysis(frame,config):
    exact = exact_text_audit(frame)
    near = bounded_near_audit(frame,config)
    dates = pd.to_datetime(frame['review_date'],errors='coerce',utc=True)
    counts_by = lambda column:{str(k):int(v) for k,v in frame[column].value_counts().items()}
    def dominant_share(column):
        c = frame[column].value_counts()
        return percent(int(c.max()),len(frame)) if len(c) else None
    absent = [c for c in CATEGORIES[:-1] if not frame['product_category'].eq(c).any()]
    missing = [c for c in ['product_id','review_date','verified_purchase','helpful_votes'] if frame[c].isna().all()]
    issues = [f"Source count: {frame['source_dataset'].nunique()}; absent target categories: {', '.join(absent) or 'none'}.",
              f"Entirely missing metadata fields: {', '.join(missing) or 'none'}.",
              'Supplied language labels and rating-derived overall sentiment are not independently verified annotations.']
    return {'exact_duplicates':exact,'bounded_near_duplicates':near,
      'product_group_cross_split_groups':int(frame.groupby('product_group')['split'].nunique().gt(1).sum()),
      'dominant_share_percent':{column:dominant_share(column) for column in ['product_category','language','source_dataset']},
      'split_languages':{str(k):counts_by_group(g,'language') for k,g in frame.groupby('split')},
      'split_categories':{str(k):counts_by_group(g,'product_category') for k,g in frame.groupby('split')},
      'temporal_assessment':{'available_dates':int(dates.notna().sum()),'drift_assessable':bool(dates.nunique()>1),
                             'year_counts':{str(k):int(v) for k,v in dates.dt.year.dropna().value_counts().sort_index().items()}},
      'geography':{'market_values':counts_by('market'),'verified_customer_country_count':0,
                   'note':'India-marketplace provenance is retained; customer residence cannot be established.'},
      'verified_issues':issues,
      'potential_risks':['Similar product names/variants can leak across exact-name groups.',
                         'Short generic text and approximate similarity matching do not establish independent customers.',
                         'Whole-dataset EDA exposes holdout distributions: reserve a new independent final test set for future confirmatory evaluation.'],
      'unverified_assumptions':['Individual customer geography, independent reviewer identities and marketplace-original text cannot be verified.']}

def counts_by_group(group,column):
    return {str(k):int(v) for k,v in group[column].value_counts().items()}
