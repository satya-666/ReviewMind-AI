"""Optional real TLS PostgreSQL test; configure TEST_POSTGRES_URL explicitly."""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.app.settings import Settings
from backend.app.main import create_app
from backend.app.db import Feedback

@pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL'),reason='Set TEST_POSTGRES_URL to an isolated migrated TLS PostgreSQL database')
def test_postgres_migrations_tls_persistence_and_deletion():
    settings=Settings(database_url=os.environ['TEST_POSTGRES_URL'],auto_create_db=False)
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/health').status_code==200
        with client.app.state.database.engine.connect() as connection:
            assert connection.execute(text('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()')).scalar() is True
        prediction=client.post('/api/analyze',json={'text':'The battery works well','category':'Smartphones'}).json()
        receipt=client.post('/api/feedback',json={'request_id':prediction['request_id'],'rating':5,'consent':True}).json()
        assert receipt['status']=='stored'
    with TestClient(create_app(settings)) as client:
        with Session(client.app.state.database.engine) as session:assert session.get(Feedback,receipt['feedback_id']).rating==5
        assert client.delete('/api/feedback/'+receipt['feedback_id'],headers={'X-Delete-Token':receipt['delete_token']}).json()['status']=='deleted'
