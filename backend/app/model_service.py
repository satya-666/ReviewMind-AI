"""Load one checksum-verified Phase 3 baseline; no training or remote substitution."""
import hashlib,json,threading,time,logging
import psutil
from src.models.inference import ReviewPredictor

LOG=logging.getLogger('reviewmind.model')

class ModelService:
    def __init__(self,settings):
        self.predictor=None;self.error=None;self.lock=threading.Lock()
        self.startup_seconds=0.;self.rss_bytes=0;self.manifest={}
        started=time.perf_counter()
        try:
            self.manifest=json.loads(settings.manifest_path.read_text())
            expected=self.manifest['checkpoint_sha256']
            if hashlib.sha256(settings.model_path.read_bytes()).hexdigest()!=expected:
                raise ValueError('Unapproved checkpoint checksum')
            self.predictor=ReviewPredictor(settings.model_path,kind='baseline')
            if self.predictor.version!=self.manifest['model_version']:
                raise ValueError('Checkpoint metadata version mismatch')
            self.predictor.single('Startup validation review')
        except Exception as error:
            self.predictor=None;self.error='model_unavailable'
            LOG.error('Model startup failed (%s)',type(error).__name__)
        self.startup_seconds=time.perf_counter()-started
        self.rss_bytes=psutil.Process().memory_info().rss

    def analyze(self,text,category):
        if self.predictor is None:raise RuntimeError('model_unavailable')
        if not self.lock.acquire(blocking=False):raise BlockingIOError('inference_busy')
        try:
            start=time.perf_counter();result=self.predictor.single(text,category)
            result['prediction_ms']=(time.perf_counter()-start)*1000
            return result
        finally:self.lock.release()
