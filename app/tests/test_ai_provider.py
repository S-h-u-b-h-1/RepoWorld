import json

import httpx
import pytest

import app.ai as ai
from app.demo import build_demo
from app.github import RepoError


@pytest.mark.asyncio
async def test_bharatcode_request_is_server_side_and_valid(monkeypatch):
    requests = []
    original_async_client = httpx.AsyncClient

    def mock_handler(req):
        requests.append(req)
        return httpx.Response(200, json={
            'choices': [{
                'finish_reason': 'stop',
                'message': {'content': json.dumps({
                    'steps': [
                        {'nodeId': 'apps/web', 'title': 'Web', 'description': 'Inspect the frontend folder.'},
                        {'nodeId': 'services/gateway', 'title': 'Gateway', 'description': 'Inspect the public API routes.'},
                    ]
                })},
            }]
        })

    class FakeClient:
        def __init__(self, **kwargs):
            self._client = original_async_client(transport=httpx.MockTransport(mock_handler))
        async def __aenter__(self):
            return await self._client.__aenter__()
        async def __aexit__(self, *args):
            return await self._client.__aexit__(*args)
        async def post(self, *args, **kwargs):
            return await self._client.post(*args, **kwargs)

    monkeypatch.setenv('BHARATCODE_API_KEY', 'dummy-server-only-secret')
    monkeypatch.setattr(ai.httpx, 'AsyncClient', FakeClient)
    result = await ai.make_ai_tour(build_demo())
    assert result['mode'] == 'ai'
    assert len(result['steps']) == 2
    assert len(requests) == 1
    req = requests[0]
    assert str(req.url) == ai.BHARATCODE_CHAT_URL
    assert req.headers['authorization'] == 'Bearer dummy-server-only-secret'
    payload = json.loads(req.content)
    assert payload['model'] == 'qwen-3.8-27b'
    assert payload['reasoning_effort'] == 'none'
    assert 'dummy-server-only-secret' not in req.content.decode()
    assert 'source code' not in str(payload).lower() or 'never' in str(payload).lower()


@pytest.mark.asyncio
async def test_incomplete_model_reply_is_not_treated_as_success(monkeypatch):
    original_async_client = httpx.AsyncClient

    class FakeClient:
        def __init__(self, **kwargs):
            self._client = original_async_client(transport=httpx.MockTransport(lambda req: httpx.Response(
                200, json={'choices':[{'finish_reason':'length','message':{'content':'{"steps":[]}'}}]}
            )))
        async def __aenter__(self):
            return await self._client.__aenter__()
        async def __aexit__(self, *args):
            return await self._client.__aexit__(*args)
        async def post(self, *args, **kwargs):
            return await self._client.post(*args, **kwargs)

    monkeypatch.setenv('BHARATCODE_API_KEY', 'dummy-key')
    monkeypatch.setattr(ai.httpx,'AsyncClient',FakeClient)
    with pytest.raises(RepoError, match='output limit'):
        await ai.make_ai_tour(build_demo())
