"""Free Render preview: HTTPS & CSRF remain secure without billing or a model key."""
import httpx
import pytest
from app import main
from scripts.check_production import check_config

FREE={
    'APP_ENV':'production',
    'RENDER_EXTERNAL_URL':'https://repoworld.onrender.com',
    'REPOWORLD_EPHEMERAL_DEMO':'1',
    'REPOWORLD_DB_PATH':'/tmp/repoworld.sqlite3',
    'REPOWORLD_REQUIRE_MOUNTED_DB':'0',
}


def test_free_render_configuration_is_explicit_and_safe(monkeypatch):
    rows=check_config(FREE)
    assert all(ok for _name,ok,_detail in rows), rows
    assert not all(ok for _name,ok,_detail in check_config({**FREE,'REPOWORLD_EPHEMERAL_DEMO':'0'}))
    assert not all(ok for _name,ok,_detail in check_config({**FREE,'REPOWORLD_DB_PATH':'./.data/state.db'}))


@pytest.mark.asyncio
async def test_free_demo_ready_without_secret_and_labeled_fallback(monkeypatch,tmp_path):
    for key,value in {**FREE,'REPOWORLD_DB_PATH':str(tmp_path/'preview.sqlite3')}.items():
        monkeypatch.setenv(key,value)
    monkeypatch.delenv('APP_BASE_URL',raising=False)
    monkeypatch.delenv('BHARATCODE_API_KEY',raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                 base_url='https://repoworld.onrender.com') as client:
        ready=await client.get('/api/ready')
        assert ready.status_code==200,ready.text
        assert ready.json()['ready'] is True
        image=await client.get('/api/ready.svg')
        assert image.status_code==200 and image.headers['content-type'].startswith('image/svg+xml')
        assert image.headers['cache-control']=='no-store'
        assert '<svg ' in image.text and '</svg>' in image.text
        session=await client.get('/api/session')
        assert session.status_code==200,session.text
        assert session.json()['aiConfigured'] is False
        assert 'secure' in session.headers.get('set-cookie','').lower()
        assert 'httponly' in session.headers.get('set-cookie','').lower()
        assert (await client.get('/api/health')).status_code==200


@pytest.mark.asyncio
async def test_free_demo_does_not_relax_origin_or_mount_guard(monkeypatch,tmp_path):
    for key,value in {**FREE,'REPOWORLD_DB_PATH':str(tmp_path/'preview.sqlite3')}.items():
        monkeypatch.setenv(key,value)
    monkeypatch.delenv('APP_BASE_URL',raising=False)
    monkeypatch.delenv('BHARATCODE_API_KEY',raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                 base_url='https://repoworld.onrender.com') as client:
        sess=(await client.get('/api/session')).json()
        denied=await client.post('/api/tour',json={'graph':{}},
            headers={'origin':'https://evil.example','X-RepoWorld-CSRF':sess['csrf']})
        assert denied.status_code==403
        monkeypatch.setenv('REPOWORLD_REQUIRE_MOUNTED_DB','1')
        assert (await client.get('/api/ready')).status_code==503
        blocked_image=await client.get('/api/ready.svg')
        assert blocked_image.status_code==503
        assert 'image/svg+xml' not in blocked_image.headers.get('content-type','')
        monkeypatch.setenv('REPOWORLD_REQUIRE_MOUNTED_DB','0')
        monkeypatch.delenv('REPOWORLD_EPHEMERAL_DEMO')
        assert (await client.get('/api/ready')).status_code==503
        assert (await client.get('/api/ready.svg')).status_code==503
