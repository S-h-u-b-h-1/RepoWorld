#!/usr/bin/env python3
"""Check a REAL local RepoWorld import without exposing cookies, keys, or source data.

This performs one public GitHub import and consumes the normal GitHub/API quotas.
It is not an authentication bypass and never reads or sends BHARATCODE_API_KEY.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from dotenv import dotenv_values


def main() -> int:
    parser = argparse.ArgumentParser(description="Test RepoWorld local guest session and import")
    parser.add_argument("repository", nargs="?", default="openwisp/openwisp-utils")
    parser.add_argument("--base", help="Local app origin, default APP_BASE_URL or 127.0.0.1:8004")
    args = parser.parse_args()
    config = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
    base = (args.base or os.getenv("APP_BASE_URL") or config.get("APP_BASE_URL") or "http://127.0.0.1:8004").rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme != "http" or parsed.hostname not in ("localhost", "127.0.0.1", "::1") or parsed.path or parsed.query or parsed.fragment:
        parser.error("This diagnostic only supports an HTTP loopback address.")
    print("RepoWorld local import diagnostic — no credentials displayed")
    print("Local origin:", base)
    print("Repository:", args.repository)
    try:
        with httpx.Client(base_url=base, timeout=httpx.Timeout(75, connect=5), follow_redirects=False) as client:
            health = client.get("/api/health")
            print("Health:", health.status_code, "version:", health.json().get("version") if health.status_code == 200 else "unknown")
            if health.status_code != 200:
                return 1
            session = client.get("/api/session")
            print("Guest session:", session.status_code)
            if session.status_code != 200:
                return 1
            csrf = session.json().get("csrf")
            if not csrf:
                print("Session has no CSRF value; import cannot continue.")
                return 1
            response = client.post("/api/my-repos", json={"url": args.repository},
                                   headers={"Origin": base, "X-RepoWorld-CSRF": csrf})
            print("Import HTTP:", response.status_code)
            try:
                body = response.json()
            except ValueError:
                print("Response was not JSON")
                return 1
            if response.status_code != 200:
                message = str(body.get("detail") or body.get("error") or "Unknown error")
                print("Import error:", message[:340])
                if response.status_code == 403:
                    print("Tip: use the same loopback origin and port in the browser as shown above.")
                retry = response.headers.get("Retry-After")
                if retry and retry.isdigit():
                    print("Retry-After seconds:", retry)
                return 1
            graph = body.get("graph") or {}
            print("Import success:", graph.get("owner"), "/", graph.get("name"))
            print("City buildings:", len(graph.get("nodes") or []))
            print("Static dependency links:", len(graph.get("edges") or []))
            print("Browser session cookie: present, not displayed")
            return 0
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        print("Local connection failed:", type(exc).__name__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
