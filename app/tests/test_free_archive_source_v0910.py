"""BharatCode source evidence from bounded public HEAD archives on Render Free."""
from __future__ import annotations

import base64
from io import BytesIO
import stat
import zipfile

import httpx
import pytest

from app import assistant


def public_city():
    return {'source':'github','url':'https://github.com/public/demo','branch':'HEAD',
            'owner':'public','name':'demo','nodes':[
                {'id':'src/api','kind':'api','path':'src/api',
                 'files':['src/api/engine.py'],
                 'fileIndex':['src/api/engine.py']},
                {'id':'src/front','kind':'frontend','path':'src/front',
                 'files':['src/front/index.ts'],
                 'fileIndex':['src/front/index.ts']}
            ],'edges':[]}


def archive(*, unsafe=False):
    data=BytesIO()
    with zipfile.ZipFile(data,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('demo-HEAD/src/api/engine.py',
                   "def render_widget():\n    return 'safe result'\n")
        z.writestr('demo-HEAD/src/front/index.ts',
                   "import { useState } from 'react';\nexport const app = () => true;\n")
        z.writestr('demo-HEAD/README.md','# Demo repository\n')
        if unsafe:
            z.writestr('demo-HEAD/../../.env','SECRET_NOT_VISIBLE=xyz')
            sym=zipfile.ZipInfo('demo-HEAD/src/api/trap.py')
            sym.create_system=3
            sym.external_attr=(stat.S_IFLNK|0o777)<<16
            z.writestr(sym,'../../.env')
    return data.getvalue()


def client_for(payload, status=200, extra_headers=None):
    seen=[]
    def handler(request):
        seen.append(str(request.url))
        assert str(request.url)=='https://codeload.github.com/public/demo/zip/HEAD'
        return httpx.Response(status,content=payload,headers=extra_headers or {})
    return httpx.AsyncClient(transport=httpx.MockTransport(handler)),seen


@pytest.mark.asyncio
async def test_free_demo_reads_real_archive_code_without_any_github_rest(monkeypatch):
    monkeypatch.setenv('REPOWORLD_EPHEMERAL_DEMO','1')
    monkeypatch.delenv('GITHUB_TOKEN',raising=False)
    client,seen=client_for(archive())
    async with client:
        result=await assistant.read_public_sources(public_city(),['src/api/engine.py'],
                                                    client=client,cues='render_widget')
    assert len(seen)==1
    assert not any('api.github.com' in url for url in seen)
    assert len(result)==1
    assert result[0]['file']=='src/api/engine.py'
    assert result[0]['commit'] is None
    assert 'render_widget' in result[0]['content']
    links=assistant._links(public_city(),['src/api/engine.py'],result)
    assert links[0]['evidence']=='excerpt'
    assert '/blob/HEAD/' in links[0]['url']
    assert not links[0].get('commit')


@pytest.mark.asyncio
async def test_issue_identifiers_are_observed_only_in_fetched_public_bytes(monkeypatch):
    monkeypatch.setenv('REPOWORLD_EPHEMERAL_DEMO','1')
    monkeypatch.delenv('GITHUB_TOKEN',raising=False)
    issue={'number':7,'title':'render_widget fails in latest version',
           'body':'See src/api/engine.py and render_widget',
           'matches':[{'nodeId':'src/api','path':'src/api/engine.py','confidence':'referenced'}]}
    client,_=client_for(archive(unsafe=True))
    async with client:
        records=await assistant.read_public_sources(public_city(),[],
                   client=client,cues='render_widget',issue=issue)
    assert records
    assert records[0]['matchKind']=='symbol'
    assert records[0]['matchedSymbols']==['render_widget']
    assert not any('.env' in x['file'] or 'trap.py' in x['file'] for x in records)
    places=assistant.observed_issue_locations(public_city(),records,issue)
    assert places and places[0]['nodeId']=='src/api'
    assert places[0]['evidence']=='identifier-observed'
    assert 'HEAD' in places[0]['url'] and 'github.com/public/demo' in places[0]['url']
    # The issue did not reproduce a defect and no revision SHA was verified.
    assert all(x.get('commit') is None for x in records)


@pytest.mark.asyncio
async def test_corrupt_oversized_and_throttled_archive_never_fabricate_evidence(monkeypatch):
    monkeypatch.setenv('REPOWORLD_EPHEMERAL_DEMO','1')
    monkeypatch.delenv('GITHUB_TOKEN',raising=False)
    from app.archive_import import MAX_ARCHIVE_BYTES
    cases=[
        (b'PK\\x03\\x04broken',200,None),
        (archive(),429,None),
        (archive(),200,{'content-length':str(MAX_ARCHIVE_BYTES+1)}),
        (archive(),302,{'location':'https://attacker.invalid/a.zip'}),
    ]
    for payload,status,headers in cases:
        client,seen=client_for(payload,status,headers)
        async with client:
            result=await assistant.read_public_sources(public_city(),
                       ['src/api/engine.py'],client=client)
        assert result==[]
        assert len(seen)==1


@pytest.mark.asyncio
async def test_free_demo_ai_uses_unpinned_source_evidence_and_no_fake_commit(monkeypatch):
    monkeypatch.setenv('REPOWORLD_EPHEMERAL_DEMO','1')
    monkeypatch.delenv('GITHUB_TOKEN',raising=False)
    monkeypatch.setenv('BHARATCODE_API_KEY','fake-test-key')
    async def fake_model(system,prompt,max_tokens):
        assert 'render_widget' in prompt
        return ('{"answer":"Inspect render_widget and test its reported behavior.",'
                '"steps":["Read the implementation"],"tests":["Write a regression test"],'
                '"sources":["src/api/engine.py"],"nodeIds":["src/api"]}')
    monkeypatch.setattr(assistant,'_complete',fake_model)
    client,seen=client_for(archive())
    async with client:
        result=await assistant.guide_question(public_city(),
            'Where is render_widget implemented?',node_id='src/api',client=client)
    assert result['mode']=='ai' and result['sourceScope']=='live-branch'
    assert result['sourceFilesRead']==1
    assert len(seen)==1
    assert result['sources'][0]['evidence']=='excerpt'
    assert result['sources'][0].get('commit') is None
