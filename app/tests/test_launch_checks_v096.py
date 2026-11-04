"""Deploy-time preflight and safe hosted smoke checks."""
from __future__ import annotations

from io import BytesIO
import zipfile

import httpx
import pytest

from app import auth, main
from scripts.audit_public_release import audit
from scripts.check_production import check_config
from scripts.smoke_hosted import _origin, run


def test_render_external_url_is_used_without_trusting_browser_host(monkeypatch):
    monkeypatch.delenv('APP_BASE_URL',raising=False)
    monkeypatch.setenv('RENDER_EXTERNAL_URL','https://repoworld-demo.onrender.com')
    assert auth.base_url()=='https://repoworld-demo.onrender.com'
    rows=check_config({'RENDER_EXTERNAL_URL':'https://repoworld-demo.onrender.com',
                       'APP_ENV':'production','BHARATCODE_API_KEY':'test-not-secret',
                       'REPOWORLD_DB_PATH':'/var/data/repoworld.sqlite3',
                       'REPOWORLD_REQUIRE_MOUNTED_DB':'1'})
    assert all(ok for _,ok,_ in rows)
    monkeypatch.setenv('APP_BASE_URL','https://custom.example')
    assert auth.base_url()=='https://custom.example'


@pytest.mark.asyncio
async def test_readiness_requires_mounted_disk_when_enabled(monkeypatch,tmp_path):
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.setenv('APP_BASE_URL','https://repo.example')
    monkeypatch.setenv('BHARATCODE_API_KEY','test-private-key')
    monkeypatch.setenv('REPOWORLD_DB_PATH',str(tmp_path/'state.sqlite3'))
    monkeypatch.setenv('REPOWORLD_REQUIRE_MOUNTED_DB','1')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='https://repo.example') as client:
        monkeypatch.setattr(main.os.path,'ismount',lambda _:False)
        r=await client.get('/api/ready')
        assert r.status_code==503
        monkeypatch.setattr(main.os.path,'ismount',lambda _:True)
        r=await client.get('/api/ready')
        assert r.status_code==200
        assert r.json()['ready'] is True


def test_safe_smoke_script_checks_a_mocked_host_without_provider_calls():
    seen=[]
    def handler(req):
        seen.append((req.method,req.url.path))
        headers={'x-frame-options':'DENY','cache-control':'no-cache'}
        if req.url.path == '/api/health':return httpx.Response(200,json={'ok':True,'version':'0.9.6'})
        if req.url.path == '/api/ready':return httpx.Response(200,json={'ready':True})
        if req.url.path == '/':return httpx.Response(200,text='RepoWorld',headers=headers)
        if req.url.path == '/api/session':return httpx.Response(200,json={'guest':True,'csrf':'testcsrf'},headers={'set-cookie':'rw_session=example; HttpOnly; SameSite=Lax'})
        if req.url.path == '/api/repository':return httpx.Response(410)
        raise AssertionError('Unexpected provider or endpoint call: '+str(req.url))
    notes=run('http://127.0.0.1:8004',allow_local=True,transport=httpx.MockTransport(handler))
    assert any('No GitHub import' in note for note in notes)
    assert len(seen)==5
    with pytest.raises(ValueError):_origin('http://malicious.example',allow_local=True)


def test_release_archive_audit_rejects_secrets_and_invalid_paths(tmp_path):
    bad=tmp_path/'bad.zip'
    with zipfile.ZipFile(bad,'w') as f:
        f.writestr('RepoWorld/README.md','Safe')
        f.writestr('RepoWorld/BharatCode.txt','Safe')
        f.writestr('RepoWorld/render.yaml','Safe')
        f.writestr('RepoWorld/app/main.py','print(1)')
        f.writestr('RepoWorld/.env','BHARATCODE_API_KEY=do-not-publish')
    assert any('Private or generated file' in item for item in audit(str(bad)))
    good=tmp_path/'good.zip'
    with zipfile.ZipFile(good,'w') as f:
        for item in ('README.md','BharatCode.txt','render.yaml','app/main.py'):
            f.writestr('RepoWorld/'+item,'Safe')
    assert audit(str(good))==[]
