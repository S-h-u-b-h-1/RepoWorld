# RepoWorld v0.9.6 — The City of Code

**RepoWorld is a read-only, sign-in-free tool for exploring public GitHub repositories as interactive 3D cities.** Districts are groups of source files; buildings represent modules; illuminated links represent sampled **static imports**, not runtime traffic. Issue Radar displays GitHub's reported open issues as referenced, suggested, or unplaced locations. An optional BharatCode assistant helps developers investigate code and plan safe next steps.

**Status:** v0.9.6 source is published at https://github.com/S-h-u-b-h-1/RepoWorld; its local and mocked-hosting checks passed. The application is **not yet verified as publicly deployed or submitted**. A zero-cost Render preview is configured below (without a paid disk). See [RELEASE_NOTES.md](RELEASE_NOTES.md) and [ROADMAP.md](ROADMAP.md).

## Try RepoWorld (no account)

1. Open RepoWorld. A new browser sees **Add GitHub repository**; a returning browser with saved cities sees its last city.
2. Import a **public** GitHub repository such as `https://github.com/openwisp/openwisp-utils`.
3. Click buildings to inspect modules, sampled declarations and import connections. Open **Explore code** (or `⌘ K`) to locate code, ask questions, and browse open issues.
4. Click an issue marker to open its original report and a source-scoped investigation. The assistant proposes where to inspect, not an automatically verified fix.

There is **no login**, GitHub OAuth, or Google signup. Each browser receives an anonymous HttpOnly session cookie. Existing browsers may preserve previously imported public snapshots for 14 days (unless the cookie is cleared). Switching devices or losing the cookie loses access to those saved cities. This is a demonstration, not an account system; never use it for sensitive or private repositories.

## New in v0.9.6 — public launch hardening (no UI changes)

- **Independent guest limits behind proxies.** Short-window AI request limits use each authenticated-by-cookie guest workspace, not the reverse proxy's potentially shared IP. SQLite-backed **global** and **per-guest** AI/import budgets remain enforced in production.
- **Bounded streaming requests.** API writes now enforce a strict body-size limit before JSON parsing, including when `Content-Length` is missing (chunked input). Oversized requests return HTTP 413.
- **Deployment hygiene.** Frontend JS/CSS and the entry page revalidate after a release; production enables HSTS. We did not add new buttons or alter the 3D renderer.
- **Ready only with durable storage.** When `REPOWORLD_REQUIRE_MOUNTED_DB=1`, the readiness endpoint returns HTTP 503 until the SQLite database directory is a real mount point; this prevents silently launching on ephemeral storage.
- **Simpler Render URL setup.** Render sets `RENDER_EXTERNAL_URL` at runtime. RepoWorld can use it automatically, while `APP_BASE_URL` remains the override for custom domains. Never infer the security origin from a browser-supplied Host header.
- **Read-only hosted smoke:** `python scripts/smoke_hosted.py https://YOUR-SERVICE.onrender.com`. By default it checks health, readiness, session cookie and browser headers without spending GitHub or BharatCode quota. Add `--import-repo openwisp/openwisp-utils` only when testing a real import intentionally.
- **Source-sanitization audit:** `python scripts/audit_public_release.py RepoWorld-v0.9.6.zip` checks archive CRC, required files, private-path exclusion and obvious key patterns.

## New in v0.9.5 — Public city links (no sign-in)

- Open the **existing repository dropdown at the top left** and choose **Copy public city link**. It copies an address such as `https://YOUR-HOST/?repo=openwisp%2Fopenwisp-utils`. **No new permanent buttons or sidebars** were added.
- Only the public `owner/repo` identifier is included. Share links never contain saved database IDs, guest session cookies, CSRF values, API credentials, issue context, or source snippets.
- If the destination browser already has that repository saved, RepoWorld opens the city. Otherwise it opens **Add GitHub repository** with the public name prefilled. The visitor must click **Create my city** to use GitHub; loading a link never auto-imports or calls BharatCode.
- **Localhost links are local previews only.** You must deploy RepoWorld to a public HTTPS domain before sharing links with other people. This feature does not make a local website public or preserve guest workspaces across browsers.
- The unused `GET /api/repository` compatibility endpoint now returns HTTP **410 Gone** without fetching GitHub. All supported imports use the existing CSRF-protected, persistently budgeted `POST /api/my-repos` route.

