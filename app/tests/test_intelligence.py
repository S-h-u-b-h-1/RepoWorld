"""Grounded code finder and reverse-import impact tests."""
from __future__ import annotations
import httpx
import pytest

from app.demo import build_demo
from app.intelligence import find_modules, impact_trace, describe_module
from app.graph import extract_symbols, build_graph
import app.main as main


@pytest.mark.parametrize("question,expected", [
    ("Where is login handled?", "services/auth"),
    ("Where would I edit checkout?", "services/orders"),
    ("Where are the API endpoints?", "services/gateway"),
    ("Where do we store cache?", "data/redis"),
    ("Where are the tests?", "tests/e2e"),
])
def test_finder_identifies_path_backed_candidates(question, expected):
    result = find_modules(build_demo(), question)
    assert result['results'][0]['nodeId'] == expected
    assert result['results'][0]['files']
    assert 'paths' in result['scope']


def test_no_fake_matches_or_hidden_code_conclusions():
    assert find_modules(build_demo(), 'xyznothingpresent')['results'] == []
    assert find_modules(build_demo(), 'where is the code?')['results'] == []
    assert 'appear' in describe_module('src/auth', ['src/auth/session.ts'], 3)
    with pytest.raises(ValueError):
        find_modules(build_demo(), 'x' * 161)


def test_reverse_impact_direction_and_examples():
    result = impact_trace(build_demo(), 'services/auth')
    assert result['root'] == 'services/auth'
    assert [n['nodeId'] for n in result['direct']] == ['services/gateway']
    assert 'apps/web' in {n['nodeId'] for n in result['indirect']}
    assert all(row['importPath'][-1] == 'services/auth' for row in result['direct'] + result['indirect'])
    assert 'not' in result['scope'].lower()
    assert 'services/auth' not in result['dependencies']


def test_impact_stops_at_cap_and_does_not_invent_edges():
    graph = build_demo()
    graph['edges'] = [{'source': 'a', 'target': 'b'}, {'source': 'b', 'target': 'a'},
                      {'source': 'services/gateway', 'target': 'services/auth'}]
    result = impact_trace(graph, 'services/auth')
    assert len(result['direct']) == 1
    assert result['indirect'] == []
    assert all(e['source'] in {'services/gateway'} for e in result['edges'])
    with pytest.raises(KeyError):
        impact_trace(graph, 'secret/unknown')


@pytest.mark.asyncio
async def test_saved_repo_finder_and_impact_are_account_isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('REPOWORLD_DB_PATH', str(tmp_path / 'isolated.sqlite3'))
    monkeypatch.setenv('APP_BASE_URL', 'http://127.0.0.1:8002')
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('REPOWORLD_DEV_PREVIEW', '1')
    main._request_times.clear()

    async def fake_import(url):
        graph = build_demo()
        graph.update(name='sample', owner='testorg', source='github',url='https://github.com/testorg/sample')
        return graph
    monkeypatch.setattr(main, 'get_repository_graph', fake_import)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://127.0.0.1:8002') as client:
        assert (await client.get('/api/my-repos/no-id/find',params={'q':'login'})).status_code == 401
        assert (await client.get('/api/my-repos/no-id/impact',params={'nodeId':'services/auth'})).status_code == 401
        session = (await client.get('/api/session')).json()
        new = await client.post('/api/my-repos',json={'url':'testorg/sample'},headers={'X-RepoWorld-CSRF':session['csrf']})
        assert new.status_code == 200
        rid = new.json()['id']
        matched = await client.get(f'/api/my-repos/{rid}/find', params={'q':'Where is login handled?'})
        assert matched.status_code == 200
        assert matched.json()['results'][0]['nodeId'] == 'services/auth'
        trace = await client.get(f'/api/my-repos/{rid}/impact', params={'nodeId':'services/auth'})
        assert trace.status_code == 200
        assert trace.json()['direct'][0]['nodeId'] == 'services/gateway'
        assert (await client.get(f'/api/my-repos/{rid}/impact', params={'nodeId':'unknown'})).status_code == 404
        assert (await client.get(f'/api/my-repos/{rid}/find', params={'q':'a'})).status_code == 422
        client.cookies.clear()
        await client.get('/api/session')
        assert (await client.get(f'/api/my-repos/{rid}/find',params={'q':'login'})).status_code == 404
        assert (await client.get(f'/api/my-repos/{rid}/impact',params={'nodeId':'services/auth'})).status_code == 404


def test_sampled_source_declarations_are_searchable_without_running_code():
    assert [s['name'] for s in extract_symbols('def verify_session(x): pass\nclass SessionStore:\n pass', 'app/auth.py')] == ['verify_session', 'SessionStore']
    assert 'createUser' in [s['name'] for s in extract_symbols('export function createUser() {}\nconst loadProfile = async (id) => null', 'src/user.ts')]
    graph=build_graph([{'path':'app/auth.py','type':'blob','size':47}, {'path':'app/main.py','type':'blob','size':20}],
        {'app/auth.py':'def verify_session(token): return True\n'}, name='demo')
    assert graph['nodes'][0]['symbols'][0]['name']=='verify_session'
    result=find_modules(graph, 'verify session')
    assert result['results'][0]['nodeId']=='app'
    assert result['results'][0]['symbols'][0]['name']=='verify_session'
