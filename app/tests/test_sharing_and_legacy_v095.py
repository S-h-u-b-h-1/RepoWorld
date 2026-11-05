"""Launch-safe anonymous sharing and retirement of unbudgeted legacy importing."""
from __future__ import annotations

import httpx
import pytest

from app import main


@pytest.mark.asyncio
async def test_old_repository_get_is_retired_without_fetching_github(monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("The legacy GET route must not contact GitHub")
    monkeypatch.setattr(main, "get_repository_graph", forbidden)
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8004") as client:
        result = await client.get("/api/repository?url=known-owner/real-repo")
        assert result.status_code == 410
        assert "retired" in result.json()["detail"].lower()
        assert result.headers["cache-control"] == "no-store"
        assert (await client.get("/api/health")).json()["version"] == "0.9.8"


@pytest.mark.asyncio
async def test_guest_api_session_keeps_secret_bearing_tokens_out_of_shareable_url(tmp_path, monkeypatch):
    monkeypatch.setenv("REPOWORLD_DB_PATH", str(tmp_path / "anonymous.sqlite3"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                 base_url="http://127.0.0.1:8004") as client:
        response = await client.get("/api/session")
        assert response.status_code == 200
        assert response.json()["guest"] is True
        assert response.json()["csrf"]
        # Sharing requires no server endpoint, no public guest identity and
        # no automated model/API calls. Query parameters are client hints only.
        homepage = await client.get("/?repo=openwisp%2Fopenwisp-utils")
        assert homepage.status_code == 200
        assert "RepoWorld" in homepage.text
        assert "repo=" not in homepage.text
