"""Regression tests for failed public GitHub imports in the v0.9 release."""
from __future__ import annotations

import base64
import json
import time

import httpx
import pytest

from app import github, main


def _metadata(*, private=False, branch='main'):
    return {'name': 'demo', 'owner': {'login': 'public'}, 'private': private,
            'default_branch': branch, 'stargazers_count': 12, 'language': 'Python'}


def _tree(n=24, *, extension='py'):
    return {'truncated': False, 'tree': [
        {'path': f'package{index%8}/module{index}.{extension}', 'type': 'blob',
         'size': 24, 'sha': f'{index+1:040x}'}
        for index in range(n)
    ]}


@pytest.mark.asyncio
async def test_public_import_caps_source_requests_without_a_token(monkeypatch):
    monkeypatch.delenv('GITHUB_TOKEN', raising=False)
    monkeypatch.delenv('REPOWORLD_IMPORT_SOURCE_LIMIT', raising=False)
    calls=[]
    def handler(req):
        calls.append(req.url.path)
        path=req.url.path
        if path=='/repos/public/demo':
            return httpx.Response(200,json=_metadata())
        if path.endswith('/git/trees/main'):
            return httpx.Response(200,json=_tree(48))
        if '/git/blobs/' in path:
            return httpx.Response(200,json={'encoding':'base64',
                              'content':base64.b64encode(b'def hello():\n  pass\n').decode()})
        return httpx.Response(404)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        graph=await github.get_repository_graph('public/demo',client)
    assert len(calls)==2+github.DEFAULT_PUBLIC_SOURCE_LIMIT
    assert graph['source']=='github' and graph['stats']['files']==48
    assert graph['stats']['inspectedSources']==github.DEFAULT_PUBLIC_SOURCE_LIMIT
    assert len({x['source'] for x in graph.get('edges',[])})<=8
    assert 'small source sample' in ' '.join(graph['warnings']).lower()


@pytest.mark.asyncio
async def test_metadata_rate_limit_communicates_retry_after(monkeypatch):
    monkeypatch.delenv('GITHUB_TOKEN', raising=False)
    reset=str(int(time.time())+91)
    def handler(req):
        return httpx.Response(403,headers={'X-RateLimit-Remaining':'0',
                         'X-RateLimit-Reset':reset},json={'message':'API rate limit exceeded'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(github.RepoError) as exc:
            await github.get_repository_graph('public/demo',client)
    assert exc.value.status==429
    assert 1<=exc.value.retry_after<=91
    assert 'rate limit' in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_secondary_limit_propagates_retry_after():
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda req:httpx.Response(429,headers={'Retry-After':'44'}))) as client:
        with pytest.raises(github.RepoError) as exc:
            await github.get_repository_graph('public/demo',client)
    assert exc.value.status==429 and exc.value.retry_after==44


@pytest.mark.asyncio
async def test_github_token_failure_is_not_misreported_as_rate_limit(monkeypatch):
    monkeypatch.setenv('GITHUB_TOKEN','fake-secret-never-print')
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda req:httpx.Response(401,json={'message':'Bad credentials'}))) as client:
        with pytest.raises(github.RepoError) as exc:
            await github.get_repository_graph('public/demo',client)
    assert exc.value.status==502
    assert 'GITHUB_TOKEN' in exc.value.detail
    assert 'fake-secret' not in exc.value.detail


@pytest.mark.asyncio
async def test_ordinary_permission_denial_not_wrongly_called_rate_limit():
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda req:httpx.Response(403,json={'message':'Resource not accessible by integration'}))) as client:
        with pytest.raises(github.RepoError) as exc:
            await github.get_repository_graph('public/demo',client)
    assert exc.value.status==403


@pytest.mark.asyncio
async def test_source_blob_failures_keep_usable_partial_graph(monkeypatch):
    monkeypatch.delenv('GITHUB_TOKEN', raising=False)
    def handler(req):
        path=req.url.path
        if path=='/repos/public/demo':return httpx.Response(200,json=_metadata())
        if path.endswith('/git/trees/main'):return httpx.Response(200,json=_tree(3))
        if '/git/blobs/' in path:return httpx.Response(503)
        return httpx.Response(404)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        graph=await github.get_repository_graph('public/demo',client)
    assert graph['stats']['files']==3 and graph['stats']['inspectedSources']==0
    assert len(graph['nodes'])>=1
    assert 'only 0 of 3' in ' '.join(graph['warnings']).lower()


