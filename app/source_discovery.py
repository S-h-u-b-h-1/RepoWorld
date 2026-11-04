"""Conservative, issue-specific source discovery for public GitHub trees.

Only canonical public GitHub tree paths are candidates. A name match is a
retrieval hint, not proof the implementation behaves as an issue describes.
"""
from __future__ import annotations

from pathlib import PurePosixPath
import re

CODE_EXTENSIONS = frozenset({'.py', '.js', '.jsx', '.ts', '.tsx', '.go', '.mjs', '.cjs', '.sql', '.sh'})
_SKIP = frozenset({'the', 'with', 'from', 'that', 'this', 'have', 'when', 'where', 'test', 'tests',
                   'code', 'issue', 'file', 'module', 'feature', 'should', 'could', 'error', 'output',
                   'only', 'using', 'into', 'make', 'support', 'enable', 'get', 'set', 'add', 'var',
                   'webdriver', 'chrome', 'chromedriver', 'firefox', 'openwisp', 'utils', 'python'})
_GENERIC = frozenset({'__init__', 'index', 'main', 'base', 'config', 'settings', 'setup'})
_SYMBOL = re.compile(r'\b(?:[a-zA-Z][a-zA-Z\d]*_[a-zA-Z\d_]{3,}|[A-Z][A-Z_\d]{5,})\b')
_WORD = re.compile(r'[a-z\d]{4,}')


def safe_code_path(path: str) -> bool:
    if not isinstance(path, str) or not 2 < len(path) < 380 or path.startswith('/') or '\\' in path or '\x00' in path:
        return False
    if any(part in ('', '.', '..') or part.startswith('.env') for part in path.split('/')):
        return False
    return PurePosixPath(path).suffix.lower() in CODE_EXTENSIONS


def issue_symbols(issue: dict) -> list[str]:
    """Identifiers in the report are search cues, NEVER verified code facts."""
    title = str(issue.get('title') or '')[:250]
    body = str(issue.get('body') or '')[:4800]
    tokens: list[str] = []
    for part in (title, body):
        for match in _SYMBOL.finditer(part):
            symbol = match.group(0)
            low = symbol.lower()
            if low not in _SKIP and low not in (s.lower() for s in tokens):
                tokens.append(symbol)
            if len(tokens) >= 28:
                return tokens
    return tokens


def rank_issue_paths(paths: list[str], issue: dict) -> list[tuple[int, str]]:
    """Rank by explicit paths and filename evidence, not vague directory matches."""
    title = str(issue.get('title') or '')[:250].lower()
    body = str(issue.get('body') or '')[:4800].lower()
    title_terms = set(_WORD.findall(title)) - _SKIP
    body_terms = set(_WORD.findall(body)) - _SKIP
    result: list[tuple[int, str]] = []
    for path in paths[:20000]:
        if not safe_code_path(path):
            continue
        lower = path.lower()
        filename = lower.rsplit('/', 1)[-1]
        stem = filename.rsplit('.', 1)[0]
        tokens = set(_WORD.findall(stem.replace('_', ' ').replace('-', ' '))) - _SKIP
        score = 0
        if len(path) > 5 and lower in body:
            score += 180
        elif len(filename) >= 7 and re.search(r'(?<![\w.])' + re.escape(filename) + r'(?![\w.])', title + ' ' + body):
            score += 115
        if len(stem) >= 5 and stem not in _GENERIC:
            if re.search(r'\b' + re.escape(stem) + r'\b', title):
                score += 80
            elif re.search(r'\b' + re.escape(stem) + r'\b', body):
                score += 52
        score += 13 * len(tokens & title_terms) + 7 * len(tokens & body_terms)
        if any(t in lower for t in ('/tests/', '/test/')) and ('selenium' in body_terms or 'test' in title):
            score += 2
        if stem in _GENERIC:
            score -= 35
        if score > 0:
            result.append((score, path))
    result.sort(key=lambda row: (-row[0], len(row[1]), row[1]))
    return result


def live_symbol_matches(source: str, issue: dict) -> list[str]:
    """Exact whole-identifier matches in fetched source, not in the issue snippet."""
    matches = []
    for symbol in issue_symbols(issue):
        if re.search(r'(?<![\w])' + re.escape(symbol) + r'(?![\w])', source, re.IGNORECASE):
            matches.append(symbol)
    return matches[:12]
