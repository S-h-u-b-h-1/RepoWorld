"""RepoWorld v0.9.11: city, anonymous sharing, and public-launch safeguards."""
from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
import logging
import os
import time

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .ai import answer_question, build_static_tour, has_key, make_ai_tour
from .assistant import guide_question
from .issues import fetch_issue_radar
from .auth import (choose_repo, delete_repo, ensure_guest_session, repo_summaries,
                   require_user, save_repo, session_user, stored_repo)
from .demo import build_demo
from .github import RepoError, get_repository_graph, parse_repository
from .intelligence import find_modules, impact_trace
from .quotas import reserve_ai, reserve_import, reserve_refresh
from .request_limits import RequestBodyLimit

APP_ROOT = Path(__file__).resolve().parent
app = FastAPI(title="RepoWorld", description="Explore a repository as a living city", version="0.9.11", docs_url="/api/docs", redoc_url=None)
app.add_middleware(RequestBodyLimit)
logger = logging.getLogger("repoworld.import")
app.mount("/static", StaticFiles(directory=str(APP_ROOT / "static")), name="static")
_request_times: dict[str, deque] = defaultdict(deque)


class GraphRequest(BaseModel):
    graph: dict


class AskRequest(BaseModel):
    graph: dict
    question: str = Field(min_length=1, max_length=450)


class ImportRequest(BaseModel):
    url: str = Field(min_length=3, max_length=240)
    refresh: bool = False


class ChooseRequest(BaseModel):
    repoId: str | None


class DeveloperQuestion(BaseModel):
    question: str = Field(min_length=3, max_length=650)
    nodeId: str | None = Field(default=None, max_length=450)
    issueNumber: int | None = Field(default=None, ge=1)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=6)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data: https://avatars.githubusercontent.com https://lh3.googleusercontent.com "
        "https://lh4.googleusercontent.com https://lh5.googleusercontent.com https://lh6.googleusercontent.com; "
        "connect-src 'self' https://api.github.com; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if os.getenv("APP_ENV") == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # The single-page entrypoint and JS/CSS must revalidate after deployments.
    if request.url.path == "/" or request.url.path in {"/static/app.js", "/static/browser-radar.js", "/static/investigation-notes.js", "/static/world.js", "/static/styles.css"}:
        response.headers["Cache-Control"] = "no-cache"
    if request.url.path.startswith("/api/") or request.url.path.startswith("/auth/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RepoError)
async def repo_error_handler(_request: Request, error: RepoError):
    return JSONResponse(status_code=error.status, content={"error": error.detail},
                        headers={"Retry-After":str(error.retry_after)} if hasattr(error,"retry_after") else None)


def _limit(request: Request, bucket: str, *, count: int = 8, window: int = 300):
    ip = request.client.host if request.client else "unknown"
    key = f"{bucket}:{ip}"
    now = time.monotonic()
    times = _request_times[key]
    while times and times[0] < now - window:
        times.popleft()
    if len(times) >= count:
        raise RepoError("Too many requests. Try again shortly.", 429)
    times.append(now)
    if len(_request_times) > 2000:
        _request_times.clear()


def _body_limit(request: Request, max_bytes: int = 160_000) -> None:
    size = request.headers.get("content-length")
    if size and size.isdigit() and int(size) > max_bytes:
        raise RepoError("Request is too large.", 413)


@app.get("/", include_in_schema=False)
async def home():
    return FileResponse(APP_ROOT / "static" / "index.html")


@app.get("/api/health")
async def health():
    """Liveness probe; does not imply the production setup is safe."""
    return {"ok": True, "product": "RepoWorld", "version": "0.9.11"}


@app.get("/api/ready")
async def ready():
    """Deployment readiness; never return credentials or detailed env values."""
    if os.getenv('APP_ENV') == 'production':
        from .auth import base_url, _database, _data_path
        try:
            url=base_url()
            storage=_data_path()
            ephemeral_demo = os.getenv('REPOWORLD_EPHEMERAL_DEMO') == '1'
            if not url.startswith('https://') or not storage.is_absolute():
                raise ValueError('Missing production HTTPS origin or absolute storage path')
            if not has_key() and not ephemeral_demo:
                raise ValueError('Missing BharatCode key for durable production configuration')
            if ephemeral_demo:
                # Intentional free-tier preview: anonymous workspaces and quotas
                # reset when Render spins down, restarts or redeploys. The API
                # must not quietly accept a purported mounted disk in this mode.
                if os.getenv('REPOWORLD_REQUIRE_MOUNTED_DB') == '1':
                    raise ValueError('Ephemeral demo cannot require mounted storage')
            elif os.getenv('REPOWORLD_REQUIRE_MOUNTED_DB') == '1' and not os.path.ismount(storage.parent):
                raise ValueError('Production database directory is not a mounted persistent disk')
            with _database() as db:
                db.execute('SELECT 1').fetchone()
        except Exception:
            return JSONResponse(status_code=503,content={'ready':False})
    return {'ready':True, 'version':'0.9.11'}


_READY_PIXEL_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1" viewBox="0 0 1 1">'
    '<rect width="1" height="1"/></svg>'
)


