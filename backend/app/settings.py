"""Validated environment configuration; no secrets are returned to clients."""
from dataclasses import dataclass,field
import os
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[2]

@dataclass
class Settings:
    environment:str='development'
    model_path:Path=ROOT/'models/phase3/full/baseline/logistic_regression.joblib'
    manifest_path:Path=ROOT/'backend/model_manifest.json'
    database_url:str='sqlite:///'+str(ROOT/'.cache/web/feedback.db')
    origins:list[str]=field(default_factory=lambda:['http://localhost:8000','http://127.0.0.1:8000'])
    hosts:list[str]=field(default_factory=lambda:['localhost','127.0.0.1','testserver'])
    api_base_url:str=''
    rate_per_minute:int=20
    global_rate_per_minute:int=120
    body_limit:int=16384
    retention_days:int=30
    auto_create_db:bool=True
    gemini_api_key:str=field(default='',repr=False)
    serpapi_api_key:str=field(default='',repr=False)
    gemini_model:str='gemini-3.1-flash-lite'

    @classmethod
    def from_env(cls):
        production=os.getenv('APP_ENV','development')=='production'
        host=os.getenv('RENDER_EXTERNAL_HOSTNAME','')
        return cls(environment=os.getenv('APP_ENV','development'),
          model_path=Path(os.getenv('MODEL_PATH',str(cls.model_path))),
          manifest_path=Path(os.getenv('MODEL_MANIFEST_PATH',str(cls.manifest_path))),
          database_url=os.getenv('DATABASE_URL',cls.database_url),
          origins=[x.strip() for x in os.getenv('ALLOWED_ORIGINS','' if production else 'http://localhost:8000,http://127.0.0.1:8000').split(',') if x.strip()],
          hosts=[x.strip() for x in os.getenv('ALLOWED_HOSTS',host if production else 'localhost,127.0.0.1,testserver').split(',') if x.strip()],
          api_base_url=os.getenv('FRONTEND_API_URL','').rstrip('/'),
          rate_per_minute=int(os.getenv('RATE_LIMIT_PER_MINUTE','20')),
          global_rate_per_minute=int(os.getenv('GLOBAL_RATE_LIMIT_PER_MINUTE','120')),
          serpapi_api_key=os.getenv('SERPAPI_API_KEY','').strip(),
          gemini_api_key=os.getenv('GEMINI_API_KEY','').strip(),
          gemini_model=os.getenv('GEMINI_MODEL','gemini-3.1-flash-lite'),
          auto_create_db=os.getenv('AUTO_CREATE_DB','false' if production else 'true')=='true')

    def validate(self):
        if self.gemini_model!='gemini-3.1-flash-lite':
            raise ValueError('Only the reviewed free-tier Gemini model is enabled; review pricing before changing models')
        if not 1<=self.rate_per_minute<=1000 or not 1<=self.global_rate_per_minute<=10000:
            raise ValueError('Rate limits must be bounded positive values')
        if not self.hosts or '*' in self.hosts or '*' in self.origins:
            raise ValueError('Explicit approved hosts/origins required')
        for origin in self.origins:
            parsed=urlparse(origin)
            if parsed.scheme not in {'http','https'} or not parsed.netloc or parsed.path not in {'','/'}:
                raise ValueError('Origins must be exact HTTP(S) origins')
        if self.environment=='production':
            if not self.origins or any(not x.startswith('https://') for x in self.origins):
                raise ValueError('Production requires explicit HTTPS frontend origins')
            if not self.database_url.startswith(('postgresql://','postgresql+psycopg://')):
                raise ValueError('Production feedback requires persistent PostgreSQL')
            if self.auto_create_db:
                raise ValueError('Apply database migrations explicitly in production')
        if self.api_base_url:
            parsed=urlparse(self.api_base_url)
            if parsed.scheme not in {'http','https'} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {'','/'}:
                raise ValueError('Public API configuration must be an origin without credentials')
            if self.environment=='production' and parsed.scheme!='https':raise ValueError('Production API origin must use HTTPS')
        return self
