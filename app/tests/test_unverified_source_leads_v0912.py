"""Explicit public-source lookup for unverified browser-only GitHub issue leads."""
import httpx
import pytest

from app import main
from app.demo import build_demo


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setenv('REPOWORLD_DB_PATH', str(tmp_path/'source-leads.sqlite3'))
    monkeypatch.setenv('REPOWORLD_DEV_PREVIEW','1')
    monkeypatch.setenv('APP_ENV','development')
    monkeypatch.setenv('APP_BASE_URL','http://127.0.0.1:8004')
    monkeypatch.delenv('BHARATCODE_API_KEY',raising=False)
    monkeypatch.delenv('GITHUB_TOKEN',raising=False)
    monkeypatch.delenv('REPOWORLD_ENFORCE_BUDGETS',raising=False)
    main._request_times.clear()


def http():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                             base_url='http://127.0.0.1:8004')


async def imported(http_client, monkeypatch):
    async def github_snapshot(_url):
        graph=build_demo()
        graph.update(source='github',url='https://github.com/example/commerce',
                     owner='example',name='commerce',branch='HEAD')
        return graph
    monkeypatch.setattr(main,'get_repository_graph',github_snapshot)
    sess=(await http_client.get('/api/session')).json()
    resp=await http_client.post('/api/my-repos',json={'url':'example/commerce'},
             headers={'X-RepoWorld-CSRF':sess['csrf']})
    assert resp.status_code==200,resp.text
    return resp.json()['id'],sess['csrf']


@pytest.mark.asyncio
async def test_explicit_lead_fetches_real_source_but_never_validates_issue_or_calls_ai(monkeypatch):
    calls=[]
    async def fake_read(graph, paths, *, cues, issue):
        calls.append((graph, paths, cues, issue))
        return [{'file':'services/auth/src/sessions.ts',
                 'content':'188: export function updateRecipient() { return true; }',
                 'commit':None,'lineStart':188,'lineEnd':188,
                 'matchedSymbols':['updateRecipient'],'matchKind':'symbol'}]
    async def forbid(*args,**kwargs):
        raise AssertionError('No model or verified issue-list call permitted in source lead')
    monkeypatch.setattr(main,'read_public_sources',fake_read)
    monkeypatch.setattr(main,'fetch_issue_radar',forbid)
    monkeypatch.setattr(main,'guide_question',forbid)
    monkeypatch.setattr(main,'has_key',lambda:True)  # Even a key must not change behavior.
    async with http() as client:
        rid,csrf=await imported(client,monkeypatch)
        endpoint=f'/api/my-repos/{rid}/source-lead'
        response=await client.post(endpoint,
            json={'title':'Disable cycling to recipients while editing',
                  'body':'User report mentions updateRecipient.'},
            headers={'X-RepoWorld-CSRF':csrf})
        assert response.status_code==200,response.text
        data=response.json()
        assert data['mode']=='source-lead'
        assert data['issueVerified'] is False and data['assistantUsed'] is False
        assert data['sourceScope']=='live-branch' and data['sourceFilesRead']==1
        assert data['sources'][0]['evidence']=='excerpt'
        assert data['sources'][0]['matchKind']=='symbol'
        assert data['sources'][0]['matchedSymbols']==['updateRecipient']
        assert data['sources'][0]['url'].startswith('https://github.com/example/commerce/blob/HEAD/')
        assert '#L188-L188' in data['sources'][0]['url']
        assert data['sources'][0].get('commit') is None
        assert 'issue' in data['disclosure'].lower()
        assert len(calls)==1 and calls[0][1]==[]
        assert calls[0][3]['matches']==[]
        assert 'Disable cycling' in calls[0][2]


@pytest.mark.asyncio
async def test_source_lead_protects_other_guests_csrf_and_non_github_snapshots(monkeypatch):
    attempts=[]
    async def fake_read(*args,**kwargs):
        attempts.append(1);return []
    monkeypatch.setattr(main,'read_public_sources',fake_read)
    async with http() as owner, http() as stranger:
        rid,csrf=await imported(owner,monkeypatch)
        url=f'/api/my-repos/{rid}/source-lead'
        args={'title':'Find a real code module','body':'Report text is unverified'}
        denied=await owner.post(url,json=args)
        assert denied.status_code==403
        invalid=await owner.post(url,json={'title':'  ','body':''},
                                 headers={'X-RepoWorld-CSRF':csrf})
        assert invalid.status_code==422
        oversized=await owner.post(url,json={'title':'Safe title','body':'x'*1801},
                                   headers={'X-RepoWorld-CSRF':csrf})
        assert oversized.status_code in (413,422)
        await stranger.get('/api/session')
        assert (await stranger.post(url,json=args,headers={'X-RepoWorld-CSRF':'fake'})).status_code in (403,404)
        assert attempts==[]


@pytest.mark.asyncio
async def test_source_lead_is_explicit_not_automatic_and_budgeted(monkeypatch):
    calls=[]
    async def fake_read(*args,**kwargs):
        calls.append(1);return []
    monkeypatch.setattr(main,'read_public_sources',fake_read)
    async with http() as client:
        rid,csrf=await imported(client,monkeypatch)
        assert not calls
        url=f'/api/my-repos/{rid}/source-lead'
        for _ in range(3):
            r=await client.post(url,json={'title':'Find a source file'},
                headers={'X-RepoWorld-CSRF':csrf})
            assert r.status_code==200,r.text
            assert r.json()['sources']==[]
            assert r.json()['sourceScope']=='unavailable'
        blocked=await client.post(url,json={'title':'Find a source file'},
                                 headers={'X-RepoWorld-CSRF':csrf})
        assert blocked.status_code==429
        assert len(calls)==3


@pytest.mark.asyncio
async def test_persistent_hourly_budget_limits_probes_separately_from_ai(monkeypatch):
    calls=[]
    async def fake_read(*args,**kwargs):
        calls.append(1);return []
    monkeypatch.setattr(main,'read_public_sources',fake_read)
    monkeypatch.setenv('REPOWORLD_ENFORCE_BUDGETS','1')
    monkeypatch.setenv('REPOWORLD_SOURCE_GUEST_HOURLY','1')
    monkeypatch.setenv('REPOWORLD_SOURCE_GLOBAL_HOURLY','2')
    async with http() as client:
        rid,csrf=await imported(client,monkeypatch)
        url=f'/api/my-repos/{rid}/source-lead'
        first=await client.post(url,json={'title':'Investigate a source'},
            headers={'X-RepoWorld-CSRF':csrf})
        second=await client.post(url,json={'title':'Investigate a source'},
            headers={'X-RepoWorld-CSRF':csrf})
        assert first.status_code==200,first.text
        assert second.status_code==429
        assert 'Source lookup browser hourly' in second.text
        assert second.headers['retry-after'].isdigit()
        assert len(calls)==1
