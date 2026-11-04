"""v0.9.3: local browser-origin aliases cannot break imports; CSRF stays mandatory."""
import httpx
import pytest

from app import main
from app.demo import build_demo

@pytest.fixture(autouse=True)
def isolate(monkeypatch,tmp_path):
    monkeypatch.setenv('REPOWORLD_DB_PATH',str(tmp_path/'origin-v093.sqlite3'))
    monkeypatch.setenv('APP_ENV','development')
    monkeypatch.setenv('APP_BASE_URL','http://127.0.0.1:8004')
    monkeypatch.delenv('REPOWORLD_ENFORCE_BUDGETS',raising=False)
    main._request_times.clear()

@pytest.mark.asyncio
@pytest.mark.parametrize('host,origin',[
    ('127.0.0.1:8004','http://localhost:8004'),
    ('localhost:8004','http://127.0.0.1:8004'),
    ('localhost:8004','http://localhost:8004'),
    ('127.0.0.1:8004','http://127.0.0.1:8004'),
])
async def test_local_loopback_aliases_allow_import(monkeypatch,host,origin):
    async def fake_graph(url,*,refresh=False):
        graph=build_demo()
        graph.update(owner='openwisp',name='openwisp-utils',source='github')
        return graph
    monkeypatch.setattr(main,'get_repository_graph',fake_graph)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://'+host) as client:
        session=(await client.get('/api/session')).json()
        response=await client.post('/api/my-repos',json={'url':'openwisp/openwisp-utils'},headers={
            'Origin':origin,'X-RepoWorld-CSRF':session['csrf']})
        assert response.status_code==200,response.text
        assert response.json()['graph']['name']=='openwisp-utils'

@pytest.mark.asyncio
@pytest.mark.parametrize('host,origin',[
    ('127.0.0.1:8004','http://localhost:8005'),
    ('localhost:8004','http://127.0.0.1:8005'),
    ('127.0.0.1:8004','https://localhost:8004'),
    ('127.0.0.1:8004','http://host.local:8004'),
    ('not-local.invalid:8004','http://localhost:8004'),
    ('not-local.invalid:8004','http://127.0.0.1:8004'),
    ('localhost:8005','http://127.0.0.1:8004'),
    ('127.0.0.1:8004','null'),
])
async def test_invalid_origins_cannot_mutate(host,origin):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://'+host) as client:
        session=(await client.get('/api/session')).json()
        resp=await client.post('/api/tour',json={'graph':build_demo()},headers={
            'Origin':origin,'X-RepoWorld-CSRF':session['csrf']})
        assert resp.status_code==403

@pytest.mark.asyncio
async def test_local_alias_still_requires_csrf():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://127.0.0.1:8004') as client:
        await client.get('/api/session')
        response=await client.post('/api/tour',json={'graph':build_demo()},headers={'Origin':'http://localhost:8004'})
        assert response.status_code==403
        assert 'verification' in response.json()['detail'].lower()

@pytest.mark.asyncio
async def test_production_remains_exact_origin(monkeypatch):
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.setenv('APP_BASE_URL','https://repoworld.example')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='https://repoworld.example') as client:
        session=(await client.get('/api/session')).json()
        headers={'X-RepoWorld-CSRF':session['csrf']}
        assert (await client.post('/api/tour',json={'graph':build_demo()},headers={**headers,'Origin':'http://localhost:8004'})).status_code==403
        assert (await client.post('/api/tour',json={'graph':build_demo()},headers={**headers,'Origin':'https://repoworld.example'})).status_code==200
