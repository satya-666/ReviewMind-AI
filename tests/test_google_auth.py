"""Real signed-token checks against fixture Google certificates, without network calls."""
import json,time
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from google.auth import crypt,jwt
from backend.app.auth import GoogleAuth
from backend.app.settings import Settings
from backend.app.main import create_app

CLIENT='fixture-client.apps.googleusercontent.com'

@pytest.fixture
def signed_auth():
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    private=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
    public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    auth=GoogleAuth(CLIENT,True)
    def certificates(url,method='GET',**kwargs):
        assert url=='https://www.googleapis.com/oauth2/v1/certs'
        return type('Response',(),{'status':200,'data':json.dumps({'fixture-key':public}).encode()})()
    auth.request=certificates
    def token(**overrides):
        claims={'iss':'https://accounts.google.com','aud':CLIENT,'sub':'google-subject-123','email':'person@gmail.com',
                'email_verified':True,'iat':int(time.time())-10,'exp':int(time.time())+600,**overrides}
        return jwt.encode(crypt.RSASigner.from_string(private,key_id='fixture-key'),claims).decode()
    yield auth,token
    auth.session.close()


def test_google_identity_uses_signed_subject(signed_auth):
    auth,token=signed_auth
    result=auth.verify(token())
    assert result['id']=='google-subject-123' and result['email']=='person@gmail.com'

@pytest.mark.parametrize('claims',[{'aud':'another-client'}, {'iss':'https://evil.example'}, {'exp':1},
                                   {'email_verified':False}, {'sub':''}])
def test_google_identity_rejects_invalid_claims(signed_auth,claims):
    auth,token=signed_auth
    with pytest.raises(HTTPException) as rejected:auth.verify(token(**claims))
    assert rejected.value.status_code==401


def test_google_identity_rejects_forgery(signed_auth):
    auth,token=signed_auth
    parts=token().split('.')
    parts[1]=parts[1][:-5]+'AAAAA'
    with pytest.raises(HTTPException) as rejected:auth.verify('.'.join(parts))
    assert rejected.value.status_code==401


def test_api_enforces_google_sign_in_and_cors(tmp_path,monkeypatch,signed_auth):
    auth,token=signed_auth
    verify=auth.verify
    monkeypatch.setattr(GoogleAuth,'verify',lambda self,value:verify(value))
    settings=Settings(google_client_id=CLIENT,database_url='sqlite:///'+str(tmp_path/'auth.db'),rate_per_minute=100)
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/auth/config').json()=={'required':True,'client_id':CLIENT}
        for path in ['/api/chat','/api/analyze','/api/recommend','/api/feedback']:
            assert client.post(path,json={}).status_code==401
        assert client.delete('/api/feedback/00000000-0000-0000-0000-000000000000').status_code==401
        assert client.get('/api/auth/me').status_code==401
        headers={'Authorization':'Bearer '+token()}
        me=client.get('/api/auth/me',headers=headers)
        assert me.status_code==200 and me.json()['user']['id']=='google-subject-123'
        chat=client.post('/api/chats',headers=headers,json={'title':'Hello'}).json()
        assert client.post('/api/chat',headers=headers,json={'text':'hello','chat_id':chat['id']}).status_code==200
        rejected=client.get('/api/auth/me',headers={'Authorization':'Bearer bogus'})
        assert rejected.status_code==401 and 'bogus' not in rejected.text
        preflight=client.options('/api/chat',headers={'Origin':'http://localhost:8000','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'authorization,content-type'})
        assert preflight.status_code==200
        assert 'https://accounts.google.com/gsi/' in client.get('/').headers['content-security-policy']


def test_unconfigured_required_auth_fails_closed():
    from starlette.requests import Request
    auth=GoogleAuth('',True)
    with pytest.raises(HTTPException) as rejected:
        auth.user(Request({'type':'http','headers':[]}))
    assert rejected.value.status_code==503
    auth.session.close()
