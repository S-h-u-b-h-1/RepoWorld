import base64
import httpx
import pytest
from app.demo import build_demo
from app.assistant import context_for_question, guide_question, read_public_sources, redact_public_source
import app.assistant as assistant
from app.github import RepoError


def sample_graph():
    g=build_demo();g.update({'source':'github','url':'https://github.com/example/commerce','owner':'example'})
    return g


def test_assistant_context_restricts_selected_node_and_file_list():
    g=sample_graph()
    ctx=context_for_question(g,'How do sessions work?',node_id='services/auth')
    assert ctx['candidateNodeIds'][0]=='services/auth'
    assert 'services/auth/src/sessions.ts' in ctx['files']
    with pytest.raises(RepoError):context_for_question(g,'How?',node_id='not-a-node')


def test_redacts_known_secret_patterns():
    text='api_key = "verysecretvalue"\npassword="randomlongpassword"\nsk-abcdefghijklmnopqrstuvwxyz'
    redacted=redact_public_source(text)
    assert 'verysecretvalue' not in redacted and 'randomlongpassword' not in redacted
    assert 'sk-abc' not in redacted


@pytest.mark.asyncio
async def test_no_key_is_clearly_labelled_not_ai(monkeypatch):
    monkeypatch.delenv('BHARATCODE_API_KEY',raising=False)
    data=await guide_question(sample_graph(),'How should I add session rotation?',node_id='services/auth')
    assert data['mode']=='navigation' and data['model'] is None
    assert data['nodeIds'][0]=='services/auth'
    assert data['sources'][0]['url'].startswith('https://github.com/example/commerce/blob/')
    assert 'not verified' in data['answer']


@pytest.mark.asyncio
async def test_source_fetch_only_uses_files_in_saved_graph_and_public_repo():
    graph=sample_graph();paths=[]
    def handler(req):
        paths.append(str(req.url))
        if str(req.url).endswith('/commerce'):return httpx.Response(200,json={'private':False})
        if '/contents/' in str(req.url):
            return httpx.Response(200,json={'type':'file','encoding':'base64','size':17,'content':base64.b64encode(b'export function login() {}').decode()})
        return httpx.Response(404)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        sources=await read_public_sources(graph,['/etc/passwd','services/auth/src/sessions.ts','../../.env'],client=client)
    assert len(sources)==1 and sources[0]['file']=='services/auth/src/sessions.ts'
    assert len(paths)==3 and all('api.github.com' in p for p in paths)
    assert '/commits/main' in paths[1]


@pytest.mark.asyncio
async def test_ai_answer_invalid_citations_and_nodes_are_dropped(monkeypatch):
    graph=sample_graph();monkeypatch.setenv('BHARATCODE_API_KEY','test-token')
    async def fake_read(graph,paths,client=None,cues="",issue=None):return [{'file':'services/auth/src/sessions.ts','content':'function checkSession(){}','truncated':False}]
    async def fake_complete(system,prompt,max_tokens):
        assert 'checkSession' in prompt
        return '{"answer":"The excerpt declares checkSession; verify its behavior.","steps":["Read the session service"],"nodeIds":["services/auth","malicious"],"sources":["services/auth/src/sessions.ts","/etc/passwd"]}'
    monkeypatch.setattr(assistant,'read_public_sources',fake_read)
    monkeypatch.setattr(assistant,'_complete',fake_complete)
    result=await guide_question(graph,'What is checkSession?',node_id='services/auth')
    assert result['mode']=='ai' and result['nodeIds']==['services/auth']
    assert len(result['sources'])==1 and '/etc/' not in result['sources'][0]['url']


