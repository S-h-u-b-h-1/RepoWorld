"""Safe, API-quota-free public GitHub archive imports for ephemeral demo mode."""
from __future__ import annotations

from io import BytesIO
import stat
import time
import zipfile

import httpx
import pytest

from app import github
from app.archive_import import get_public_archive_graph, MAX_ARCHIVE_BYTES


def archive(*, traversal=False, symlink=False, duplicate_root=False):
    output=BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('demo-HEAD/src/api/main.py', 'def main():\n  return 42\n')
        z.writestr('demo-HEAD/src/api/handlers.py', 'from . import main\n')
        z.writestr('demo-HEAD/src/front/app.ts', 'export const app = () => true;\n')
        z.writestr('demo-HEAD/README.md', '# Public repository\n')
        if traversal:
            z.writestr('demo-HEAD/../../.env', 'secret=not-a-real-secret')
        if symlink:
            info=zipfile.ZipInfo('demo-HEAD/src/api/trap.py')
            info.create_system=3
            info.external_attr=(stat.S_IFLNK | 0o777) << 16
            z.writestr(info, '../.env')
        if duplicate_root:
            z.writestr('other-HEAD/src/evil.py','def bad(): pass')
    return output.getvalue()


@pytest.mark.asyncio
async def test_free_preview_imports_real_archive_without_any_api_request(monkeypatch):
    monkeypatch.setenv('REPOWORLD_EPHEMERAL_DEMO','1')
    monkeypatch.delenv('GITHUB_TOKEN',raising=False)
    calls=[]
    payload=archive()
    def handler(req):
        calls.append(str(req.url))
        assert str(req.url)=='https://codeload.github.com/public/demo/zip/HEAD'
        return httpx.Response(200,headers={'content-type':'application/zip'},content=payload)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        graph=await github.get_repository_graph('public/demo',client=client)
    assert len(calls)==1 and not any('api.github.com' in x for x in calls)
    assert graph['source']=='github' and graph['owner']=='public' and graph['name']=='demo'
    assert graph['stats']['files']==4
    assert graph['stats']['inspectedSources']>=1
    assert graph['branch']=='HEAD'
    assert all('PRIVATE' not in x for x in graph['warnings'])
    assert 'not independently verified' in ' '.join(graph['warnings']).lower()
    assert any('src/api/main.py' in n['fileIndex'] for n in graph['nodes'])


@pytest.mark.asyncio
async def test_archive_does_not_use_unsafe_names_or_symlink(monkeypatch):
    monkeypatch.setenv('REPOWORLD_EPHEMERAL_DEMO','1')
    monkeypatch.delenv('GITHUB_TOKEN',raising=False)
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda _:httpx.Response(200,content=archive(traversal=True,symlink=True)))) as client:
        graph=await github.get_repository_graph('public/demo',client=client)
    files=[x for n in graph['nodes'] for x in n['fileIndex']]
    assert not any('..' in file or '.env' in file or 'trap.py' in file for file in files)


@pytest.mark.asyncio
async def test_mixed_archive_roots_are_rejected(monkeypatch):
    monkeypatch.setenv('REPOWORLD_EPHEMERAL_DEMO','1')
    monkeypatch.delenv('GITHUB_TOKEN',raising=False)
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda _:httpx.Response(200,content=archive(duplicate_root=True)))) as client:
        with pytest.raises(github.RepoError) as exc:
            await github.get_repository_graph('public/demo',client=client)
    assert exc.value.status==502


@pytest.mark.asyncio
async def test_archive_size_cap_and_no_redirect(monkeypatch):
    monkeypatch.setenv('REPOWORLD_EPHEMERAL_DEMO','1')
    monkeypatch.delenv('GITHUB_TOKEN',raising=False)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _:
        httpx.Response(200,headers={'content-length':str(MAX_ARCHIVE_BYTES+1)},content=b'PK\x03\x04'))) as client:
        with pytest.raises(github.RepoError) as exc:
            await github.get_repository_graph('public/demo',client=client)
    assert exc.value.status==413
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _:
        httpx.Response(302,headers={'location':'https://attacker.invalid/archive.zip'}))) as client:
        with pytest.raises(github.RepoError) as exc:
            await github.get_repository_graph('public/demo',client=client)
    assert exc.value.status==502


@pytest.mark.asyncio
async def test_archive_rate_limit_is_not_retried_or_hidden(monkeypatch):
    monkeypatch.setenv('REPOWORLD_EPHEMERAL_DEMO','1')
    monkeypatch.delenv('GITHUB_TOKEN',raising=False)
    calls=[]
    def handler(req):
        calls.append(str(req.url))
        return httpx.Response(429)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(github.RepoError) as exc:
            await github.get_repository_graph('public/demo',client=client)
    assert exc.value.status==429 and len(calls)==1


@pytest.mark.asyncio
async def test_corrupt_archive_never_yields_fabricated_city(monkeypatch):
    monkeypatch.setenv('REPOWORLD_EPHEMERAL_DEMO','1')
    monkeypatch.delenv('GITHUB_TOKEN',raising=False)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _:
        httpx.Response(200,content=b'PK\x03\x04badzip'))) as client:
        with pytest.raises(github.RepoError) as exc:
            await github.get_repository_graph('public/demo',client=client)
    assert exc.value.status==502


@pytest.mark.asyncio
async def test_archive_not_reused_without_rechecking_public_visibility(monkeypatch):
    monkeypatch.setenv('REPOWORLD_EPHEMERAL_DEMO','1')
    monkeypatch.delenv('GITHUB_TOKEN',raising=False)
    calls=[]
    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200,content=archive()) if len(calls)==1 else httpx.Response(404)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result=await github.get_repository_graph('public/demo',client=client)
        assert result['nodes']
        with pytest.raises(github.RepoError) as exc:
            await github.get_repository_graph('public/demo',client=client)
    assert exc.value.status==404 and len(calls)==2


@pytest.mark.asyncio
async def test_anonymous_browser_import_saves_real_archive_city_without_api(monkeypatch,tmp_path):
    """Exercise the actual CSRF-protected import route with a mocked archive host."""
    from app import main
    from app import archive_import
    monkeypatch.setenv('APP_ENV','development')
    monkeypatch.setenv('APP_BASE_URL','http://127.0.0.1:8004')
    monkeypatch.setenv('REPOWORLD_EPHEMERAL_DEMO','1')
    monkeypatch.setenv('REPOWORLD_DB_PATH',str(tmp_path/'repoworld.sqlite3'))
    monkeypatch.delenv('GITHUB_TOKEN',raising=False)
    real_async_client=httpx.AsyncClient
    calls=[]
    def handler(request):
        calls.append(str(request.url))
        assert request.url.host=='codeload.github.com'
        return httpx.Response(200,content=archive())
    async with real_async_client(transport=httpx.ASGITransport(app=main.app),
                                 base_url='http://127.0.0.1:8004') as client:
        monkeypatch.setattr(archive_import.httpx,'AsyncClient',
                            lambda **kwargs:real_async_client(transport=httpx.MockTransport(handler)))
        session=(await client.get('/api/session')).json()
        response=await client.post('/api/my-repos',json={'url':'public/demo'},
                                   headers={'origin':'http://127.0.0.1:8004',
                                            'X-RepoWorld-CSRF':session['csrf']})
        assert response.status_code==200,response.text
        saved=response.json()
        assert saved['graph']['source']=='github'
        assert saved['graph']['stats']['files']==4
        assert 'public/demo' in calls[0]
        listed=(await client.get('/api/session')).json()['repositories']
        assert any(item['fullName']=='public/demo' for item in listed)
    assert len(calls)==1
