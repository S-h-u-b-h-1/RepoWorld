"""Safe, read-only launch smoke test against a deployed RepoWorld origin.

By default this checks no GitHub or BharatCode endpoints that spend API quota.
Explicit --import adds an end-to-end public import + Issue Radar check.
Never prints auth cookies, CSRF tokens or secret environment values.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlsplit

# Support direct invocation: python scripts/smoke_hosted.py ...
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.github import parse_repository, RepoError
from app.main import app as repoworld_app


def _origin(value: str, *, allow_local: bool = False) -> str:
    parsed=urlsplit(value.rstrip('/'))
    if parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password or not parsed.hostname:
        raise ValueError('Enter only the website origin (no path or query).')
    if parsed.scheme == 'https':
        return value.rstrip('/')
    if allow_local and parsed.scheme == 'http' and parsed.hostname in ('localhost','127.0.0.1'):
        return value.rstrip('/')
    raise ValueError('Public smoke testing requires an HTTPS URL.')


def run(origin: str, *, import_repo: str | None = None, allow_local: bool = False,
        transport: httpx.BaseTransport | None = None, require_ai: bool = False,
        verify_live_ai: bool = False, require_source_evidence: bool = False,
        allow_browser_issues_fallback: bool = False) -> list[str]:
    if (verify_live_ai or require_source_evidence) and not import_repo:
        raise ValueError('Live AI checks require --import-repo to identify a saved public city.')
    if require_source_evidence and not verify_live_ai:
        raise ValueError('--require-source-evidence also requires --verify-live-ai.')
    require_ai = require_ai or verify_live_ai
    origin=_origin(origin, allow_local=allow_local)
    notes=[]
    def check(condition: bool, label: str):
        if not condition:
            raise RuntimeError(label)
        notes.append('PASS '+label)

    with httpx.Client(base_url=origin, transport=transport, timeout=30, follow_redirects=False) as client:
        health=client.get('/api/health')
        check(health.status_code==200 and health.json().get('ok') is True, 'Health endpoint')
        check(health.json().get('version') == repoworld_app.version,
              f'Deployed backend matches source version {repoworld_app.version}')
        ready=client.get('/api/ready')
        check(ready.status_code==200 and ready.json().get('ready') is True, 'Deployment readiness')
        image=client.get('/api/ready.svg')
        check(image.status_code==200 and 'image/svg+xml' in image.headers.get('content-type','')
              and image.headers.get('cache-control')=='no-store', 'Launcher readiness SVG')
        index=client.get('/')
        check(index.status_code==200 and 'RepoWorld' in index.text, 'Website homepage')
        browser_issues=client.get('/static/browser-radar.js')
        check(browser_issues.status_code==200 and 'RepoWorldBrowserIssueRadar' in browser_issues.text, 'Browser-direct Issue Radar available')
        check(index.headers.get('x-frame-options')=='DENY', 'Frame protection')
        check(index.headers.get('cache-control')=='no-cache', 'Frontend updates revalidate')
        if not allow_local:
            check('max-age=' in index.headers.get('strict-transport-security',''), 'HTTPS transport policy')
        session=client.get('/api/session')
        check(session.status_code==200 and session.json().get('guest') is True, 'Anonymous workspace')
        status=client.get('/api/status')
        check(status.status_code==200 and isinstance(status.json().get('aiConfigured'),bool), 'AI capability status')
        configured=status.json()['aiConfigured']
        check(session.json().get('aiConfigured') is configured, 'Session and AI status agree')
        if require_ai:
            check(configured, 'BharatCode key configured on host (not a live model test)')
        elif not configured:
            notes.append('WARN BharatCode not configured on host; deterministic guidance is not AI inference.')
        check(bool(session.json().get('csrf')), 'Workspace CSRF configured')
        cookie=session.headers.get('set-cookie','').lower()
        check('httponly' in cookie or bool(client.cookies.get('rw_session')), 'Session cookie created')
        if not allow_local:
            check('secure' in cookie, 'Secure session cookie')
        check(client.get('/api/repository?url=x/y').status_code==410, 'Legacy unbudgeted import is closed')

        if import_repo:
            try:
                owner, repo = parse_repository(import_repo)
            except RepoError as exc:
                raise ValueError(exc.detail) from exc
            payload={'url':f'{owner}/{repo}'}
            response=client.post('/api/my-repos', json=payload,
                                 headers={'Origin':origin,'X-RepoWorld-CSRF':session.json()['csrf']},
                                 timeout=90)
            check(response.status_code==200, f'Public import {owner}/{repo} (HTTP {response.status_code})')
            item=response.json()
            check(bool(item.get('graph',{}).get('nodes')), 'Imported city has buildings')
            issues=client.get(f"/api/my-repos/{item['id']}/issues", timeout=45)
            if issues.status_code==429 and allow_browser_issues_fallback:
                try:
                    error=str(issues.json().get('error') or issues.json().get('detail') or '').lower()
                except (ValueError,AttributeError):
                    error=''
                # Never bypass RepoWorld's own budget/guest 429. This flag only
                # continues past a clearly identified provider GitHub quota.
                check('github' in error and 'rate limit' in error,
                      'Only GitHub provider 429 may use browser-fallback smoke mode')
                notes.append('WARN Server GitHub Issue Radar is provider-rate-limited. Browser fallback exists but was not browser-tested here.')
            else:
                check(issues.status_code==200 and isinstance(issues.json().get('issues'),list), 'GitHub Issue Radar')
            if verify_live_ai:
                question=('Using only public repository evidence, identify a source module '
                          'to inspect first and say what remains unknown.')
                model_response=client.post(
                    f"/api/my-repos/{item['id']}/assistant",
                    json={'question':question},
                    headers={'Origin':origin,'X-RepoWorld-CSRF':session.json()['csrf']},
                    timeout=245,
                )
                check(model_response.status_code==200,
                      f'BharatCode assistant route (HTTP {model_response.status_code})')
                answer=model_response.json()
                check(answer.get('mode')=='ai' and answer.get('model')=='qwen-3.8-27b'
                      and isinstance(answer.get('answer'),str) and bool(answer['answer'].strip()),
                      'BharatCode real model response (not navigation fallback)')
                cited=any(isinstance(s,dict) and s.get('evidence')=='excerpt'
                          for s in answer.get('sources',[]))
                if require_source_evidence:
                    check(answer.get('sourceFilesRead',0)>0 and cited,
                          'Model answer includes inspected public source evidence')
                elif not cited:
                    notes.append('WARN Model replied, but inspected source citations were not confirmed.')
            else:
                notes.append('INFO No BharatCode model calls made; use --verify-live-ai explicitly.')
        else:
            notes.append('INFO No GitHub import or BharatCode model calls made.')
    return notes


def main():
    parser=argparse.ArgumentParser(description='RepoWorld hosted smoke check (does not reveal secrets)')
    parser.add_argument('url',help='Public HTTPS origin such as https://repoworld.onrender.com')
    parser.add_argument('--import-repo',default=None,help='Optional public owner/repo (spends import budget)')
    parser.add_argument('--allow-local',action='store_true',help='Use HTTP loopback for development')
    parser.add_argument('--require-ai',action='store_true',help='Fail if BharatCode is not configured (no model call)')
    parser.add_argument('--verify-live-ai',action='store_true',help='Spend one explicitly requested model call after import')
    parser.add_argument('--require-source-evidence',action='store_true',help='Require a fetched source excerpt in the model answer')
    parser.add_argument('--allow-browser-issues-fallback',action='store_true',
                        help='Continue past provider-specific GitHub issue 429; does NOT verify actual browser CORS')
    args=parser.parse_args()
    try:
        for note in run(args.url,import_repo=args.import_repo,allow_local=args.allow_local,
                        require_ai=args.require_ai,verify_live_ai=args.verify_live_ai,
                        require_source_evidence=args.require_source_evidence,
                        allow_browser_issues_fallback=args.allow_browser_issues_fallback):
            print(note)
        return 0
    except (ValueError, RuntimeError, httpx.RequestError, KeyError, TypeError) as exc:
        print('FAIL '+str(exc),file=sys.stderr)
        return 1

if __name__=='__main__':raise SystemExit(main())
