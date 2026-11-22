"""Public demo routing and provider failure recovery, independent of credentials."""
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.settings import Settings
from backend.app.chat import ProviderError
from src.models.aspects.rules import aspects

SAMPLE='The camera is excellent in daylight, but the battery drains by noon and charging is painfully slow.'
SHOP='I need wireless earbuds under ₹3,000 in India. Clear calls and battery life matter most. Compare three options and show your sources.'

def test_sample_real_model_never_calls_external_providers(tmp_path,monkeypatch):
    with TestClient(create_app(Settings(database_url='sqlite:///'+str(tmp_path/'demo.db')))) as client:
        monkeypatch.setattr(client.app.state.conversation,'generate',lambda *a:pytest.fail('Review sent to Gemini'))
        monkeypatch.setattr(client.app.state.products,'search',lambda *a:pytest.fail('Review sent to search'))
        result=client.post('/api/chat',json={'text':SAMPLE,'mode':'review','category':'Smartphones','allow_gemini':False}).json()
        assert result['type']=='analysis' and result['model_version']=='phase3-full-logistic_regression-seed42'
        assert {a['aspect']:a['sentiment'] for a in result['aspects']}=={'camera':'positive','battery':'negative','charging_speed':'negative'}
        assert all(a['evidence'] in SAMPLE for a in result['aspects'])
        text='Camera   is excellent.\nBattery is not good.'
        assert all(a['evidence'] in text for a in client.post('/api/analyze',json={'text':text,'category':'Smartphones'}).json()['aspects'])

@pytest.mark.parametrize('status',['timeout','not_configured','unavailable','no_results'])
def test_shopping_distinguishes_failure_from_empty_results(tmp_path,monkeypatch,status):
    with TestClient(create_app(Settings(database_url='sqlite:///'+str(tmp_path/'shop.db')))) as client:
        monkeypatch.setattr(client.app.state.products,'search',lambda query,budget,brand: {'available':False,'products':[],'sources':[],'status':status})
        monkeypatch.setattr(client.app.state.conversation,'generate',lambda *a:pytest.fail('No evidence should need no LLM'))
        result=client.post('/api/chat',json={'text':SHOP,'allow_gemini':True,'allow_product_search':True}).json()
        assert result['product_status']==status and result['products']==[]
        assert ('Search completed' in result['reply'])==(status=='no_results')

def test_retrieved_sources_survive_conversation_timeout(tmp_path,monkeypatch):
    with TestClient(create_app(Settings(database_url='sqlite:///'+str(tmp_path/'source.db')))) as client:
        listing={'title':'Fixture listing','source_url':'https://example.com/earbuds','price_inr':2500,'specifications':[],'retrieved_at':'2026-11-22'}
        def search(query,budget,brand):
            assert query==SHOP and budget==3000
            return {'available':True,'products':[listing]*4,'sources':[listing['source_url']]*4,'status':'ok'}
        monkeypatch.setattr(client.app.state.products,'search',search)
        def timeout(*args):raise ProviderError('timeout')
        monkeypatch.setattr(client.app.state.conversation,'generate',timeout)
        result=client.post('/api/chat',json={'text':SHOP,'allow_gemini':True,'allow_product_search':True}).json()
        assert result['products']==[listing]*3 and result['sources']==[listing['source_url']]*3
        assert result['response_source']=='built_in'
        assert result['provider_status']=='timeout'

def test_diagnostic_fixture_evidence_is_verbatim():
    for case in json.loads(Path('tests/fixtures/aspect_diagnostics.json').read_text()):
        for aspect in aspects(case['text'],case['category']):assert aspect['evidence'] in case['text']
