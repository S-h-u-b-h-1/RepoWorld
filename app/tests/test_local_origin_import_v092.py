"""Import must accept both local browser loopback names without weakening CSRF."""
import httpx
import pytest

from app import main
from app.demo import build_demo


@pytest.fixture(autouse=True)
def isolate_storage(monkeypatch, tmp_path):
    monkeypatch.setenv("REPOWORLD_DB_PATH", str(tmp_path / "origin-test.sqlite3"))
    monkeypatch.setenv("APP_BASE_URL", "http://127.0.0.1:8004")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("REPOWORLD_ENFORCE_BUDGETS", raising=False)


@pytest.mark.asyncio
async def test_localhost_import_with_matching_origin(monkeypatch):
    async def fake_get_repo(url, *, refresh=False):
        graph = build_demo()
        graph["name"], graph["owner"] = "openwisp-utils", "openwisp"
        return graph
    monkeypatch.setattr(main, "get_repository_graph", fake_get_repo)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://localhost:8004") as client:
        session = (await client.get("/api/session")).json()
        result = await client.post("/api/my-repos", json={"url": "openwisp/openwisp-utils"},
                                   headers={"Origin": "http://localhost:8004", "X-RepoWorld-CSRF": session["csrf"]})
        assert result.status_code == 200, result.text
        assert result.json()["graph"]["owner"] == "openwisp"
        assert len((await client.get("/api/session")).json()["repositories"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_origin", ["https://evil.example", "http://localhost:8005", "http://attacker.invalid:8004", "null", "http://localhost:8004.evil.example", "http://localhost:8004/other"])
async def test_bad_origins_are_still_denied(bad_origin):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://localhost:8004") as client:
        session = (await client.get("/api/session")).json()
        result = await client.post("/api/tour", json={"graph": build_demo()},
                                   headers={"Origin": bad_origin, "X-RepoWorld-CSRF": session["csrf"]})
        assert result.status_code == 403


@pytest.mark.asyncio
async def test_localhost_with_no_csrf_still_denied():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://localhost:8004") as client:
        await client.get("/api/session")
        result = await client.post("/api/tour", json={"graph": build_demo()}, headers={"Origin": "http://localhost:8004"})
        assert result.status_code == 403


@pytest.mark.asyncio
async def test_production_does_not_accept_loopback_origin(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_BASE_URL", "https://repoworld.example")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="https://repoworld.example") as client:
        session = (await client.get("/api/session")).json()
        result = await client.post("/api/tour", json={"graph": build_demo()},
                                   headers={"Origin": "http://localhost:8004", "X-RepoWorld-CSRF": session["csrf"]})
        assert result.status_code == 403
        ok = await client.post("/api/tour", json={"graph": build_demo()},
                               headers={"Origin": "https://repoworld.example", "X-RepoWorld-CSRF": session["csrf"]})
        assert ok.status_code == 200
