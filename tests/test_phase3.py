"""Synthetic unit fixtures are not training data or human benchmark labels."""
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pytest
import yaml
from src.training.data import ROOT,LABEL_MAP,prepare,sample_rows
from src.analysis.rating_analysis import weak_sentiment
from src.models.baseline.train import build
from src.models.aspects.rules import aspects,load_taxonomy
from src.models.inference import ReviewPredictor
from src.evaluation.metrics import metrics,product_bootstrap

@pytest.fixture
def training_fixture():
    texts=['terrible broken bad','bad sound poor','awful poor build','average ordinary okay','neutral average okay',
      'okay average performance','excellent good amazing','great excellent sound','good quality works']*3
    labels=[0,0,0,1,1,1,2,2,2]*3
    return pd.DataFrame({'cleaned_text':texts,'label_id':labels,'product_group':[str(i//3) for i in range(len(texts))]})

def test_label_mapping_and_sampling(training_fixture):
    assert LABEL_MAP=={'negative':0,'neutral':1,'positive':2}
    assert weak_sentiment(pd.Series([1,2,3,4,5])).tolist()==['negative','negative','neutral','positive','positive']
    assert weak_sentiment(pd.Series([None,0,6])).eq('unavailable').all()
    assert sample_rows(training_fixture,12,42).equals(sample_rows(training_fixture,12,42))

@pytest.mark.parametrize('kind',['logistic_regression','linear_svm'])
def test_baseline_save_load_batch(training_fixture,tmp_path,kind):
    cfg={'word_max_features':100,'char_max_features':100,'max_iterations':1000}
    model=build(kind,cfg,seed=42).fit(training_fixture.cleaned_text,training_fixture.label_id)
    second=build(kind,cfg,seed=42).fit(training_fixture.cleaned_text,training_fixture.label_id)
    assert np.array_equal(model.predict(training_fixture.cleaned_text),second.predict(training_fixture.cleaned_text))
    path=tmp_path/(kind+'.joblib');joblib.dump(model,path)
    predictor=ReviewPredictor(path)
    assert predictor.batch([])==[]
    output=predictor.batch(['excellent sound','बहुत अच्छा है','battery acha hai'])
    assert len(output)==3 and all(r['sentiment'] in LABEL_MAP for r in output)
    assert set(output[0]['scores'])==set(LABEL_MAP)
    assert output[0]['model_version']==path.name
    if kind=='linear_svm':assert output[0]['confidence'] is None
    for invalid in ['',None,45,'...']:
        with pytest.raises(ValueError):predictor.single(invalid)

def test_transformer_configuration_and_tokenization():
    from transformers import AutoTokenizer,AutoConfig,BertConfig,BertForSequenceClassification
    from src.models.sentiment.transformer import Reviews,device_for
    cfg=yaml.safe_load((ROOT/'configs/phase3_config.yaml').read_text())['transformer']
    source=ROOT/cfg['pretrained_path']
    tokenizer=AutoTokenizer.from_pretrained(source,local_files_only=True)
    batch=tokenizer(['good battery','बैटरी अच्छी है','battery acha hai'],padding=True,return_tensors='pt')
    assert 'attention_mask' in batch and len(batch['input_ids'])==3
    architecture=AutoConfig.from_pretrained(source,local_files_only=True)
    assert architecture.hidden_size==128 and architecture.num_hidden_layers==2
    test_model=BertForSequenceClassification(BertConfig(vocab_size=100,hidden_size=16,num_hidden_layers=1,num_attention_heads=2,intermediate_size=32,num_labels=3))
    assert test_model.config.num_labels==3  # Configuration self-check, not a trained model claim.
    assert str(device_for('cpu'))=='cpu'
    dataset=Reviews(pd.DataFrame({'cleaned_text':['hello'],'label_id':[2]}),tokenizer,16)
    assert len(dataset)==1 and dataset[0]['input_ids'].shape[0]==16

def test_aspect_taxonomy_and_scoped_sentiment():
    taxonomy=load_taxonomy();assert len(taxonomy)==9
    text='The camera is excellent, but the battery drains quickly.'
    result=aspects(text,'smartphones')
    assert any(r['aspect']=='camera' and r['sentiment']=='positive' for r in result)
    assert any(r['aspect']=='battery' and r['sentiment']=='negative' for r in result)
    assert all(text[r['start']:r['end']]==r['term'] for r in result)
    assert aspects('Battery is not good','smartphones')[0]['sentiment']=='negative'
    assert aspects('बैटरी खराब है','smartphones')[0]['aspect']=='battery'
    assert aspects('battery acha hai','smartphones')[0]['sentiment']=='positive'
    assert aspects('works well','unknown')==[]
    assert aspects('Battery included','smartphones')[0]['sentiment']=='unknown'

def test_metrics_and_bootstrap():
    score=metrics([0,1,2],[0,0,2])
    assert score['accuracy']==pytest.approx(2/3)
    assert score['macro_f1']==pytest.approx((2/3+0+1)/3)
    assert score['confusion_matrix']==[[1,0,0],[1,0,0],[0,0,1]]
    assert metrics([],[])['macro_f1'] is None
    frame=pd.DataFrame({'label_id':[0,1,2],'product_group':['a','b','c']})
    assert product_bootstrap(frame,[0,0,2],10,42)==product_bootstrap(frame,[0,0,2],10,42)

def test_annotation_work_is_preserved_and_smoke_is_separate(tmp_path,monkeypatch):
    import src.training.data as data
    monkeypatch.setattr(data,'ROOT',tmp_path)
    directory=tmp_path/'data/annotations';directory.mkdir(parents=True)
    target=directory/'phase3_annotation_queue.json'
    original=json.dumps([{'overall_label':'positive','annotator_id':'test-annotator'}])
    target.write_text(original)
    status=data.annotation_workflow({}, {'seed':42,'annotation_sample_per_split':10})
    assert 'preserved' in status['status'] and target.read_text()==original
    smoke=data.annotation_workflow({}, {'seed':42,'annotation_sample_per_split':10},'smoke')
    assert smoke['path']=='data/annotations/phase3_smoke_annotation_queue.json'
    assert target.read_text()==original

def test_actual_phase3_splits_and_leakage():
    splits,manifest=prepare(yaml.safe_load((ROOT/'configs/phase3_config.yaml').read_text()))
    frame=pd.concat(splits.values(),ignore_index=True)
    for column in ['review_id','product_group','duplicate_group','canonical_key']:
        assert frame.groupby(column)['split'].nunique().max()==1
    assert manifest['original_split_sizes']['train']==len(splits['train'])
    assert len(splits['test'])>0

def test_actual_trained_artifacts_and_inference():
    result=json.loads((ROOT/'reports/phase3_results.json').read_text())
    assert result['mode']=='full' and result['input_files_unchanged']
    assert {'logistic_regression','linear_svm'}<=set(result['models'])
    assert result['selection']['frozen_before_test']
    for name,record in result['models'].items():
        assert record['trained'] and record['training_reviews']>0
        predictor=ReviewPredictor(ROOT/record['artifact_path'])
        outputs=predictor.batch(['excellent sound','battery not good','बहुत अच्छा है','battery acha hai'],'audio_devices')
        assert len(outputs)==4 and all(o['model_version']==record['version'] for o in outputs)
        assert record['test']['reviews']==result['dataset']['splits']['test']['reviews']
    assert result['aspects']['supervised_model_trained'] is False
    assert result['aspects']['aspect_sentiment_macro_f1'] is None
