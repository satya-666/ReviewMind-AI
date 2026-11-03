"""Overall rating-derived weak labels, never aspect or human sentiment labels."""
import pandas as pd
from .dataset_analysis import counts, summary, percent

def weak_sentiment(ratings):
    numeric = pd.to_numeric(ratings,errors='coerce')
    labels = pd.Series('unavailable',index=ratings.index,dtype='string')
    labels.loc[numeric.isin([1,2])] = 'negative'
    labels.loc[numeric.eq(3)] = 'neutral'
    labels.loc[numeric.isin([4,5])] = 'positive'
    return labels

def rating_stats(frame):
    ratings = pd.to_numeric(frame['rating'],errors='coerce')
    valid = ratings[ratings.isin([1,2,3,4,5])]
    return {'distribution':counts(valid,[1,2,3,4,5]),'summary':summary(valid),
            'low_rated_percent':percent(int(valid.isin([1,2]).sum()),len(valid)),
            'high_rated_percent':percent(int(valid.isin([4,5]).sum()),len(valid)),
            'weak_sentiment_counts':counts(weak_sentiment(ratings),['negative','neutral','positive','unavailable']),
            'weak_label_definition':'1–2 negative, 3 neutral, 4–5 positive; exploratory overall rating-derived weak labels only'}

def rating_analysis(frame):
    result = rating_stats(frame)
    for column in ['product_category','source_dataset','language','split']:
        result['by_'+column] = {str(k):rating_stats(g) for k,g in frame.groupby(column)}
    return result
