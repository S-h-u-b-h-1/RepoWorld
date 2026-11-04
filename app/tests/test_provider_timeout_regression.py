"""Regression tests for live BharatCode requests that outlast the old 60-second ceiling."""
import asyncio

import httpx
import pytest

from app import ai, assistant
from app.demo import build_demo
from app.github import RepoError


def public_graph():
    graph=build_demo()
    graph.update({'source':'github','url':'https://github.com/example/commerce','owner':'example'})
    return graph


@pytest.mark.parametrize('value,expected', [
    ('180',180),('220',220),('10',30),('500',240),('n/a',180),('NaN',180),('inf',180),('-10',30),
])
def test_provider_read_timeout_clamps_and_validates(monkeypatch,value,expected):
    monkeypatch.setenv('BHARATCODE_TIMEOUT_SECONDS',value)
    assert ai.provider_read_timeout()==expected


@pytest.mark.asyncio
async def test_provider_uses_longer_configurable_read_timeout(monkeypatch):
    observed={}
    class FakeClient:
        def __init__(self,*,timeout,follow_redirects):
            observed.update(timeout=timeout,follow_redirects=follow_redirects)
        async def __aenter__(self):return self
        async def __aexit__(self,*_):return None
        async def post(self,*args,**kwargs):
            observed['payload']=kwargs['json']
            return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':'{"answer":"ok"}'}}]})
    monkeypatch.setattr(ai.httpx,'AsyncClient',FakeClient)
    monkeypatch.setenv('BHARATCODE_API_KEY','a-demo-key')
    monkeypatch.setenv('BHARATCODE_TIMEOUT_SECONDS','155')
    result=await ai._complete('system','question')
    assert result=='{"answer":"ok"}'
    assert observed['timeout'].read==155
    assert observed['timeout'].connect==12
    assert observed['follow_redirects'] is False
    assert observed['payload']['model']=='qwen-3.8-27b'


@pytest.mark.asyncio
async def test_read_timeout_is_reported_as_504_without_retry(monkeypatch):
    observed={'calls':0}
    class FakeClient:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*_):return None
        async def post(self,*args,**kwargs):
            observed['calls']+=1
            raise httpx.ReadTimeout('provider queue stalled')
    monkeypatch.setattr(ai.httpx,'AsyncClient',FakeClient)
    monkeypatch.setenv('BHARATCODE_API_KEY','a-demo-key')
    monkeypatch.setenv('BHARATCODE_TIMEOUT_SECONDS','175')
    with pytest.raises(RepoError,match='175 seconds') as error:
        await ai._complete('system','question')
    assert error.value.status==504
    assert observed['calls']==1


@pytest.mark.asyncio
async def test_developer_assistant_timeout_returns_honest_static_guide(monkeypatch):
    monkeypatch.setenv('BHARATCODE_API_KEY','a-demo-key')
    async def fake_read(*args,**kwargs):return []
    async def fake_complete(*args,**kwargs):raise RepoError('Provider timed out',504)
    monkeypatch.setattr(assistant,'read_public_sources',fake_read)
    monkeypatch.setattr(assistant,'_complete',fake_complete)
    result=await assistant.guide_question(public_graph(),'Where is session login implemented?',node_id='services/auth')
    assert result['mode']=='navigation'
    assert result['providerStatus']=='timeout'
    assert result['model'] is None
    assert result['nodeIds'][0]=='services/auth'
    assert result['sources'][0]['url'].startswith('https://github.com/example/commerce/blob/')
    assert 'not an AI answer' in result['disclosure']


@pytest.mark.asyncio
async def test_authorization_errors_are_never_hidden_by_fallback(monkeypatch):
    monkeypatch.setenv('BHARATCODE_API_KEY','a-demo-key')
    async def fake_read(*args,**kwargs):return []
    async def fake_complete(*args,**kwargs):raise RepoError('Unauthorized',503)
    monkeypatch.setattr(assistant,'read_public_sources',fake_read)
    monkeypatch.setattr(assistant,'_complete',fake_complete)
    with pytest.raises(RepoError,match='Unauthorized'):
        await assistant.guide_question(public_graph(),'How do sessions work?',node_id='services/auth')
