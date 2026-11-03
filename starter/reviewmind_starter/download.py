"""Download a bounded sample of Amazon Reviews 2023 review records.
Run after installing requirements. Requires internet. Not India-specific.
"""
import argparse, csv, json, pathlib
from huggingface_hub import HfFileSystem
import pyarrow.parquet as pq
import fsspec

p=argparse.ArgumentParser()
p.add_argument('--per-category',type=int,default=2000)
p.add_argument('--out',default='data')
a=p.parse_args()
root=pathlib.Path(a.out);root.mkdir(parents=True,exist_ok=True)
repo='datasets/McAuley-Lab/Amazon-Reviews-2023'
fs=HfFileSystem()
categories=['Electronics','Cell_Phones_and_Accessories','Computers','Video_Games','Office_Products']
fields=['source','category','parent_asin','rating','title','text','timestamp','verified_purchase','helpful_vote']
for cat in categories:
    try:
        files=sorted(fs.glob(f'{repo}/raw_review_{cat}/*.parquet'))
        if not files:
            print(f'SKIP {cat}: no files found');continue
        target=root/f'{cat}.csv'; count=0
        with target.open('w',newline='',encoding='utf-8') as dest:
            writer=csv.DictWriter(dest,fieldnames=fields);writer.writeheader()
            for file in files:
                with fs.open(file,'rb') as source:
                    parquet=pq.ParquetFile(source)
                    for batch in parquet.iter_batches(batch_size=512):
                        for record in batch.to_pylist():
                            body=str(record.get('text') or '').strip()
                            if len(body)<20:continue
                            row={'source':'Amazon Reviews 2023 (McAuley Lab)','category':cat,'parent_asin':record.get('parent_asin'),'rating':record.get('rating'),'title':record.get('title'),'text':body,'timestamp':record.get('timestamp'),'verified_purchase':record.get('verified_purchase'),'helpful_vote':record.get('helpful_vote')}
                            writer.writerow(row);count+=1
                            if count>=a.per_category:break
                        if count>=a.per_category:break
                if count>=a.per_category:break
        print(f'{cat}: {count} reviews -> {target}')
    except Exception as exc:
        print(f'FAILED {cat}: {type(exc).__name__}: {exc}')
print('Finished. Verify license and use conditions before training or redistributing.')
