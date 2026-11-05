#!/usr/bin/env python3
"""Non-mutating local origin/CSRF check: sends no GitHub or model API requests.

The script creates an anonymous session and calls the read-only static tour
builder. It does not print tokens, cookies, environment variables or API keys.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlsplit

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.demo import build_demo


def main() -> int:
    parser = argparse.ArgumentParser(description='Check the running RepoWorld server and local origin policy')
    parser.add_argument('--base', default='http://127.0.0.1:8004',
                        help='local server URL, default http://127.0.0.1:8004')
    args = parser.parse_args()
    parsed = urlsplit(args.base)
    if (parsed.scheme != 'http' or parsed.hostname not in {'localhost','127.0.0.1','::1'}
            or parsed.path not in {'','/'} or parsed.query or parsed.fragment):
        parser.error('Only local HTTP loopback URLs are supported.')
    port = parsed.port or 80
    if not 1 <= port <= 65535:
        parser.error('Invalid local port.')
    base = args.base.rstrip('/')
    origins = [f'http://localhost:{port}', f'http://127.0.0.1:{port}']
    print('RepoWorld local origin check (no credentials displayed)')
    try:
        with httpx.Client(base_url=base, timeout=7) as client:
            response = client.get('/api/health')
            if response.status_code != 200:
                print('Health:', response.status_code)
                return 1
            version = response.json().get('version','unknown')
            print('Server version:', version)
            if version != '0.9.7':
                print('The running server is not v0.9.7. Stop the old server before testing this fix.')
                return 1
            session = client.get('/api/session')
            if session.status_code != 200:
                print('Session status:', session.status_code)
                return 1
            csrf = session.json().get('csrf')
            if not csrf:
                print('Missing session verification token.')
                return 1
            for origin in origins:
                resp = client.post('/api/tour', json={'graph':build_demo()},
                                   headers={'Origin':origin,'X-RepoWorld-CSRF':csrf})
                print(f'Origin {origin}: HTTP {resp.status_code}')
                if resp.status_code != 200:
                    try:
                        message = resp.json().get('detail') or resp.json().get('error')
                    except ValueError:
                        message = 'unreadable response'
                    print('Reason:', str(message)[:220])
                    return 1
            blocked = client.post('/api/tour',json={'graph':build_demo()},
                                  headers={'Origin':'https://untrusted.example',
                                           'X-RepoWorld-CSRF':csrf})
            print('Untrusted origin correctly blocked:',blocked.status_code==403)
            if blocked.status_code!=403:
                return 1
            print('PASS: The running local server accepts both loopback aliases and blocks external origins.')
            return 0
    except (httpx.HTTPError,ValueError) as exc:
        print('Connection problem:',type(exc).__name__)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
