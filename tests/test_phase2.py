"""Unit fixtures are artificial; integration checks read actual Phase 1 artifacts."""
import json
from pathlib import Path
import pandas as pd
import pytest
import yaml
from scripts.clean_data import SCHEMA
from src.analysis.dataset_analysis import load_splits, validation_summary, dataset_overview, sha256
from src.analysis.rating_analysis import rating_analysis, weak_sentiment
from src.analysis.category_analysis import category_analysis
from src.analysis.language_analysis import language_analysis, uncertain_sample, redact
from src.analysis.text_analysis import text_analysis, tokens
from src.analysis.product_analysis import product_analysis
from src.analysis.bias_analysis import exact_text_audit, bounded_near_audit, verify_phase1_reproduction
from src.analysis.visualization import plot_figures, FIGURES
from scripts.run_phase2 import ROOT, analyze, write_json

@pytest.fixture
def config():
    return yaml.safe_load((ROOT/'configs/phase2_config.yaml').read_text())

@pytest.fixture
def small():
    d = pd.DataFrame({k:[None]*5 for k in SCHEMA})
    d['review_id'] = ['a','b','c','d','e']
    d['product_group'] = ['p1','p1','p2','p3','p4']
    d['product_name'] = ['A','A','B','C','D']
    d['product_category'] = ['audio_devices']*3+['laptops']*2
    d['split'] = ['train','train','validation','test','train']
    d['language'] = ['english','unknown','hinglish','english','unknown']
    d['rating'] = pd.Series([1,2,3,4,5],dtype='Float64')
    d['review_text'] = ['good battery','bad sound','bahut acha hai','works very well','ok']
    d['cleaned_text'] = d['review_text']
    d['duplicate_group'] = d['review_id']
    d['source_platform'] = 'flipkart'; d['source_dataset'] = 'fixture'
    d['market'] = 'unknown'; d['source_record_id'] = d['review_id']
    d['language_confidence'] = [.99,None,None,.98,None]
    d['language_manual_review'] = [False,True,True,False,True]
    return d

def test_load_and_schema(tmp_path,small):
    config = {'splits':{name:name+'.parquet' for name in ['train','validation','test']}}
    for name,path in config['splits'].items():
        small.loc[small['split'].eq(name)].to_parquet(tmp_path/path,index=False)
    loaded = load_splits(tmp_path,config)
    assert len(loaded)==5 and loaded.review_id.is_unique
    (tmp_path/'test.parquet').unlink()
    with pytest.raises(FileNotFoundError,match='Missing Phase 1'):
        load_splits(tmp_path,config)
    small.drop(columns='rating').to_parquet(tmp_path/'train.parquet',index=False)
    with pytest.raises(ValueError,match='missing required columns'):
        load_splits(tmp_path,config)

def test_rating_calculations(small):
    result = rating_analysis(small)
    assert result['summary']['mean']==3
    assert result['summary']['median']==3
    assert result['low_rated_percent']==40
    assert result['high_rated_percent']==40
    assert result['weak_sentiment_counts']=={'negative':2,'neutral':1,'positive':2,'unavailable':0}
    assert weak_sentiment(pd.Series([None,0,6])).eq('unavailable').all()

def test_categories_and_products(small,config):
    categories=category_analysis(small,config)
    assert categories['audio_devices']['reviews']==3
    assert categories['audio_devices']['unique_product_name_groups']==2
    assert categories['audio_devices']['rating']['summary']['mean']==2
    assert categories['smartphones']['reviews']==0
    assert categories['smartphones']['rating']['summary']['mean'] is None
    products=product_analysis(small,config)
    assert products['coverage_bands']['fewer_than_5']==4
    assert products['top_1_review_share_percent']==40
    missing=small.copy(); missing['rating']=float('nan')
    assert product_analysis(missing,config)['per_group']['p1']['average_rating'] is None

def test_language_and_sample(small,config):
    result=language_analysis(small,config)
    assert result['counts']['english']==2
    assert result['percentages']['hinglish']==20
    assert result['unknown_or_low_confidence_percent']==60
    assert uncertain_sample(small,config).review_id.tolist()==uncertain_sample(small,config).review_id.tolist()
    assert 'example.com' not in redact('contact me at person@example.com')