@app.get("/api/ready.svg", include_in_schema=False)
async def ready_image():
    """Image-based readiness probe for the separate, free static launcher.

    A static favicon can load even when the database is unavailable. Return a
    renderable image only when the same checks as /api/ready succeed. Cross-
    origin image loading does not require exposing readiness JSON via CORS.
    """
    result = await ready()
    if not isinstance(result, dict) or result.get("ready") is not True:
        return Response(status_code=503)
    return Response(content=_READY_PIXEL_SVG, media_type="image/svg+xml")


@app.get("/api/session")
async def get_session(request: Request, response: Response):
    # No signup/login. A random, browser-specific session is created on first visit.
    session = ensure_guest_session(request, response)
    repo_items, active = repo_summaries(session[1])
    return {"authenticated": True, "guest": True, "csrf": session[2],
            "repositories": repo_items, "activeRepo": active,
            "aiConfigured": has_key()}


@app.get("/api/my-repos/{repo_id}")
async def get_saved_repo(request: Request, repo_id: str):
    _profile, uid, _csrf = require_user(request)
    return {"id": repo_id, "graph": stored_repo(uid, repo_id)}


@app.post("/api/my-repos")
async def import_my_repo(request: Request, payload: ImportRequest):
    _body_limit(request)
    _profile, uid, _csrf = require_user(request, mutation=True)
    # Parse before debiting a request quota. Never log user-supplied arbitrary URLs.
    owner, repo = parse_repository(payload.url)
    _limit(request, f"import:{uid}", count=10)
    reserve_import(uid, request.client.host if request.client else "unknown")
    began = time.monotonic()
    try:
        graph = (await get_repository_graph(payload.url, refresh=True)) if payload.refresh else await get_repository_graph(payload.url)
        saved = save_repo(uid, graph)
    except RepoError as exc:
        logger.warning("Public repo import failed: %s/%s, status=%d, elapsed=%.1fs, reason=%s",
                       owner, repo, exc.status, time.monotonic()-began, exc.detail)
        raise
    logger.info("Public repo imported: %s/%s, elapsed=%.1fs, sampled_files=%s",
                owner, repo, time.monotonic()-began, graph.get("stats",{}).get("inspectedSources"))
    return saved


@app.post("/api/me/active")
async def activate_repo(request: Request, payload: ChooseRequest):
    _profile, uid, _csrf = require_user(request, mutation=True)
    choose_repo(uid, payload.repoId)
    return {"ok": True}


@app.delete("/api/my-repos/{repo_id}")
async def remove_my_repo(request: Request, repo_id: str):
    _profile, uid, _csrf = require_user(request, mutation=True)
    delete_repo(uid, repo_id)
    return {"ok": True}


@app.get("/api/status")
async def status():
    return {"aiConfigured": has_key(), "demoAvailable": True,
            "model": "qwen-3.8-27b" if has_key() else None}


@app.get("/api/demo")
async def demo():
    # A fictional fixture for local browser QA, not auto-loaded as a user's city.
    return build_demo()


@app.get("/api/repository", include_in_schema=False)
async def legacy_repository_import():
    """Retire an unused GET endpoint that bypassed persistent import budgets.

    The maintained, CSRF-protected POST /api/my-repos path uses the shared
    anonymous import quota and saves only user-owned public snapshots.
    Do not fetch GitHub or accept a repository query string from this route.
    """
    raise HTTPException(
        status_code=410,
        detail="This older repository endpoint is retired. Use Add GitHub repository in RepoWorld.",
    )


