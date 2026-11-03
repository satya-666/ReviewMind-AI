"""Freeze validation selections before held-out weak-label evaluation."""
from pathlib import Path
import json
import time
import numpy as np
from src.evaluation.metrics import metrics,grouped_metrics,product_bootstrap,error_slices
from src.training.data import ROOT

def evaluate(frame,predictor,config):
    texts=frame['cleaned_text'].tolist()
    predictor(texts[:min(4,len(texts))])  # Warm-up is outside recorded inference time.
    tick=time.perf_counter();pred=np.asarray(predictor(texts),dtype=int)
    seconds=time.perf_counter()-tick
    report=metrics(frame['label_id'],pred)
    report.update({'inference_total_seconds':seconds,'inference_ms_per_review':seconds*1000/len(frame),
      'latency_protocol':'One warmed batch pass including text preprocessing/tokenization; throughput-derived ms/review, not single-request p95',
      'by_category':grouped_metrics(frame,pred,'product_category'),
      'by_language':grouped_metrics(frame,pred,'language',config['minimum_language_metric_reviews']),
      'product_group_bootstrap':product_bootstrap(frame,pred,config['bootstrap_product_resamples'],config['seed']),
      'diagnostic_error_slices':error_slices(frame,pred)})
    return report,pred

def save_private_errors(frame,pred,name,seed):
    g=frame.loc[pred!=frame['label_id'].to_numpy()].copy()
    g['prediction']=np.asarray(pred)[pred!=frame['label_id'].to_numpy()]
    sample=g.sample(n=min(12,len(g)),random_state=seed)
    # Keep real error snippets private; no reviewed record is redistributed to GitHub.
    rows=[{'review_id':r.review_id,'text':r.review_text,'weak_label':r.weak_label,'prediction_id':int(r.prediction)} for r in sample.itertuples()]
    path=ROOT/'data/interim'/('phase3_errors_'+name+'.json')
    path.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    return {'error_count':len(g),'private_sample_count':len(sample),'local_path':str(path.relative_to(ROOT)),
      'interpretation':'Disagreement with weak star labels, not verified model errors; slices are heuristic markers, not sarcasm/mixed-sentiment annotations'}
