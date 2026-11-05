# RepoWorld — BharatCode Build League release card

**Organizer's latest published cutoff checked on 5 November 2026:** 10 November 2026, 11:59 PM IST. Check https://bharatcode.ai/hackathon for changes. Unstop has separately shown 8 November as a registration date, so register early and prioritize the official page.

## Official entry fields

- **Project name:** RepoWorld — The City of Code
- **Track:** Coding & developer tools
- **Public GitHub repository:** https://github.com/S-h-u-b-h-1/RepoWorld
- **Fast launch page:** https://repoworld-launch.onrender.com
- **Direct app:** https://repoworld-3b9e.onrender.com
- **Root required file:** [BharatCode.txt](BharatCode.txt)

**Short summary (under 1,000 characters):**

RepoWorld turns public GitHub repositories into interactive 3D cities to help developers understand unfamiliar codebases and find a place to contribute. Each district represents a source area, each clickable building maps to real indexed modules, and illuminated links depict *sampled static imports*, not runtime calls. Explore source locations, change-impact hints, and GitHub's open issues, with reported paths clearly distinguished from unverified suggestions. The optional server-side BharatCode Qwen 3.8 27B assistant provides read-only, source-scoped investigation guidance when configured; otherwise RepoWorld clearly labels its deterministic fallback. No sign-in required; public repositories only.

## Rules and claims

1. The source and the root manifest are public. Never publish .env, API keys, cookies or private repositories.
2. **Real BharatCode use is a release gate.** Presence of an integration is not proof that the hosted API key works or a generation completed. Verify with an explicitly authorized model call and preserve non-sensitive test results before claiming live AI.
3. Free Render may sleep and may discard SQLite guest workspaces at restart. Browser-local re-import remembers only a public owner/repo; it is not durable snapshot storage.
4. Only current GitHub data and fetched source excerpts qualify as source observations; model proposals are not verified fixes.
5. The official event judges consider GitHub stars, registered website votes and judges' evaluation. Do not automate votes or buy community engagement.
6. A video is not listed as a mandatory field on the official submission form as checked; a clear optional live demo can strengthen judges' understanding.
7. **Submission status: not verified.** A public GitHub repo and live URL do not imply the event form was submitted. Check the signed-in portal for accepted entry/confirmation.

## Short demo walkthrough (approx. 90 seconds)

- **0–15s:** Problem: unfamiliar GitHub repositories are hard to navigate. Show the live app and paste a public repo URL.
- **15–35s:** Move through the code city, focus a district and open two real buildings. Explain that links are sampled static imports, never claimed runtime telemetry.
- **35–55s:** Open the source explorer and Issue Radar. Choose an issue and distinguish referenced, suggested and unplaced positions.
- **55–75s:** Ask a narrow source-specific question. Only describe the answer as BharatCode-generated if the real provider responded; otherwise explain the labeled offline guide.
- **75–90s:** Show a source link, the public GitHub repo with BharatCode.txt, and the free deployment. End with the practical value: faster codebase orientation and evidence-aware issue triage.

## Final release checks

```bash
python scripts/check_build_league.py
python scripts/check_production.py
python scripts/smoke_hosted.py https://repoworld-3b9e.onrender.com --require-ai
# Only when the real model key is configured and provider usage is authorized:
python scripts/smoke_hosted.py https://repoworld-3b9e.onrender.com --import-repo pallets/flask --verify-live-ai --require-source-evidence
```

The final command deliberately imports a real public repository and spends one model request. If GitHub source retrieval or model inference is unavailable, it should fail rather than claiming RAG is verified.

**Required final action:** Submit the project through the signed-in official portal and confirm the entry appears under its registered account. Avoid claiming this was completed until there is evidence.
