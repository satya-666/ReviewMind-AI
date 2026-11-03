"""All reported sentiment scores measure agreement with explicit weak labels."""
import numpy as np
from sklearn.metrics import accuracy_score,precision_recall_fscore_support,f1_score,confusion_matrix
from src.training.data import LABELS

def metrics(y,pred):
    y=np.asarray(y,dtype=int);pred=np.asarray(pred,dtype=int)
    if not len(y):
        return {'reviews':0,'accuracy':None,'macro_precision':None,'macro_recall':None,'macro_f1':None,'weighted_f1':None,
                'per_class':{},'confusion_matrix':[[0]*3 for _ in range(3)]}
    p,r,f,s=precision_recall_fscore_support(y,pred,labels=[0,1,2],zero_division=0)
    return {'reviews':len(y),'accuracy':float(accuracy_score(y,pred)),
      'macro_precision':float(p.mean()),'macro_recall':float(r.mean()),'macro_f1':float(f.mean()),
      'weighted_f1':float(f1_score(y,pred,labels=[0,1,2],average='weighted',zero_division=0)),
      'per_class':{label:{'precision':float(p[i]),'recall':float(r[i]),'f1':float(f[i]),'support':int(s[i])} for i,label in enumerate(LABELS)},
      'confusion_matrix':confusion_matrix(y,pred,labels=[0,1,2]).tolist(),
      'label_basis':'rating-derived weak supervision; not verified sentiment understanding'}

def grouped_metrics(frame,pred,column,minimum=1):
    result={}
    for name,g in frame.groupby(column):
        positions=frame.index.get_indexer(g.index)
        result[str(name)]=metrics(g['label_id'],np.asarray(pred)[positions]) if len(g)>=minimum else {
          'reviews':len(g),'status':f'not scored: fewer than {minimum} records','macro_f1':None,'accuracy':None}
    return result

def product_bootstrap(frame,pred,repetitions,seed):
    if repetitions<=0 or frame.empty:
        return {'status':'not computed'}
    rng=np.random.default_rng(seed)
    groups=[g.index.to_numpy() for _,g in frame.groupby('product_group')]
    values=[]
    for _ in range(repetitions):
        idx=np.concatenate([groups[i] for i in rng.integers(0,len(groups),size=len(groups))])
        values.append(metrics(frame.loc[idx,'label_id'],np.asarray(pred)[idx])['macro_f1'])
    return {'macro_f1_percentile_95':[float(x) for x in np.quantile(values,[.025,.975])],
      'resamples':repetitions,'unit':'exact-name product groups, sampled with replacement',
      'limitation':'Conditional exploratory interval; few groups, weak labels and uncertain identity limit coverage interpretation'}

def error_slices(frame,pred):
    text=frame['cleaned_text'].str.casefold()
    masks={'negation_marker':text.str.contains(r'\b(?:not|no|never|nahi|nahin)\b',regex=True),
      'mixed_opinion_marker':text.str.contains(r'\b(?:but|however|although|lekin)\b',regex=True),
      'sarcasm_marker_only':text.str.contains(r'/s|yeah right|as if',regex=True),
      'hinglish_label':frame['language'].eq('hinglish'),
      'roman_hindi_marker':text.str.contains(r'\b(?:hai|nahi|bahut|acha|accha|bekar)\b',regex=True),
      'short_under_3_words':text.str.split().str.len().lt(3),
      'long_over_50_words':text.str.split().str.len().gt(50),
      'product_term_marker':text.str.contains(r'\b(?:battery|sound|keyboard|router|charging)\b',regex=True)}
    return {name:metrics(frame.loc[mask,'label_id'],np.asarray(pred)[mask.to_numpy()]) for name,mask in masks.items()}
