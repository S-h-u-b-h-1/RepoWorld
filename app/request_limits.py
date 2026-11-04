"""Bounded HTTP request bodies for a public, account-free developer demo.

Reject oversized streaming/chunked requests *before* FastAPI parses JSON.
A Content-Length check alone is insufficient because HTTP clients can omit it.
This middleware is deliberately independent of reverse-proxy client-IP headers.
"""
from __future__ import annotations

from starlette.responses import JSONResponse


class RequestBodyLimit:
    def __init__(self, app):
        self.app = app

    @staticmethod
    def limit(path: str) -> int:
        # A typical issue question including bounded chat history is small.
        if path.startswith('/api/my-repos/') and path.endswith('/assistant'):
            return 18_000
        if path == '/api/my-repos':
            return 16_000
        if path.startswith('/api/'):
            return 160_000
        return 160_000

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('method', 'GET').upper() not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            await self.app(scope, receive, send)
            return

        limit = self.limit(scope.get('path', ''))
        headers = {k.lower(): v for k, v in scope.get('headers', [])}
        raw_length = headers.get(b'content-length', b'').strip()
        if raw_length.isdigit() and int(raw_length) > limit:
            await self._reject(scope, receive, send)
            return

        payload = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            if message['type'] != 'http.request':
                continue
            chunk = message.get('body', b'')
            if len(payload) + len(chunk) > limit:
                await self._reject(scope, receive, send)
                return
            payload.extend(chunk)
            if not message.get('more_body', False):
                break

        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {'type': 'http.request', 'body': bytes(payload), 'more_body': False}
            return await receive()

        await self.app(scope, replay, send)

    @staticmethod
    async def _reject(scope, receive, send):
        response = JSONResponse({'error': 'Request body is too large.'}, status_code=413)
        await response(scope, receive, send)
