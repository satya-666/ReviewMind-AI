"""Acquire the versioned public archive once; save checksums and license evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]

def download(config):
    source = config['source']
    raw = ROOT / source['archive']
    evidence = ROOT / 'reports/evidence'
    evidence.mkdir(parents=True, exist_ok=True)
    metadata_path = evidence / 'flipkart_metadata.json'
    if not metadata_path.exists():
        response = requests.get('https://www.kaggle.com/api/v1/datasets/view/' + source['dataset'], timeout=60)
        response.raise_for_status()
        response.json()
        metadata_path.write_bytes(response.content)
    metadata = json.loads(metadata_path.read_text())
    if metadata.get('licenseName') != 'Database: Open Database, Contents: Database Contents':
        raise ValueError('License changed or unverified: stop for manual review')
    url = ('https://www.kaggle.com/api/v1/datasets/download/' + source['dataset']
           + '?datasetVersionNumber=' + str(source['version']))
    reused = raw.exists()
    if not reused:
        raw.parent.mkdir(parents=True, exist_ok=True)
        temporary = raw.with_suffix('.partial')
        try:
            with requests.get(url, stream=True, timeout=(20,60)) as response:
                response.raise_for_status()
                with temporary.open('wb') as output:
                    size = 0
                    for chunk in response.iter_content(65536):
                        size += len(chunk)
                        if size > 100_000_000:
                            raise ValueError('Archive exceeds 100 MB safety bound')
                        output.write(chunk)
            with zipfile.ZipFile(temporary) as archive:
                assert source['member'] in archive.namelist()
                assert archive.testzip() is None
            temporary.rename(raw)
        finally:
            temporary.unlink(missing_ok=True)
    with zipfile.ZipFile(raw) as archive:
        assert source['member'] in archive.namelist()
        assert archive.testzip() is None
    sha = hashlib.sha256(raw.read_bytes()).hexdigest()
    manifest_path = ROOT / 'reports/download_manifest.json'
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text())
        if previous['sha256'] != sha:
            raise ValueError('Previously downloaded archive checksum changed')
    manifest = {'dataset':source['dataset'], 'version':source['version'], 'url':url,
                'access_date':config['access_date'], 'sha256':sha, 'bytes':raw.stat().st_size,
                'reused_existing_archive':reused, 'license':metadata['licenseName']}
    manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=str(ROOT/'configs/dataset_config.yaml'))
    args = parser.parse_args()
    download(yaml.safe_load(Path(args.config).read_text()))
