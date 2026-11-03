"""Loading and descriptive quality checks; never modify Phase 1 artifacts."""
import hashlib
from pathlib import Path
import pandas as pd
from scripts.clean_data import SCHEMA, clean_text, usable
from scripts.categorize import CATEGORIES

LANGUAGES = ['english','hindi','hinglish','other_indic','other','unknown']
SPLITS = ['train','validation','test']

def percent(count, total):
    return round(100 * count / total, 4) if total else None

def counts(series, levels=None):
    values = series.dropna().value_counts()
    return {str(k):int(values.get(k,0)) for k in (levels if levels is not None else sorted(values.index))}

def summary(series):
    values = pd.to_numeric(series,errors='coerce').dropna()
    if values.empty:
        return dict.fromkeys(['count','mean','median','min','p25','p75','p95','max'],None) | {'count':0}
    return {'count':len(values),'mean':float(values.mean()),'median':float(values.median()),
            'min':float(values.min()),'p25':float(values.quantile(.25)),
            'p75':float(values.quantile(.75)),'p95':float(values.quantile(.95)),'max':float(values.max())}

def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()

def load_splits(root, config):
    frames = []
    for name, relative in config['splits'].items():
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f'Missing Phase 1 split: {relative}; run Phase 1 first')
        frame = pd.read_parquet(path)
        missing = set(SCHEMA + ['cleaned_text','product_group','duplicate_group']) - set(frame.columns)
        if missing:
            raise ValueError(f'{relative}: missing required columns {sorted(missing)}')
        if 'split' in frame and not frame['split'].eq(name).all():
            raise ValueError(f'{relative}: inconsistent stored split labels')
        frame['split'] = name
        frames.append(frame)
    if set(config['splits']) != set(SPLITS):
        raise ValueError('Configuration must specify train, validation and test')
    return pd.concat(frames,ignore_index=True).sort_values('review_id',kind='stable').reset_index(drop=True)

def missingness(frame):
    return {column:{'count':int((frame[column].isna() | frame[column].astype('string').str.strip().eq('').fillna(False)).sum()),
                    'percent':percent(int((frame[column].isna() | frame[column].astype('string').str.strip().eq('').fillna(False)).sum()),len(frame))}
            for column in SCHEMA}

def validation_summary(frame):
    ratings = pd.to_numeric(frame['rating'],errors='coerce')
    invalid_rating = frame['rating'].notna() & (~ratings.between(1,5) | ratings.mod(1).ne(0))
    failures = {
      'missing_or_blank_review_ids':int((frame['review_id'].isna() | frame['review_id'].astype('string').str.strip().eq('')).sum()),
      'repeated_review_ids':int(frame['review_id'].duplicated().sum()),
      'invalid_ratings':int(invalid_rating.sum()),
      'invalid_categories':int((~frame['product_category'].isin(CATEGORIES)).sum()),
      'invalid_language_labels':int((~frame['language'].isin(LANGUAGES)).sum()),
      'unusable_original_text':int((~frame['review_text'].map(lambda x:usable(clean_text(x))).astype(bool)).sum()),
      'unusable_cleaned_text':int((~frame['cleaned_text'].map(lambda x:usable(clean_text(x))).astype(bool)).sum()),
      'missing_product_groups':int(frame['product_group'].isna().sum()),
      'missing_duplicate_groups':int(frame['duplicate_group'].isna().sum()),
    }
    for column in ['review_id','product_group','duplicate_group']:
        failures[column+'_cross_split_groups'] = int(frame.groupby(column)['split'].nunique().gt(1).sum())
    failures['product_groups_with_conflicting_categories'] = int(frame.groupby('product_group')['product_category'].nunique().gt(1).sum())
    known = frame.dropna(subset=['product_id'])
    failures['known_product_ids_cross_split'] = int(known.groupby(['source_platform','product_id'])['split'].nunique().gt(1).sum())
    dates = pd.to_datetime(frame['review_date'],utc=True,errors='coerce')
    failures['invalid_nonmissing_dates'] = int((frame['review_date'].notna() & dates.isna()).sum())
    return {'passed':not any(failures.values()),'checks':failures,
            'catalog_product_identity_verified':bool(len(frame) and frame['product_id'].notna().all()),
            'product_identity_basis':'exact-name product_group proxy; no verified catalog identities',
            'missingness':missingness(frame)}

def dataset_overview(frame):
    validation = validation_summary(frame)
    valid = frame['review_text'].map(lambda x:usable(clean_text(x))).astype(bool) & frame['rating'].notna()
    per_product = frame.groupby('product_group').size()
    dates = pd.to_datetime(frame['review_date'],errors='coerce',utc=True).dropna()
    missing = pd.DataFrame({k:frame[k].isna() | frame[k].astype('string').str.strip().eq('').fillna(False) for k in SCHEMA})
    return {'total_reviews':len(frame),'verified_catalog_products':int(frame['product_id'].nunique()),
      'unique_product_name_groups':int(frame['product_group'].nunique()),
      'represented_technology_categories':int(frame.loc[frame['product_category'].ne('unknown'),'product_category'].nunique()),
      'reviews_per_source':counts(frame['source_dataset']),'reviews_per_platform':counts(frame['source_platform']),
      'reviews_per_category':counts(frame['product_category'],CATEGORIES),
      'reviews_per_language':counts(frame['language'],LANGUAGES),'reviews_per_split':counts(frame['split'],SPLITS),
      'rows_with_any_missing_schema_field':int(missing.any(axis=1).sum()),
      'usable_count':int(valid.sum()),'usable_percent':percent(int(valid.sum()),len(frame)),
      'usable_definition':'Nonempty usable original text and nonmissing rating; does not validate language or catalog identity',
      'reviews_per_product_group':summary(per_product),
      'review_date_range':{'min':dates.min().isoformat() if len(dates) else None,'max':dates.max().isoformat() if len(dates) else None,'available_reviews':len(dates)},
      'source_category_coverage':{source:counts(group['product_category'],CATEGORIES) for source,group in frame.groupby('source_dataset')},
      'missingness':validation['missingness']}
