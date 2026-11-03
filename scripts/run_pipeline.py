"""Run Phase 1 only, using the checksum-pinned Flipkart source adapter."""
import hashlib
import json
import zipfile
import pandas as pd
import yaml
from download import ROOT, download
from inspect_data import inspect
from clean_data import SCHEMA, clean_text, stable_id, normalize_rating, usable, spam_like
from categorize import categorize
from detect_language import detect_language
from deduplicate import duplicate_groups
from split_dataset import assign_splits, quarantine_leakage, assert_no_leakage, NAMES
from generate_report import generate_report

def main():
    config = yaml.safe_load((ROOT/'configs/dataset_config.yaml').read_text())
    source = config['source']
    download(config)
    inspect()
    archive_path = ROOT/source['archive']
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    with zipfile.ZipFile(archive_path) as archive:
        raw = pd.read_csv(archive.open(source['member']), dtype=str, keep_default_na=False)
    expected = {'product_name','product_price','Rate','Review','Summary','Sentiment'}
    if set(raw.columns) != expected:
        raise ValueError('Source schema changed; inspect and update adapter')
    frame = pd.DataFrame(index=raw.index)
    frame['source_record_id'] = [f"v{source['version']}:{source['member']}:row:{i+1}" for i in raw.index]
    frame['review_id'] = [stable_id(source['dataset'],digest,x) for x in frame['source_record_id']]
    frame['source_dataset'] = source['dataset']
    frame['source_platform'] = 'flipkart'
    frame['source_archive_sha256'] = digest
    frame['source_version'] = source['version']
    frame['source_row'] = raw.index + 1
    frame['product_name'] = raw['product_name'].replace('',None)
    frame['product_id'] = None  # No reliable catalog identifier in this source.
    frame['product_group'] = [stable_id('flipkart_exact_name',clean_text(n)) if clean_text(n)
                              else stable_id('missing_product',r) for n,r in zip(raw['product_name'],frame['review_id'])]
    frame['product_group_method'] = 'exact_name_proxy_not_catalog_id'
    frame['product_category'] = raw['product_name'].map(categorize)
    # Summary contains the review body; Review is the title. Preserve each verbatim.
    frame['review_text'] = raw['Summary'].replace('',None)
    frame['review_title_original'] = raw['Review'].replace('',None)
    frame['text_origin'] = 'Summary'
    fallback = ~frame['review_text'].map(lambda x:usable(clean_text(x)))
    frame.loc[fallback,'review_text'] = frame.loc[fallback,'review_title_original']
    frame.loc[fallback,'text_origin'] = 'Review_title_fallback'
    frame['rating_original'] = raw['Rate'].replace('',None)
    frame['rating'] = raw['Rate'].map(lambda x:normalize_rating(x,source['rating_scale'])).astype('Float64')
    frame['rating_invalid'] = raw['Rate'].ne('') & frame['rating'].isna()
    frame['review_date'] = None
    frame['verified_purchase'] = pd.Series(pd.NA,index=frame.index,dtype='boolean')
    frame['helpful_votes'] = pd.Series(pd.NA,index=frame.index,dtype='Int64')
    frame['market'] = source['market']
    frame['language'] = 'unknown'
    frame['license_status'] = source['license_status']
    frame['cleaned_text'] = frame['review_text'].map(clean_text)
    frame['short_review'] = frame['cleaned_text'].str.split().str.len().lt(3)
    frame['spam_like'] = frame['cleaned_text'].map(spam_like)
    frame['encoding_warning'] = frame['cleaned_text'].str.contains('�|Ã|Â',regex=True)
    frame.to_parquet(ROOT/'data/interim/standardized.parquet',index=False)
    print('Standardized',len(frame),flush=True)
    stages = []
    exclusions = []
    def remove(mask, reason):
        nonlocal frame
        before = len(frame)
        excluded = frame.loc[mask].copy()
        excluded['exclusion_reason'] = reason
        exclusions.append(excluded)
        frame = frame.loc[~mask].copy()
        stages.append({'stage':reason,'input':before,'removed':len(excluded),'remaining':len(frame)})
    remove(~frame['cleaned_text'].map(usable),'empty_or_unusable_text')
    # Only repeated stable source IDs prove duplicate records; identical phrases do not.
    remove(frame.duplicated('review_id'),'duplicate_source_record_id')
    cleaned_count = len(frame)
    remove(frame['product_category'].eq('unknown'),'unknown_or_out_of_scope_product')
    remove(~frame['license_status'].eq('verified_publisher_declaration'),'license_not_cleared')
    frame = frame.reset_index(drop=True)
    print('Technology candidates',len(frame),flush=True)
    language_columns = ['language','language_confidence','language_manual_review','language_method']
    # Reuse exact-text labels only when the detector code fingerprint matches.
    fingerprint = hashlib.sha256((ROOT/'scripts/detect_language.py').read_bytes()).hexdigest()
    cache_path = ROOT/'data/interim/language_cache.parquet'
    cache = {}
    if cache_path.exists():
        cached = pd.read_parquet(cache_path)
        if cached['detector_sha256'].eq(fingerprint).all():
            cache = {r[0]:tuple(r[1:5]) for r in cached.itertuples(index=False,name=None)}
    languages = []
    for text in frame['cleaned_text']:
        if text not in cache:
            cache[text] = detect_language(text)
        languages.append(cache[text])
    pd.DataFrame([(k,*v,fingerprint) for k,v in cache.items()],columns=['cleaned_text',*language_columns,'detector_sha256']).to_parquet(cache_path,index=False)
    frame[language_columns] = pd.DataFrame(languages,index=frame.index)
    print('Language labeling finished',flush=True)
    groups, duplicates = duplicate_groups(frame,config['near_duplicate'])
    frame['duplicate_group'] = groups
    frame.to_parquet(ROOT/'data/processed/cleaned.parquet',index=False)
    print('Duplicate grouping finished',flush=True)
    frame['split'] = assign_splits(frame,config['seed'],config['split_fractions'])
    proposed = frame['split'].value_counts().to_dict()
    ready, leakage = quarantine_leakage(frame)
    leakage['exclusion_reason'] = 'cross_split_duplicate_text_group'
    exclusions.append(leakage)
    stages.append({'stage':'cross_split_duplicate_text_group','input':len(frame),'removed':len(leakage),'remaining':len(ready)})
    assert_no_leakage(ready)
    assert set(SCHEMA) <= set(ready.columns)
    ready.to_parquet(ROOT/'data/processed/training_ready.parquet',index=False)
    for name in NAMES:
        ready.loc[ready['split'].eq(name)].to_parquet(ROOT/f'data/splits/{name}.parquet',index=False)
    pd.concat(exclusions,ignore_index=True).to_parquet(ROOT/'data/interim/excluded.parquet',index=False)
    # Store pair evidence without review text in the report.
    pairs = []
    for a,b in duplicates.pop('exact_pairs'):
        pairs.append({'review_id_a':frame.iloc[a]['review_id'],'review_id_b':frame.iloc[b]['review_id'],'type':'exact','similarity':1.0})
    for a,b,score in duplicates.pop('near_pairs'):
        pairs.append({'review_id_a':frame.iloc[a]['review_id'],'review_id_b':frame.iloc[b]['review_id'],'type':'near','similarity':score})
    pd.DataFrame(pairs,columns=['review_id_a','review_id_b','type','similarity']).to_parquet(ROOT/'data/interim/duplicate_pairs.parquet',index=False)
    duplicates['identical_full_source_rows'] = int(raw.duplicated().sum())
    duplicates['policy'] = 'Retain ambiguous identical rows and customer phrases; quarantine evaluation rows sharing a detected text group with higher-priority train/validation split.'
    (ROOT/'reports/deduplication.json').write_text(json.dumps(duplicates,indent=2)+'\n')
    generate_report(raw,frame,ready,stages,duplicates,config,cleaned_count,proposed)
    print('Training-ready',len(ready),ready['split'].value_counts().to_dict(),flush=True)

if __name__ == '__main__':
    main()
