"""Measure a fresh in-process ASGI serving stack; no transformer or training imports."""
import json,os,statistics,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
started=time.perf_counter()
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.settings import Settings
import psutil

def run():
    settings=Settings(database_url='sqlite:///'+str(ROOT/'.cache/web/benchmark.db'),rate_per_minute=200,global_rate_per_minute=1000)
    timings=[]
    with TestClient(create_app(settings)) as client:
        startup=time.perf_counter()-started
        assert client.get('/api/health').status_code==200
        client.post('/api/analyze',json={'text':'The sound is clear but the battery is poor.','category':'Audio devices'})
        for _ in range(30):
            tick=time.perf_counter()
            response=client.post('/api/analyze',json={'text':'The sound is clear but the battery is poor.','category':'Audio devices'})
            timings.append((time.perf_counter()-tick)*1000)
            assert response.status_code==200
        ordered=sorted(timings)
        result={'architecture':'Phase 3 validation-selected TF-IDF Logistic Regression, CPU, one copy',
          'model_version':response.json()['model_version'],'fresh_process_app_ready_seconds':startup,
          'model_service_load_seconds':client.app.state.model.startup_seconds,
          'process_rss_mib_after_requests':psutil.Process().memory_info().rss/1024**2,
          'model_ready_process_rss_mib':client.app.state.model.rss_bytes/1024**2,
          'request_count':len(timings),'median_api_ms':statistics.median(timings),'p95_api_ms':ordered[int(.95*(len(ordered)-1))],
          'max_api_ms':max(timings),'transformer_imported':'torch' in sys.modules,
          'protocol':'Fresh Python process, TestClient ASGI with real model and SQLite metadata write; warmed sequential single-review requests, no network. Not a Render/Linux/load benchmark.',
          'host':'Apple M3 arm64 macOS','deployment_workers':1,'inference_concurrency':1}
        assert not result['transformer_imported']
    (ROOT/'reports/phase3_5_benchmark.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':run()
