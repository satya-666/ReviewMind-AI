"""Real local Phase 3 model integration; no mocked sentiment predictions."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json,uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.main import create_app
from backend.app.settings import Settings,ROOT
from backend.app.db import Feedback,Prediction

@pytest.fixture
def configured(tmp_path):
    return Settings(database_url='sqlite:///'+str(tmp_path/'feedback.db'),rate_per_minute=100,global_rate_per_minute=500)

@pytest.fixture
def client(configured):
    with TestClient(create_app(configured)) as c:yield c

def analyze(client,text='The sound is excellent but the battery is poor.',language='en'):
    return client.post('/api/analyze',json={'text':text,'category':'Headphones','language':language})

def test_health_model_info_and_static_boundaries(client):
    health=client.get('/api/health');assert health.status_code==200 and health.json()['model_ready']
    info=client.get('/api/model-info').json()
    assert info['architecture']=='TF-IDF + Logistic Regression'
    assert info['sentiment_labels']==['negative','neutral','positive']
    assert not info['capabilities']['recommendations']
    assert '/Users/' not in json.dumps(info) and 'checkpoint_sha256' not in info
    assert client.get('/').status_code==200
    for path in ['/data/raw/flipkart_v1.zip','/models/phase3/full/baseline/logistic_regression.joblib','/.env','/assets/../../requirements.txt']:
        assert client.get(path).status_code==404
    assert client.get('/').headers['x-content-type-options']=='nosniff'

@pytest.mark.parametrize('text,language',[('The battery is not good.','en'),('बैटरी अच्छी है।','hi'),('battery acha hai but sound poor','hinglish')])
def test_real_sentiment_and_languages(client,text,language):
    r=analyze(client,text,language);assert r.status_code==200
    payload=r.json();expected=client.app.state.model.predictor.single(text,'audio_devices')
    assert payload['sentiment']==expected['sentiment']
    assert payload['scores']==expected['scores']
    assert payload['model_version']==expected['model_version']
    assert payload['sentiment'] in ['negative','neutral','positive']
    assert payload['raw_text_stored'] is False
    if language!='en':assert any('accuracy is not established' in w for w in payload['warnings'])

def test_actual_aspect_rules_and_unsupported_category(client):
    r=client.post('/api/analyze',json={'text':'The camera is excellent, but the battery drains quickly.','category':'Smartphones'})
    assert r.status_code==200
    aspects=r.json()['aspects']
    assert any(a['name']=='Camera' and a['sentiment']=='positive' for a in aspects)
    assert any(a['name']=='Battery' and a['sentiment']=='negative' for a in aspects)
    assert all(a['confidence'] is None and 'positive' not in a for a in aspects)
    unknown=client.post('/api/analyze',json={'text':'The product works well','category':'Not a real category'}).json()
    assert unknown['aspects']==[] and unknown['category'] is None

@pytest.mark.parametrize('body',[{'text':''},{'text':'   '},{'text':'...'}, {'text':42},{'text':'x'*5001},{'text':'good','language':'fr'},{'text':'good','secret':'not allowed'}])
def test_request_validation(client,body):
    r=client.post('/api/analyze',json=body);assert r.status_code==422
    assert r.json()['error']['code']=='invalid_request'
    assert 'secret' not in r.text

def test_body_limit_and_invalid_json(client):
    r=client.post('/api/analyze',content=b'x'*17000,headers={'Content-Type':'application/json'})
    assert r.status_code==413
    r=client.post('/api/analyze',content=b'{bad',headers={'Content-Type':'application/json'})
    assert r.status_code==422

def test_recommendations_are_honestly_unavailable(client):
    r=client.post('/api/recommend',json={'query':'Best phone under 20000','preferences':{'category':'Smartphones','budget':20000,'priorities':['Battery'],'language':'en','style':'friendly','user_name':'Guest'}})
    assert r.status_code==200 and r.json()['status']=='not_available'
    assert r.json()['products']==[] and 'top_pick' not in r.json()

def test_feedback_persistence_metadata_and_deletion(configured):
    request_id=None
    with TestClient(create_app(configured)) as c:
        result=analyze(c).json();request_id=result['request_id']
        body={'request_id':request_id,'rating':4,'correction':'neutral','message':'Useful beta feedback','consent':True}
        stored=c.post('/api/feedback',json=body);assert stored.status_code==201
        receipt=stored.json();assert receipt['status']=='stored'
        assert c.post('/api/feedback',json=body).status_code==409
        with Session(c.app.state.database.engine) as session:
            row=session.get(Feedback,receipt['feedback_id'])
            assert row.model_version==result['model_version'] and row.predicted_sentiment==result['sentiment']
            assert not hasattr(row,'review_text') and row.created_at is not None
    with TestClient(create_app(configured)) as c:
        with Session(c.app.state.database.engine) as session:
            assert session.get(Feedback,receipt['feedback_id']).rating==4
        assert c.delete('/api/feedback/'+receipt['feedback_id'],headers={'X-Delete-Token':'wrong'}).status_code==404
        assert c.delete('/api/feedback/'+receipt['feedback_id'],headers={'X-Delete-Token':receipt['delete_token']}).json()['status']=='deleted'
        with Session(c.app.state.database.engine) as session:assert session.get(Feedback,receipt['feedback_id']) is None

def test_feedback_rejects_unknown_or_unconsented(client):
    body={'request_id':str(uuid.uuid4()),'rating':5,'consent':True}
    assert client.post('/api/feedback',json=body).status_code==404
    body['consent']=False;assert client.post('/api/feedback',json=body).status_code==422

def test_retention_deletes_old_feedback(client):
    data=analyze(client).json();receipt=client.post('/api/feedback',json={'request_id':data['request_id'],'rating':2,'consent':True}).json()
    db=client.app.state.database
    with Session(db.engine) as session:
        session.get(Feedback,receipt['feedback_id']).created_at=datetime.now(timezone.utc)-timedelta(days=31)
        session.get(Prediction,data['request_id']).created_at=datetime.now(timezone.utc)-timedelta(days=31)
        session.commit()
    db.purge_expired()
    with Session(db.engine) as session:
        assert session.get(Feedback,receipt['feedback_id']) is None
        assert session.get(Prediction,data['request_id']) is None

def test_rate_limiting_does_not_trust_spoofed_ip(configured):
    configured.rate_per_minute=2
    with TestClient(create_app(configured)) as c:
        for _ in range(2):assert c.post('/api/recommend',json={'query':'phone'}).status_code==200
        r=c.post('/api/recommend',json={'query':'phone'},headers={'X-Forwarded-For':'1.2.3.4'})
        assert r.status_code==429 and r.headers['retry-after']=='60'

def test_cors_and_hosts(client):
    good=client.options('/api/analyze',headers={'Origin':'http://localhost:8000','Access-Control-Request-Method':'POST'})
    assert good.headers['access-control-allow-origin']=='http://localhost:8000'
    assert client.post('/api/analyze',json={'text':'good battery'},headers={'Origin':'https://evil.example'}).status_code==403
    assert client.get('/api/health',headers={'Host':'evil.example'}).status_code==400

def test_model_loading_failure_is_safe(configured):
    configured.model_path=Path('/definitely/missing/model.joblib')
    with TestClient(create_app(configured)) as c:
        assert c.get('/api/health').status_code==503
        r=analyze(c);assert r.status_code==503
        assert '/definitely' not in r.text and 'Traceback' not in r.text

def test_inference_and_database_errors_are_safe(client,monkeypatch):
    def broken(*a,**k):raise RuntimeError('private secret internals')
    monkeypatch.setattr(client.app.state.model,'analyze',broken)
    r=analyze(client);assert r.status_code==503 and 'private secret' not in r.text
    client.app.state.database=None
    assert client.post('/api/feedback',json={'request_id':str(uuid.uuid4()),'rating':1,'consent':True}).status_code==503

def test_frontend_is_analysis_focused_and_uses_real_api(client):
    html=(ROOT/'frontend/index.html').read_text();js=(ROOT/'frontend/assets/app.js').read_text()
    assert 'const MOCK' not in js+html and 'Sample Phone A' not in js+html
    assert 'ReviewMindAPI.analyze' in js
    assert 'Submit Feedback' in html and 'Analyze Review' in html
    for obsolete in ['data-plan=', 'id="budget"', 'id="pbtn"', 'id="examples"', 'const EXAMPLES']:
        assert obsolete not in html+js
    assert client.get('/assets/app.js').status_code==200

@pytest.mark.parametrize('category',['Smartphones','phone',' mobile phones '])
def test_reported_phone_review_aspects(client,category):
    text='The phone has excellent battery life and a great display, but the camera quality is disappointing.'
    data=client.post('/api/analyze',json={'text':text,'category':category}).json()
    found={a['aspect']:a['sentiment'] for a in data['aspects']}
    assert found=={'battery':'positive','display':'positive','camera':'negative'}
    assert data['aspects_method']=='rule_based_not_supervised'
    assert all(a['confidence'] is None for a in data['aspects'])

def test_missing_category_explains_aspect_requirement(client):
    data=client.post('/api/analyze',json={'text':'The battery life is excellent'}).json()
    assert data['aspects']==[] and any('Choose a product category' in w for w in data['warnings'])

@pytest.mark.parametrize('category,text,expected',[
    ('Laptops','The performance is excellent but the keyboard is poor.',{'performance','keyboard'}),
    ('Headphones','The sound is clear and bass is good.',{'sound_quality','bass'}),
    ('Wearables','The heart rate tracking is good.',{'tracking_accuracy'}),
    ('TVs and monitors','The picture is great but the speaker is poor.',{'display','sound_quality'}),
    ('Computer accessories','The storage capacity is good.',{'storage'}),
    ('Tablets','The screen is great and the battery is good.',{'display','battery'}),
    ('Networking devices','The bandwidth and signal are good.',{'speed','range'}),
    ('Chargers and power banks','The charging speed is good.',{'charging_speed'}),
])
def test_supported_category_aspect_mentions(client,category,text,expected):
    data=client.post('/api/analyze',json={'text':text,'category':category}).json()
    assert expected <= {a['aspect'] for a in data['aspects']}
