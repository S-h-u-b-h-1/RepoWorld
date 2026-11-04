"""Anonymous, browser-scoped workspaces for the no-login RepoWorld hackathon demo.

Each browser receives a random HttpOnly SameSite cookie and its own saved
public-repository snapshots. No GitHub or Google identity, email or OAuth token
is collected. Losing the browser cookie loses access to that anonymous workspace.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import HTTPException, Request, Response

SESSION_COOKIE = "rw_session"
SESSION_AGE = 14 * 24 * 3600
MAX_REPOS = 6


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _data_path() -> Path:
    return Path(os.environ.get("REPOWORLD_DB_PATH") or Path(__file__).resolve().parent.parent / ".data" / "repoworld.sqlite3")


def _database() -> sqlite3.Connection:
    path = _data_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    # Keep the earlier schema to preserve snapshots and still-valid local-preview cookies.
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY, provider TEXT NOT NULL, provider_id TEXT NOT NULL,
        name TEXT NOT NULL, username TEXT NOT NULL, avatar TEXT NOT NULL DEFAULT '',
        email TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL,
        UNIQUE(provider,provider_id)
    );
    CREATE TABLE IF NOT EXISTS sessions (
        token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        csrf TEXT NOT NULL, expires_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS repositories (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        owner TEXT NOT NULL, repo TEXT NOT NULL, graph_json TEXT NOT NULL,
        created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
        UNIQUE(user_id,owner,repo)
    );
    CREATE TABLE IF NOT EXISTS preferences (
        user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        active_repo TEXT
    );
    """)
    return conn


def base_url() -> str:
    # Render supplies a trustworthy HTTPS URL at runtime. Prefer an explicit
    # custom APP_BASE_URL when present; never derive public origins from Host.
    value = (os.environ.get("APP_BASE_URL") or os.environ.get("RENDER_EXTERNAL_URL")
             or "http://127.0.0.1:8004").rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise RuntimeError("APP_BASE_URL must be an origin, e.g. https://app.example.com")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("APP_BASE_URL requires HTTPS for public hosts")
    return value


def cookie_secure() -> bool:
    return base_url().startswith("https://")


def session_user(request: Request) -> tuple[dict, str, str] | None:
    raw = request.cookies.get(SESSION_COOKIE, "")
    if not raw or len(raw) > 256:
        return None
    with _database() as db:
        row = db.execute("""SELECT u.*, s.csrf, s.expires_at FROM sessions s
            JOIN users u ON u.id=s.user_id WHERE s.token_hash=?""", (_hash(raw),)).fetchone()
        if not row or row["expires_at"] <= int(time.time()):
            return None
        # Old local-preview workspaces may be reused after an upgrade; do not
        # require a new identity or expose personal data in the guest UI.
        return {"name": "Guest Explorer", "provider": "guest"}, row["id"], row["csrf"]


def ensure_guest_session(request: Request, response: Response) -> tuple[dict, str, str]:
    existing = session_user(request)
    if existing:
        return existing
    now = int(time.time())
    user_id = str(uuid4())
    raw_token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    with _database() as db:
        # Opportunistic expiry cleanup; snapshots of older guest workspaces
        # must not remain indefinitely after their sessions have expired.
        db.execute("DELETE FROM sessions WHERE expires_at<?", (now,))
        db.execute("""DELETE FROM users WHERE provider='guest' AND id NOT IN
            (SELECT user_id FROM sessions)""")
        db.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?)",
                   (user_id, "guest", user_id, "Guest Explorer", "guest", "", "", now))
        db.execute("INSERT INTO sessions VALUES (?,?,?,?)", (_hash(raw_token), user_id, csrf, now + SESSION_AGE))
        db.execute("INSERT INTO preferences(user_id,active_repo) VALUES (?,NULL)", (user_id,))
    response.set_cookie(SESSION_COOKIE, raw_token, max_age=SESSION_AGE, httponly=True,
                        secure=cookie_secure(), samesite="lax", path="/")
    return {"name": "Guest Explorer", "provider": "guest"}, user_id, csrf



def _origin_parts(value: str) -> tuple[str, str, int] | None:
    """Return a strict (scheme, host, port) triple for an HTTP(S) origin.

    Reject paths, credentials and malformed ports rather than comparing raw
    strings or trusting a forwarded Host header.
    """
    try:
        part = urlsplit(value)
        if (part.scheme not in {"http", "https"} or not part.hostname
                or part.username is not None or part.password is not None
                or part.path or part.query or part.fragment):
            return None
        port = part.port or (443 if part.scheme == "https" else 80)
        return part.scheme, part.hostname.lower().rstrip("."), port
    except (ValueError, TypeError):
        return None


