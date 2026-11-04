"""No-signup guest workspaces: isolation, session cookies, CSRF and persistence."""
import httpx
import pytest

import app.auth as auth
import app.main as main
from app.demo import build_demo


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("REPOWORLD_DB_PATH", str(tmp_path / "guest.sqlite3"))
    monkeypatch.setenv("APP_BASE_URL", "http://127.0.0.1:8004")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("BHARATCODE_API_KEY", raising=False)
    main._request_times.clear()


def client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url="http://127.0.0.1:8004")


@pytest.mark.asyncio
async def test_first_visit_creates_private_guest_without_oauth():
    async with client() as http:
        first=await http.get("/api/session")
        assert first.status_code==200
        assert first.json()["guest"] is True
        assert first.json()["authenticated"] is True
        assert first.json()["repositories"]==[]
        assert first.json()["csrf"]
        assert "rw_session=" in first.headers["set-cookie"]
        assert "httponly" in first.headers["set-cookie"].lower()
        assert "samesite=lax" in first.headers["set-cookie"].lower()
        session_cookie=http.cookies.get("rw_session")
        again=await http.get("/api/session")
        assert again.json()["csrf"]==first.json()["csrf"]
        assert http.cookies.get("rw_session")==session_cookie
        assert (await http.get("/auth/github/start")).status_code==404
        assert (await http.get("/auth/google/start")).status_code==404
        assert (await http.post("/auth/preview")).status_code==404
        assert (await http.post("/api/logout")).status_code==404


@pytest.mark.asyncio
async def test_silent_guest_cannot_write_until_session_initialized():
    async with client() as http:
        assert (await http.get("/api/my-repos/not-owned")).status_code==401
        assert (await http.post("/api/tour",json={"graph":build_demo()})).status_code==401
        first=await http.get("/api/session")
        assert first.status_code==200
        assert (await http.post("/api/tour",json={"graph":build_demo()})).status_code==403
        csrf=first.json()["csrf"]
        assert (await http.post("/api/tour",json={"graph":build_demo()},headers={"X-RepoWorld-CSRF":csrf,"Origin":"https://attack.example"})).status_code==403
        ok=await http.post("/api/tour",json={"graph":build_demo()},headers={"X-RepoWorld-CSRF":csrf})
        assert ok.status_code==200


@pytest.mark.asyncio
async def test_guest_city_persists_on_same_browser_but_cannot_be_read_by_second_browser(monkeypatch):
    async def fake_graph(url):
        assert url=="testorg/sample"
        g=build_demo()
        g.update(name="sample",owner="testorg",url="https://github.com/testorg/sample",branch="main",source="github")
        return g
    monkeypatch.setattr(main,"get_repository_graph",fake_graph)
    async with client() as browser1, client() as browser2:
        csrf1=(await browser1.get("/api/session")).json()["csrf"]
        assert (await browser1.post("/api/my-repos",json={"url":"testorg/sample"})).status_code==403
        imported=await browser1.post("/api/my-repos",json={"url":"testorg/sample"},headers={"X-RepoWorld-CSRF":csrf1})
        assert imported.status_code==200
        rid=imported.json()["id"]
        reloaded=(await browser1.get("/api/session")).json()
        assert reloaded["activeRepo"]==rid and reloaded["repositories"][0]["fullName"]=="testorg/sample"
        assert (await browser1.get("/api/my-repos/"+rid)).status_code==200
        second=(await browser2.get("/api/session")).json()
        assert second["repositories"]==[]
        assert second["csrf"]!=csrf1
        assert (await browser2.get("/api/my-repos/"+rid)).status_code==404
        assert (await browser2.get("/api/my-repos/"+rid+"/issues")).status_code==404
        assert (await browser1.post("/api/me/active",json={"repoId":None},headers={"X-RepoWorld-CSRF":csrf1})).status_code==200
        assert (await browser1.get("/api/session")).json()["activeRepo"] is None
        assert (await browser1.post("/api/me/active",json={"repoId":rid},headers={"X-RepoWorld-CSRF":csrf1})).status_code==200


@pytest.mark.asyncio
async def test_new_browser_cookie_cannot_access_old_city(monkeypatch):
    async def fake_graph(url):
        g=build_demo()
        g.update(name="sample",owner="testorg",url="https://github.com/testorg/sample",source="github")
        return g
    monkeypatch.setattr(main,"get_repository_graph",fake_graph)
    async with client() as browser:
        csrf=(await browser.get("/api/session")).json()["csrf"]
        rid=(await browser.post("/api/my-repos",json={"url":"testorg/sample"},headers={"X-RepoWorld-CSRF":csrf})).json()["id"]
        browser.cookies.clear()
        new_session=(await browser.get("/api/session")).json()
        assert new_session["activeRepo"] is None
        assert new_session["csrf"]!=csrf
        assert (await browser.get("/api/my-repos/"+rid)).status_code==404


@pytest.mark.asyncio
async def test_saved_city_limit_with_refresh_allowed():
    with auth._database() as db:
        db.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?)",("u", "guest", "u", "Guest", "guest", "", "", 1))
    for i in range(auth.MAX_REPOS):
        graph=build_demo();graph.update(owner="test",name="repo-"+str(i))
        auth.save_repo("u",graph)
    with pytest.raises(Exception) as error:
        graph=build_demo();graph.update(owner="test",name="another")
        auth.save_repo("u",graph)
    assert error.value.status_code==429
    graph=build_demo();graph.update(owner="test",name="repo-0")
    assert auth.save_repo("u",graph)["id"]


def test_secure_cookie_requires_https_for_public_domain(monkeypatch):
    monkeypatch.setenv("APP_BASE_URL","https://repoworld.example")
    assert auth.cookie_secure() is True
    monkeypatch.setenv("APP_BASE_URL","http://repoworld.example")
    with pytest.raises(RuntimeError):auth.base_url()

@pytest.mark.asyncio
async def test_public_ai_cannot_use_arbitrary_graph_to_spend_model_quota(monkeypatch):
    async def fake_graph(url):
        g=build_demo()
        g.update(name="sample",owner="testorg",url="https://github.com/testorg/sample",source="github")
        return g
    async def stub_model(graph):
        return {"mode":"ai","steps":[]}
    monkeypatch.setattr(main,"get_repository_graph",fake_graph)
    monkeypatch.setattr(main,"make_ai_tour",stub_model)
    async with client() as http:
        csrf=(await http.get("/api/session")).json()["csrf"]
        hdr={"X-RepoWorld-CSRF":csrf}
        assert (await http.post("/api/ai/tour",json={"graph":build_demo()},headers=hdr)).status_code==403
        imported=(await http.post("/api/my-repos",json={"url":"testorg/sample"},headers=hdr)).json()
        assert (await http.post("/api/ai/tour",json={"graph":imported["graph"]},headers=hdr)).status_code==200
        tampered=dict(imported["graph"]);tampered["name"]="not-the-saved-one"
        assert (await http.post("/api/ai/tour",json={"graph":tampered},headers=hdr)).status_code==403
