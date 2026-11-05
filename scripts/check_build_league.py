"""Offline source-only compliance gate for the BharatCode Build League.

This gate does NOT verify live BharatCode inference, community votes, registration,
or submission. The organizer can change requirements; check the official page.
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO="https://github.com/S-h-u-b-h-1/RepoWorld"
EVENT="https://bharatcode.ai/hackathon"
REQUIRED=("README.md","BharatCode.txt","LICENSE","render.yaml","app/ai.py",
          "app/main.py","app/static/index.html","app/static/app.js")


def check_repo(root: Path) -> list[str]:
    missing=[p for p in REQUIRED if not (root/p).is_file()]
    errors=["Missing required public release file: "+p for p in missing]
    if missing:return errors
    rules=(root/"BharatCode.txt").read_text(encoding="utf-8")
    readme=(root/"README.md").read_text(encoding="utf-8")
    backend=(root/"app/ai.py").read_text(encoding="utf-8")
    render=(root/"render.yaml").read_text(encoding="utf-8")
    if REPO not in rules or EVENT not in rules:
        errors.append("BharatCode.txt must identify the public project and official hackathon.")
    if REPO not in readme:
        errors.append("README must link the canonical public GitHub repository.")
    if 'qwen-3.8-27b' not in backend or 'https://bharatcode.ai/api/model/v1/chat/completions' not in backend:
        errors.append("Server-side BharatCode model/API integration cannot be identified.")
    if 'BHARATCODE_API_KEY' not in backend:
        errors.append("Server-side BharatCode key configuration cannot be identified.")
    if 'plan: free' not in render:
        errors.append("Free-tier deployment plan is not described by render.yaml.")
    if (root/"app/static/app.js").stat().st_size<1000:
        errors.append("Interactive app bundle is unexpectedly empty.")
    return errors


def main() -> int:
    root=Path(__file__).resolve().parents[1]
    errors=check_repo(root)
    if errors:
        for error in errors:print("FAIL "+error,file=sys.stderr)
        return 1
    print("PASS Build League source checklist: root manifest, public links, model integration and free deployment.")
    print("NOT CHECKED Live API key, genuine inference, official submission, community votes or real hosted UX.")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
