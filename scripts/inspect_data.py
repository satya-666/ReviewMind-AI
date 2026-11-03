"""Inspect local ZIP/CSV/JSON/JSONL/Parquet files without modifying originals."""
import json
from pathlib import Path
import zipfile
import pandas as pd
from download import ROOT

def inspect():
    inventory = []
    for path in sorted((ROOT/'data/raw').rglob('*')):
        if not path.is_file() or path.name.startswith('.'):
            continue
        item = {'path':str(path.relative_to(ROOT)), 'bytes':path.stat().st_size}
        if path.suffix == '.zip':
            with zipfile.ZipFile(path) as archive:
                item['members'] = []
                for name in archive.namelist():
                    member = {'name':name}
                    if name.endswith('.csv'):
                        frame = pd.read_csv(archive.open(name), dtype=str, keep_default_na=False)
                        member.update(rows=len(frame), columns=list(frame.columns))
                    item['members'].append(member)
        elif path.suffix in {'.csv','.json','.jsonl','.parquet'}:
            if path.suffix == '.csv':
                frame = pd.read_csv(path)
            elif path.suffix == '.parquet':
                frame = pd.read_parquet(path)
            else:
                frame = pd.read_json(path, lines=path.suffix == '.jsonl')
            item.update(rows=len(frame), columns=list(frame.columns))
        inventory.append(item)
    (ROOT/'reports/raw_inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
    return inventory

if __name__ == '__main__':
    print(json.dumps(inspect(), indent=2))
