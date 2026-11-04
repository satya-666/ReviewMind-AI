"""Persist prediction metadata and consented feedback, never raw review text."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import hashlib,secrets,uuid
from sqlalchemy import create_engine,String,Integer,DateTime,ForeignKey,Text,select,delete
from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column,Session

class Base(DeclarativeBase):pass

class Prediction(Base):
    __tablename__='predictions'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    model_version:Mapped[str]=mapped_column(String(128))
    sentiment:Mapped[str]=mapped_column(String(12))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)

class Feedback(Base):
    __tablename__='feedback'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    request_id:Mapped[str]=mapped_column(ForeignKey('predictions.id'),unique=True)
    model_version:Mapped[str]=mapped_column(String(128))
    predicted_sentiment:Mapped[str]=mapped_column(String(12))
    rating:Mapped[int]=mapped_column(Integer)
    correction:Mapped[str|None]=mapped_column(String(12),nullable=True)
    message:Mapped[str|None]=mapped_column(Text,nullable=True)
    delete_token_sha256:Mapped[str]=mapped_column(String(64))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)

class Database:
    def __init__(self,url,retention_days=30):
        if url.startswith('postgresql://'):url=url.replace('postgresql://','postgresql+psycopg://',1)
        if url.startswith('postgresql+psycopg://'):
            from sqlalchemy.engine import make_url
            parsed=make_url(url);url=parsed.update_query_dict({'sslmode':'require'})
        if isinstance(url,str) and url.startswith('sqlite:///'):
            filename=url.removeprefix('sqlite:///')
            if filename!=':memory:':Path(filename).parent.mkdir(parents=True,exist_ok=True)
        options={'connect_args':{'check_same_thread':False}} if str(url).startswith('sqlite') else {'pool_size':2,'max_overflow':2,'pool_timeout':5,'connect_args':{'connect_timeout':5}}
        self.engine=create_engine(url,pool_pre_ping=True,**options);self.retention_days=retention_days

    def ready(self):
        with Session(self.engine) as session:
            session.execute(select(Prediction.id).limit(1))

    def purge_expired(self):
        with Session(self.engine) as session:
            self.cleanup(session);session.commit()

    def cleanup(self,session):
        cutoff=datetime.now(timezone.utc)-timedelta(days=self.retention_days)
        session.execute(delete(Feedback).where(Feedback.created_at<cutoff))
        # Preserve referential integrity for feedback submitted near the prediction TTL.
        linked=select(Feedback.request_id)
        session.execute(delete(Prediction).where(Prediction.created_at<cutoff,Prediction.id.not_in(linked)))

    def record_prediction(self,request_id,version,label):
        with Session(self.engine) as session:
            self.cleanup(session)
            session.add(Prediction(id=request_id,model_version=version,sentiment=label,created_at=datetime.now(timezone.utc)))
            session.commit()

    def feedback(self,request_id,rating,correction,message):
        with Session(self.engine) as session:
            self.cleanup(session)
            prediction=session.get(Prediction,str(request_id))
            if prediction is None:return None
            token=secrets.token_urlsafe(32);identifier=str(uuid.uuid4());now=datetime.now(timezone.utc)
            row=Feedback(id=identifier,request_id=prediction.id,model_version=prediction.model_version,
              predicted_sentiment=prediction.sentiment,rating=rating,correction=correction,message=message,
              delete_token_sha256=hashlib.sha256(token.encode()).hexdigest(),created_at=now)
            session.add(row);session.commit()
            return {'feedback_id':identifier,'created_at':now.isoformat(),'delete_token':token,'status':'stored'}

    def delete_feedback(self,identifier,token):
        with Session(self.engine) as session:
            row=session.get(Feedback,str(identifier))
            if row is None or not secrets.compare_digest(row.delete_token_sha256,hashlib.sha256(token.encode()).hexdigest()):return False
            session.delete(row);session.commit();return True
