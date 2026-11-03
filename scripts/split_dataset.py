"""Balance exact-name product groups; quarantine text groups crossing split boundaries."""
import hashlib
import numpy as np
import pandas as pd
NAMES = ['train','validation','test']

def assign_splits(frame, seed=42, fractions=(.7,.15,.15)):
    if frame.empty:
        return pd.Series([], dtype='str', index=frame.index)
    keys = frame['product_group']
    strata = frame['product_category'] + '|' + frame['language']
    table = pd.crosstab(keys, strata)
    table['__total'] = table.sum(axis=1)
    target = np.asarray(fractions)[:,None] * table.sum().to_numpy()[None,:]
    counts = np.zeros_like(target)
    assignments = {}
    order = sorted(table.index, key=lambda k:(-table.loc[k,'__total'], hashlib.sha256(f'{seed}:{k}'.encode()).hexdigest()))
    for key in order:
        vector = table.loc[key].to_numpy()
        scores = []
        for s in range(3):
            trial = counts.copy(); trial[s] += vector
            scores.append(float((((trial-target)**2)/(target+1)).sum()))
        s = int(np.argmin(scores)); counts[s] += vector; assignments[key] = NAMES[s]
    return keys.map(assignments)

def quarantine_leakage(frame):
    priority = {'train':0,'validation':1,'test':2}
    winners = frame.groupby('duplicate_group')['split'].agg(lambda s:min(s, key=priority.get))
    keep = frame['split'] == frame['duplicate_group'].map(winners)
    return frame.loc[keep].copy(), frame.loc[~keep].copy()

def assert_no_leakage(frame):
    for key in ['review_id','product_group','duplicate_group']:
        if len(frame):
            assert frame.groupby(key)['split'].nunique().max() <= 1, key
