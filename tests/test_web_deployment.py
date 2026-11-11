"""Deployment trust boundaries can be checked without provisioning cloud services."""
import json,hashlib
from pathlib import Path
import pytest,yaml
from backend.app.settings import Settings,ROOT
from backend.app.model_service import ModelService

def test_production_settings_fail_closed():
    with pytest.raises(ValueError):Settings(environment='production').validate()
    with pytest.raises(ValueError):Settings(origins=['*']).validate()
    with pytest.raises(ValueError):Settings(api_base_url='https://user:secret@example.com').validate()
    with pytest.raises(ValueError):Settings(api_base_url='https://example.com/?key=secret').validate()
    validated=Settings(environment='production',database_url='postgresql://user:example@localhost/example',
      auto_create_db=False,hosts=['api.example.com'],origins=['https://ui.example.com']).validate()
    assert validated.environment=='production'

def test_pinned_model_manifest_matches_real_checkpoint():
    manifest=json.loads((ROOT/'backend/model_manifest.json').read_text())
    path=ROOT/'models/phase3/full/baseline/logistic_regression.joblib'
    assert hashlib.sha256(path.read_bytes()).hexdigest()==manifest['checkpoint_sha256']
    assert manifest['model_version']=='phase3-full-logistic_regression-seed42'

def test_corrupt_checkpoint_not_deserialized(tmp_path):
    bad=tmp_path/'model.joblib';bad.write_bytes(b'untrusted arbitrary bytes')
    service=ModelService(Settings(model_path=bad))
    assert service.predictor is None and service.error=='model_unavailable'

def test_blueprint_has_manual_deploy_and_private_postgres():
    config=yaml.safe_load((ROOT/'render.yaml').read_text())
    assert all(service['autoDeployTrigger']=='off' for service in config['services'])
    assert config['databases'][0]['ipAllowList']==[]
    assert config['databases'][0]['diskSizeGB']==1
    assert not config['databases'][0]['storageAutoscalingEnabled']
    api=config['services'][0]
    assert api['healthCheckPath']=='/api/health'
    assert not any(var['key']=='MODEL_ARTIFACT_URL' for var in api['envVars'])
    assert api['dockerContext']=='.' and api['dockerfilePath']=='./backend/Dockerfile'
    assert any(var['key']=='MODEL_PATH' and var.get('value')=='/app/runtime/model.joblib' for var in api['envVars'])

def test_bundled_verification_fails_on_missing_or_corrupt_model(tmp_path,monkeypatch):
    from scripts.verify_serving_model import verify
    monkeypatch.setenv('MODEL_PATH',str(tmp_path/'model.joblib'))
    with pytest.raises(ValueError,match='missing'):verify()
    assert not (tmp_path/'model.joblib').exists()
    (tmp_path/'model.joblib').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='checksum'):verify()

def test_bundled_model_bootstrap_and_real_inference(tmp_path,monkeypatch):
    import shutil
    from scripts.verify_serving_model import verify
    path=tmp_path/'model.joblib'
    shutil.copyfile(ROOT/'models/phase3/full/baseline/logistic_regression.joblib',path)
    shutil.copyfile(ROOT/'backend/model_metadata.json',path.with_suffix('.metadata.json'))
    monkeypatch.setenv('MODEL_PATH',str(path))
    monkeypatch.delenv('MODEL_ARTIFACT_URL',raising=False)
    verify()
    service=ModelService(Settings(model_path=path))
    assert service.predictor is not None
    result=service.analyze('The battery is excellent but the camera is poor.','smartphones')
    assert result['model_version']=='phase3-full-logistic_regression-seed42'
    assert result['sentiment'] in {'positive','neutral','negative'}
    path.with_suffix('.metadata.json').write_text('{"version":"wrong"}')
    with pytest.raises(ValueError,match='metadata version'):verify()
