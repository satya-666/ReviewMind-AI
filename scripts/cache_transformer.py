"""Download only the small authorized pretrained encoder; record immutable provenance."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import yaml

def cache(config):
    import requests
    from huggingface_hub import snapshot_download
    t=config['transformer'];name=t['model_name']
    response=requests.get('https://huggingface.co/api/models/'+name+'/revision/'+t['revision'],timeout=60)
    response.raise_for_status();meta=response.json()
    if meta.get('cardData',{}).get('license')!='apache-2.0':
        raise ValueError('Verify pretrained model licensing before download')
    revision=meta['sha']
    path=ROOT/t['pretrained_path']
    snapshot_download(name,revision=revision,local_dir=path,
      allow_patterns=['config.json','vocab.txt','tokenizer.json','tokenizer_config.json','special_tokens_map.json','model.safetensors','pytorch_model.bin','README.md','LICENSE'],
      cache_dir=ROOT/'.cache/huggingface')
    record={'model':name,'revision':revision,'license':'apache-2.0','source_url':'https://huggingface.co/'+name,
            'local_path':t['pretrained_path'],'scope':'Pretrained English-only compact encoder; classification head must be trained'}
    (ROOT/'reports/phase3_transformer_source.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))

if __name__=='__main__':
    cache(yaml.safe_load((ROOT/'configs/phase3_config.yaml').read_text()))
