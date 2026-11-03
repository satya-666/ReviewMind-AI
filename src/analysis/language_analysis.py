"""Analyze supplied weak language labels without reclassifying the source records."""
import re
import pandas as pd
from .dataset_analysis import counts, summary, percent, LANGUAGES
from .rating_analysis import rating_stats

def language_analysis(frame,config):
    confidence = pd.to_numeric(frame.get('language_confidence',pd.Series(index=frame.index,dtype=float)),errors='coerce')
    uncertain = frame['language'].eq('unknown') | confidence.lt(config['low_language_confidence_below']) | confidence.isna()
    manual = frame.get('language_manual_review',pd.Series(False,index=frame.index)).fillna(True)
    uncertain = uncertain | manual
    result = {'counts':counts(frame['language'],LANGUAGES),
      'percentages':{k:percent(int(frame['language'].eq(k).sum()),len(frame)) for k in LANGUAGES},
      'unknown_or_low_confidence_count':int(uncertain.sum()),
      'unknown_or_low_confidence_percent':percent(int(uncertain.sum()),len(frame)),
      'confidence_summary':summary(confidence),'confidence_missing_percent':percent(int(confidence.isna().sum()),len(frame)),
      'confidence_note':'Detector scores are uncalibrated. Null heuristic scores are unavailable, not evidence of high confidence.',
      'by_language':{}}
    for language in LANGUAGES:
        g = frame.loc[frame['language'].eq(language)]
        result['by_language'][language] = {'reviews':len(g),'characters':summary(g['cleaned_text'].str.len()),
            'whitespace_words':summary(g['cleaned_text'].str.split().str.len()),
            'rating':rating_stats(g),'sources':counts(g['source_dataset']),
            'categories':counts(g['product_category']),'confidence':summary(confidence.loc[g.index])}
    return result

def uncertain_sample(frame,config):
    pieces = []
    for label in ['unknown','hinglish','other']:
        group = frame.loc[frame['language'].eq(label)].sort_values('review_id')
        pieces.append(group.sample(n=min(config['language_sample_per_group'],len(group)),random_state=config['seed']))
    return pd.concat(pieces,ignore_index=True) if pieces else frame.iloc[:0].copy()

def redact(text,limit=500):
    text = re.sub(r'https?://\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:\+?\d[\d\s()-]{7,}\d)', '[REDACTED]',str(text))
    return text[:limit] if limit is not None else text
