"""Real baseline inference and honest analysis-only beta APIs."""
from contextlib import asynccontextmanager
import asyncio,json,logging,uuid
from contextlib import suppress
from starlette.concurrency import run_in_threadpool
from fastapi import FastAPI,Request,Header
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse,FileResponse,Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.exc import IntegrityError,SQLAlchemyError
from backend.app.settings import Settings,ROOT
from backend.app.db import Database,Base
from backend.app.schemas import Analyze,Recommend,FeedbackInput
from backend.app.model_service import ModelService
from backend.app.security import Guard

LOG=logging.getLogger('reviewmind.api')
CATEGORIES={
 'smartphones':['Smartphones','smartphone','phone','phones','mobile phone','mobile phones'], 'laptops':['Laptops','laptop'],
 'audio_devices':['Audio devices','Headphones','earbuds','speakers'],
 'wearables':['Wearables','Smartwatches','smartwatch'], 'tvs_monitors':['TVs and monitors','TVs/monitors'],
 'accessories':['Computer accessories','Accessories'], 'tablets':['Tablets','tablet'],
 'networking_devices':['Networking devices'], 'chargers_power_banks':['Chargers and power banks']}
ALIASES={alias.casefold():key for key,values in CATEGORIES.items() for alias in [key,*values]}

def error(status,code,message):return JSONResponse({'error':{'code':code,'message':message}},status_code=status)

