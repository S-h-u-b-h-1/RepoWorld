"""Read-only GitHub issue radar with evidence-qualified placement on modules.

Only published open *issues* (not PRs) are used. File references and module
paths can be placed; otherwise a clearly labelled lexical suggestion is made.
Never claim an issue implies a proven bug in a particular source file.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import os
import re
import time
from urllib.parse import quote

import httpx

from .github import GH_API, RepoError, parse_repository, _json
from .intelligence import find_modules

ISSUE_LIMIT = 100
TTL_SECONDS = 240
_CACHE: dict[str, tuple[float, dict]] = {}
WORD_EDGE = r"[A-Za-z0-9_./-]"


def _mentioned(text: str, path: str) -> bool:
    if not path or len(path) < 4:
        return False
    return bool(re.search(rf"(?<!{WORD_EDGE}){re.escape(path)}(?!{WORD_EDGE})", text, re.IGNORECASE))


def _paths(node: dict) -> list[str]:
    """Bounded index from a GitHub tree, not inferred or model-generated paths."""
    indexed=node.get('fileIndex') or node.get('files') or []
    return [p for p in indexed[:240] if isinstance(p,str) and 3<len(p)<450]


def _terms(value: str) -> set[str]:
    # Terms are lexical hints, never evidence that code was inspected.
    value=re.sub(r'([a-z])([A-Z])',r'\1 \2',value)
    stop={'the','and','with','from','when','this','that','should','would','could',
          'file','code','test','tests','issue','error','feature','enable','support',
          'check','using','utils','openwisp','module','function','report','admin',
          'python','please','needs','into','true','false','only'}
    return {w for w in re.findall(r'[a-z0-9]{4,}',value.lower()) if w not in stop}


def match_issue(graph: dict, title: str, body: str) -> list[dict]:
    """Explicit file/path references first; otherwise a cautious, single hint.

    Heuristic matches always remain 'suggested', even when an issue body names
    a function that might live in the candidate file.
    """
    nodes=[n for n in graph.get('nodes',[])[:72] if isinstance(n,dict) and isinstance(n.get('id'),str)]
    content=title[:250]+'\n'+body[:6500]
    names: dict[str,set[str]]=defaultdict(set)
    for node in nodes:
        for path in _paths(node):names[path.rsplit('/',1)[-1].lower()].add(node['id'])
    matches=[]
    for node in nodes:
        found=None
        for path in _paths(node):
            if '/' in path and _mentioned(content,path):
                found=('file',path);break
        if not found:
            path=node.get('path','')
            if isinstance(path,str) and path not in ('root','src','app','lib') and '/' in path and _mentioned(content,path):
                found=('module',path)
        if not found:
            for path in _paths(node):
                base=path.rsplit('/',1)[-1].lower()
                if len(base)>=7 and names[base]=={node['id']} and _mentioned(content,base):
                    found=('unique-file-name',path);break
        if found:
            matches.append({'nodeId':node['id'],'confidence':'referenced',
                            'evidence':f'Issue text references {found[1]}','path':found[1]})
    if matches:return matches[:8]

    # A unique filename term from the report may suggest where to look. Never
    # promote it to a direct reference, even if the words seem convincing.
    title_terms=_terms(title)
    body_terms=_terms(body[:2200])
    candidates=[]
    for node in nodes:
        for path in _paths(node):
            stem=path.rsplit('/',1)[-1].rsplit('.',1)[0]
            file_terms=_terms(stem)
            explicit=file_terms & title_terms
            contextual=file_terms & body_terms
            if not (explicit or contextual):continue
            score=4*len(explicit)+2*len(contextual)
            if path.lower().endswith(('.py','.js','.jsx','.ts','.tsx','.go')):score+=1
            if score>=3:
                candidates.append((score,node['id'],path,sorted(explicit|contextual)))
    candidates.sort(key=lambda x:(-x[0],x[2]))
    if candidates:
        best=candidates[0]
        # Never attach an ambiguous hint to a random building.
        if len(candidates)==1 or best[0]>=candidates[1][0]+3:
            return [{'nodeId':best[1],'confidence':'suggested','path':best[2],
                     'evidence':'Possible file from matching terms ('+', '.join(best[3][:4])+'); source not verified'}]

    ranked=find_modules(graph,title[:160]).get('results',[]) if len(title.strip())>=2 else []
    if ranked and ranked[0]['score']>=16 and ranked[0].get('matchedTerms'):
        best=ranked[0]
        if len(ranked)==1 or best['score']>=ranked[1]['score']*1.5:
            # Avoid attributing every miscellaneous issue to an oversized hub.
            node=next((n for n in nodes if n['id']==best['nodeId']),{})
            if node.get('id')=='root' or int(node.get('fileCount') or 0)>100:
                return []
            return [{'nodeId':best['nodeId'],'confidence':'suggested',
                     'evidence':'Possible module from issue title; not a verified file reference',
                     'path':best['path']}]
    return []


def _clean_issue(item: dict, graph: dict, owner: str, repo: str) -> dict | None:
    if not isinstance(item,dict) or item.get('pull_request') or item.get('state') != 'open':
        return None
    number=item.get('number')
    if not isinstance(number,int) or number <= 0:
        return None
    title=str(item.get('title') or '').strip()[:240]
    body=str(item.get('body') or '')[:6500]
    labels=[str(label.get('name') or '')[:80] for label in item.get('labels',[])[:10] if isinstance(label,dict)]
    matches=match_issue(graph,title,body)
    return {'number':number, 'title':title, 'url':f'https://github.com/{owner}/{repo}/issues/{number}',
            'labels':labels, 'updatedAt':str(item.get('updated_at') or '')[:35],
            'matches':matches, 'snippet':re.sub(r'\s+',' ',body).strip()[:240],
            'body':body[:4200], 'commentsCount':max(0,min(9999,int(item.get('comments') or 0))) if str(item.get('comments') or '0').isdigit() else 0}


def _assemble(graph: dict, owner: str, repo: str, raw: list, *, checked_at: str | None=None) -> dict:
    issues=[cleaned for row in raw if (cleaned:=_clean_issue(row,graph,owner,repo))]
    by_node=defaultdict(lambda:{'referenced':[],'suggested':[]})
    for issue in issues:
        for match in issue['matches']:
            by_node[match['nodeId']][match['confidence']].append(issue['number'])
    return {'issues':issues,'byNode':dict(by_node), 'total':len(issues),
            'placed':sum(bool(i['matches']) for i in issues), 'unplaced':sum(not i['matches'] for i in issues),
            'partial':len(raw)>=ISSUE_LIMIT,'checkedAt':checked_at or datetime.now(timezone.utc).isoformat(),
            'scope':'Latest 100 open GitHub issue records (pull requests excluded). References are matched to sampled files and grouped modules; suggested positions are unverified. Some issues may be unplaced.'}


async def fetch_issue_radar(graph: dict, *, client: httpx.AsyncClient | None=None, use_cache: bool=True) -> dict:
    if graph.get('source')!='github':
        return _assemble(graph,'fictional','demo',[])
    owner,repo=parse_repository(str(graph.get('url','')))
    key=(owner+'/'+repo).lower()
    cached=_CACHE.get(key) if use_cache and client is None else None
    token=os.environ.get('GITHUB_TOKEN','').strip()
    headers={'Accept':'application/vnd.github+json','User-Agent':'RepoWorld/0.6', 'X-GitHub-Api-Version':'2022-11-28'}
    if token:headers['Authorization']=f'Bearer {token}'
    own=client is None
    if own:client=httpx.AsyncClient(timeout=httpx.Timeout(13),follow_redirects=False)
    assert client is not None
    try:
        url=f'{GH_API}/repos/{quote(owner,safe="")}/{quote(repo,safe="")}'
        meta=await _json(client,url,headers)
        if meta.get('private') is not False:
            raise RepoError('Issue radar only supports repositories confirmed public by GitHub.',403)
        # Recheck visibility even when serving a cached issue list. A formerly
        # public issue might have become private after an earlier request.
        if cached and time.monotonic()-cached[0]<TTL_SECONDS:
            return _assemble(graph,owner,repo,cached[1]['raw'],checked_at=cached[1]['checkedAt'])
        try:
            result=await client.get(url+'/issues',params={'state':'open','sort':'updated','direction':'desc','per_page':ISSUE_LIMIT,'page':1},headers=headers)
        except httpx.TimeoutException as e:
            raise RepoError('GitHub issues timed out; retry shortly.',504) from e
        except httpx.RequestError as e:
            raise RepoError('GitHub issues could not be reached.',502) from e
        if result.status_code in (403,429):raise RepoError('GitHub issue API rate limit reached.',429)
        if result.status_code!=200:raise RepoError(f'GitHub issue API returned HTTP {result.status_code}.',502)
        try:raw=result.json()
        except ValueError as e:raise RepoError('GitHub returned invalid issue data.',502) from e
        if not isinstance(raw,list):raise RepoError('GitHub returned an unexpected issue format.',502)
        raw=raw[:ISSUE_LIMIT]
        checked=datetime.now(timezone.utc).isoformat()
        if own:
            if len(_CACHE)>200:_CACHE.clear()
            _CACHE[key]=(time.monotonic(),{'raw':raw,'checkedAt':checked})
        return _assemble(graph,owner,repo,raw,checked_at=checked)
    finally:
        if own:await client.aclose()
