"""Load real local checkpoints; confidence semantics differ by estimator."""
import json
from pathlib import Path
import joblib
import numpy as np
from scripts.clean_data import clean_text,usable
from src.training.data import LABELS
from src.models.aspects.rules import aspects

class ReviewPredictor:
    def __init__(self,path,kind=None,device='cpu',max_length=96):
        self.path=Path(path);self.kind=kind or ('transformer' if self.path.is_dir() else 'baseline')
        self.version=self.path.name
        self.max_length=max_length
        if self.kind=='baseline':self.model=joblib.load(path)
        else:
            from transformers import AutoModelForSequenceClassification,AutoTokenizer
            from src.models.sentiment.transformer import device_for
            self.device=device_for(device)
            self.model=AutoModelForSequenceClassification.from_pretrained(path,local_files_only=True).to(self.device)
            self.tokenizer=AutoTokenizer.from_pretrained(path,local_files_only=True)
        metadata=self.path/'reviewmind_metadata.json' if self.path.is_dir() else self.path.with_suffix('.metadata.json')
        if metadata.exists():
            info=json.loads(metadata.read_text());self.version=info.get('version',self.version);self.max_length=info.get('max_length',self.max_length)

    def batch(self,texts,category=None):
        if not isinstance(texts,list):raise ValueError('Batch must be a list of strings')
        cleaned=[]
        for text in texts:
            if not isinstance(text,str) or not usable(clean_text(text)):
                raise ValueError('Each review must be a nonempty usable string')
            cleaned.append(clean_text(text))
        if not cleaned:return []
        if self.kind=='transformer':
            from src.models.sentiment.transformer import predict
            scores=predict(self.model,self.tokenizer,cleaned,self.device,self.max_length)
            ids=scores.argmax(1);confidence=scores.max(1);semantics='uncalibrated_softmax'
        else:
            ids=self.model.predict(cleaned)
            if hasattr(self.model,'predict_proba'):
                scores=self.model.predict_proba(cleaned);confidence=scores.max(1);semantics='uncalibrated_probability'
            else:
                scores=self.model.decision_function(cleaned);confidence=[None]*len(cleaned);semantics='decision_margins_not_probabilities'
        return [{'sentiment':LABELS[int(label)],'confidence':float(confidence[i]) if confidence[i] is not None else None,
          'scores':{name:float(scores[i,j]) for j,name in enumerate(LABELS)},'confidence_semantics':semantics,
          'model_version':self.version,'label_training_basis':'rating-derived weak supervision',
          'aspects':aspects(texts[i],category) if category else []} for i,label in enumerate(ids)]

    def single(self,text,category=None):
        return self.batch([text],category)[0]
