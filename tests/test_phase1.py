"""Synthetic unit fixtures stay in tests; integration tests use actual acquired data."""
import hashlib
import json
import zipfile
import pandas as pd
import pytest
import yaml
from download import ROOT
from clean_data import SCHEMA, clean_text, normalize_rating, normalize_date, stable_id, usable
from categorize import categorize, CATEGORIES
from detect_language import detect_language
from deduplicate import duplicate_groups
from split_dataset import assign_splits, quarantine_leakage, assert_no_leakage

@pytest.mark.parametrize('value,scale,expected',[(1,[1,5],1),(5,[1,5],5),(5,[0,10],3),
    (None,[1,5],None),('',[1,5],None),(6,[1,5],None),('bad',[1,5],None),
    (3,None,None),(float('nan'),[1,5],None),(float('inf'),[1,5],None)])
def test_rating(value,scale,expected):
    assert normalize_rating(value,scale) == expected

def test_cleaning_and_missing():
    assert clean_text(None) == ''
    assert clean_text('  अच्छा\n phone! 😀 ') == 'अच्छा phone! 😀'
    assert clean_text('e\u0301') == 'é'
    assert not usable('...')
    assert not usable('nan')
    assert usable('😀')
    assert usable('ok')
    assert normalize_date('bad-date') is None
    assert normalize_date(None) is None
    assert normalize_date('2099-01-01') is None
    assert normalize_date('2022-12-01').startswith('2022-12-01T')

@pytest.mark.parametrize('name,expected',[
    ('Bluetooth Headset','audio_devices'),('Wireless Router','networking_devices'),
    ('WiFi Router Stand','unknown'),('Wood Portable Laptop Table','unknown'),
    ('MacBook Pro Laptop','laptops'),('iPhone 13','smartphones'),
    ('iPhone 13 Case','unknown'),('Galaxy Tab','tablets'),('Smartwatch','wearables'),
    ('LED TV','tvs_monitors'),('USB Charger','chargers_power_banks'),
    ('External Hard Disk','accessories'),('Cricket Bat','unknown'),('Analog Watch','unknown'),
    ('Gaming LaptopÐÒ','laptops'),('Mickey Mouse Fabric SofaFinish Color Black','unknown'),
    ('Laptop TableFinish Color Pink','unknown'),('Smart TV Stick Media Streaming Device','unknown'),
    ('Smartwatch (Blue Strap, Regular)','wearables'),('Charger compatible with iphone','chargers_power_banks'),
    ('Bluetooth Laptop/Desktop Speaker','audio_devices'),('Guitar Interface for iPad','unknown')])
def test_category(name,expected):
    assert categorize(name) == expected

def test_language():
    assert detect_language('bahut accha hai')[0] == 'hinglish'
    assert detect_language('यह फोन बहुत अच्छा है और इसकी बैटरी शानदार है')[0] == 'hindi'
    assert detect_language('The sound quality of these headphones is excellent and I recommend them.')[0] == 'english'
    assert detect_language('ok')[0] == 'unknown'
    assert detect_language('')[0] == 'unknown'
    assert detect_language('अच्छा phone battery')[2] is True

def test_stable_identifiers():
    assert stable_id('dataset','row',1) == stable_id('dataset','row',1)
    assert stable_id('dataset','row',1) != stable_id('dataset','row',2)
    assert stable_id('a:b','c') != stable_id('a','b:c')

def test_duplicate_groups():
    text = 'The sound quality of these headphones is excellent and the battery lasts a long time.'
    d = pd.DataFrame({'review_id':['a','b','c','d'], 'cleaned_text':[text,text,text+'!', 'Entirely unrelated review.']})
    groups, report = duplicate_groups(d,{'permutations':128,'min_characters':40,'jaccard_threshold':.9})
    assert groups[0] == groups[1] == groups[2]
    assert groups[3] != groups[0]
    assert report['exact_text_pairs'] == 1
    assert report['near_text_pairs'] >= 1
    assert len(d) == 4  # Same phrases do not prove records have the same author.

