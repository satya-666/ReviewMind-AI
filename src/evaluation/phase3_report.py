"""Plots and report use completed experiment records, never invented loss curves."""
from pathlib import Path
import numpy as np
from src.analysis.visualization import plt
from src.training.data import LABELS

def figures(result,directory,prefix='phase3_full'):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    models=result['models'];names=list(models);paths=[]
    context=f"Weak star labels • mode={result['mode']} • same held-out derived split • n={result['dataset']['splits']['test']['reviews']:,}"
    def save(suffix,title,draw,size=(10,6)):
        fig,ax=plt.subplots(figsize=size);draw(ax);ax.set_title(title,fontweight='bold',pad=12)
        fig.text(.02,.015,context,fontsize=8,color='#555555');fig.tight_layout(rect=(0,.05,1,1))
        path=directory/(prefix+'_'+suffix+'.png');fig.savefig(path,dpi=160,metadata={'Software':'ReviewMind AI Phase 3'});plt.close(fig);paths.append(path.name)
    def comparison(ax):
        x=np.arange(len(names));width=.35
        ax.bar(x-width/2,[models[n]['validation']['macro_f1'] for n in names],width,label='Validation macro F1')
        ax.bar(x+width/2,[models[n]['test']['macro_f1'] for n in names],width,label='Held-out weak macro F1')
        ax.set_xticks(x,names);ax.set_ylim(0,1);ax.set_ylabel('Macro F1');ax.legend()
    save('model_comparison','Validation selection and weak-label test agreement',comparison)
    for name,model in models.items():
        def matrix(ax,model=model):
            cm=np.array(model['test']['confusion_matrix']);ax.imshow(cm,cmap='Blues')
            ax.set_xticks(range(3),LABELS);ax.set_yticks(range(3),LABELS);ax.set_xlabel('Predicted');ax.set_ylabel('Weak reference')
            for i in range(3):
                for j in range(3):ax.text(j,i,str(cm[i,j]),ha='center',va='center',color='white' if cm[i,j]>cm.max()/2 else 'black')
        save(name+'_confusion','Confusion matrix: '+name,matrix)
        def classes(ax,model=model):
            x=np.arange(3);ax.bar(x-.18,[model['test']['per_class'][l]['precision'] for l in LABELS],.36,label='Precision')
            ax.bar(x+.18,[model['test']['per_class'][l]['recall'] for l in LABELS],.36,label='Recall')
            ax.set_xticks(x,LABELS);ax.set_ylim(0,1);ax.set_ylabel('Score');ax.legend()
        save(name+'_precision_recall','Class-wise weak-label scores: '+name,classes)
    for field,title in [('by_category','Per-category macro F1'),('by_language','Per-language macro F1 (small groups omitted)')]:
        groups=sorted({k for model in models.values() for k,g in model['test'][field].items() if g.get('macro_f1') is not None})
        def grouped(ax,groups=groups,field=field):
            width=.8/len(names);x=np.arange(len(groups))
            for i,name in enumerate(names):
                values=[models[name]['test'][field].get(g,{}).get('macro_f1',np.nan) for g in groups]
                ax.bar(x+(i-(len(names)-1)/2)*width,values,width,label=name)
            ax.set_xticks(x,[g.replace('_',' ') for g in groups],rotation=25,ha='right');ax.set_ylim(0,1);ax.set_ylabel('Macro F1');ax.legend()
        save(field,title,grouped)
    def latency(ax):
        ax.barh(names,[models[n]['test']['inference_ms_per_review'] for n in names]);ax.set_xlabel('Warmed batched throughput: milliseconds/review')
    save('inference_latency','Measured inference throughput (hardware-dependent)',latency)
    history=models.get('compact_bert',{}).get('history',[])
    if history:
        def losses(ax):
            ax.plot([e['epoch'] for e in history],[e['training_weighted_cross_entropy'] for e in history],marker='o',label='Training weighted cross entropy')
            ax.plot([e['epoch'] for e in history],[e['validation_weighted_cross_entropy'] for e in history],marker='o',label='Validation weighted cross entropy')
            ax.set_xlabel('Completed epoch');ax.set_ylabel('Mean of weighted batch losses');ax.set_xticks([e['epoch'] for e in history]);ax.legend()
        save('transformer_loss','Observed transformer training/validation losses',losses)
    return paths

