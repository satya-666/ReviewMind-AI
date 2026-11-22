"""Recheck the serving classifier against a train-majority baseline; no model changes."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import joblib,numpy as np,pandas as pd,yaml
from sklearn.base import clone
from src.training.data import prepare,LABELS
from src.evaluation.metrics import metrics,error_slices
from src.analysis.dataset_analysis import sha256
from scripts.deduplicate import duplicate_groups
from src.models.aspects.rules import aspects


def run():
    config=yaml.safe_load((ROOT/'configs/phase3_config.yaml').read_text())
    splits,manifest=prepare(config);train,test=splits['train'],splits['test']
    model_path=ROOT/'models/phase3/full/baseline/logistic_regression.joblib'
    model=joblib.load(model_path)
    # Refit the frozen pipeline solely on train to verify checkpoint reproducibility.
    fitted=clone(model).fit(train.cleaned_text,train.label_id)
    predicted=model.predict(test.cleaned_text)
    assert np.array_equal(predicted,fitted.predict(test.cleaned_text)), 'Serving checkpoint differs from train-only refit'
    for (_,a),(_,b) in zip(model.named_steps['tfidf'].transformer_list,fitted.named_steps['tfidf'].transformer_list):
        assert a.vocabulary_==b.vocabulary_ and np.array_equal(a.idf_,b.idf_), 'TF-IDF was not fitted solely on train'
    majority=int(train.label_id.mode()[0])
    frame=pd.concat(splits.values(),ignore_index=True)
    groups,audit=duplicate_groups(frame,{'permutations':128,'min_characters':80,'jaccard_threshold':.90})
    cross=int(pd.DataFrame({'group':groups,'split':frame.split}).groupby('group').split.nunique().gt(1).sum())
    assert cross==0,'Detected cross-split near duplicates'
    result={'dataset':manifest,'model_sha256':sha256(model_path),'labels':LABELS,
      'train_only_tfidf_refit_identical':True,'majority_training_class':LABELS[majority],
      'majority':metrics(test.label_id,np.full(len(test),majority)),
      'classifier':metrics(test.label_id,predicted),'diagnostic_slices':error_slices(test,predicted),
      'duplicate_audit':{'cross_split_groups':cross,'exact_pairs':audit['exact_text_pairs'],'near_pairs':audit['near_text_pairs'],
        'method':'All retained rows: exact casefold text plus seeded 128-permutation MinHash candidates; character 5-gram Jaccard >=0.90 for text >=80 characters. Approximate candidate search is not proof of universal absence.'}}
    # Keep original customer text private; publish IDs and observed labels, not redistributed reviews.
    errors=test.loc[predicted!=test.label_id.to_numpy()].copy();errors['prediction']=predicted[predicted!=test.label_id.to_numpy()]
    examples=[]
    for row in errors.head(5).itertuples():
        examples.append({'review_id':row.review_id,'text':row.review_text,'weak_label':row.weak_label,'prediction':LABELS[int(row.prediction)]})
    private=ROOT/'data/interim/portfolio_errors.json';private.write_text(json.dumps(examples,ensure_ascii=False,indent=2)+'\n')
    result['error_examples']=[{k:v for k,v in r.items() if k!='text'} for r in examples]
    result['error_examples_private_path']='data/interim/portfolio_errors.json'
    # Authored manual fixtures are transparent diagnostics, not independent human labels.
    cases=json.loads((ROOT/'tests/fixtures/aspect_diagnostics.json').read_text())
    tp=fp=fn=correct=matched=0;details=[]
    for case in cases:
        found={a['aspect']:a['sentiment'] for a in aspects(case['text'],case['category'])};expected=case['aspects']
        shared=found.keys() & expected.keys();tp+=len(shared);fp+=len(found.keys()-expected.keys());fn+=len(expected.keys()-found.keys())
        correct+=sum(found[k]==expected[k] for k in shared);matched+=len(shared)
        details.append({'id':case['id'],'expected':expected,'actual':found})
    result['manual_aspects']={'reviews':len(cases),'true_positive':tp,'false_positive':fp,'false_negative':fn,
      'detection_precision':tp/(tp+fp) if tp+fp else 0,'detection_recall':tp/(tp+fn) if tp+fn else 0,
      'polarity_accuracy_on_matched_aspects':correct/matched if matched else 0,'matched_aspects':matched,
      'limitations':'Small developer-authored English/Hinglish diagnostic set, selected with knowledge of rules; no independent annotator or representative sampling; not a supervised ABSA benchmark.','cases':details}
    target=ROOT/'reports/portfolio_evaluation.json';target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    lines=['# Reproducible portfolio evaluation','', 'Run `.venv/bin/python scripts/evaluate_portfolio.py` after dataset preparation. This evaluates the existing serving checkpoint and a train-majority baseline on identical held-out rows. A frozen clone refitted only on train reproduces TF-IDF vocabulary, IDF and all test predictions. It does not retune on test.','',
      'Labels come from stars (1–2 negative, 3 neutral, 4–5 positive), not independent sentiment annotations. The test has already been inspected in earlier phases; it is not a fresh final holdout. Smartphone and Hindi training coverage is absent.','',
      '| Model | Test reviews | Macro F1 |','|---|---:|---:|',f"| Train-majority | {len(test)} | {result['majority']['macro_f1']:.4f} |",f"| TF-IDF + logistic regression | {len(test)} | {result['classifier']['macro_f1']:.4f} |",'',
      '| Class | Train | Test | Precision | Recall |','|---|---:|---:|---:|---:|']
    for name in LABELS:
        row=result['classifier']['per_class'][name];lines.append(f"| {name} | {manifest['splits']['train']['classes'][name]} | {row['support']} | {row['precision']:.4f} | {row['recall']:.4f} |")
    lines+=['','Confusion matrix: rows = true rating label, columns = prediction, order negative / neutral / positive.','', '```json',json.dumps(result['classifier']['confusion_matrix']),'```','',
      f"Duplicate audit: {cross} detected cross-split groups. {result['duplicate_audit']['method']}",'',
      'Mixed and negation slices are lexical markers with rating labels, not labeled mixed/negation understanding. Per-slice metrics and sample counts are in [the JSON](portfolio_evaluation.json). Hinglish is too small for a reliable generalization claim.','',
      f"Manual aspect diagnostics: {len(cases)} authored examples; detection precision {result['manual_aspects']['detection_precision']:.3f}, recall {result['manual_aspects']['detection_recall']:.3f}; matched-aspect polarity accuracy {result['manual_aspects']['polarity_accuracy_on_matched_aspects']:.3f}. {result['manual_aspects']['limitations']}",'',
      'Five real rating-label disagreements are identified in the JSON. Exact customer text is written locally to `data/interim/portfolio_errors.json` by the reproduction command and is excluded from Git. Inspect these alongside their rating labels; a disagreement can reflect an imperfect weak label.','',
      'Dataset: Nirali Vaghani, Flipkart Product reviews with sentiment Dataset v1 (Kaggle); archive hash and split hashes are in the JSON manifest. Attribution, source evidence, ODbL/DbCL notices and acquisition constraints are in [the dataset card](../docs/PHASE_1.md).']
    (ROOT/'reports/portfolio_evaluation.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'classifier_macro_f1':result['classifier']['macro_f1'],'majority_macro_f1':result['majority']['macro_f1'],'test_reviews':len(test),'aspects':result['manual_aspects']},indent=2))
    return result

if __name__=='__main__':run()
