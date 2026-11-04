"""Public demo budgets must be persistent, transactional, and privacy-bounded."""
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from app import auth, main
from app.demo import build_demo
from app.quotas import Budget, BudgetExceeded, consume, reserve_ai


def env_setup(monkeypatch, tmp_path):
    monkeypatch.setenv('REPOWORLD_DB_PATH',str(tmp_path/'database.sqlite3'))
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.setenv('APP_BASE_URL','https://repo.example')
    monkeypatch.setenv('REPOWORLD_AI_GLOBAL_DAILY','2')
    monkeypatch.setenv('REPOWORLD_AI_GUEST_DAILY','10')
    monkeypatch.setenv('REPOWORLD_AI_GUEST_10MIN','10')
    monkeypatch.setenv('REPOWORLD_AI_IP_DAILY','10')


def test_transactional_quota_and_no_partial_debit(monkeypatch,tmp_path):
    env_setup(monkeypatch,tmp_path)
    specs=[Budget('small','visitor1',60,1),Budget('global','global',60,4)]
    consume(specs,now=100)
    with pytest.raises(BudgetExceeded) as err:consume(specs,now=101)
    assert err.value.retry_after==19
    # Denied request did not consume the global budget.
    consume([specs[1]],now=101)
    consume(specs,now=161)  # new fixed window


def test_concurrent_visitors_cannot_exceed_global_daily(monkeypatch,tmp_path):
    env_setup(monkeypatch,tmp_path)
    def attempt(i):
        try:reserve_ai('visitor-'+str(i), 'network-'+str(i));return True
        except BudgetExceeded:return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(attempt,range(14)))
    assert sum(results)==2
    with auth._database() as db:
        assert db.execute("SELECT count FROM request_quotas WHERE quota_key LIKE 'AI global daily:%'").fetchone()['count']==2


@pytest.mark.asyncio
async def test_production_import_limit_returns_retry_after(monkeypatch,tmp_path):
    env_setup(monkeypatch,tmp_path)
    monkeypatch.setenv('REPOWORLD_IMPORT_GUEST_HOURLY','1')
    async def fake_import(url):
        graph=build_demo()
        graph.update(owner='testorg',name='testrepo',url='https://github.com/testorg/testrepo',source='github')
        return graph
    monkeypatch.setattr(main,'get_repository_graph',fake_import)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='https://repo.example') as client:
        session=(await client.get('/api/session')).json()
        headers={'X-RepoWorld-CSRF':session['csrf']}
        first=await client.post('/api/my-repos',json={'url':'testorg/testrepo'},headers=headers)
        assert first.status_code==200
        second=await client.post('/api/my-repos',json={'url':'testorg/testrepo'},headers=headers)
        assert second.status_code==429
        assert int(second.headers['retry-after'])>0
        # A rejected import doesn't destroy the existing saved city.
        assert len((await client.get('/api/session')).json()['repositories'])==1


def test_dev_mode_does_not_exhaust_public_key_budget(monkeypatch,tmp_path):
    monkeypatch.setenv('REPOWORLD_DB_PATH',str(tmp_path/'dev.sqlite3'))
    monkeypatch.setenv('APP_ENV','development')
    monkeypatch.delenv('REPOWORLD_ENFORCE_BUDGETS',raising=False)
    for _ in range(100):reserve_ai('local','localhost')
    with auth._database() as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE name='request_quotas'").fetchone() is None
