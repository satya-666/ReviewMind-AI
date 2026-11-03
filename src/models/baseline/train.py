"""Fit TF-IDF on training only; select C/class weighting on validation only."""
from pathlib import Path
import time
import joblib
from sklearn.pipeline import Pipeline,FeatureUnion
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from src.evaluation.metrics import metrics

def build(kind,config,C=1.,class_weight=None,seed=42):
    features=FeatureUnion([
      ('word',TfidfVectorizer(ngram_range=(1,2),min_df=2,max_features=config['word_max_features'],sublinear_tf=True)),
      ('char',TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),min_df=2,max_features=config['char_max_features'],sublinear_tf=True))])
    if kind=='logistic_regression':
        classifier=LogisticRegression(C=C,class_weight=class_weight,max_iter=config['max_iterations'],random_state=seed)
    elif kind=='linear_svm':
        classifier=LinearSVC(C=C,class_weight=class_weight,max_iter=config['max_iterations'],random_state=seed)
    else:
        raise ValueError('Unknown baseline '+kind)
    return Pipeline([('tfidf',features),('classifier',classifier)])

def train_baselines(train,validation,config,directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    result={};models={}
    for kind in ['logistic_regression','linear_svm']:
        started=time.perf_counter();trials=[];best=None;best_score=-1.
        for C in config['baseline']['C']:
            for weight in config['baseline']['class_weights']:
                model=build(kind,config['baseline'],C,weight,config['seed'])
                tick=time.perf_counter()
                model.fit(train['cleaned_text'],train['label_id'])
                score=metrics(validation['label_id'],model.predict(validation['cleaned_text']))
                trial={'C':C,'class_weight':weight,'seconds':time.perf_counter()-tick,'validation':score}
                trials.append(trial)
                print(kind,'C=',C,'weight=',weight,'validation macro F1=',round(score['macro_f1'],4),flush=True)
                if score['macro_f1']>best_score:
                    best_score=score['macro_f1'];best=model;selected={'C':C,'class_weight':weight};best_validation=score
        path=directory/(kind+'.joblib');joblib.dump(best,path)
        models[kind]=best
        result[kind]={'architecture':'word (1,2) + character-within-word (3,5) TF-IDF + '+kind,
          'trained':True,'training_reviews':len(train),'validation_reviews':len(validation),
          'parameters':selected,'validation':best_validation,'selection_trials':trials,
          'training_seconds':time.perf_counter()-started,'artifact_path':str(path),
          'artifact_bytes':path.stat().st_size,'seed':config['seed'],
          'confidence_semantics':'uncalibrated classifier probabilities' if kind=='logistic_regression' else 'decision margins; not probabilities'}
    return models,result
