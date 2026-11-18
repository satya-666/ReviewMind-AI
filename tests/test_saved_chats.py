"""Account isolation and persistence; model fixture is not live AI evidence."""
import pytest
from fastapi.testclient import TestClient
from backend.app.auth import GoogleAuth
from backend.app.main import create_app
from backend.app.settings import Settings
from backend.app.db import Database

@pytest.fixture
def configured(tmp_path,monkeypatch):
    monkeypatch.setattr(GoogleAuth,'verify',lambda self,token:{'id':token,'email':token+'@gmail.com','expires_at':9999999999})
    return Settings(google_client_id='fixture.apps.googleusercontent.com',database_url='sqlite:///'+str(tmp_path/'chats.db'),rate_per_minute=100)

def headers(user):return {'Authorization':'Bearer '+user}

def test_saved_chat_lifecycle_and_account_isolation(configured,monkeypatch):
    with TestClient(create_app(configured)) as client:
        monkeypatch.setattr(client.app.state.agent,'respond',lambda *a:{'type':'chat','reply':'fixture answer','response_source':'gemini','provider_status':'ready'})
        assert client.get('/api/chats').status_code==401
        made=client.post('/api/chats',json={'title':'My phone research'},headers=headers('alice'))
        assert made.status_code==201
        chat=made.json();identifier=chat['id']
        for method,path in [('get','/api/chats/'+identifier),('delete','/api/chats/'+identifier)]:
            assert getattr(client,method)(path,headers=headers('bob')).status_code==404
        body={'text':'phones under 20k','chat_id':identifier}
        assert client.post('/api/chat',json=body,headers=headers('bob')).status_code==404
        assert client.post('/api/chat',json=body,headers=headers('alice')).status_code==200
        saved=client.get('/api/chats/'+identifier,headers=headers('alice')).json()
        assert saved['messages'][0]['text']=='phones under 20k'
        assert saved['messages'][1]['result']['reply']=='fixture answer'
        assert client.get('/api/chats',headers=headers('bob')).json()['chats']==[]
        assert client.post('/api/chat',json={'text':'hello'},headers=headers('alice')).status_code==422
        assert client.post('/api/chats',json={'title':'forged','owner':'bob'},headers=headers('alice')).status_code==422
    # Restarted app / new browser session still sees persisted account history.
    with TestClient(create_app(configured)) as client:
        assert client.get('/api/chats',headers=headers('alice')).json()['chats'][0]['id']==identifier
        assert client.get('/api/chats/'+identifier,headers=headers('alice')).json()['messages']==saved['messages']
        assert client.delete('/api/chats',headers=headers('bob')).status_code==200
        assert client.get('/api/chats/'+identifier,headers=headers('alice')).status_code==200
        assert client.delete('/api/chats/'+identifier,headers=headers('alice')).status_code==200
        assert client.get('/api/chats/'+identifier,headers=headers('alice')).status_code==404
        assert client.get('/api/chats',headers=headers('alice')).json()['chats']==[]


def test_failed_provider_does_not_save_fabricated_answer(configured,monkeypatch):
    from backend.app.chat import ProviderError
    with TestClient(create_app(configured)) as client:
        identifier=client.post('/api/chats',json={'title':'Research'},headers=headers('alice')).json()['id']
        def fail(*args):raise ProviderError('timeout')
        monkeypatch.setattr(client.app.state.agent,'respond',fail)
        assert client.post('/api/chat',json={'text':'hello','chat_id':identifier},headers=headers('alice')).status_code==503
        assert client.get('/api/chats/'+identifier,headers=headers('alice')).json()['messages']==[]


def test_chat_limits_and_append_after_deletion(configured):
    from backend.app.db import Base,Chat
    from sqlalchemy.orm import Session
    db=Database(configured.database_url);Base.metadata.create_all(db.engine)
    chat=db.create_chat('alice','Full chat')
    with Session(db.engine) as session:
        row=session.get(Chat,chat['id']);row.messages=[{'role':'user','text':'x'}]*100;session.commit()
    with pytest.raises(ValueError,match='full'):db.append_chat('alice',chat['id'],'hello',{})
    assert db.delete_chat('alice',chat['id'])
    assert not db.append_chat('alice',chat['id'],'hello',{})
    db.engine.dispose()


def test_chat_migration_preserves_existing_predictions(tmp_path,monkeypatch):
    from alembic.config import Config
    from alembic import command
    from backend.app.settings import ROOT
    database_url='sqlite:///'+str(tmp_path/'migrated.db')
    monkeypatch.setenv('APP_ENV','development');monkeypatch.setenv('DATABASE_URL',database_url)
    config=Config(str(ROOT/'backend/alembic.ini'))
    command.upgrade(config,'0001_feedback')
    db=Database(database_url)
    db.record_prediction('existing-id','fixture-version','positive')
    command.upgrade(config,'head')
    assert db.prediction_context('existing-id')['sentiment']=='positive'
    chat=db.create_chat('alice','Saved after migration')
    assert db.get_chat('alice',chat['id'])['title']=='Saved after migration'
    db.engine.dispose()