## New in v0.9.4 — Source-to-city issue investigation

- A GitHub issue starts with **referenced**, **suggested**, or **unplaced** building status. When an optional BharatCode investigation fetches actual public source and observes an issue-mentioned identifier, RepoWorld can map that file to its real retained city module (including files omitted from the import sample).
- The existing issue sheet then shows a **Code located in the city** action. Clicking it focuses the correct 3D building. No permanent navigation, sidebar, or renderer redesign was added.
- The map receives a **source-observed** issue marker only after that evidence is fetched. Unverified path/title guesses cannot create such markers; a source observation does *not* prove the reported defect or a working fix.
- If BharatCode times out **after** fetching relevant public source, the local fallback can retain source-observed locations without pretending the AI responded.
- These additional source-observed placements are **browser-session-only** and will disappear after a reload or Issue Radar refresh; the remote issue reports remain the system of record. No new database fields or migration is required.

## What is fixed in v0.9.3

- Corrected an additional local-only CSRF origin mismatch: `localhost:8004` and `127.0.0.1:8004` now work even if the browser-origin and HTTP Host headers use different loopback spellings. Production still requires the exact configured origin; external origins remain blocked.
- Added `scripts/diagnose_origin.py` to safely test origin/CSRF policy without calling GitHub, and `scripts/check_local_import.py` to test the complete browser-session → CSRF → public import flow from the running local server. It prints no credentials and uses a real import quota/API calls. This does not replace a browser check.


- **Smaller GitHub API footprint.** Importing a public repository without a server-side `GITHUB_TOKEN` makes at most 2 metadata/tree requests plus **6** sampled source requests (previously up to 22 samples). The map and issue index still use the repository tree; assistant investigations retrieve additional source files only when needed. With a configured token, the default source sample is 16 (not 22).
- **Bounded source inspection.** Concurrent source fetches have an overall time budget; slow or unavailable blobs now produce a marked partial graph, rather than failing or hanging the entire import. A tree or metadata failure still returns a clear error.
- **Actionable errors.** GitHub rate limits return HTTP 429 with a `Retry-After` hint, invalid server tokens are distinguished from throttling, and empty repositories receive an explanatory response. The import form shows the actual error without a new permanent panel.
- **Import diagnostics.** `scripts/diagnose_github.py` reports only status, remaining rate budget, and timings. It does not print your API key or token. It uses one REST call by default, or two with `--tree`.
- **No design regressions.** Existing 3D geometry, camera controls, city colors, Issue Radar, AI assistant, and login-free workspaces are unchanged.

## Existing v0.9 functionality

- **Better issue source discovery:** Before explaining an issue, RepoWorld can look up a bounded list of candidate files from the current, verified-public GitHub tree. It ranks filename hints, then checks **actual fetched source text** for the reported identifiers. It does not treat code pasted into the issue as verified code. A relevant source link includes the Git commit and excerpt line range when available. Older imported cities can benefit even when the needed file was missing from the original sample.
- **Source uncertainty:** Unknown issue locations remain suggestions. If matching symbols cannot be confirmed, the response does not present arbitrary nearby files as verified code citations. No test execution, code changes, or claimed runtime behavior.
- **Public-use limits:** SQLite-backed transactional daily/hourly AI, import, and forced-issue-refresh quotas work across requests and restarts. Model concurrency is bounded. The operator can tune the default budgets. A browser cookie is not a user identity; global limits still apply if cookies are reset.
- **Fewer repeated GitHub calls:** Recent public repository graphs are cached in memory for 8 minutes. **Refresh code index** bypasses the cache. GitHub issue reports retain their existing shorter cache.
- **Deployment readiness:** `/api/ready` checks production HTTPS origin, writable SQLite, and the server-side BharatCode key without exposing secrets. Render configuration includes a persistent disk and a single web worker.
- **No UI redesign:** The existing near-black 3D city, opaque charcoal overlays, no permanent sidebar, issue markers, and v0.8.3 precision zoom remain unchanged.

