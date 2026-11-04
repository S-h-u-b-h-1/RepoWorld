"""New endpoints must use account-owned saved graphs and CSRF, never client graphs."""
from pathlib import Path
import httpx
import pytest
import app.main as main
from app.demo import build_demo


@pytest.fixture(autouse=True)
def isolate(tmp_path,monkeypatch):
    monkeypatch.setenv('REPOWORLD_DB_PATH',str(tmp_path/'isolated.sqlite3'))
    monkeypatch.setenv('REPOWORLD_DEV_PREVIEW','1')
    monkeypatch.setenv('APP_ENV','development')
    monkeypatch.setenv('APP_BASE_URL','http://127.0.0.1:8004')
    monkeypatch.delenv('BHARATCODE_API_KEY',raising=False)
    main._request_times.clear()


def client():return httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://127.0.0.1:8004')


@pytest.mark.asyncio
async def test_issues_and_guide_are_account_scoped_read_only(monkeypatch):
    calls=[]
    async def fake_graph(url):
        graph=build_demo()
        graph.update(source='github',owner='example',url='https://github.com/example/project',name='project')
        return graph
    async def fake_issues(graph,**kwargs):
        calls.append(('issues',graph['name']))
        return {'issues':[{'number':9,'title':'Fix login','matches':[{'nodeId':'services/auth','confidence':'suggested'}]}],
                'byNode':{'services/auth':{'referenced':[],'suggested':[9]}},'total':1,'placed':1,'unplaced':0,'partial':False}
    async def fake_guide(graph,question,**kwargs):
        calls.append(('assistant',graph['name'],question,kwargs.get('node_id'),(kwargs.get('issue') or {}).get('number')))
        return {'mode':'navigation','answer':'Start with auth','steps':[],'nodeIds':['services/auth'],'sources':[]}
    monkeypatch.setattr(main,'get_repository_graph',fake_graph)
    monkeypatch.setattr(main,'fetch_issue_radar',fake_issues)
    monkeypatch.setattr(main,'guide_question',fake_guide)
    async with client() as http:
        assert (await http.get('/api/my-repos/not-owned/issues')).status_code==401
        assert (await http.post('/api/my-repos/not-owned/assistant',json={'question':'Help me'})).status_code==401
        csrf=(await http.get('/api/session')).json()['csrf']
        imported=(await http.post('/api/my-repos',json={'url':'example/project'},headers={'X-RepoWorld-CSRF':csrf})).json()
        rid=imported['id']
        assert (await http.get('/api/my-repos/'+rid+'/issues')).json()['total']==1
        assert (await http.post('/api/my-repos/'+rid+'/assistant',json={'question':'Help me'})).status_code==403
        answer=await http.post('/api/my-repos/'+rid+'/assistant',json={'question':'Help me improve login','nodeId':'services/auth','issueNumber':9},headers={'X-RepoWorld-CSRF':csrf})
        assert answer.status_code==200 and answer.json()['mode']=='navigation'
        assert ('assistant','project','Help me improve login','services/auth',9) in calls
        assert (await http.post('/api/my-repos/'+rid+'/assistant',json={'question':'Help me','nodeId':'unlisted'},headers={'X-RepoWorld-CSRF':csrf})).status_code==404
        assert (await http.get('/api/my-repos/other/issues')).status_code==404
        http.cookies.clear()
        await http.get('/api/session')
        assert (await http.get('/api/my-repos/'+rid+'/issues')).status_code==404