@app.post("/api/tour")
async def tour(request: Request, payload: GraphRequest):
    _body_limit(request)
    require_user(request, mutation=True)
    return build_static_tour(payload.graph)


def _saved_ai_graph(user_id: str, submitted: dict) -> dict:
    """Only allow public AI inference on an actual saved graph in this browser."""
    repos, _active = repo_summaries(user_id)
    for summary in repos:
        graph = stored_repo(user_id, summary["id"])
        if graph == submitted:
            return graph
    raise HTTPException(403, detail="The AI tour must use a repository saved in this browser workspace.")


@app.post("/api/ai/tour")
async def ai_tour(request: Request, payload: GraphRequest):
    _body_limit(request)
    _profile, uid, _csrf = require_user(request, mutation=True)
    graph = _saved_ai_graph(uid, payload.graph)
    _limit(request, f"ai:{uid}", count=8)
    reserve_ai(uid, request.client.host if request.client else "unknown")
    return await make_ai_tour(graph)


@app.post("/api/ai/ask")
async def ai_ask(request: Request, payload: AskRequest):
    _body_limit(request)
    _profile, uid, _csrf = require_user(request, mutation=True)
    graph = _saved_ai_graph(uid, payload.graph)
    _limit(request, f"ai:{uid}", count=8)
    reserve_ai(uid, request.client.host if request.client else "unknown")
    return await answer_question(graph, payload.question)


@app.get("/api/my-repos/{repo_id}/find")
async def locate_code(request: Request, repo_id: str, q: str = Query(min_length=2, max_length=160)):
    """Find likely code modules using server-stored, user-owned repository data."""
    _profile, uid, _csrf = require_user(request)
    _limit(request, f"find:{uid}", count=90, window=300)
    graph = stored_repo(uid, repo_id)
    try:
        return find_modules(graph, q)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/my-repos/{repo_id}/impact")
async def trace_change_impact(request: Request, repo_id: str, nodeId: str = Query(min_length=1, max_length=450)):
    """A bounded, reverse-static-import reachability trace—not runtime behavior."""
    _profile, uid, _csrf = require_user(request)
    _limit(request, f"trace:{uid}", count=90, window=300)
    graph = stored_repo(uid, repo_id)
    try:
        return impact_trace(graph, nodeId)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/my-repos/{repo_id}/issues")
async def issue_radar(request: Request, repo_id: str, refresh: bool = Query(default=False)):
    """Fetch open, public GitHub issues; qualify where a city marker can be placed."""
    _profile, uid, _csrf = require_user(request)
    _limit(request, f"issues:{uid}", count=30, window=300)
    graph = stored_repo(uid, repo_id)
    if refresh: reserve_refresh(uid)
    return await fetch_issue_radar(graph, use_cache=not refresh)


@app.post("/api/my-repos/{repo_id}/assistant")
async def developer_assistant(request: Request, repo_id: str, payload: DeveloperQuestion):
    """Source-scoped guidance for a saved repo, with optional live BharatCode AI."""
    _body_limit(request, 18_000)
    _profile, uid, _csrf = require_user(request, mutation=True)
    # Reverse proxies can expose one shared client IP for all visitors.
    # Key the short-term limit to the already verified anonymous workspace.
    # Persistent global/browser quotas provide the shared provider budget.
    _limit(request, f"assistant:{uid}", count=8, window=600)
    graph = stored_repo(uid, repo_id)
    if payload.nodeId is not None and payload.nodeId not in {n.get("id") for n in graph.get("nodes", []) if isinstance(n, dict)}:
        raise HTTPException(status_code=404, detail="Selected building not found in this repository snapshot.")
    issue = None
    if payload.issueNumber is not None:
        radar = await fetch_issue_radar(graph)
        issue = next((i for i in radar['issues'] if i['number'] == payload.issueNumber), None)
        if issue is None:
            raise HTTPException(status_code=404, detail="Open issue not found in the latest sampled issue list.")
    if has_key():reserve_ai(uid, request.client.host if request.client else "unknown")
    return await guide_question(graph, payload.question, node_id=payload.nodeId, issue=issue, history=payload.history)