def _is_allowed_origin(request: Request, origin: str) -> bool:
    """Allow the configured origin, or equivalent *loopback* origins in dev.

    A local import is legitimate if a browser and the server use different
    names for the SAME loopback port, e.g. Origin localhost:8004 and Host
    127.0.0.1:8004. Never relax non-loopback/production origins. CSRF remains
    independently required for every write.
    """
    configured = _origin_parts(base_url())
    incoming = _origin_parts(origin)
    if not configured or not incoming:
        return False

    # Public deployment must use the configured HTTPS origin exactly.
    if os.environ.get("APP_ENV", "development").lower() == "production":
        return origin == base_url()

    loopback = {"localhost", "127.0.0.1", "::1"}
    # Validate the *actual* Host header, not just the advertised app URL.
    host_header = request.headers.get("host", "")
    request_host = _origin_parts(f"http://{host_header}")
    if configured[0] == "http" and configured[1] in loopback:
        return bool(
            incoming[0] == "http" and incoming[1] in loopback and
            request_host and request_host[1] in loopback and
            configured[2] == incoming[2] == request_host[2]
        )

    # In dev, a non-loopback origin still needs to match the declared origin.
    # This is useful when testing behind a correctly configured HTTPS tunnel.
    return origin == base_url()


def require_user(request: Request, *, mutation: bool = False) -> tuple[dict, str, str]:
    result = session_user(request)
    if not result:
        raise HTTPException(401, detail="Open RepoWorld in this browser to initialize your workspace.")
    if mutation:
        csrf = request.headers.get("X-RepoWorld-CSRF", "")
        if not csrf or not secrets.compare_digest(csrf, result[2]):
            raise HTTPException(403, detail="Workspace verification failed. Reload and try again.")
        origin = request.headers.get("origin")
        if origin and not _is_allowed_origin(request, origin):
            if os.environ.get("APP_ENV", "development").lower() != "production":
                raise HTTPException(403, detail=(
                    "RepoWorld rejected the browser origin. Open the same local server at "
                    f"{base_url()} and reload. If using a proxy, set APP_BASE_URL "
                    "to the exact browser origin."
                ))
            raise HTTPException(403, detail="Cross-origin changes are not allowed.")
    return result


def repo_summaries(user_id: str) -> tuple[list[dict], str | None]:
    with _database() as db:
        rows = db.execute("SELECT id,owner,repo,created_at,updated_at FROM repositories WHERE user_id=? ORDER BY updated_at DESC", (user_id,)).fetchall()
        pref = db.execute("SELECT active_repo FROM preferences WHERE user_id=?", (user_id,)).fetchone()
    items = [{"id": r["id"], "owner": r["owner"], "name": r["repo"],
              "fullName": f"{r['owner']}/{r['repo']}", "updatedAt": r["updated_at"]} for r in rows]
    active = pref["active_repo"] if pref else None
    if active and not any(item["id"] == active for item in items):
        active = None
    return items, active


def save_repo(user_id: str, graph: dict) -> dict:
    blob = json.dumps(graph, separators=(",", ":"), ensure_ascii=False)
    if len(blob) > 2_500_000:
        raise HTTPException(413, detail="This repository snapshot exceeds the storage limit.")
    owner, name = graph["owner"], graph["name"]
    now = int(time.time())
    with _database() as db:
        row = db.execute("SELECT id FROM repositories WHERE user_id=? AND owner=? AND repo=?",
                         (user_id, owner, name)).fetchone()
        if not row:
            count = db.execute("SELECT COUNT(*) FROM repositories WHERE user_id=?", (user_id,)).fetchone()[0]
            if count >= MAX_REPOS:
                raise HTTPException(429, detail=f"This browser has reached its {MAX_REPOS}-repository demo limit. Remove an old city first.")
        rid = row["id"] if row else str(uuid4())
        if row:
            db.execute("UPDATE repositories SET graph_json=?,updated_at=? WHERE id=? AND user_id=?",
                       (blob, now, rid, user_id))
        else:
            db.execute("INSERT INTO repositories VALUES(?,?,?,?,?,?,?)",
                       (rid, user_id, owner, name, blob, now, now))
        db.execute("INSERT INTO preferences(user_id,active_repo) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET active_repo=excluded.active_repo", (user_id, rid))
    return {"id": rid, "graph": graph}


def stored_repo(user_id: str, repo_id: str) -> dict:
    with _database() as db:
        row = db.execute("SELECT graph_json FROM repositories WHERE id=? AND user_id=?", (repo_id, user_id)).fetchone()
    if not row:
        raise HTTPException(404, detail="Repository not found in this browser workspace.")
    return json.loads(row["graph_json"])


def choose_repo(user_id: str, repo_id: str | None) -> None:
    if repo_id:
        stored_repo(user_id, repo_id)
    with _database() as db:
        db.execute("INSERT INTO preferences(user_id,active_repo) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET active_repo=excluded.active_repo", (user_id, repo_id))


def delete_repo(user_id: str, repo_id: str) -> None:
    with _database() as db:
        cur = db.execute("DELETE FROM repositories WHERE id=? AND user_id=?", (repo_id, user_id))
        if not cur.rowcount:
            raise HTTPException(404, detail="Repository not found in this browser workspace.")
        db.execute("UPDATE preferences SET active_repo=NULL WHERE user_id=? AND active_repo=?", (user_id, repo_id))