@pytest.mark.asyncio
async def test_issue_ai_prefers_explicit_file_and_passes_report_as_untrusted_context(monkeypatch):
    graph=sample_graph()
    issue={'number':120,'title':'Session fails after rotation',
           'body':'When a session rotates, a token is rejected. Mentioned services/auth/src/sessions.ts',
           'matches':[{'nodeId':'services/auth','confidence':'referenced',
                       'path':'services/auth/src/sessions.ts','evidence':'The issue references the path'}]}
    context=context_for_question(graph,'Investigate issue 120',issue=issue)
    assert context['files'][0]=='services/auth/src/sessions.ts'
    monkeypatch.setenv('BHARATCODE_API_KEY','test-token')
    async def fake_read(graph,paths,client=None,cues="",issue=None):
        assert paths[0]=='services/auth/src/sessions.ts'
        return [{'file':'services/auth/src/sessions.ts','content':'function rotateSession() {}','truncated':False}]
    async def fake_complete(system,prompt,max_tokens):
        assert 'Session fails after rotation' in prompt
        assert 'The issue references the path' in prompt
        assert 'distinguish the reported symptom' in system
        return '{"answer":"Issue reports a session rotation failure; inspect this function before changing code.","steps":["Inspect rotating tokens","Run session tests"],"nodeIds":["services/auth"],"sources":["services/auth/src/sessions.ts"]}'
    monkeypatch.setattr(assistant,'read_public_sources',fake_read)
    monkeypatch.setattr(assistant,'_complete',fake_complete)
    result=await guide_question(graph,'Investigate issue #120',issue=issue)
    assert result['mode']=='ai'
    assert result['sources'][0]['file']=='services/auth/src/sessions.ts'
    assert result['steps']==['Inspect rotating tokens','Run session tests']


def test_source_excerpt_finds_symbols_far_below_file_start():
    from app.assistant import _source_excerpt
    source='\n'.join([f'# filler line {i}' for i in range(250)]+['def get_chrome_webdriver(cls):','    pass']+['# tail']*25)
    excerpt,start,end=_source_excerpt(source,'Please investigate get_chrome_webdriver and CHROMEDRIVER_LOG')
    assert 230<=start<=251 and 251<=end
    assert 'get_chrome_webdriver' in excerpt and '251: def get_chrome_webdriver(cls):' in excerpt


@pytest.mark.asyncio
async def test_pins_live_source_links_to_verified_commit_and_lines():
    from app.assistant import _links
    graph=sample_graph();requests=[]
    sha='a'*40
    content='\n'.join(['# filler']*180+['def get_chrome_webdriver():','    return 1']+['# filler']*10)
    def handler(req):
        requests.append(str(req.url))
        if str(req.url).endswith('/commerce'):return httpx.Response(200,json={'private':False})
        if '/commits/' in str(req.url):return httpx.Response(200,json={'sha':sha})
        if '/contents/' in str(req.url):
            assert str(req.url).endswith('ref='+sha)
            return httpx.Response(200,json={'type':'file','encoding':'base64','size':len(content),'content':base64.b64encode(content.encode()).decode()})
        return httpx.Response(404)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        src=await read_public_sources(graph,['services/auth/src/sessions.ts'],client=client,cues='get_chrome_webdriver')
    assert len(src)==1 and src[0]['commit']==sha
    assert src[0]['lineStart']>100 and 'get_chrome_webdriver' in src[0]['content']
    link=_links(graph,['services/auth/src/sessions.ts'],src)[0]
    assert '/blob/'+sha+'/' in link['url'] and '#L' in link['url'] and link['evidence']=='excerpt'


