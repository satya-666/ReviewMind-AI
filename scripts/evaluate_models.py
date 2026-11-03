"""Reload completed real checkpoints and verify held-out weak-label metrics."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import yaml
from src.training.data import prepare,LABEL_MAP
from src.models.inference import ReviewPredictor
from src.evaluation.metrics import metrics

def evaluate_saved(result_path=ROOT/'reports/phase3_results.json'):
    result=json.loads(Path(result_path).read_text())
    splits,manifest=prepare(result['configuration'],result['mode'])
    if manifest['splits']['test']['review_ids_sha256']!=result['dataset']['splits']['test']['review_ids_sha256']:
        raise ValueError('Evaluation split identifiers changed')
    if manifest['input_sha256']!=result['dataset']['input_sha256']:
        raise ValueError('Phase 1 input checksums changed')
    test=splits['test'];output={}
    for name,record in result['models'].items():
        predictor=ReviewPredictor(ROOT/record['artifact_path'],device='cpu')
        predictions=predictor.batch(test['cleaned_text'].tolist())
        actual=metrics(test['label_id'],[LABEL_MAP[r['sentiment']] for r in predictions])
        matched=actual['confusion_matrix']==record['test']['confusion_matrix']
        output[name]={'metrics':actual,'matches_original_confusion_matrix':matched}
        if not matched:raise ValueError('Reloaded prediction mismatch: '+name)
        print('Reloaded and verified',name,flush=True)
    target=ROOT/'reports/phase3_reevaluation.json'
    target.write_text(json.dumps(output,indent=2)+'\n')
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--results',type=Path,default=ROOT/'reports/phase3_results.json')
    evaluate_saved(parser.parse_args().results)