def create_app(settings=None):
    settings=(settings or Settings.from_env()).validate()
    @asynccontextmanager
    async def lifespan(app):
        app.state.model=ModelService(settings);app.state.database=None
        try:
            db=Database(settings.database_url,settings.retention_days)
            if settings.auto_create_db:Base.metadata.create_all(db.engine)
            db.ready();db.purge_expired();app.state.database=db
        except Exception as problem:
            LOG.error('Feedback storage startup failed (%s)',type(problem).__name__)
        async def retention():
            while True:
                await asyncio.sleep(3600)
                if app.state.database:
                    try:await run_in_threadpool(app.state.database.purge_expired)
                    except SQLAlchemyError:LOG.error('Scheduled feedback cleanup failed')
        task=asyncio.create_task(retention())
        yield
        task.cancel()
        with suppress(asyncio.CancelledError):await task
        if app.state.database:app.state.database.engine.dispose()
    app=FastAPI(title='ReviewMind AI beta',version='3.5',lifespan=lifespan,debug=False,
      docs_url='/api/docs' if settings.environment=='development' else None,redoc_url=None,
      openapi_url='/api/openapi.json' if settings.environment=='development' else None)
    app.add_middleware(Guard,settings=settings)
    app.add_middleware(CORSMiddleware,allow_origins=settings.origins,allow_credentials=False,
      allow_methods=['GET','POST','DELETE'],allow_headers=['Content-Type','X-Delete-Token'])
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=settings.hosts)

    @app.exception_handler(RequestValidationError)
    async def invalid(request,exception):
        return error(422,'invalid_request','Check the required fields, supported values and input length.')
    @app.exception_handler(Exception)
    async def unexpected(request,exception):
        LOG.error('Request failed (%s)',type(exception).__name__)
        return error(500,'internal_error','The request could not be completed. Please retry later.')

    @app.get('/api/health')
    def health():
        model=app.state.model
        database_ready=False
        if app.state.database:
            try:app.state.database.ready();database_ready=True
            except SQLAlchemyError:pass
        ready=model.predictor is not None and database_ready
        return JSONResponse({'status':'ready' if ready else 'unavailable','model_ready':model.predictor is not None,
            'feedback_ready':database_ready,'model_version':model.predictor.version if model.predictor else None},status_code=200 if ready else 503)

    @app.get('/api/model-info')
    def model_info():
        model=app.state.model
        return {'ready':model.predictor is not None,'model_version':model.predictor.version if model.predictor else None,
          'architecture':'TF-IDF + Logistic Regression','selection_basis':'Phase 3 validation macro F1',
          'sentiment_labels':['negative','neutral','positive'],'confidence':'uncalibrated probability',
          'categories':list(CATEGORIES),'languages':{
            'en':{'accepted':True,'evaluation':'English weak-rating-label evaluation only'},
            'hi':{'accepted':True,'evaluation':'No Hindi training/evaluation; experimental input handling only'},
            'hinglish':{'accepted':True,'evaluation':'Insufficient examples; no reliable capability claim'}},
          'capabilities':{'sentiment_analysis':model.predictor is not None,'aspects':'category-aware lexical rules, not supervised ABSA',
            'recommendations':False,'fake_review_detection':False,'product_comparison':False,'review_evidence':False,
            'authentication':False,'billing':False},
          'limitations':['Overall labels learned from star ratings, not independent human annotations.',
             'Aspect sentiments are heuristic and may be unknown or mixed; no aspect percentages are supported.'],
          'privacy':{'raw_review_text_stored':False,'feedback_retention_days':settings.retention_days,'guest_only':True}}

    @app.post('/api/analyze')
    def analyze(body:Analyze):
        model=app.state.model;db=app.state.database
        if model.predictor is None or db is None:return error(503,'model_unavailable','Analysis is unavailable while the model or storage is not ready.')
        category=ALIASES.get((body.category or '').strip().casefold())
        warnings=['Experimental beta: rating-derived weak supervision; scores are uncalibrated.']
        if body.language not in {'en','english'}:warnings.append('Hindi/Hinglish/other language accuracy is not established. Treat this prediction as experimental.')
        if body.category and category is None:warnings.append('Category not recognized; overall sentiment is returned without aspect rules.')
        if not body.category:warnings.append('Choose a product category to enable category-specific aspect detection.')
        try:prediction=model.analyze(body.text,category)
        except BlockingIOError:return error(503,'inference_busy','Another analysis is running. Please retry shortly.')
        except Exception as problem:
            LOG.error('Prediction failed (%s)',type(problem).__name__)
            return error(503,'inference_failed','Analysis could not be completed. Please retry later.')
        request_id=str(uuid.uuid4())
        try:db.record_prediction(request_id,prediction['model_version'],prediction['sentiment'])
        except SQLAlchemyError:
            LOG.error('Prediction metadata storage failed')
            return error(503,'storage_unavailable','Feedback storage is unavailable. Please retry later.')
        prediction['aspects']=[dict(a,name=a['aspect'].replace('_',' ').title()) for a in prediction['aspects']]
        return dict(prediction,request_id=request_id,status='analysis',type='analysis',category=category,
          warnings=warnings,aspects_method='rule_based_not_supervised',raw_text_stored=False)

    @app.post('/api/recommend')
    def recommend(body:Recommend):
        return {'request_id':str(uuid.uuid4()),'status':'not_available','type':'analysis_only','products':[],
          'message':'Product recommendations, prices, ranking, comparisons and fake-review scoring are not available in this beta. Paste a review in Analyze review mode for real model inference.',
          'available_actions':['analyze_review'],'model_ready':app.state.model.predictor is not None}

    @app.post('/api/feedback',status_code=201)
    def feedback(body:FeedbackInput):
        db=app.state.database
        if db is None:return error(503,'storage_unavailable','Feedback storage is unavailable.')
        try:
            stored=db.feedback(body.request_id,body.rating,body.correction,body.message)
            return stored if stored else error(404,'request_not_found','Prediction request not found or expired.')
        except IntegrityError:return error(409,'feedback_exists','Feedback has already been stored for this prediction.')
        except SQLAlchemyError:
            LOG.error('Feedback write failed')
            return error(503,'storage_unavailable','Feedback was not stored. Please retry later.')

    @app.delete('/api/feedback/{identifier}')
    def remove_feedback(identifier:uuid.UUID,x_delete_token:str=Header(default='',max_length=128)):
        if app.state.database is None:return error(503,'storage_unavailable','Feedback storage is unavailable.')
        try:removed=app.state.database.delete_feedback(identifier,x_delete_token)
        except SQLAlchemyError:return error(503,'storage_unavailable','Feedback could not be deleted.')
        return {'status':'deleted'} if removed else error(404,'feedback_not_found','Feedback or deletion token not found.')

    @app.get('/')
    def index():return FileResponse(ROOT/'frontend/index.html')
    @app.get('/assets/config.js')
    def config_js():return Response('window.REVIEWMIND_CONFIG = '+json.dumps({'apiBaseUrl':settings.api_base_url})+';',media_type='text/javascript')
    app.mount('/assets',StaticFiles(directory=ROOT/'frontend/assets'),name='assets')
    return app

app=create_app()
