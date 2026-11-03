"""Read-only EDA entry point: python scripts/run_phase2.py [--config PATH]."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import yaml
from src.analysis.dataset_analysis import load_splits, validation_summary, dataset_overview, sha256
from src.analysis.category_analysis import category_analysis
from src.analysis.rating_analysis import rating_analysis
from src.analysis.language_analysis import language_analysis, uncertain_sample, redact
from src.analysis.text_analysis import text_analysis
from src.analysis.product_analysis import product_analysis
from src.analysis.bias_analysis import bias_analysis, verify_phase1_reproduction
from src.analysis.visualization import plot_figures
from src.analysis.report import research_report

def write_json(path,value):
    content = json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(content,encoding='utf-8'); temporary.replace(path)

def analyze(frame,config):
    return {'overview':dataset_overview(frame),'categories':category_analysis(frame,config),
      'ratings':rating_analysis(frame),'languages':language_analysis(frame,config),
      'text':text_analysis(frame,config),'products':product_analysis(frame,config),'bias':bias_analysis(frame,config)}

def run(config_path=ROOT/'configs/phase2_config.yaml'):
    config = yaml.safe_load(Path(config_path).read_text())
    paths = list(config['splits'].values()) + ['data/processed/cleaned.parquet','data/processed/training_ready.parquet']
    manifest = {name:sha256(ROOT/name) for name in paths if (ROOT/name).exists()}
    frame = load_splits(ROOT,config)
    if frame.empty:
        raise ValueError('No review records available in Phase 1 splits; no fictional charts or report will be generated')
    validation = validation_summary(frame)
    validation['split_reproduction'] = verify_phase1_reproduction(ROOT,frame)
    record = json.loads((ROOT/'reports/reproducibility.json').read_text()) if (ROOT/'reports/reproducibility.json').exists() else {}
    expected = record.get('after',{})
    validation['recorded_checksum_matches'] = bool(expected) and all(manifest.get(k)==v for k,v in expected.items())
    print(f'Loaded {len(frame):,} reviews; schema checks passed={validation["passed"]}',flush=True)
    metrics = analyze(frame,config)
    validation['scope'] = 'Schema/value/source-ID/exact-name-group checks; passing does not prove semantic or catalog-identity leakage absence'
    validation['similarity_warnings'] = {
      'canonical_phrase_cross_split_groups':metrics['bias']['exact_duplicates']['token_canonical_cross_split_groups'],
      'canonical_phrase_cross_split_rows':metrics['bias']['exact_duplicates']['token_canonical_cross_split_rows'],
      'bounded_near_duplicate_pairs':metrics['bias']['bounded_near_duplicates']['verified_high_similarity_cross_split_pairs']}
    metrics['validation'] = validation
    metrics['reproducibility'] = {'config':config,'input_sha256':manifest,'phase1_base_commit':'26b7ea014f03542a4b5b3bfdd4dd8e52613bbdf4',
      'analysis_code_sha256':{str(p.relative_to(ROOT)):sha256(p) for p in sorted((ROOT/'src/analysis').glob('*.py'))},
      'software':{k:importlib.metadata.version(k) for k in ['pandas','pyarrow','matplotlib','datasketch','nbformat','nbclient']}}
    local = ROOT/'data/interim/phase2_language_sample.json'
    sample = uncertain_sample(frame,config)
    local_rows = [{'review_id':row.review_id,'supplied_language':row.language,
                   'excerpt':redact(row.cleaned_text)} for row in sample.itertuples()]
    write_json(local,{'seed':config['seed'],'not_for_publication':True,'sample':local_rows})
    metrics['languages']['local_review_sample_count'] = len(sample)
    reports = ROOT/'reports'; reports.mkdir(exist_ok=True)
    metrics['figures'] = plot_figures(frame,metrics,reports/'figures')
    # Refuse to claim a successful run if any Phase 1 artifact changed during EDA.
    if manifest != {name:sha256(ROOT/name) for name in manifest}:
        raise RuntimeError('Phase 1 input checksum changed during analysis')
    write_json(reports/'phase2_metrics.json',metrics)
    write_json(reports/'phase2_validation.json',validation)
    (reports/'phase2_eda_report.md').write_text(research_report(metrics),encoding='utf-8')
    if not validation['passed']:
        raise ValueError('Phase 1 validation failed; see reports/phase2_validation.json. Inputs were not repaired.')
    if not validation['split_reproduction']['verified']:
        print('WARNING: Split reproduction could not be verified; inspect validation report.',flush=True)
    print(f'Wrote {len(metrics["figures"])} figures, metrics, validation summary and research report.',flush=True)
    return metrics

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'configs/phase2_config.yaml')
    arguments = parser.parse_args()
    try:
        run(arguments.config)
    except (ValueError,FileNotFoundError,KeyError) as error:
        raise SystemExit(f'Phase 2 failed: {error}') from error
