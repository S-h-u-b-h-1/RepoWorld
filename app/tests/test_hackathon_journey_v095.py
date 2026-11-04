"""Full anonymous import -> issue radar -> assistant flow (no live credentials)."""
from __future__ import annotations

import httpx
import pytest

from app import main
from app.demo import build_demo


@pytest.mark.asyncio
async def test_complete_read_only_visitor_journey_preserves_workspace_isolation(monkeypatch,tmp_path):
    monkeypatch.setenv('REPOWORLD_DB_PATH',str(tmp_path/'visitor.sqlite3'))
    monkeypatch.setenv('APP_BASE_URL','http://127.0.0.1:8004')
    monkeypatch.setenv('APP_ENV','development')
    monkeypatch.delenv('BHARATCODE_API_KEY',raising=False)
    requests={'import':0,'radar':0,'assistant':0}
    graph=build_demo()
    graph.update({'owner':'testowner','name':'demo-city','source':'github',
                  'url':'https://github.com/testowner/demo-city','branch':'main'})
    selected=next(n for n in graph['nodes'] if n['id']=='services/auth')
    issue={'number':717,'title':'Add logging for session validation',
           'url':'https://github.com/testowner/demo-city/issues/717','body':'A source-backed reproduction is needed.',
           'labels':['enhancement'],'matches':[{'nodeId':selected['id'],
             'confidence':'referenced','path':'services/auth/src/sessions.ts',
             'evidence':'Issue references a source path'}]}

    async def fake_import(raw,*,refresh=False):
        assert raw=='testowner/demo-city'
        requests['import']+=1
        return graph

    async def fake_issues(loaded,*,use_cache=True):
        assert loaded['name']=='demo-city'
        requests['radar']+=1
        return {'total':1,'placed':1,'unplaced':0,'issues':[issue],
                'byNode':{selected['id']:{'referenced':[717],'suggested':[]}},
                'partial':False,'scope':'Mock public issue fixture'}

    async def fake_assistant(loaded,question,*,node_id=None,issue=None,history=None):
        assert loaded['name']=='demo-city'
        assert node_id==selected['id']
        assert issue['number']==717
        requests['assistant']+=1
        return {'mode':'navigation','answer':'Inspect the linked source and add a regression test.',
                'steps':['Check the target function'],
                'sources':[{'file':'services/auth/src/sessions.ts','url':
                   'https://github.com/testowner/demo-city/blob/main/services/auth/src/sessions.ts'}],
                'disclosure':'Controlled test fixture; no model call.'}

    monkeypatch.setattr(main,'get_repository_graph',fake_import)
    monkeypatch.setattr(main,'fetch_issue_radar',fake_issues)
    monkeypatch.setattr(main,'guide_question',fake_assistant)

    transport=httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport,base_url='http://127.0.0.1:8004') as visitor:
        boot=await visitor.get('/api/session')
        assert boot.status_code==200
        csrf=boot.json()['csrf']
        headers={'Origin':'http://localhost:8004','X-RepoWorld-CSRF':csrf}
        imported=await visitor.post('/api/my-repos',json={'url':'testowner/demo-city'},headers=headers)
        assert imported.status_code==200,imported.text
        rid=imported.json()['id']
        assert requests['import']==1
        assert (await visitor.get('/api/my-repos/'+rid)).status_code==200
        radar=await visitor.get('/api/my-repos/'+rid+'/issues')
        assert radar.status_code==200 and radar.json()['issues'][0]['number']==717
        answer=await visitor.post('/api/my-repos/'+rid+'/assistant',json={
            'question':'Where can I investigate issue #717?',
            'nodeId':selected['id'],'issueNumber':717},headers=headers)
        assert answer.status_code==200,answer.text
        assert 'regression test' in answer.json()['answer']
        assert requests=={'import':1,'radar':2,'assistant':1}

    async with httpx.AsyncClient(transport=transport,base_url='http://127.0.0.1:8004') as other:
        assert (await other.get('/api/session')).status_code==200
        forbidden=await other.get('/api/my-repos/'+rid)
        assert forbidden.status_code==404
        assert (await other.get('/api/my-repos/'+rid+'/issues')).status_code==404
