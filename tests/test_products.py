"""Provider fixtures, not evidence of live shopping retrieval."""
import io,json,urllib.error
import pytest
from backend.app.products import ProductData,budget_from,brand_from,public_url
from backend.app.chat import GeminiConversation,ProviderError
from backend.app.settings import Settings

def test_budget_and_public_sources():
    assert budget_from(['under ₹25,000','My budget is 20k'])==20000
    assert budget_from(['₹1.5 lakh'])==150000
    assert brand_from(['I prefer Apple.','Only Samsung.'])=='Samsung'
    for url in ['http://example.com','https://127.0.0.1/a','https://user:pass@example.com','javascript:alert(1)','https://example.local/a','https://example.com:8443']:
        assert public_url(url) is None
    assert public_url('https://retailer.example/item')

def test_india_retrieval_filters_and_preserves_evidence(monkeypatch):
    captured=[]
    fixture={'shopping_results':[
      {'title':'Samsung Fixture Phone','price':'₹19,999','product_link':'https://retailer.example/one','extensions':['5000 mAh'],'rating':4.2,'reviews':22},
      {'title':'Samsung over budget','price':'₹25,000','product_link':'https://retailer.example/two'},
      {'title':'Other brand','price':'₹18,000','product_link':'https://retailer.example/three'},
      {'title':'Samsung foreign','price':'$199','product_link':'https://retailer.example/four'},
      {'title':'Samsung unsafe','price':'₹12,000','product_link':'https://127.0.0.1/secret'}]}
    def opened(self,req,timeout):
        captured.append(req.full_url);return io.BytesIO(json.dumps(fixture).encode())
    monkeypatch.setattr('urllib.request.OpenerDirector.open',opened)
    result=ProductData('fixture-only-key').search('Samsung phone',20000,'Samsung')
    assert result['available'] and len(result['products'])==1
    p=result['products'][0]
    assert p['price_inr']==19999 and p['specifications']==['5000 mAh']
    assert p['source_url']=='https://retailer.example/one' and p['retrieved_at'].endswith('+00:00')
    assert 'gl=in' in captured[0] and 'google_domain=google.co.in' in captured[0]
    assert 'fixture-only-key' not in json.dumps(result)

def test_product_missing_key_quota_and_missing_fields(monkeypatch):
    assert ProductData().search('phone')['status']=='not_configured'
    def quota(*a,**k):raise urllib.error.HTTPError('https://serpapi.com',429,'quota',{},None)
    monkeypatch.setattr('urllib.request.OpenerDirector.open',quota)
    assert ProductData('fixture').search('phone')['status']=='quota_exhausted'
    monkeypatch.setattr('urllib.request.OpenerDirector.open',lambda *a,**k:io.BytesIO(json.dumps({'shopping_results':[{'title':'Unknown-price fixture','product_link':'https://example.com/item'}]}).encode()))
    result=ProductData('fixture').search('phone')
    assert result['products'][0]['price_inr'] is None and result['products'][0]['specifications']==[]
    assert not ProductData('fixture').search('phone',20000)['available']

def test_function_call_roundtrip_preserves_signatures_and_grounding(monkeypatch):
    requests=[];context={'product_data':{'sources':[],'products':[]}}
    parts=[{'thoughtSignature':'fixture-signature','functionCall':{'name':'product_search','args':{'query':'phone'}}}]
    def opened(self,req,timeout):
        payload=json.loads(req.data);requests.append(payload)
        content={'parts':parts,'role':'model'} if len(requests)==1 else {'parts':[{'text':'Listing: INR 19999 https://example.com/item'}]}
        return io.BytesIO(json.dumps({'candidates':[{'finishReason':'STOP','content':content}]}).encode())
    monkeypatch.setattr('urllib.request.OpenerDirector.open',opened)
    def execute(name,args):
        assert name=='product_search' and args=={'query':'phone'}
        context['product_data']={'sources':['https://example.com/item'],'products':[{'price_inr':19999}]}
        return context['product_data']
    reply=GeminiConversation(Settings(gemini_api_key='fixture-key')).generate('Suggest phone',[],context,'en',[{'name':'product_search'}],execute)
    assert '19999' in reply and len(requests)==2
    assert requests[1]['contents'][-2]['parts']==parts
    assert requests[1]['contents'][-1]['parts'][0]['functionResponse']['name']=='product_search'
    assert 'tools' not in requests[1]

def test_agent_product_calls_require_consent_and_real_results(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    with TestClient(create_app(Settings(database_url='sqlite:///'+str(tmp_path/'test.db'),serpapi_api_key='fixture'))) as client:
        captured=[]
        def search(query,budget,brand):
            captured.append((query,budget,brand));return {'available':False,'products':[],'sources':[],'status':'no_results'}
        monkeypatch.setattr(client.app.state.products,'search',search)
        def generate(message,history,context,language,tools,execute):
            names=[t['name'] for t in tools]
            if 'product_search' in names:execute('product_search',{'query':'Samsung phone','brand':'Samsung'})
            return 'No listings found; no invented recommendations.'
        monkeypatch.setattr(client.app.state.conversation,'generate',generate)
        body={'text':'Suggest a Samsung smartphone under ₹20,000','allow_gemini':True}
        assert client.post('/api/chat',json=body).status_code==200 and not captured
        result=client.post('/api/chat',json={**body,'allow_product_search':True}).json()
        assert captured==[('Samsung phone',20000,'Samsung')]
        assert result['products']==[] and not result['product_data_available']
        assert result['tools_used']==['product_search','gemini']

def test_tool_cannot_classify_greeting_or_bypass_product_consent(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    with TestClient(create_app(Settings(database_url='sqlite:///'+str(tmp_path/'guard.db'),serpapi_api_key='fixture'))) as client:
        monkeypatch.setattr(client.app.state.model,'analyze',lambda *a:pytest.fail('Greeting reached classifier'))
        monkeypatch.setattr(client.app.state.products,'search',lambda *a:pytest.fail('Unconsented search'))
        def generate(message,history,context,language,tools,execute):
            assert 'error' in execute('sentiment_analysis',{'text':'Hello'})
            assert 'error' in execute('product_search',{'query':'phone'})
            return 'Hello fixture.'
        monkeypatch.setattr(client.app.state.conversation,'generate',generate)
        assert client.post('/api/chat',json={'text':'Hello','allow_gemini':True}).status_code==200


def test_tool_analysis_does_not_expose_invented_classifier_reasoning(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    text='The battery is excellent but the camera is terrible.'
    with TestClient(create_app(Settings(database_url='sqlite:///'+str(tmp_path/'reason.db')))) as client:
        def generate(message,history,context,language,tools,execute):
            execute('sentiment_analysis',{'text':text,'category':'Smartphones'})
            return 'The classifier averages conflicting sentiments. This is intentionally unsupported fixture text.'
        monkeypatch.setattr(client.app.state.conversation,'generate',generate)
        result=client.post('/api/chat',json={'text':'Can you explain this review: '+text,'allow_gemini':True}).json()
        assert result['type']=='analysis' and result['model_version']=='phase3-full-logistic_regression-seed42'
        assert 'averages' not in result['reply'] and 'Exact causal feature importance is unavailable' in result['reply']
        assert result['tools_used']==['sentiment','aspect_rules','gemini']