def test_unicode_lengths_and_terms(small,config):
    small.loc[0,'cleaned_text']='अच्छा फोन 😀'
    result=text_analysis(small,config)
    assert result['character_length']['max']==len('works very well')
    assert result['whitespace_word_count']['median']==3
    assert tokens('अच्छा फोन')==['अच्छा','फोन']
    assert result['extremely_short_count']==2
    assert result['terms']['unigrams']==[]  # Privacy frequency floor is not met.

def test_missing_values_and_empty(small,config,tmp_path):
    result=dataset_overview(small)
    assert result['missingness']['product_id']['percent']==100
    assert result['review_date_range']['min'] is None
    empty=small.iloc[:0]
    metrics=analyze(empty,config)
    assert metrics['overview']['total_reviews']==0
    assert metrics['ratings']['summary']['mean'] is None
    assert metrics['languages']['unknown_or_low_confidence_percent'] is None
    assert len(plot_figures(empty,metrics,tmp_path))==len(FIGURES)
    write_json(tmp_path/'empty.json',metrics)
    assert json.loads((tmp_path/'empty.json').read_text())['overview']['total_reviews']==0

def test_duplicate_and_product_leakage(small,config):
    assert validation_summary(small)['passed']
    changed=small.copy()
    changed.loc[2,'review_id']='a'
    changed.loc[2,'product_group']='p1'
    changed.loc[2,'cleaned_text']='good battery'
    validation=validation_summary(changed)
    assert not validation['passed']
    assert validation['checks']['review_id_cross_split_groups']==1
    assert validation['checks']['product_group_cross_split_groups']==1
    assert exact_text_audit(changed)['normalized_text_cross_split_groups']==1
    text='The headphones have excellent sound and the battery works for many hours.'
    changed.loc[0,'cleaned_text']=text
    changed.loc[2,'cleaned_text']=text+'!'
    assert bounded_near_audit(changed,config)['verified_high_similarity_cross_split_pairs']>=1

def test_chart_and_json_generation(small,config,tmp_path):
    metrics=analyze(small,config)
    paths=plot_figures(small,metrics,tmp_path)
    assert set(paths)=={name+'.png' for name in FIGURES}
    for name in paths:
        assert (tmp_path/name).read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
        assert (tmp_path/name).stat().st_size>1000
    write_json(tmp_path/'metrics.json',metrics)
    assert json.loads((tmp_path/'metrics.json').read_text())['ratings']['summary']['mean']==3

def test_reproducibility(small,config):
    assert json.dumps(analyze(small,config),sort_keys=True,allow_nan=False)==json.dumps(analyze(small,config),sort_keys=True,allow_nan=False)

def test_actual_phase2_artifacts(config):
    frame=load_splits(ROOT,config)
    m=json.loads((ROOT/'reports/phase2_metrics.json').read_text())
    assert len(frame)==m['overview']['total_reviews']
    assert validation_summary(frame)['passed']
    assert verify_phase1_reproduction(ROOT,frame)['verified']
    assert sum(m['ratings']['distribution'].values())==frame.rating.notna().sum()
    assert sum(m['languages']['counts'].values())==len(frame)
    assert sum(c['reviews'] for c in m['categories'].values())==len(frame)
    for path,digest in m['reproducibility']['input_sha256'].items():
        assert sha256(ROOT/path)==digest
    assert len(list((ROOT/'reports/figures').glob('*.png')))==len(FIGURES)

def test_no_public_notebook_review_records():
    notebooks=list((ROOT/'notebooks').glob('*.ipynb'))
    assert len(notebooks)==4
    for path in notebooks:
        notebook=json.loads(path.read_text())
        assert path.stat().st_size<100_000
        for cell in notebook['cells']:
            if cell['cell_type']=='code':
                assert cell['execution_count'] is not None
                assert not any(output['output_type']=='error' for output in cell.get('outputs',[]))
                assert not any('image/png' in output.get('data',{}) for output in cell.get('outputs',[]))
