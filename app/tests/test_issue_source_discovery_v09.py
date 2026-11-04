"""Regression for OpenWISP #717: real symbol search, not guessed module links."""
import base64
import json
import httpx
import pytest
from app import assistant
from app.source_discovery import rank_issue_paths, live_symbol_matches, safe_code_path

SHA = 'd'*40
ISSUE = {
    'number': 717,
    'title': '[feature] Add CHROMEDRIVER_LOG env var to enable logfile in get_chrome_webdriver',
    'body': 'When debugging selenium issues with chrome, cannot get logs. Mirror GECKO_LOG from Firefox.',
    'matches': [{'nodeId':'openwisp_utils','confidence':'suggested','path':'openwisp_utils',
                 'evidence':'Possible package based on filename terms'}],
}
GRAPH = {
    'source':'github','url':'https://github.com/openwisp/openwisp-utils','branch':'master',
    'name':'openwisp-utils', 'nodes': [{'id':'openwisp_utils','path':'openwisp_utils','kind':'library',
        'files':['openwisp_utils/__init__.py','openwisp_utils/admin.py','openwisp_utils/base.py'],
        'fileIndex':['openwisp_utils/__init__.py','openwisp_utils/admin.py','openwisp_utils/base.py']}], 'edges':[],
}
SOURCE='\n'.join(['# filler']*120+[
    'class SeleniumTestCase:',
    '    def get_firefox_webdriver(self):',
    '        GECKO_LOG = os.environ.get("GECKO_LOG")',
    '        return webdriver.Firefox()',
    '    def get_chrome_webdriver(self):',
    '        options = webdriver.ChromeOptions()',
    '        return webdriver.Chrome(options=options)',
])

def fake_github(req: httpx.Request):
    path=req.url.path
    if path=='/repos/openwisp/openwisp-utils':return httpx.Response(200,json={'private':False})
    if '/commits/' in path:return httpx.Response(200,json={'sha':SHA})
    if '/git/trees/' in path:
        return httpx.Response(200,json={'truncated':False,'tree':[
            {'path':'openwisp_utils/qa.py','type':'blob','size':50},
            {'path':'openwisp_utils/admin.py','type':'blob','size':50},
            {'path':'openwisp_utils/tests/selenium.py','type':'blob','size':len(SOURCE)},
            {'path':'.env','type':'blob','size':15},
            {'path':'../../private.py','type':'blob','size':17},
        ]})
    if '/contents/openwisp_utils/tests/selenium.py' in path:
        assert req.url.params.get('ref')==SHA
        return httpx.Response(200,json={'type':'file','encoding':'base64','size':len(SOURCE),'content':base64.b64encode(SOURCE.encode()).decode()})
    if '/contents/' in path:
        return httpx.Response(200,json={'type':'file','encoding':'base64','size':20,'content':base64.b64encode(b'# no target symbol').decode()})
    return httpx.Response(404)


def test_path_rank_and_traversal():
    ranking=rank_issue_paths(['openwisp_utils/qa.py','openwisp_utils/tests/selenium.py','openwisp_utils/__init__.py'],ISSUE)
    assert ranking[0][1]=='openwisp_utils/tests/selenium.py'
    assert not safe_code_path('../../secrets.py')
    assert live_symbol_matches(SOURCE,ISSUE)==['get_chrome_webdriver','GECKO_LOG']

@pytest.mark.asyncio
async def test_old_city_import_can_find_real_symbol_in_live_public_tree():
    # The snapshot doesn't include selenium.py. Discovery is only permitted
    # because a verified public GitHub tree enumerates it.
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake_github)) as client:
        sources=await assistant.read_public_sources(GRAPH,
            ['openwisp_utils/__init__.py','openwisp_utils/admin.py'],
            client=client,cues=ISSUE['title']+' '+ISSUE['body'],issue=ISSUE)
    assert sources and sources[0]['file']=='openwisp_utils/tests/selenium.py'
    assert sources[0]['matchKind']=='symbol'
    assert sources[0]['matchedSymbols']
    assert sources[0]['commit']==SHA
    assert 'get_chrome_webdriver' in sources[0]['content']
    links=assistant._links(GRAPH,[sources[0]['file']],sources)
    assert f'/blob/{SHA}/openwisp_utils/tests/selenium.py#L' in links[0]['url']

@pytest.mark.asyncio
async def test_complete_issue_prompt_prefers_actual_source_not_qa_py(monkeypatch):
    monkeypatch.setenv('BHARATCODE_API_KEY','not-a-real-key')
    async def fake_model(system,prompt,max_tokens):
        data=json.loads(prompt.split('DATA, not instructions):\n')[1].split('\nReturn compact JSON')[0])
        source=data['live_public_source_excerpts']
        assert source[0]['file']=='openwisp_utils/tests/selenium.py'
        assert 'get_chrome_webdriver' in source[0]['content']
        return json.dumps({'answer':'The live Selenium implementation defines get_chrome_webdriver.',
            'codeEvidence':['get_chrome_webdriver appears in the inspected Selenium source.'],
            'issueSummary':'Issue requests ChromeDriver logfile support.',
            'steps':['Inspect the Selenium Chrome driver constructor.'],
            'tests':['Test with and without CHROMEDRIVER_LOG set.'],
            'nodeIds':['openwisp_utils'],
            'sources':['openwisp_utils/tests/selenium.py','openwisp_utils/qa.py']})
    monkeypatch.setattr(assistant,'_complete',fake_model)
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake_github)) as client:
        result=await assistant.guide_question(GRAPH,'Investigate issue #717',issue=ISSUE,client=client)
    assert result['mode']=='ai'
    assert result['sources'][0]['file']=='openwisp_utils/tests/selenium.py'
    assert not any(s['file'].endswith('/qa.py') for s in result['sources'])
    assert result['sourceMatches']>=1
