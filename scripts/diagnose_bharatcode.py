"""Safely check BharatCode credentials and a tiny completion without exposing tokens.

Run from RepoWorld root using its virtualenv:
  python scripts/diagnose_bharatcode.py
Does not print your API key, request headers, response text, or prompt content.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
import time

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)
BASE = "https://bharatcode.ai/api/model/v1"


def report(label: str, response: httpx.Response, elapsed: float) -> None:
    request_id = response.headers.get("x-request-id", "")[:90]
    print(f"{label}: HTTP {response.status_code} in {elapsed:.1f}s" +
          (f" | request ID {request_id}" if request_id else ""))
    if response.status_code == 401 or response.status_code == 403:
        print("Authorization failed: check the API key, student verification, and eligible models.")
    elif response.status_code == 429:
        print("Rate-limited: check the account limits before trying again.")
    elif response.status_code in (502, 503, 504):
        print("Provider busy/unavailable: check live capacity and retry later.")


async def main() -> int:
    key = os.environ.get("BHARATCODE_API_KEY", "").strip()
    if not key:
        print("No BHARATCODE_API_KEY found in the environment or .env file.")
        return 2
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    timeout = httpx.Timeout(connect=12, read=125, write=15, pool=12)
    print("Checking BharatCode API. Your key and response contents will not be printed.")
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            start = time.monotonic()
            models = await client.get(BASE + "/models", headers=headers)
            report("Model access", models, time.monotonic() - start)
            if not models.is_success:
                return 1
            try:
                model_ids = {m.get("id") for m in models.json().get("data", []) if isinstance(m, dict)}
                if model_ids and "qwen-3.8-27b" not in model_ids:
                    print("Qwen 3.8 27B was not listed for this account; check your student entitlement.")
                    return 1
            except (ValueError, AttributeError, TypeError):
                print("Could not read the model catalog; attempting one tiny completion.")
            start = time.monotonic()
            response = await client.post(BASE + "/chat/completions", headers=headers, json={
                "model": "qwen-3.8-27b",
                "messages": [{"role": "user", "content": "Reply with just OK."}],
                "max_tokens": 32,
                "reasoning_effort": "none",
            })
            report("Short completion", response, time.monotonic() - start)
            if response.is_success:
                print("The live API completed a short request successfully.")
                return 0
            return 1
    except httpx.TimeoutException:
        print("Timed out talking to BharatCode. This does NOT establish an invalid key.")
    except httpx.RequestError:
        print("Network connection to BharatCode failed. Check connectivity or proxy settings.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("Cancelled")
        sys.exit(130)
