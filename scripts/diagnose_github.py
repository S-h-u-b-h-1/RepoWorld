"""Check public GitHub REST import access without printing or transmitting secrets.

Run from the RepoWorld directory:
  python scripts/diagnose_github.py openwisp/openwisp-utils
  python scripts/diagnose_github.py openwisp/openwisp-utils --tree

Default performs ONE GitHub metadata request. --tree makes a second tree request.
No browser login, OAuth, or personal access token is required for public repos.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import sys
from time import monotonic
from urllib.parse import quote

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env', override=False)
sys.path.insert(0, str(ROOT))
from app.github import parse_repository, RepoError, GH_API  # noqa: E402


async def check(repo_value: str, tree: bool) -> int:
    try:
        owner, repo = parse_repository(repo_value)
    except RepoError as exc:
        print(f'Invalid repository URL: {exc.detail}')
        return 2
    token = os.getenv('GITHUB_TOKEN', '').strip()
    headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
               'User-Agent': 'RepoWorld-Import-Diagnostic/0.9.1'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    print('GitHub importer diagnostic — no secrets displayed')
    print('Public repository:', f'{owner}/{repo}')
    print('Server token present:', 'yes' if token else 'no (public imports supported)')
    async with httpx.AsyncClient(timeout=httpx.Timeout(16, connect=6), follow_redirects=False) as client:
        base = f'{GH_API}/repos/{quote(owner, safe="")}/{quote(repo, safe="")}'
        paths = [base]
        data = None
        for url in paths:
            start = monotonic()
            try:
                response = await client.get(url, headers=headers)
            except httpx.RequestError as exc:
                print('GitHub request failed:', type(exc).__name__)
                return 1
            print('HTTP status:', response.status_code)
            print('Elapsed seconds:', round(monotonic() - start, 2))
            print('Rate limit remaining:', response.headers.get('X-RateLimit-Remaining', 'not supplied'))
            print('Rate limit reset (Unix seconds):', response.headers.get('X-RateLimit-Reset', 'not supplied'))
            print('Retry-After seconds:', response.headers.get('Retry-After', 'not supplied'))
            if response.status_code != 200:
                print('Result: GitHub API did not accept the request. No import attempted.')
                return 1
            try:
                data = response.json()
            except ValueError:
                print('Result: GitHub returned invalid JSON')
                return 1
        if data.get('private') is not False:
            print('Result: Repository is not confirmed public')
            return 1
        print('Public repository metadata: verified')
        if tree:
            branch = str(data.get('default_branch') or 'main')
            start = monotonic()
            try:
                result = await client.get(base + '/git/trees/' + quote(branch, safe=''),
                                          headers=headers, params={'recursive': 1})
            except httpx.RequestError as exc:
                print('Tree request failed:', type(exc).__name__)
                return 1
            print('Git tree HTTP status:', result.status_code)
            print('Tree elapsed seconds:', round(monotonic()-start, 2))
            print('Rate limit remaining:', result.headers.get('X-RateLimit-Remaining', 'not supplied'))
            if result.status_code != 200:
                return 1
            try:
                graph=result.json()
            except ValueError:
                print('Tree returned invalid JSON')
                return 1
            print('Git tree entries:', len(graph.get('tree', [])))
            print('Tree truncated:', bool(graph.get('truncated')))
        print('Result: GitHub metadata access works. RepoWorld import has additional steps.')
        return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Safe public GitHub API import diagnostics')
    parser.add_argument('repository', nargs='?', default='openwisp/openwisp-utils')
    parser.add_argument('--tree', action='store_true', help='Also read the Git tree (one more request)')
    args = parser.parse_args()
    raise SystemExit(asyncio.run(check(args.repository, args.tree)))
