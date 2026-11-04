"""Admin-only deployment bootstrap: private HTTPS checkpoint, mandatory pinned checksum."""
import hashlib,json,os,shutil,tempfile,urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]

def fetch():
    manifest=json.loads((ROOT/'backend/model_manifest.json').read_text())
    target=Path(os.getenv('MODEL_PATH',str(ROOT/'models/phase3/full/baseline/logistic_regression.joblib')))
    expected=manifest['checkpoint_sha256']
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest()!=expected:raise ValueError('Existing model checksum mismatch; refusing to load')
        if not target.with_suffix('.metadata.json').exists():
            shutil.copyfile(ROOT/'backend/model_metadata.json',target.with_suffix('.metadata.json'))
        return
    url=os.getenv('MODEL_ARTIFACT_URL','')
    if urlparse(url).scheme!='https':raise ValueError('Supply a private HTTPS MODEL_ARTIFACT_URL after deployment approval')
    target.parent.mkdir(parents=True,exist_ok=True)
    class HTTPSOnly(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            if urlparse(newurl).scheme!='https':raise ValueError('Refusing insecure model redirect')
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    opener=urllib.request.build_opener(HTTPSOnly())
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as destination:
            temporary=Path(destination.name);size=0;digest=hashlib.sha256()
            with opener.open(url,timeout=60) as source:
                while chunk:=source.read(65536):
                    size+=len(chunk)
                    if size>10000000:raise ValueError('Serving artifact exceeds 10 MB baseline limit')
                    digest.update(chunk);destination.write(chunk)
        if digest.hexdigest()!=expected:raise ValueError('Downloaded model checksum mismatch')
        temporary.replace(target)
        shutil.copyfile(ROOT/'backend/model_metadata.json',target.with_suffix('.metadata.json'))
    finally:
        if temporary:temporary.unlink(missing_ok=True)

if __name__=='__main__':
    try:fetch()
    except Exception as error:
        # Never print presigned URLs, credentials or provider exception bodies.
        raise SystemExit('Serving model bootstrap failed ('+type(error).__name__+'). Verify the private artifact configuration and pinned checksum.') from None
