"""Derive weak labels and leakage-filtered views without changing Phase 1 files."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from src.analysis.dataset_analysis import load_splits, validation_summary, sha256, counts
from src.analysis.rating_analysis import weak_sentiment
from src.analysis.text_analysis import tokens

ROOT=Path(__file__).resolve().parents[2]
LABELS=['negative','neutral','positive']
LABEL_MAP={name:i for i,name in enumerate(LABELS)}

def prepare(config,mode='full'):
    frame=load_splits(ROOT,config)
    original_sizes=counts(frame['split'])
    validation=validation_summary(frame)
    if not validation['passed']:
        raise ValueError('Phase 1 structural validation failed; inputs are not modified')
    frame['canonical_key']=frame['cleaned_text'].map(lambda s:' '.join(tokens(s)))
    empty=frame['canonical_key'].eq('')
    frame.loc[empty,'canonical_key']=frame.loc[empty,'review_id']
    priority={'train':0,'validation':1,'test':2}
    winners=frame.groupby('canonical_key')['split'].agg(lambda s:min(s,key=priority.get))
    keep=frame['split'].eq(frame['canonical_key'].map(winners))
    removed=frame.loc[~keep]
    frame=frame.loc[keep].copy()
    frame['weak_label']=weak_sentiment(frame['rating'])
    if not frame['weak_label'].isin(LABELS).all():
        raise ValueError('Missing/invalid star ratings cannot become supervision')
    frame['label_id']=frame['weak_label'].map(LABEL_MAP).astype(int)
    for field in ['review_id','product_group','duplicate_group','canonical_key']:
        if frame.groupby(field)['split'].nunique().gt(1).any():
            raise ValueError('Cross-split overlap remains: '+field)
    splits={name:frame.loc[frame['split'].eq(name)].sort_values('review_id').reset_index(drop=True) for name in config['splits']}
    if mode=='smoke':
        splits={name:sample_rows(g,config['smoke'][name+'_reviews'],config['seed']) for name,g in splits.items()}
    manifest={'label_provenance':'rating-derived weak overall labels only; no human-verified sentiment benchmark',
      'input_sha256':{path:sha256(ROOT/path) for path in config['splits'].values()},
      'structural_validation':validation['checks'],'original_split_sizes':original_sizes,
      'canonical_quarantine_removed':counts(removed['split']),
      'derivation':'Full Phase 2 token-canonical key; retain train before validation before test; never move evaluation data into training',
      'splits':{name:{'reviews':len(g),'classes':counts(g['weak_label'],LABELS),'languages':counts(g['language']),
         'categories':counts(g['product_category']),'product_groups':int(g['product_group'].nunique()),
         'review_ids_sha256':hashlib.sha256('\n'.join(g.review_id).encode()).hexdigest()} for name,g in splits.items()},
      'catalog_product_identity_verified':False,'human_sentiment_test_available':False,
      'scope':'Exploratory weak-label benchmark, previously inspected during EDA; not an independent final test set'}
    return splits,manifest

def sample_rows(frame,limit,seed):
    if limit is None or len(frame)<=limit:
        return frame.copy().reset_index(drop=True)
    from sklearn.model_selection import train_test_split
    indices,_=train_test_split(np.arange(len(frame)),train_size=limit,random_state=seed,stratify=frame['label_id'])
    return frame.iloc[sorted(indices)].reset_index(drop=True)

def annotation_workflow(splits,config,mode='full'):
    directory=ROOT/'data/annotations';directory.mkdir(exist_ok=True)
    target=directory/('phase3_smoke_annotation_queue.json' if mode=='smoke' else 'phase3_annotation_queue.json')
    if target.exists():
        existing=json.loads(target.read_text())
        if any(r.get('overall_label') or r.get('aspects') or r.get('annotator_id') for r in existing):
            return {'status':'existing annotation work preserved; independent provenance/adjudication must be verified before model use',
              'queued_reviews':len(existing),'path':str(target.relative_to(ROOT)),'human_labels_used_for_training':False}
    rows=[]
    for split,g in splits.items():
        sample=sample_rows(g,config['annotation_sample_per_split'],config['seed'])
        for row in sample.itertuples():
            rows.append({'review_id':row.review_id,'source_split':split,'product_category':row.product_category,
              'language_hint_unverified':row.language,'text':row.review_text,'overall_label':None,
              'aspects':None,'annotator_id':None,'adjudicated':False})
    target.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    return {'queued_reviews':len(rows),'human_labels_completed':0,'path':str(target.relative_to(ROOT)),
            'public_raw_text':False,'status':'awaiting independent human annotation; not used for supervised ABSA or primary evaluation'}
