"""Issue radar: only actual public open issues, with evidence-qualified placement."""
import httpx
import pytest

from app.demo import build_demo
from app.github import RepoError
from app.issues import _assemble, fetch_issue_radar, match_issue, _CACHE


def sample_graph():
    graph=build_demo()
    graph.update({'source':'github','url':'https://github.com/testorg/commerce','owner':'testorg'})
    return graph


def test_issue_mapping_file_reference_and_no_path_false_positive():
    graph=sample_graph()
    result=match_issue(graph,'Auth broken in services/auth/src/sessions.ts','Please fix this session bug')
    assert any(r['nodeId']=='services/auth' and r['confidence']=='referenced' for r in result)
    assert not any(r['nodeId']=='services/payments' for r in result)
    result=match_issue(graph,'Checkout payment fails','Please debug this feature')
    assert all(m['confidence']=='suggested' for m in result)
    assert match_issue(graph,'Need help','General discussion that references no path')==[]


def test_issue_assembly_excludes_pull_requests_and_closed_issues():
    graph=sample_graph()
    raw=[{'number':11,'state':'open','title':'Fix session','body':'services/auth/src/sessions.ts','labels':[{'name':'bug'}],'updated_at':'2026-11-04T00:00:00Z'},
         {'number':12,'state':'open','title':'Fix session','pull_request':{'url':'a'}},
         {'number':13,'state':'closed','title':'Fix session'},
         {'number':14,'state':'open','title':'Help please','body':'unknown'}]
    data=_assemble(graph,'testorg','commerce',raw)
    assert data['total']==2 and data['placed']==1 and data['unplaced']==1
    assert data['issues'][0]['url']=='https://github.com/testorg/commerce/issues/11'
    assert data['byNode']['services/auth']['referenced']==[11]
    assert data['partial'] is False


@pytest.mark.asyncio
async def test_fetch_issues_read_only_and_verify_public_visibility():
    graph=sample_graph();seen=[]
    def handler(req):
        seen.append((str(req.url),req.method))
        if req.url.path.endswith('/commerce'):return httpx.Response(200,json={'private':False})
        if req.url.path.endswith('/issues'):return httpx.Response(200,json=[{'number':27,'state':'open','title':'Fix auth','body':'services/auth/src/sessions.ts'}])
        return httpx.Response(404)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        data=await fetch_issue_radar(graph,client=client)
    assert data['total']==1
    assert all(method=='GET' for _url,method in seen)
    assert '/issues?state=open' in seen[1][0]


@pytest.mark.asyncio
async def test_changed_private_repository_blocks_issue_access():
    graph=sample_graph()
    def handler(req):return httpx.Response(200,json={'private':True})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RepoError) as exc:
            await fetch_issue_radar(graph,client=client)
    assert exc.value.status==403


def test_issue_detail_retains_bounded_plain_text_body_and_match_evidence():
    graph=sample_graph()
    payload='services/auth/src/sessions.ts\n'+'reproduction: invalid session token\n'*900
    result=_assemble(graph,'testorg','commerce',[
        {'number':6,'title':'Auth fails','state':'open','body':payload,'comments':5,'labels':[{'name':'help wanted'}]}
    ])
    issue=result['issues'][0]
    assert len(issue['body'])<=4200 and issue['body'].startswith('services/auth/src/sessions.ts')
    assert issue['commentsCount']==5
    assert issue['matches'][0]['confidence']=='referenced'
    assert 'sessions.ts' in issue['matches'][0]['evidence']
    assert issue['url']=='https://github.com/testorg/commerce/issues/6'


def test_issue_uses_full_file_index_to_suggest_real_function_location():
    # #717 OpenWISP scenario: webdriver is in selenium.py, not qa.py. The issue
    # body mentions Selenium but not the path; a location is *suggested*, never verified.
    graph={'nodes':[
        {'id':'openwisp_utils','path':'openwisp_utils','fileCount':14,
         'files':['openwisp_utils/__init__.py','openwisp_utils/qa.py'],
         'fileIndex':['openwisp_utils/__init__.py','openwisp_utils/qa.py']},
        {'id':'openwisp_utils/tests','path':'openwisp_utils/tests','fileCount':200,
         'files':['openwisp_utils/tests/__init__.py'],
         'fileIndex':['openwisp_utils/tests/__init__.py','openwisp_utils/tests/selenium.py']}]}
    matches=match_issue(graph,'Add CHROMEDRIVER_LOG in get_chrome_webdriver',
                        'When debugging selenium issues with chrome, we cannot get the log.')
    assert matches and matches[0]['nodeId']=='openwisp_utils/tests'
    assert matches[0]['confidence']=='suggested' and matches[0]['path'].endswith('/selenium.py')


def test_issues_do_not_invent_a_location_without_path_evidence():
    graph={'nodes':[{'id':'root','path':'root','fileCount':900,'files':['setup.py'],
                     'fileIndex':['setup.py','README.md']}]}
    assert match_issue(graph,'Unknown build hangs on Tuesday','Help with flaky behavior')==[]
