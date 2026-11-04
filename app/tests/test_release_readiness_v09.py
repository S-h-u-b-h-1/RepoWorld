"""Release gates: readiness, auth-free use, repeat imports, no credential leakage."""
import base64
import httpx
import pytest
from app import github, main


@pytest.mark.asyncio
async def test_production_readiness_refuses_missing_credentials(monkeypatch,tmp_path):
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.setenv('APP_BASE_URL','https://repo.example')
    monkeypatch.setenv('REPOWORLD_DB_PATH',str(tmp_path/'state.sqlite3'))
    monkeypatch.delenv('BHARATCODE_API_KEY',raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='https://repo.example') as client:
        response=await client.get('/api/ready')
        assert response.status_code==503 and response.json()=={'ready':False}
        monkeypatch.setenv('BHARATCODE_API_KEY','private-test-key')
        response=await client.get('/api/ready')
        assert response.status_code==200 and response.json()['ready']
        assert 'private-test-key' not in response.text


@pytest.mark.asyncio
async def test_repository_cache_avoids_repeated_github_reads_and_refresh_bypasses(monkeypatch):
    github._GRAPH_CACHE.clear()
    calls=[]
    content=b'export const hello = 1;'
    def handler(req):
        calls.append(req.url.path)
        if req.url.path=='/repos/testowner/v09-cache':
            return httpx.Response(200,json={'private':False,'name':'v09-cache','default_branch':'main','owner':{'login':'testowner'}})
        if req.url.path.endswith('/git/trees/main'):
            return httpx.Response(200,json={'tree':[{'path':'src/main.ts','type':'blob','size':len(content),'sha':'a'*40}], 'truncated':False})
        if '/git/blobs/' in req.url.path:
            return httpx.Response(200,json={'encoding':'base64','content':base64.b64encode(content).decode()})
        return httpx.Response(404)
    constructor=httpx.AsyncClient
    def mock_factory(*args,**kwargs):
        return constructor(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(github.httpx,'AsyncClient',mock_factory)
    first=await github.get_repository_graph('testowner/v09-cache')
    expected=len(calls)
    assert expected>=3
    first['name']='malicious-mutation'
    second=await github.get_repository_graph('testowner/v09-cache')
    assert len(calls)==expected+1 and second['name']=='v09-cache'
    assert calls[-1]=='/repos/testowner/v09-cache'
    await github.get_repository_graph('testowner/v09-cache',refresh=True)
    assert len(calls)>expected+1
    github._GRAPH_CACHE.clear()

@pytest.mark.asyncio
async def test_cached_import_is_refused_if_repository_becomes_private(monkeypatch):
    github._GRAPH_CACHE.clear()
    state={'private':False}
    content=b'export const safe = true;'
    def handler(req):
        if req.url.path=='/repos/testowner/privacy-change':
            return httpx.Response(200,json={'private':state['private'],'name':'privacy-change',
                                            'default_branch':'main','owner':{'login':'testowner'}})
        if req.url.path.endswith('/git/trees/main'):
            return httpx.Response(200,json={'tree':[{'path':'src/main.ts','type':'blob',
                                                    'size':len(content),'sha':'b'*40}],'truncated':False})
        if '/git/blobs/' in req.url.path:
            return httpx.Response(200,json={'encoding':'base64','content':base64.b64encode(content).decode()})
        return httpx.Response(404)
    constructor=httpx.AsyncClient
    monkeypatch.setattr(github.httpx,'AsyncClient',lambda *args,**kwargs:constructor(transport=httpx.MockTransport(handler)))
    await github.get_repository_graph('testowner/privacy-change')
    state['private']=True
    with pytest.raises(github.RepoError) as error:
        await github.get_repository_graph('testowner/privacy-change')
    assert error.value.status==403
    github._GRAPH_CACHE.clear()
