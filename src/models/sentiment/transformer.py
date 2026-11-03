"""Bounded, seeded Hugging Face/PyTorch fine-tuning; checkpoints stay local."""
from pathlib import Path
import math
import random
import time
import numpy as np
import torch
from torch.utils.data import Dataset,DataLoader
from transformers import AutoTokenizer,AutoModelForSequenceClassification,get_linear_schedule_with_warmup
from src.training.data import LABELS,sample_rows
from src.evaluation.metrics import metrics

class Reviews(Dataset):
    def __init__(self,frame,tokenizer,max_length):
        self.encodings=tokenizer(frame['cleaned_text'].tolist(),padding='max_length',truncation=True,max_length=max_length,return_tensors='pt')
        self.labels=torch.tensor(frame['label_id'].to_numpy(),dtype=torch.long)
    def __len__(self):
        return len(self.labels)
    def __getitem__(self,index):
        return {k:v[index] for k,v in self.encodings.items()} | {'labels':self.labels[index]}

def device_for(requested='auto'):
    if requested=='auto':
        return torch.device('cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu')
    if requested=='cuda' and not torch.cuda.is_available():
        raise ValueError('CUDA requested but unavailable; use auto or cpu')
    if requested=='mps' and not torch.backends.mps.is_available():
        raise ValueError('MPS requested but unavailable; use auto or cpu')
    return torch.device(requested)

def synchronize(device):
    if device.type=='mps':torch.mps.synchronize()
    elif device.type=='cuda':torch.cuda.synchronize()

def predict(model,tokenizer,texts,device,max_length,batch_size=32):
    if not texts:
        return np.empty((0,3),dtype=float)
    model.eval();pieces=[]
    with torch.inference_mode():
        for start in range(0,len(texts),batch_size):
            encoded=tokenizer(texts[start:start+batch_size],padding=True,truncation=True,max_length=max_length,return_tensors='pt').to(device)
            pieces.append(torch.softmax(model(**encoded).logits,dim=-1).cpu().numpy())
    return np.concatenate(pieces)

def train_transformer(train,validation,config,root,directory,smoke=False):
    t=config['transformer'];seed=config['seed']
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.set_num_threads(t['threads'])
    torch.use_deterministic_algorithms(True,warn_only=True)
    device=device_for(t['device'])
    if t['mixed_precision'] and device.type!='cuda':
        raise ValueError('Mixed precision enabled only on supported CUDA hardware; disable for MPS/CPU')
    train=sample_rows(train,t['max_train_reviews'],seed)
    validation=sample_rows(validation,t['max_validation_reviews'],seed)
    source=Path(root)/t['pretrained_path']
    tokenizer=AutoTokenizer.from_pretrained(source,local_files_only=True)
    model=AutoModelForSequenceClassification.from_pretrained(source,num_labels=3,
        id2label=dict(enumerate(LABELS)),label2id={k:i for i,k in enumerate(LABELS)},local_files_only=True).to(device)
    dataset=Reviews(train,tokenizer,t['max_length'])
    generator=torch.Generator().manual_seed(seed)
    loader=DataLoader(dataset,batch_size=t['batch_size'],shuffle=True,generator=generator,num_workers=0)
    vloader=DataLoader(Reviews(validation,tokenizer,t['max_length']),batch_size=t['batch_size'],num_workers=0)
    weights=None
    if t['class_weight']=='balanced':
        class_counts=np.bincount(train['label_id'],minlength=3)
        if (class_counts==0).any():raise ValueError('Training requires all three weak classes')
        weights=torch.tensor(len(train)/(3*class_counts),dtype=torch.float32,device=device)
    criterion=torch.nn.CrossEntropyLoss(weight=weights)
    optimizer=torch.optim.AdamW(model.parameters(),lr=t['learning_rate'],weight_decay=t['weight_decay'])
    epochs=1 if smoke else t['epochs']
    updates_per_epoch=math.ceil(len(loader)/t['gradient_accumulation'])
    total_steps=updates_per_epoch*epochs
    scheduler=get_linear_schedule_with_warmup(optimizer,int(total_steps*t['warmup_fraction']),total_steps)
    scaler=torch.amp.GradScaler('cuda',enabled=t['mixed_precision'])
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    best=-1.;stale=0;history=[];started=time.perf_counter();reason='configured_epochs_completed'
    for epoch in range(epochs):
        model.train();optimizer.zero_grad();loss_sum=0.;seen=0
        for batch_index,batch in enumerate(loader):
            batch={k:v.to(device) for k,v in batch.items()};labels=batch.pop('labels')
            with torch.autocast(device_type='cuda',enabled=t['mixed_precision']):
                loss=criterion(model(**batch).logits,labels)
            # Normalize the final partial accumulation group by its actual batch count.
            group_start=(batch_index//t['gradient_accumulation'])*t['gradient_accumulation']
            divisor=min(t['gradient_accumulation'],len(loader)-group_start)
            scaler.scale(loss/divisor).backward()
            loss_sum+=float(loss.detach().cpu())*len(labels);seen+=len(labels)
            if (batch_index+1)%t['gradient_accumulation']==0 or batch_index+1==len(loader):
                scaler.unscale_(optimizer);torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
                scaler.step(optimizer);scaler.update();scheduler.step();optimizer.zero_grad()
            if batch_index%100==0:
                print('transformer epoch',epoch+1,'batch',batch_index+1,'/',len(loader),flush=True)
        model.eval();val_sum=0.;val_seen=0;ys=[];pred=[]
        with torch.inference_mode():
            for batch in vloader:
                batch={k:v.to(device) for k,v in batch.items()};labels=batch.pop('labels')
                logits=model(**batch).logits
                val_sum+=float(criterion(logits,labels).cpu())*len(labels);val_seen+=len(labels)
                ys.extend(labels.cpu().tolist());pred.extend(logits.argmax(-1).cpu().tolist())
        score=metrics(ys,pred)
        record={'epoch':epoch+1,'training_weighted_cross_entropy':loss_sum/seen,
          'validation_weighted_cross_entropy':val_sum/val_seen,'validation':score,
          'elapsed_seconds':time.perf_counter()-started}
        history.append(record)
        print('transformer epoch',epoch+1,'validation macro F1',round(score['macro_f1'],4),flush=True)
        if score['macro_f1']>best:
            best=score['macro_f1'];best_epoch=epoch+1;best_validation=score;stale=0
            model.save_pretrained(directory);tokenizer.save_pretrained(directory)
        else:stale+=1
        if stale>=t['patience']:
            reason='early_stopping_validation_macro_f1';break
        if time.perf_counter()-started>t['max_seconds']:
            reason='resource_budget_reached_after_complete_epoch';break
    synchronize(device)
    duration=time.perf_counter()-started
    model=AutoModelForSequenceClassification.from_pretrained(directory,local_files_only=True).to(device)
    info={'trained':True,'architecture':t['model_name'],'parameters':t,'device':str(device),
      'training_reviews':len(train),'validation_reviews':len(validation),'seed':seed,'epochs_completed':len(history),
      'best_epoch':best_epoch,'stop_reason':reason,'history':history,'validation':best_validation,
      'training_seconds':duration,'artifact_path':str(directory),'artifact_bytes':sum(p.stat().st_size for p in directory.rglob('*') if p.is_file()),
      'parameter_count':sum(p.numel() for p in model.parameters()),
      'scope':'Pretrained English compact BERT, weak-label resource-bounded pilot; not a multilingual or DistilBERT experiment',
      'confidence_semantics':'uncalibrated softmax scores; not calibrated confidence'}
    return (model,tokenizer,device),info
