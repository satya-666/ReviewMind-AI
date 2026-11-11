"""Verify the bundled trusted checkpoint without deserializing or downloading it."""
import hashlib,json,os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def verify():
    manifest=json.loads((ROOT/'backend/model_manifest.json').read_text())
    target=Path(os.getenv('MODEL_PATH',str(ROOT/'models/phase3/full/baseline/logistic_regression.joblib')))
    if not target.is_file():raise ValueError('Bundled serving model is missing; rebuild the image with the approved checkpoint')
    if hashlib.sha256(target.read_bytes()).hexdigest()!=manifest['checkpoint_sha256']:
        raise ValueError('Serving model checksum mismatch; refusing to load')
    metadata=json.loads(target.with_suffix('.metadata.json').read_text())
    if metadata['version']!=manifest['model_version']:
        raise ValueError('Serving model metadata version mismatch')
    print('Bundled serving model checksum and metadata verified.')

if __name__=='__main__':
    try:verify()
    except (OSError,ValueError,KeyError) as error:
        message=str(error) if isinstance(error,ValueError) and not isinstance(error,json.JSONDecodeError) else 'Bundled model metadata or artifact is missing or invalid'
        raise SystemExit('Serving model verification failed: '+message) from None
