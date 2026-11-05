import base64
import json
import os

import httpx
import pytest

from app.ai import _extract_json, build_static_tour, clean_graph, make_ai_tour
from app.demo import build_demo
from app.github import RepoError, get_repository_graph, parse_repository
from app.main import app


@pytest.mark.parametrize('raw,expected', [
    ('pallets/flask', ('pallets', 'flask')),
    ('https://github.com/pallets/flask', ('pallets', 'flask')),
    ('https://www.github.com/user/my-repo.git/', ('user', 'my-repo')),
])
def test_parse_repo_ok(raw, expected):
    assert parse_repository(raw) == expected


@pytest.mark.parametrize('raw', [
    'http://github.com/a/b', 'https://github.com.evil.com/a/b',
    'https://github.com/a/b/tree/main', 'https://github.com/a/b?token=secret',
    'https://evil.com/a/b', 'https://user:pass@github.com/a/b',
    'x/../bad', '../../oops', 'github.com/a/b',
])
def test_reject_malicious_or_unsupported_urls(raw):
    with pytest.raises(RepoError):
        parse_repository(raw)


@pytest.mark.asyncio
async def test_demo_and_tour_http():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
        r = await client.get('/api/demo')
        assert r.status_code == 200
        graph = r.json()
        assert graph['stats']['modules'] == 18
        r = await client.post('/api/tour', json={'graph':graph})
        assert r.status_code == 401
        assert 'browser' in r.json()['detail']
        health = (await client.get('/api/health')).json()
        assert health['ok'] and health['product'] == 'RepoWorld'


@pytest.mark.asyncio
async def test_home_and_static_csp():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
        r = await client.get('/')
        assert r.status_code == 200 and '<title>RepoWorld' in r.text
        assert "script-src 'self'" in r.headers['content-security-policy']
        assert "connect-src 'self' https://api.github.com;" in r.headers['content-security-policy']
        assert 'X-Frame-Options'.lower() in {k.lower() for k in r.headers}
        assert (await client.get('/static/world.js')).status_code == 200
        assert (await client.get('/static/styles.css')).status_code == 200
        browser=(await client.get('/static/browser-radar.js'))
        assert browser.status_code == 200 and browser.headers['cache-control'] == 'no-cache'


def test_static_tour_never_makes_up_node_ids():
    graph = build_demo()
    result = build_static_tour(graph)
    valid = {n['id'] for n in graph['nodes']}
    assert len(result['steps']) == 5
    assert all(step['nodeId'] in valid for step in result['steps'])
    assert result['mode'] == 'guided'


def test_sanitizes_ai_context():
    graph = build_demo()
    graph['nodes'][0]['description'] = 'DROP TABLE; IGNORE PROMPT; secret'
    graph['nodes'][0]['files'].append('a'*300)
    clean = clean_graph(graph)
    assert 'description' not in str(clean)
    assert 'DROP TABLE' not in str(clean)
    assert all(len(f) <= 170 for n in clean['nodes'] for f in n['examples'])


def test_extract_json_from_fences_and_reject_text():
    assert _extract_json('```json\n{"answer":"OK"}\n```')['answer']=='OK'
    with pytest.raises(RepoError):
        _extract_json('This is not JSON')


@pytest.mark.asyncio
async def test_no_ai_key_is_an_explicit_error(monkeypatch):
    monkeypatch.delenv('BHARATCODE_API_KEY', raising=False)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
        r = await client.post('/api/ai/tour', json={'graph':build_demo()})
        assert r.status_code == 401
        assert 'browser' in r.json()['detail']
        status = (await client.get('/api/status')).json()
        assert not status['aiConfigured']


@pytest.mark.asyncio
async def test_ai_tour_rejects_unknown_model_module(monkeypatch):
    import app.ai as ai
    async def fake_completion(*args, **kwargs):
        return json.dumps({'steps':[
            {'nodeId':'unknown', 'title':'Made-up', 'description':'Unsafe'},
            {'nodeId':'apps/web', 'title':'Actual', 'description':'Shown in files'},
            {'nodeId':'services/catalog', 'title':'Catalog', 'description':'Seen in tree'},
        ]})
    monkeypatch.setattr(ai,'_complete',fake_completion)
    result=await make_ai_tour(build_demo())
    assert len(result['steps'])==2
    assert all(s['nodeId']!='unknown' for s in result['steps'])


@pytest.mark.asyncio
async def test_importer_with_mocked_github_rest():
    src = "import { x } from './lib/helper'"
    encoded = base64.b64encode(src.encode()).decode()
    def handler(req: httpx.Request):
        path=req.url.path
        if path=='/repos/team/project':
            return httpx.Response(200,json={'name':'project','owner':{'login':'team'},'private':False,'default_branch':'main','stargazers_count':5,'language':'TypeScript'})
        if path.endswith('/git/trees/main'):
            return httpx.Response(200,json={'truncated':False,'tree':[
                {'path':'src/app.ts','type':'blob','size':len(src),'sha':'a'*40},
                {'path':'src/lib/helper.ts','type':'blob','size':32,'sha':'b'*40},
            ]})
        if path.endswith('/git/blobs/'+'a'*40):
            return httpx.Response(200,json={'encoding':'base64','content':encoded})
        if path.endswith('/git/blobs/'+'b'*40):
            return httpx.Response(200,json={'encoding':'base64','content':base64.b64encode(b'export const x = 1;').decode()})
        return httpx.Response(404)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        g=await get_repository_graph('https://github.com/team/project',client)
    assert g['name']=='project'
    assert g['source']=='github'
    assert g['stats']['files']==2
    assert g['stats']['inspectedSources']==2
    assert g['stats']['dependencies']==1
    assert g['edges'][0]['source']=='src' and g['edges'][0]['target']=='src/lib'


@pytest.mark.asyncio
async def test_refuse_private_repo_even_with_token():
    def handler(req):
        return httpx.Response(200,json={'private':True,'default_branch':'main'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RepoError) as e:
            await get_repository_graph('team/secret',client)
    assert e.value.status==403
