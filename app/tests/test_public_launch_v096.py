"""Public launch regressions: streaming body caps, proxy-safe visitors and headers."""
from __future__ import annotations

import httpx
import pytest

from app import main
from app.demo import build_demo


@pytest.mark.asyncio
async def test_chunked_oversized_body_is_refused_before_json_parsing(monkeypatch):
    async def chunks():
        for _ in range(4):
            yield b'!' * 45_000
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app), base_url='http://127.0.0.1:8004'
    ) as client:
        r = await client.post('/api/tour', content=chunks(), headers={'content-type':'application/json'})
        assert r.status_code == 413
        assert r.json() == {'error':'Request body is too large.'}


@pytest.mark.asyncio
async def test_assistant_body_is_bounded_without_content_length():
    async def chunks():
        yield b'{' + b'x' * 19_000
        yield b'}'
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app), base_url='http://127.0.0.1:8004'
    ) as client:
        response = await client.post('/api/my-repos/fake/assistant', content=chunks())
        assert response.status_code == 413


@pytest.mark.asyncio
async def test_proxy_sharing_client_ip_does_not_exhaust_other_guest(monkeypatch, tmp_path):
    monkeypatch.setenv('REPOWORLD_DB_PATH',str(tmp_path/'guest.sqlite3'))
    monkeypatch.setenv('APP_BASE_URL','http://127.0.0.1:8004')
    monkeypatch.setenv('APP_ENV','development')
    monkeypatch.delenv('BHARATCODE_API_KEY',raising=False)
    main._request_times.clear()
    graph=build_demo()
    graph.update(owner='owner',name='city',url='https://github.com/owner/city',source='github')
    async def fake_import(_url,*,refresh=False):
        return graph
    async def fake_guide(_graph,_question,*,node_id=None,issue=None,history=None):
        return {'mode':'navigation','answer':'Inspect the source.', 'steps':[],'sources':[]}
    monkeypatch.setattr(main,'get_repository_graph',fake_import)
    monkeypatch.setattr(main,'guide_question',fake_guide)
    transport=httpx.ASGITransport(app=main.app,client=('10.0.0.5',1234))
    async with (httpx.AsyncClient(transport=transport,base_url='http://127.0.0.1:8004') as a,
                httpx.AsyncClient(transport=transport,base_url='http://127.0.0.1:8004') as b):
        sessions=[(await c.get('/api/session')).json() for c in (a,b)]
        saved=[]
        for c,s in zip((a,b),sessions):
            r=await c.post('/api/my-repos',json={'url':'owner/city'},headers={'X-RepoWorld-CSRF':s['csrf']})
            assert r.status_code==200,r.text
            saved.append(r.json()['id'])
        async def ask(client, session, rid):
            return await client.post(f'/api/my-repos/{rid}/assistant', json={'question':'Where can I start?'},
                                     headers={'X-RepoWorld-CSRF':session['csrf']})
        for _ in range(8):
            assert (await ask(a,sessions[0],saved[0])).status_code==200
        assert (await ask(a,sessions[0],saved[0])).status_code==429
        # Same reverse proxy IP must not block an unrelated guest.
        assert (await ask(b,sessions[1],saved[1])).status_code==200
    main._request_times.clear()


@pytest.mark.asyncio
async def test_cache_and_security_headers_are_environment_scoped(monkeypatch,tmp_path):
    monkeypatch.setenv('APP_ENV','development')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                 base_url='http://127.0.0.1:8004') as client:
        for path in ('/','/static/app.js','/static/world.js','/static/styles.css'):
            response=await client.get(path)
            assert response.status_code==200
            assert response.headers['cache-control']=='no-cache'
        assert 'strict-transport-security' not in response.headers
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.setenv('APP_BASE_URL','https://repo.example.org')
    monkeypatch.setenv('REPOWORLD_DB_PATH',str(tmp_path/'state.db'))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                 base_url='https://repo.example.org') as client:
        response=await client.get('/')
        assert response.headers['strict-transport-security'].startswith('max-age=31536000')
        assert response.headers['x-frame-options']=='DENY'
