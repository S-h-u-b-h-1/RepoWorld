"""Evidence-qualified mapping back to real city modules. No bug-verdict claims."""
import httpx
import pytest

from app import assistant
from app.tests.test_issue_source_discovery_v09 import SOURCE, SHA, ISSUE, fake_github, GRAPH


def graph_with_test_building():
    graph = {**GRAPH, 'nodes': [*GRAPH['nodes'],
        {'id': 'openwisp_utils/tests', 'path': 'openwisp_utils/tests',
         'kind': 'test', 'files': ['openwisp_utils/tests/__init__.py'],
         'fileIndex': ['openwisp_utils/tests/__init__.py']} ]}
    return graph


@pytest.mark.asyncio
async def test_observed_symbol_returns_correct_building_even_when_import_missed_file(monkeypatch):
    graph=graph_with_test_building()
    monkeypatch.setenv('BHARATCODE_API_KEY','mock-only')
    async def fake_model(*_args):
        return '{"answer":"Inspect the Selenium driver factory.","sources":["openwisp_utils/tests/selenium.py"],"nodeIds":["openwisp_utils"]}'
    monkeypatch.setattr(assistant,'_complete',fake_model)
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake_github)) as client:
        result=await assistant.guide_question(graph,'Investigate issue #717',issue=ISSUE,client=client)
    assert result['observedLocations']
    item=result['observedLocations'][0]
    assert item['nodeId']=='openwisp_utils/tests'
    assert item['file']=='openwisp_utils/tests/selenium.py'
    assert 'get_chrome_webdriver' in item['symbols']
    assert item['evidence']=='identifier-observed'
    assert f'/blob/{SHA}/' in item['url']
    assert 'not proof' in item['scope'].lower()
    assert result['nodeIds'][0]=='openwisp_utils/tests'


@pytest.mark.asyncio
async def test_no_city_pin_for_file_outside_retained_buildings():
    # A path from the live tree is not always present in the 72 retained modules.
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake_github)) as client:
        excerpts=await assistant.read_public_sources(GRAPH,[],client=client,cues=ISSUE['title'],issue=ISSUE)
    assert excerpts[0]['file']=='openwisp_utils/tests/selenium.py'
    assert assistant.observed_issue_locations(GRAPH,excerpts,ISSUE)==[]


def test_path_hint_without_fetched_symbol_never_becomes_observed_marker():
    graph=graph_with_test_building()
    excerpts=[{'file':'openwisp_utils/tests/selenium.py','matchKind':'path-hint',
               'matchedSymbols':[],'content':'a filename guess','lineStart':1,'lineEnd':5}]
    assert assistant.observed_issue_locations(graph,excerpts,ISSUE)==[]
    # Neither an issue snippet nor a model-supplied path may create a marker.
    assert assistant.observed_issue_locations(graph,[{'file':'../../secret.py','matchKind':'symbol',
                 'matchedSymbols':['get_chrome_webdriver']}],ISSUE)==[]


@pytest.mark.asyncio
async def test_provider_timeout_keeps_source_observation_but_not_ai_claim(monkeypatch):
    monkeypatch.setenv('BHARATCODE_API_KEY','mock-only')
    async def timed_out(*_args):
        from app.github import RepoError
        raise RepoError('BharatCode timeout',504)
    monkeypatch.setattr(assistant,'_complete',timed_out)
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake_github)) as client:
        result=await assistant.guide_question(graph_with_test_building(),
                     'Investigate issue #717',issue=ISSUE,client=client)
    assert result['mode']=='navigation' and result['providerStatus']=='timeout'
    assert result['observedLocations'][0]['nodeId']=='openwisp_utils/tests'
    assert result['sources'][0]['file']=='openwisp_utils/tests/selenium.py'
    assert 'no AI explanation' in result['disclosure']