## Install on macOS

Keep the older RepoWorld server stopped (`Control+C`) before using port 8004. Unzip the download next to the previous version, then run:

```bash
cd ~/Downloads
unzip RepoWorld-v0.9.6.zip
cd RepoWorld-v0.9.6
cp ../RepoWorld-v0.9.5/.env .env
if [ -d ../RepoWorld-v0.9.5/.data ]; then cp -R ../RepoWorld-v0.9.5/.data .data; fi
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./run.sh
```

Open **http://127.0.0.1:8004**. If your previous `.env` was stored in another folder, copy it from that folder instead. Without a prior `.env`, use `cp .env.example .env` and set `BHARATCODE_API_KEY` to enable the AI. Keep the actual key on the **server**, never in browser JS, a public commit, screenshots, or chat.

### Diagnose an import before sending logs

With the v0.9.6 virtualenv active, you can run this from the project folder:

```bash
python scripts/diagnose_github.py openwisp/openwisp-utils --tree
```

After starting the server, first verify the local-origin fix without contacting GitHub:

```bash
python scripts/diagnose_origin.py
```

The script must report server version `0.9.6` and accept both loopback origins. Then run the full local import test in a second Terminal. This makes a real import and consumes GitHub API requests:

```bash
python scripts/check_local_import.py openwisp/openwisp-utils
```

The local-origin check prints no cookies, CSRF values, or API keys. The status is safe to share; **do not send any `.env` contents or credentials**. HTTP 200 for both checks means GitHub metadata and the tree are reachable. HTTP 429 indicates a rate limit; wait for the reported reset. HTTP 401 with a configured `GITHUB_TOKEN` suggests an invalid token; remove/rotate that token in `.env`. A source-blob failure may still yield a usable, partially inspected city. 

**No GitHub account login is required.** The optional server-side GitHub token is for raising API limits only, not OAuth.

Your `.data` directory contains the anonymous browser-workspace database. Preserve it if you want older city snapshots. Keep the same browser and origin to retain the session cookie; otherwise reimport the public repository.

**If the website still says "Cross-origin changes are not allowed":** run `curl -s http://127.0.0.1:8004/api/health` to confirm version `0.9.6`. The fix cannot affect a still-running older process. Then use one browser tab at `http://127.0.0.1:8004` and reload. If the diagnostic passes but the browser still fails, inspect the import request's **Origin** and **Request URL** in DevTools Network; never share cookies or CSRF headers.

### Camera controls

| Action | Input |
|---|---|
| Orbit the 3D map | Left-drag |
| Smooth cursor-focused zoom | Scroll wheel / Mac trackpad |
| Pan | Shift-drag or right-drag |
| Touch pinch zoom | Two fingers |
| Reset to city overview | Double-click the map or press Home |
| Explore a building / issue | Click a tower / issue marker |

## Evidence and limits

- The importer analyzes **only a bounded source sample** (default six source files without a token). Missing imports and incomplete file coverage are expected, especially in large repositories.
- Open issues are **reports**, not confirmed defects. A building pin can be an exact file reference or a clearly labeled suggestion; unplaced issues remain in the issue list.
- Issue source discovery performs up to six bounded file reads per investigation from a validated public tree (when available). It checks for actual symbol names in the code; this does **not** verify the reported problem or prove a fix.
- Model-generated steps, filenames and tests require human review. Commit-pinned excerpt links indicate what bytes were fetched, not that the complete repository was inspected.
- Only `https://github.com/owner/repo` public repositories are accepted. Private repositories, arbitrary URLs, and code execution are intentionally unsupported.
- GitHub unauthenticated REST requests have a low shared rate limit. The optional `GITHUB_TOKEN` **server environment variable** can improve reliability; the app still rejects private repositories. Do not expose a token in the client.
- RepoWorld's browser workspaces are anonymous and nonrecoverable, so don't store sensitive notes or proprietary project materials.

