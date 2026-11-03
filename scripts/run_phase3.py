"""Execute feasible Phase 3 work; smoke results are isolated from full experiments."""
import os
os.environ.setdefault('HF_HOME',str(__import__('pathlib').Path(__file__).resolve().parents[1]/'.cache/huggingface'))
os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
os.environ.setdefault('MLFLOW_DISABLE_AGENT_HINT','1')
import argparse,importlib.metadata,json,platform,shutil,sys,time,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import yaml
from scripts.run_phase2 import write_json
from src.training.data import prepare,annotation_workflow,LABELS
from src.analysis.dataset_analysis import sha256
from src.models.baseline.train import train_baselines
from src.models.aspects.rules import aspect_experiment
from src.evaluation.experiments import evaluate,save_private_errors

def run(mode='full',config_path=ROOT/'configs/phase3_config.yaml'):
    import mlflow
    config=yaml.safe_load(Path(config_path).read_text())
    splits,manifest=prepare(config,mode)
    output=ROOT/config['output_root']/mode;output.mkdir(parents=True,exist_ok=True)
    if mode=='smoke':
        config['baseline']['C']=[.5];config['baseline']['class_weights']=[None]
        config['bootstrap_product_resamples']=0
    print('Phase 3',mode,'derived sizes',{k:len(v) for k,v in splits.items()},flush=True)
    tracker=ROOT/config['output_root']/'mlflow.db';tracker.parent.mkdir(parents=True,exist_ok=True)
    mlflow.set_tracking_uri('sqlite:///'+str(tracker));mlflow.set_experiment('ReviewMind-Phase3-'+mode)
    start=time.perf_counter()
    import psutil
    try:cpu=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True,stderr=subprocess.DEVNULL).strip() if sys.platform=='darwin' else platform.processor()
    except (OSError,subprocess.CalledProcessError):cpu=platform.processor()
    try:ram=psutil.virtual_memory().total
    except OSError:ram=None
    result={'mode':mode,'status':'in_progress','dataset':manifest,'seed':config['seed'],'configuration':config,
      'phase2_base_commit':'2a2bded66e753d4ecb3a788fd13ef6e888562866','models':{},
      'human_verified_sentiment_evaluation':{'status':'unavailable','metrics':None},
      'multilingual_experiment':{'trained':False,'reason':'No Hindi examples and only 15 Hinglish training labels before filtering; not adequate for multilingual fine-tuning claims'},
      'hardware':{'machine':platform.machine(),'python':platform.python_version(),'cpu':cpu,
                  'ram_bytes':ram,
                  'free_disk_bytes':shutil.disk_usage(ROOT).free},
      'dependency_versions':{p:importlib.metadata.version(p) for p in ['scikit-learn','torch','transformers','mlflow-skinny','pandas','numpy']}}
    result['annotation_workflow']=annotation_workflow(splits,config,mode)
    with mlflow.start_run(run_name='phase3-'+mode) as parent:
        result['mlflow']={'parent_run_id':parent.info.run_id,'tracking_uri':config['tracking_uri'],'local_only':True}
        mlflow.log_params({'seed':config['seed'],'mode':mode,'dataset':'Flipkart Kaggle v1','label_basis':'rating-derived weak labels',
          'train_rows':len(splits['train']),'validation_rows':len(splits['validation']),'test_rows':len(splits['test'])})
        models,information=train_baselines(splits['train'],splits['validation'],config,output/'baseline')
        transformer=None
        if mode=='full':
            try:
                from src.models.sentiment.transformer import train_transformer
                transformer,info=train_transformer(splits['train'],splits['validation'],config,ROOT,output/'sentiment')
                information['compact_bert']=info
            except (OSError,RuntimeError,ValueError,ImportError) as error:
                result['transformer_failure']={'trained':False,'reason':str(error),'action':'Run scripts/cache_transformer.py, then rerun full mode; inspect hardware/device configuration'}
                print('Transformer not completed:',type(error).__name__,str(error),flush=True)
        # Freeze selections using validation scores before invoking held-out prediction.
        best_baseline=max(models,key=lambda name:information[name]['validation']['macro_f1'])
        best_overall=max(information,key=lambda name:information[name]['validation']['macro_f1'])
        result['selection']={'best_baseline':best_baseline,'best_feasible_model':best_overall,
          'criterion':'highest validation macro F1; test metrics never used for selection',
          'frozen_before_test':True,'training_budget_comparability':'Baselines use all derived training rows; compact BERT is a bounded stratified-subset pilot'}
        predictors={name:(lambda texts,m=model:m.predict(texts)) for name,model in models.items()}
        if transformer:
            from src.models.sentiment.transformer import predict
            model,tokenizer,device=transformer
            predictors['compact_bert']=lambda texts:predict(model,tokenizer,texts,device,config['transformer']['max_length']).argmax(1)
        for name,predictor in predictors.items():
            info=information[name]
            info['artifact_path']=str(Path(info['artifact_path']).relative_to(ROOT))
            info['test'],pred=evaluate(splits['test'],predictor,config)
            info['private_error_analysis']=save_private_errors(splits['test'],pred,name,config['seed'])
            info['version']='phase3-'+mode+'-'+name+'-seed'+str(config['seed'])
            artifact=ROOT/info['artifact_path']
            metadata=artifact/'reviewmind_metadata.json' if artifact.is_dir() else artifact.with_suffix('.metadata.json')
            write_json(metadata,{'version':info['version'],'labels':LABELS,'max_length':config['transformer']['max_length'],
                'label_basis':'rating-derived weak supervision','model_type':name})
            with mlflow.start_run(run_name=name,nested=True) as child:
                info['mlflow_run_id']=child.info.run_id
                mlflow.log_params({'architecture':info['architecture'],'seed':config['seed'],'artifact_path':info['artifact_path'],
                  'parameters':json.dumps(info['parameters'],sort_keys=True),'training_reviews':info['training_reviews'],
                  'dataset_split_ids':json.dumps({k:v['review_ids_sha256'] for k,v in manifest['splits'].items()}),
                  'hardware':json.dumps(result['hardware'])})
                mlflow.log_metrics({'validation_macro_f1':info['validation']['macro_f1'],'test_macro_f1':info['test']['macro_f1'],
                  'test_accuracy':info['test']['accuracy'],'training_seconds':info['training_seconds'],'model_bytes':info['artifact_bytes']})
                for epoch in info.get('history',[]):
                    mlflow.log_metrics({'training_loss':epoch['training_weighted_cross_entropy'],
                      'validation_loss':epoch['validation_weighted_cross_entropy']},step=epoch['epoch'])
            result['models'][name]=info
            print(name,'weak test accuracy',round(info['test']['accuracy'],4),'macro F1',round(info['test']['macro_f1'],4),flush=True)
        result['aspects']=aspect_experiment(splits['test'])
        result['total_seconds']=time.perf_counter()-start
        result['status']='smoke_only_not_full_experiment' if mode=='smoke' else 'partial_human_sentiment_and_supervised_absa_unavailable'
        if mode=='baseline':result['transformer_status']='not requested in baseline mode'
        result['input_files_unchanged']=all(sha256(ROOT/name)==digest for name,digest in manifest['input_sha256'].items())
        if not result['input_files_unchanged']:raise RuntimeError('Phase 1 input hash changed')
        result_path=ROOT/'reports'/('phase3_results.json' if mode=='full' else 'phase3_'+mode+'_results.json')
        write_json(result_path,result)
        from src.evaluation.phase3_report import write_report,figures
        result['figures']=figures(result,ROOT/'reports/figures',prefix='phase3_'+mode)
        write_json(result_path,result)
        write_report(result,ROOT/'reports'/('phase3_model_report.md' if mode=='full' else 'phase3_'+mode+'_report.md'))
        mlflow.log_artifact(str(result_path))
    print('Finished',mode,'results:',str(result_path.relative_to(ROOT)),flush=True)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['smoke','baseline','full'],default='full')
    parser.add_argument('--config',type=Path,default=ROOT/'configs/phase3_config.yaml')
    args=parser.parse_args();run(args.mode,args.config)
