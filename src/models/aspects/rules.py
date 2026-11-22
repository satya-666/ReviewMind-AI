"""Category-aware aspect mentions and local lexical sentiment; never supervised ABSA."""
from pathlib import Path
import re
import yaml

def load_taxonomy(path=None):
    path=Path(path) if path else Path(__file__).resolve().parents[3]/'configs/aspect_taxonomy.yaml'
    return yaml.safe_load(path.read_text())

POSITIVE=['excellent','great','good','amazing','love','clear','comfortable','fast','superb','accha','acha','achha','अच्छा','शानदार']
NEGATIVE=['bad','poor','worst','terrible','broken','drains','drain','slow','disconnect','uncomfortable','disappointing','disappointed','bekar','kharab','खराब']

def aspects(text,category,taxonomy=None):
    if not isinstance(text,str) or not text.strip():
        raise ValueError('Review must be a nonempty string')
    taxonomy=load_taxonomy() if taxonomy is None else taxonomy
    if category not in taxonomy:
        return []
    boundaries=[0]+[m.end() for m in re.finditer(r'\b(?:but|however|although|lekin)\b|[.!?;।]',text,re.I)]+[len(text)]
    result=[]
    for name,aliases in taxonomy[category].items():
        pattern=r'(?<!\w)(?:'+'|'.join(re.escape(s) for s in sorted(aliases,key=len,reverse=True))+r')(?!\w)'
        for match in re.finditer(pattern,text,re.I):
            left=max(x for x in boundaries if x<=match.start());right=min(x for x in boundaries if x>=match.end())
            clause=text[left:right]
            cues=[]
            for polarity,words in [('positive',POSITIVE),('negative',NEGATIVE)]:
                cue_pattern=r'(?<!\w)(?:'+'|'.join(re.escape(w) for w in words)+r')(?!\w)'
                for cue in re.finditer(cue_pattern,clause,re.I):
                    distance=abs(left+cue.start()-match.start())
                    if distance<=90:
                        before=clause[max(0,cue.start()-25):cue.start()]
                        negated=bool(re.search(r'\b(?:not|never|no|nahi|nahin)\b(?:\W+\w+){0,2}\W*$',before,re.I))
                        label=('negative' if polarity=='positive' else 'positive') if negated else polarity
                        cues.append((distance,label))
            if not cues:sentiment='unknown'
            else:
                closest=min(d for d,_ in cues)
                near={p for d,p in cues if d<=closest+5}
                sentiment=next(iter(near)) if len(near)==1 else 'mixed'
            result.append({'aspect':name,'term':match.group(),'start':match.start(),'end':match.end(),
              'sentiment':sentiment,'evidence':clause.strip() if cues else match.group(),'confidence':None,'method':'category_alias_and_nearest_clause_lexicon',
              'label_status':'rule_generated_not_ground_truth'})
    return sorted(result,key=lambda r:(r['start'],r['end'],r['aspect']))

def aspect_experiment(frame):
    from collections import Counter
    mentions=Counter();sentiments=Counter();rows=0
    taxonomy=load_taxonomy()
    for row in frame.itertuples():
        found=aspects(row.cleaned_text,row.product_category,taxonomy)
        rows+=bool(found)
        mentions.update({item['aspect'] for item in found})
        sentiments.update(item['sentiment'] for item in found)
    return {'method':'rule baseline only','reviews':len(frame),'reviews_with_aspect_mentions':rows,
      'review_counts_by_aspect':dict(sorted(mentions.items())),'mention_sentiment_counts':dict(sorted(sentiments.items())),
      'extraction_precision':None,'extraction_recall':None,'extraction_f1':None,'aspect_sentiment_macro_f1':None,
      'supervised_model_trained':False,'reason':'No independently licensed genuine aspect/sentiment annotations available locally; coverage counts are not quality metrics'}