def test_split_reproducibility_and_quarantine():
    d = pd.DataFrame({'review_id':[str(i) for i in range(60)],
       'product_group':[f'p{i//2}' for i in range(60)],
       'product_category':['audio_devices']*60,'language':['english']*60,
       'duplicate_group':[f't{i}' for i in range(60)]})
    d['split'] = assign_splits(d)
    assert d['split'].equals(assign_splits(d))
    shuffled = d.sample(frac=1,random_state=2)
    assert assign_splits(shuffled).sort_index().equals(d['split'].sort_index())
    assert set(d['split']) == {'train','validation','test'}
    a = d.index[d['split'].eq('train')][0]
    b = d.index[d['split'].eq('test')][0]
    d.loc[b,'duplicate_group'] = d.loc[a,'duplicate_group']
    ready, excluded = quarantine_leakage(d)
    assert b in excluded.index and a in ready.index
    assert_no_leakage(ready)

@pytest.fixture(scope='module')
def actual():
    return pd.read_parquet(ROOT/'data/processed/training_ready.parquet')

def test_actual_schema_and_nulls(actual):
    assert len(actual) > 0
    assert set(SCHEMA) <= set(actual.columns)
    assert actual.review_id.is_unique
    assert actual.product_id.isna().all()
    assert actual.review_date.isna().all()
    assert actual.verified_purchase.isna().all()
    assert actual.helpful_votes.isna().all()
    assert actual.rating.dropna().between(1,5).all()
    assert actual.product_category.isin(CATEGORIES[:-1]).all()
    assert actual.language.isin(['english','hindi','hinglish','other_indic','other','unknown']).all()
    assert actual.market.eq('india_marketplace_customer_location_unknown').all()
    assert actual.license_status.eq('verified_publisher_declaration').all()

def test_actual_provenance_and_preserved_text(actual):
    config = yaml.safe_load((ROOT/'configs/dataset_config.yaml').read_text())
    manifest = json.loads((ROOT/'reports/download_manifest.json').read_text())
    path = ROOT/config['source']['archive']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest['sha256']
    with zipfile.ZipFile(path) as archive:
        raw = pd.read_csv(archive.open(config['source']['member']),dtype=str,keep_default_na=False)
    # Verify every retained row's original source text and stable identity.
    for row in actual.itertuples():
        original = raw.iloc[row.source_row-1]
        field = 'Summary' if row.text_origin == 'Summary' else 'Review'
        assert row.review_text == original[field]
        assert row.review_id == stable_id(config['source']['dataset'],manifest['sha256'],row.source_record_id)

def test_actual_splits_and_leakage(actual):
    splits = [pd.read_parquet(ROOT/f'data/splits/{n}.parquet') for n in ['train','validation','test']]
    combined = pd.concat(splits,ignore_index=True)
    assert len(combined) == len(actual)
    assert set(combined.review_id) == set(actual.review_id)
    assert_no_leakage(combined)
    assert combined.groupby(combined.cleaned_text.str.casefold())['split'].nunique().max() == 1
    processed = pd.read_parquet(ROOT/'data/processed/cleaned.parquet')
    expected = assign_splits(processed)
    assert actual['split'].tolist() == actual.review_id.map(dict(zip(processed.review_id,expected))).tolist()
    pairs = pd.read_parquet(ROOT/'data/interim/duplicate_pairs.parquet')
    mapping = actual.set_index('review_id')['split']
    both = pairs[pairs.review_id_a.isin(mapping.index) & pairs.review_id_b.isin(mapping.index)]
    assert (both.review_id_a.map(mapping).to_numpy() == both.review_id_b.map(mapping).to_numpy()).all()

def test_report_accounting(actual):
    report = json.loads((ROOT/'reports/data_quality.json').read_text())
    excluded = pd.read_parquet(ROOT/'data/interim/excluded.parquet')
    assert report['total_raw_reviews_found'] == len(actual)+len(excluded)
    assert report['total_training_ready_reviews'] == len(actual)
    assert sum(report['split_sizes'].values()) == len(actual)
    assert sum(report['category_distribution'].values()) == len(actual)
    assert sum(report['language_distribution'].values()) == len(actual)
    assert sum(s['removed'] for s in report['cleaning_stages']) == len(excluded)