## Automated tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q app/tests
node --test app/tests/test_world.cjs app/tests/test_app.cjs
node --check app/static/app.js
node --check app/static/world.js
python -m app.tests.source_location_browser_smoke
python -m app.tests.share_links_browser_smoke
python -m app.tests.import_browser_smoke
python -m app.tests.zoom_browser_smoke
python scripts/check_production.py
```

The production configuration preflight intentionally returns a nonzero status on a local development environment. Focused Chromium checks require Playwright and an installed Chromium executable. The import-recovery regressions and OpenWISP #717 regression use **mocked GitHub API responses**, not a live provider completion.

## Free public hosting (ephemeral hackathon preview)

`render.yaml` now requests a **Render Free Python service** in Singapore, with one web worker and **no persistent disk or paid services**. This is explicitly a temporary hackathon preview. It uses an SQLite file at `/tmp/repoworld.sqlite3` and `REPOWORLD_EPHEMERAL_DEMO=1`. The preview works during an active browser session, but **all saved cities, guest sessions and usage quotas can disappear** when Render spins down after 15 minutes idle, restarts or redeploys. Returning visitors might need to import the public repository again. There is no cross-browser account synchronization.

Render Free includes hosting within its monthly compute, bandwidth and build allowances. See https://render.com/docs/free. A payment method may be charged for bandwidth/build overages, so configure the workspace's billing limits and monitor usage; do not assume all possible traffic is free. It can take roughly a minute to wake from idle.

The public site runs in `APP_ENV=production`, with HTTPS-only cookie and CSRF protections, strict Origin checks, and bounded requests. SQLite-backed quotas remain enabled, but **do not persist across restarts in Free hosting**. The global API budgets in `render.yaml` are intentionally conservative. This free demo is not suitable for production users or long-term storage.

**Deployment:** Use Render → New → Web Service or New → Blueprint and select the public GitHub `main` branch with **Free**, no persistent disk. The checked-in Blueprint uses the free profile. Set the `BHARATCODE_API_KEY` **privately** in the Render Environment panel only if the optional live model is needed. Without it, the web app starts and labels its deterministic navigation fallback; it must never claim that model inference ran. An optional `GITHUB_TOKEN` can improve public GitHub API limits, but is not required.

Do not set `APP_BASE_URL` to a local address in Render: the platform supplies `RENDER_EXTERNAL_URL` (HTTPS). The free `/api/ready` checks HTTPS, an absolute SQLite path and DB connectivity without requiring a paid disk or optional AI key. Durable production still requires a real mount and model key (unless the explicit free-demo flag is set). Check the service status with `python scripts/smoke_hosted.py https://YOUR-SERVICE.onrender.com`; `--import-repo openwisp/openwisp-utils` additionally checks live GitHub importing and Issue Radar but spends GitHub API quota. Test BharatCode separately after setting the private key. The hostname is public only when Render confirms deployment.

For an entirely free student demo, do **not** create a Starter service, attach a paid disk, or enable paid add-ons. Render free Postgres expires after 30 days; it is not configured for this release. A future free external database may add durable storage, but needs new code and separate validation.

## Hackathon submission

`BharatCode.txt` is included at the repository root. Update the live site/source links **only after they exist**, confirm current contest rules, publish a clean repository without `.env` or `.data`, record a truthful demo, and submit through the official hackathon portal. Neither a packaged ZIP nor local test counts constitute an actual submission.
