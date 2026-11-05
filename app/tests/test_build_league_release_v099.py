"""Build League source gate and explicitly authorized real-model smoke checks."""
from __future__ import annotations

from pathlib import Path
import shutil

import httpx
import pytest

from app import main
from scripts.check_build_league import REQUIRED, check_repo
from scripts.smoke_hosted import run


def test_build_league_source_gate_and_missing_manifest(tmp_path):
    root=Path(__file__).resolve().parents[2]
    assert check_repo(root)==[]
    for path in REQUIRED:
        output=tmp_path/path
        output.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(root/path,output)
    assert check_repo(tmp_path)==[]
    (tmp_path/'BharatCode.txt').unlink()
    assert any('BharatCode.txt' in problem for problem in check_repo(tmp_path))


def hosted_transport(*,model_mode='ai',evidence=True,configured=True,
                     issue_response=200,issue_error='GitHub issue API rate limit reached.'):
    requests=[]
    def handler(req):
        requests.append((req.method,req.url.path))
        path=req.url.path
        if path=='/api/health':
            return httpx.Response(200,json={'ok':True,'version':main.app.version})
        if path=='/api/ready':
            return httpx.Response(200,json={'ready':True})
        if path=='/api/ready.svg':
            return httpx.Response(200,text='<svg/>',headers={'content-type':'image/svg+xml','cache-control':'no-store'})
        if path=='/':
            return httpx.Response(200,text='RepoWorld',headers={'x-frame-options':'DENY','cache-control':'no-cache'})
        if path=='/static/browser-radar.js':
            return httpx.Response(200,text='window.RepoWorldBrowserIssueRadar=true;')
        if path=='/api/session':
            return httpx.Response(200,json={'guest':True,'csrf':'example-csrf','aiConfigured':configured},
                                  headers={'set-cookie':'rw_session=example; HttpOnly; SameSite=Lax'})
        if path=='/api/status':
            return httpx.Response(200,json={'aiConfigured':configured})
        if path=='/api/repository':
            return httpx.Response(410)
        if path=='/api/my-repos' and req.method=='POST':
            assert req.headers.get('x-repoworld-csrf')=='example-csrf'
            return httpx.Response(200,json={'id':'test-city','graph':{'nodes':[{'id':'src'}]}})
        if path=='/api/my-repos/test-city/issues':
            return (httpx.Response(issue_response,json={'issues':[]})
                    if issue_response==200 else httpx.Response(issue_response,json={'error':issue_error}))
        if path=='/api/my-repos/test-city/assistant' and req.method=='POST':
            assert req.headers.get('x-repoworld-csrf')=='example-csrf'
            return httpx.Response(200,json={'mode':model_mode,'model':'qwen-3.8-27b' if model_mode=='ai' else None,
                     'answer':'Inspect the app module.','sourceFilesRead':int(evidence),
                     'sources':[{'file':'src/main.py','evidence':'excerpt'}] if evidence else []})
        raise AssertionError('Unexpected provider endpoint: '+path)
    return httpx.MockTransport(handler),requests


def test_hosted_live_ai_smoke_requires_explicit_opt_in_and_checks_source_evidence():
    transport,calls=hosted_transport()
    notes=run('http://127.0.0.1:8004',import_repo='pallets/flask',
              allow_local=True,transport=transport,verify_live_ai=True,
              require_source_evidence=True)
    assert any('real model response' in note for note in notes)
    assert any('inspected public source' in note for note in notes)
    assert sum(path.endswith('/assistant') for _,path in calls)==1
    assert sum(path=='/api/my-repos' for _,path in calls)==1
    assert all(not path.startswith('https://bharatcode.ai') for _,path in calls)


def test_hosted_smoke_refuses_fake_ai_fallback_and_weak_source_proof():
    transport,_=hosted_transport(model_mode='navigation')
    with pytest.raises(RuntimeError,match='real model response'):
        run('http://127.0.0.1:8004',import_repo='pallets/flask',
            allow_local=True,transport=transport,verify_live_ai=True)
    transport,_=hosted_transport(evidence=False)
    with pytest.raises(RuntimeError,match='source evidence'):
        run('http://127.0.0.1:8004',import_repo='pallets/flask',allow_local=True,
            transport=transport,verify_live_ai=True,require_source_evidence=True)
    with pytest.raises(ValueError,match='require --import-repo'):
        run('http://127.0.0.1:8004',allow_local=True,verify_live_ai=True)


def test_provider_specific_issue_429_does_not_block_explicit_ai_smoke():
    transport,calls=hosted_transport(issue_response=429)
    with pytest.raises(RuntimeError,match='GitHub Issue Radar'):
        run('http://127.0.0.1:8004',import_repo='pallets/flask',
            allow_local=True,transport=transport,verify_live_ai=True)
    transport,calls=hosted_transport(issue_response=429)
    notes=run('http://127.0.0.1:8004',import_repo='pallets/flask',allow_local=True,
              transport=transport,verify_live_ai=True,require_source_evidence=True,
              allow_browser_issues_fallback=True)
    assert any('provider-rate-limited' in x for x in notes)
    assert any('real model response' in x for x in notes)
    assert sum(p.endswith('/assistant') for _,p in calls)==1


def test_guest_quota_429_is_never_ignored_by_provider_fallback_flag():
    transport,calls=hosted_transport(issue_response=429,issue_error='Too many requests. Try again shortly.')
    with pytest.raises(RuntimeError,match='Only GitHub provider'):
        run('http://127.0.0.1:8004',import_repo='pallets/flask',allow_local=True,
            transport=transport,verify_live_ai=True,allow_browser_issues_fallback=True)
    assert not any(path.endswith('/assistant') for _,path in calls)