@pytest.mark.asyncio
async def test_ai_issue_structured_response_is_bounded_and_linked_only_to_fetched_files(monkeypatch):
    graph=sample_graph()
    issue={'number':171,'title':'Session refresh error','body':'See services/auth/src/sessions.ts',
           'matches':[{'nodeId':'services/auth','confidence':'referenced','path':'services/auth/src/sessions.ts'}]}
    monkeypatch.setenv('BHARATCODE_API_KEY','test-token')
    async def fake_read(graph,paths,client=None,cues='',issue=None):
        return [{'file':'services/auth/src/sessions.ts','content':'188: def rotate_session(): pass','truncated':True,'commit':'a'*40,'lineStart':188,'lineEnd':188}]
    async def fake_complete(system,prompt,max_tokens):
        assert '188: def rotate_session' in prompt
        return '{"answer":"Review the rotation flow.","issueSummary":"Issue reports a broken session refresh.","codeEvidence":["rotate_session is present at line 188"],"tests":["Add a regression test"],"steps":["Inspect the implementation"],"nodeIds":["services/auth"],"sources":["services/auth/src/sessions.ts","imaginary.py"]}'
    monkeypatch.setattr(assistant,'read_public_sources',fake_read)
    monkeypatch.setattr(assistant,'_complete',fake_complete)
    result=await guide_question(graph,'Investigate this issue',issue=issue)
    assert result['issueSummary'].startswith('Issue reports')
    assert result['codeEvidence'] and result['tests']==['Add a regression test']
    assert len(result['sources'])==1 and result['sources'][0]['lineStart']==188
    assert result['sourceScope']=='commit-pinned'


def test_issue_717_uses_indexed_selenium_source_before_generic_module_files():
    """An issue's named Selenium behavior should retrieve Selenium source first.

    The report names get_chrome_webdriver, but not its actual source path.
    A directory-only building guess used to fetch __init__.py/admin.py/base.py.
    """
    graph={
        'source':'github', 'url':'https://github.com/openwisp/openwisp-utils',
        'name':'openwisp-utils','branch':'master','nodes':[
            {'id':'openwisp_utils','path':'openwisp_utils','kind':'library',
             'files':['openwisp_utils/__init__.py','openwisp_utils/admin.py','openwisp_utils/base.py'],
             'fileIndex':['openwisp_utils/__init__.py','openwisp_utils/admin.py','openwisp_utils/base.py']},
            {'id':'openwisp_utils/tests','path':'openwisp_utils/tests','kind':'test',
             'files':['openwisp_utils/tests/__init__.py','openwisp_utils/tests/base.py'],
             'fileIndex':['openwisp_utils/tests/__init__.py','openwisp_utils/tests/base.py',
                          'openwisp_utils/tests/selenium.py']},
        ], 'edges':[]
    }
    issue={'number':717,'title':'[feature] Add CHROMEDRIVER_LOG env var to enable logfile in get_chrome_webdriver',
           'body':'When debugging selenium issues with chrome, we cannot get the log. Match GECKO_LOG for firefox.',
           'matches':[{'nodeId':'openwisp_utils','confidence':'suggested','path':'openwisp_utils',
                       'evidence':'Possible module from title, not source evidence'}]}
    result=context_for_question(graph,'Please investigate GitHub issue #717',issue=issue)
    assert result['files'][0]=='openwisp_utils/tests/selenium.py'
    assert 'openwisp_utils/tests' in result['candidateNodeIds']
    assert result['files'].count('openwisp_utils/tests/selenium.py')==1


def test_explicit_issue_paths_remain_higher_priority_than_path_keyword_guesses():
    graph={
        'source':'github','url':'https://github.com/example/project', 'nodes':[
            {'id':'services/auth','path':'services/auth','kind':'security','files':['services/auth/src/auth.py'],
             'fileIndex':['services/auth/src/auth.py']},
            {'id':'tests/browser','path':'tests/browser','kind':'test','files':['tests/browser/selenium.py'],
             'fileIndex':['tests/browser/selenium.py']}], 'edges':[]}
    issue={'number':717,'title':'Add Selenium tracing',
           'body':'Code lives in services/auth/src/auth.py; selenium tools are used to test it.',
           'matches':[{'nodeId':'services/auth','confidence':'referenced','path':'services/auth/src/auth.py'}]}
    result=context_for_question(graph,'Investigate issue',issue=issue)
    assert result['files'][0]=='services/auth/src/auth.py'