@pytest.mark.asyncio
async def test_docs_only_repository_does_not_crash_on_empty_source_sample(monkeypatch):
    monkeypatch.delenv('GITHUB_TOKEN',raising=False)
    def handler(req):
        if req.url.path=='/repos/public/demo':return httpx.Response(200,json=_metadata())
        if '/git/trees/' in req.url.path:
            return httpx.Response(200,json={'tree':[{'path':'README.md','type':'blob','size':70,'sha':'f'*40}]})
        raise AssertionError('No source blob should be requested for a Markdown-only repo')
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        graph=await github.get_repository_graph('public/demo',client)
    assert graph['stats']['files']==1 and graph['nodes']
    assert graph['stats']['inspectedSources']==0


@pytest.mark.asyncio
async def test_empty_repository_gets_human_readable_error():
    def handler(req):
        if req.url.path=='/repos/public/demo':return httpx.Response(200,json=_metadata())
        return httpx.Response(200,json={'tree':[], 'truncated':False})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(github.RepoError) as exc:
            await github.get_repository_graph('public/demo',client)
    assert exc.value.status==422
    assert 'no files' in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_tree_timeout_gives_actionable_error():
    def handler(req):
        if req.url.path=='/repos/public/demo':return httpx.Response(200,json=_metadata())
        raise httpx.ReadTimeout('read timeout')
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(github.RepoError) as exc:
            await github.get_repository_graph('public/demo',client)
    assert exc.value.status==504 and 'too long' in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_import_api_surfaces_rate_limit_as_json_and_retry_after(monkeypatch,tmp_path):
    monkeypatch.setenv('REPOWORLD_DB_PATH',str(tmp_path/'session.sqlite3'))
    monkeypatch.setenv('APP_BASE_URL','http://127.0.0.1:8004')
    monkeypatch.setenv('APP_ENV','development')
    monkeypatch.delenv('REPOWORLD_ENFORCE_BUDGETS',raising=False)
    async def fake_get(url, *, refresh=False):
        raise github.RepoError('GitHub API rate limit reached. Retry later.',429,retry_after=91)
    monkeypatch.setattr(main,'get_repository_graph',fake_get)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://127.0.0.1:8004') as client:
        session=(await client.get('/api/session')).json()
        r=await client.post('/api/my-repos',json={'url':'public/demo'},headers={'X-RepoWorld-CSRF':session['csrf']})
        assert r.status_code==429 and r.headers['Retry-After']=='91'
        assert 'rate limit' in r.json()['error'].lower()
        assert (await client.get('/api/session')).json()['repositories']==[]


def test_large_tree_sampling_can_cover_multiple_districts():
    sample=github._source_sample(_tree(48)['tree'],6)
    assert len(sample)==6
    assert len({github.group_for_file(entry['path']) for entry in sample})==6


def test_free_demo_reduces_unauthenticated_sample_pressure_without_changing_token_default(monkeypatch):
    monkeypatch.setenv('REPOWORLD_EPHEMERAL_DEMO','1')
    monkeypatch.delenv('REPOWORLD_IMPORT_SOURCE_LIMIT',raising=False)
    assert github._source_limit(False)==2
    assert github._source_limit(True)==github.DEFAULT_AUTHENTICATED_SOURCE_LIMIT
    monkeypatch.setenv('REPOWORLD_IMPORT_SOURCE_LIMIT','4')
    assert github._source_limit(False)==4
    monkeypatch.delenv('REPOWORLD_EPHEMERAL_DEMO',raising=False)
    monkeypatch.delenv('REPOWORLD_IMPORT_SOURCE_LIMIT',raising=False)
    assert github._source_limit(False)==github.DEFAULT_PUBLIC_SOURCE_LIMIT