def write_report(result,path):
    models=result['models'];selection=result['selection'];data=result['dataset']
    lines=['# ReviewMind AI — Phase 3 model report','',
      '## 1. Executive summary','',f"Execution mode: **{result['mode']}**. Overall status: **{result['status']}**.",'',
      'Real classical models were fitted and evaluated. Transformer completion is listed below only if actual fine-tuning succeeded. Human-verified sentiment evaluation, supervised ABSA and reliable multilingual evaluation remain incomplete; the entire phase is therefore **partial**. No Phase 4 implementation is included.','',
      '## 2. Dataset and label provenance','',
      'Existing Flipkart Kaggle v1 records from Phase 1 are reused under the recorded publisher ODbL/DbCL terms and underlying-rights limitations. No customer-review dataset was downloaded. Original splits are unchanged. Exact-name product groups remain proxies, not verified catalog identities.','',
      '| Derived view | Reviews | Negative | Neutral | Positive |','|---|---:|---:|---:|---:|']
    for name,g in data['splits'].items():
        lines.append(f"| {name} | {g['reviews']} | {g['classes']['negative']} | {g['classes']['neutral']} | {g['classes']['positive']} |")
    lines+=['',f"Canonical cross-split phrase quarantine removed: {data['canonical_quarantine_removed']}. Only lower-priority evaluation rows are excluded; no test record moves into training. Source ID, exact-name group, recorded duplicate-group and canonical-key overlap checks pass.",'',
      'Star ratings map 1–2/3/4–5 to negative/neutral/positive for overall weak supervision. Models receive text only, never rating, product ID or weak label as an input feature. Weak-label agreement is not evidence of genuine human or aspect-level sentiment understanding. The prior full-dataset EDA exposed holdout distributions; this is an exploratory development benchmark, not a fresh final holdout.','',
      '## 3. Experimental setup and reproducibility','',
      f"Seed: {result['seed']}. Source/split hashes, actual row counts, hyperparameters, package versions and hardware are recorded in phase3_results.json. MLflow parent run: `{result['mlflow']['parent_run_id']}`; tracking stays local in models/phase3/mlflow.db.",'',
      f"Hardware: {result['hardware']}. Measured total experiment time: {result['total_seconds']:.2f} seconds. Input files unchanged: {result['input_files_unchanged']}.",'',
      '## 4. Baseline architectures','',
      'Word 1–2-gram and character-within-word 3–5-gram TF-IDF feed Logistic Regression or Linear SVM. Vocabularies and IDF are fitted on training only. C and class weighting are selected by validation macro F1; all trial results are saved. No test feedback is used for tuning. Linear SVM margins are not probabilities; logistic probabilities are uncalibrated.','',
      '## 5. Transformer architecture and optimization','',
      'The feasible experiment uses [Google compact English BERT](https://huggingface.co/google/bert_uncased_L-2_H-128_A-2), Apache-2.0, 2 layers/128 hidden dimensions. It is not DistilBERT or XLM-R. A bounded stratified training subset, attention masks, seeded loaders, AdamW, linear warmup/decay, gradient accumulation/clipping, validation early stopping and best-checkpoint reload are implemented. MPS/CUDA are selected when available, with CPU fallback; mixed precision is restricted to CUDA.','',
      'Hyperparameters and completed-epoch losses are actual records in JSON. The compact model is a resource pilot with a smaller training budget than classical models; scores on the same held-out rows are comparable as predictions, not as equal-budget architecture experiments. Accelerator bitwise reproducibility is not guaranteed.','']
    if result.get('transformer_failure'):
        lines+=['Transformer failure: '+result['transformer_failure']['reason'],'']
    lines+=['## 6. Aspect-based sentiment','',
      'Nine configurable category taxonomies drive alias mention extraction. Clause-scoped nearest positive/negative cues and limited negation handling produce heuristic aspect sentiment, with unknown/mixed output and no calibrated confidence. They never use star ratings.','',
      f"Actual held-out coverage: {result['aspects']['reviews_with_aspect_mentions']} of {result['aspects']['reviews']} reviews contain extracted mentions. These are coverage counts, not precision/recall. Extraction F1 and aspect-sentiment F1 are **unavailable** because there are no genuine annotations. No supervised aspect model was trained.",'',
      'SemEval-2014 laptop ABSA was inspected ([official task](https://alt.qcri.org/semeval2014/task4/), [data terms](https://alt.qcri.org/semeval2014/task4/index.php?id=data-and-tools)); the terms reference fair use/provider restrictions rather than verified unrestricted reuse. It was not downloaded or silently relicensed. SetFit mirror access could not be verified. See the annotation guide and local blank annotation queue.','',
      '## 7. Multilingual methodology','',
      'Hindi is absent and Hinglish training/evaluation groups are very small. No XLM-R/IndicBERT/MuRIL fine-tuning was attempted. Per-language weak metrics are reported only above the configured sample floor, with all three class supports retained. Unknown labels stay unknown; no translation or Roman-script-equals-English assumption is applied. No multilingual capability claim is supported.','',
      '## 8–10. Hyperparameters, evaluation and comparison','',
      '| Model | Validation macro F1 | Weak test accuracy | Weak test macro F1 | Weighted F1 | Training seconds | Artifact bytes |','|---|---:|---:|---:|---:|---:|---:|']
    for name,g in models.items():
        lines.append(f"| {name} | {g['validation']['macro_f1']:.4f} | {g['test']['accuracy']:.4f} | {g['test']['macro_f1']:.4f} | {g['test']['weighted_f1']:.4f} | {g['training_seconds']:.2f} | {g['artifact_bytes']} |")
    lines+=['',f"Best baseline: **{selection['best_baseline']}**. Best feasible model by frozen validation macro F1: **{selection['best_feasible_model']}**. Test results are not used to change this decision. Compare latency/size before choosing deployment; high class imbalance makes raw accuracy inadequate.",'',
      'All models share the same derived held-out evaluation rows. Accuracy, macro precision/recall/F1, weighted F1, all class supports, confusion matrices and batched latency are in JSON. Product-group percentile bootstrap intervals use the configured seeded resamples and are exploratory: grouping identities and weak labels are uncertain, so nominal coverage is not guaranteed.','',
      '## 11. Per-category results','',
      '| Category | Reviews | '+' | '.join(models)+' |','|---|---:|'+'---:|'*len(models)]
    categories=sorted({k for g in models.values() for k in g['test']['by_category']})
    for category in categories:
        first=next(iter(models.values()))['test']['by_category'][category]
        lines.append('| '+category+' | '+str(first['reviews'])+' | '+' | '.join(f"{g['test']['by_category'][category]['macro_f1']:.4f}" for g in models.values())+' |')
    lines+=['','Smartphones and TVs/monitors remain unrepresented; tablet records are confined to training. No held-out performance is invented for missing categories.','',
      '## 12. Per-language results','',
      '| Supplied language label | Reviews | '+' | '.join(models)+' |','|---|---:|'+'---:|'*len(models)]
    languages=sorted({k for g in models.values() for k in g['test']['by_language']})
    for language in languages:
        first=next(iter(models.values()))['test']['by_language'][language]
        lines.append('| '+language+' | '+str(first['reviews'])+' | '+' | '.join('not scored' if g['test']['by_language'][language]['macro_f1'] is None else f"{g['test']['by_language'][language]['macro_f1']:.4f}" for g in models.values())+' |')
    lines+=['','Scores are agreement with weak labels within uncertain machine-language groups, not human-verified multilingual performance. Small groups are not stable evaluation benchmarks.','',
      '## 13. Error analysis','',
      'Seeded private samples of actual model/weak-label disagreements are saved under data/interim and are not published. Diagnostic slices cover negation markers, contrast/mixed-opinion markers, sarcasm-like markers, Roman Hindi, Hinglish labels, short/long text and product terms. These markers are not validated phenomenon annotations; sparse/empty slices cannot support claims of understanding sarcasm or conflicting aspects. Rare-class confusion and label noise require human adjudication. Aggregate human inspection notes are in docs/PHASE_3_ERROR_REVIEW.md.','',
      '## 14. Resource usage and inference','',
      'Per-model measured training time, model bytes and warmed batched inference throughput are in JSON. Classical training time includes all four hyperparameter trials and TF-IDF fitting; transformer time covers optimization, validation and checkpoint writes, excluding initial weight loading/tokenization. These timings are not equal-work benchmarks. Timing varies by system load; throughput-derived milliseconds/review is not interactive single-request tail latency. Local checkpoints include preprocessing/tokenizers and version metadata and are tested by reloading them for inference. No model weights, tokenizer cache, raw annotation/error text or MLflow database is committed.','',
      '## 15. Limitations','',
      'Human-verified sentiment benchmarks and genuine aspect labels are unavailable. Product/customer identities and dates are missing; prior EDA exposed existing holdouts. Canonical filtering may discard legitimate similar phrases, while approximate similarity checks cannot prove semantic leakage absence. Repeated within-split phrases remain potential evidence inflation. Licensing is publisher-declared, with underlying rights unverified. English pretrained models plus character features do not establish Hindi/Hinglish capability.','',
      '## 16. Selection rationale','',
      f"Validation macro F1 selects {selection['best_feasible_model']}; model complexity, storage, throughput, weak-label bias and missing independent evaluation must also inform any deployment choice. No comparison is made with models trained on unrelated datasets.",'',
      '## 17. Phase 4 readiness','',
      '**Research prototype only; not ready for a validated multilingual/recommendation production stage.** Complete blinded human annotation/adjudication, licensed supervised ABSA data, catalog-linked leakage checks, fresh final holdout collection and multilingual evaluation before treating these predictions as product evidence. Phase 4 is not implemented.','',
      '## Figures','']
    lines+=['!['+name+'](figures/'+name+')' for name in result.get('figures',[])]
    Path(path).write_text('\n'.join(lines)+'\n')
