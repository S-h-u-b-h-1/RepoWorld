# RepoWorld v0.9.15 — The City of Code

### 🏆 BharatCode Build League 2026 — submitted entry

**[🚀 Try RepoWorld](https://repoworld-launch.onrender.com)** · **[🗳️ Find RepoWorld and vote on BharatCode](https://bharatcode.ai/hackathon#projects)** · **[⭐ Star the open-source repository](https://github.com/S-h-u-b-h-1/RepoWorld)**

Turn an unfamiliar public GitHub repository into an explorable **3D code city**. Inspect real module paths and sampled static imports, use **Find Code**, and investigate **open GitHub issues** with clearly qualified source-location hints. An optional **BharatCode-powered assistant** provides source-scoped guidance when inference is available; any fallback is explicitly labeled.

**Try it in three steps:** open the live launcher, import the public repository `zulip/zulip-terminal`, then explore buildings, Find Code, and Issue Radar. No sign-in required. The free backend may take time to wake after inactivity.

**If it helps you understand a codebase,** genuine GitHub stars and BharatCode community votes support the entry. Find **RepoWorld** under the event's Projects section; voting is limited to one registered BharatCode account. Feedback and bug reports are welcome.

**RepoWorld is a read-only, sign-in-free tool for exploring public GitHub repositories as interactive 3D cities.** Districts are groups of source files; buildings represent modules; illuminated links represent sampled **static imports**, not runtime traffic. Issue Radar displays GitHub's reported open issues as referenced, suggested, or unplaced locations. An optional BharatCode assistant helps developers investigate code and plan safe next steps.

**Status:** Public source: https://github.com/S-h-u-b-h-1/RepoWorld. Free hosted site: https://repoworld-3b9e.onrender.com. RepoWorld is publicly listed in the BharatCode Build League 2026 Projects section. The visual/navigation improvements have CI and mocked-browser tests; actual public-host and GitHub API behavior must still be verified after deployment. The optional BharatCode provider can time out and its labeled fallback is not a completed AI generation.

## Fast free launch page (static CDN)

Use **https://repoworld-launch.onrender.com** as the first-visit and hackathon entry URL. It is a separate **free Render static site**, not a second Python application. Its lightweight HTML/CSS loads without waking the backend, displays an illustrative 3D city fixture, and probes the public **/api/ready.svg** endpoint; the backend serves a loadable, uncached SVG only after its existing database/readiness checks succeed. When that image genuinely loads, the launcher opens the real app at **https://repoworld-3b9e.onrender.com**. Visitors can also follow its direct link or retry.

The launcher preserves only validated public `?repo=owner%2Frepo` parameters. It never reads or stores session cookies, CSRF values, private code, or BharatCode secrets; browsers may automatically attach an existing backend cookie to its image readiness request. This improves first paint and honest cold-start feedback; **it does not eliminate Render Free's backend spin-up delay or ephemeral data loss**. The interactive explorer, GitHub importer, and AI assistant remain on the existing Python service. Static launch tests are part of GitHub CI.

## Visual QA follow-up: readable mobile city and tappable district plaques

Visual acceptance screenshots at 1440×900 and 390×844 exposed a clipped mobile header and dense pale window lines at distant zoom. Mobile now hides the redundant guest tagline so the repository name can use available width, and Issue Radar summaries and inspector caveats have larger type. Remote towers use darker, calmer façades with window detail only when it can be resolved at screen scale. **Tap or click a drawn district plaque** to focus its real buildings, then open **Map controls → Overview** to return; this works without extra GitHub calls. District names remain heuristic code classifications, never runtime locations.

## Building-by-building exploration

The temporary **Explore code → Map controls** panel has **Previous building** and **Next building** controls. They cycle deterministically through real imported module buildings and open the existing inspector. When the city canvas is focused, use **[** and **]** to navigate without a mouse. The ordering uses district, name and stable module IDs; it does not invent files or run code.

## City layout reliability and mobile responsiveness

Dense repositories use spacing derived from the **actual displayed building widths**, so source-module towers and floating district footprints do not overlap in map coordinates. A bounded square-spiral wraps crowded central code districts around the non-source landmark. Overview and district focus cameras fit the calculated bounds; decorative scenery avoids real buildings. Small-scale façades skip sub-pixel windows and idle/mobile rendering is frame-rate limited. These optimizations do **not** add code links, infer new source evidence, or imply exact runtime topology.

## City readability and navigation (v0.9.10)

The original near-black, floating-district perspective remains. Decorative blocks are quieter, real source-module buildings have raised roofs and camera-aware lit façades, and the symbolic central beacon is slightly less dominant. Labels, issue text, menus, tooltips and inspector copy are larger. Open **Explore code → Map controls** for a district jump, a most-connected-module focus (only sampled static links count), and accessible +/− zoom buttons. Existing wheel/pinch zoom, Shift-drag pan and double-click reset remain. This upgrade does not change source evidence or classify decorative buildings as code.

### Issue Radar quick filters

Within **Explore code → Open issues**, search the fetched issue sample by title, issue number or labels, or filter by bug, good-first-issue, enhancement, or location-hint categories. Filtering happens entirely in the browser with no extra GitHub requests. It does not search every issue in the repository, promote unverified paths to source observations, or change the map markers.

## Portable offline city files (v0.9.15)

To move a public city map between browsers without relying on Render's temporary SQLite storage, first **Save city for offline viewing** in the existing repository menu. Then choose **Download portable city file** to save a `repoworld-owner-repo.json` backup to your device. On another browser/device, choose **Restore city from file** in the repository menu or the empty welcome screen. Restoring validates a versioned file format and the same strict public-GitHub URL, path, edge and module bounds as the existing local backup, then saves *one* sanitized map in the new browser's local storage and opens it as an explicitly **offline preview**.

This is a **manual file transfer**, not cloud sync or a persistent server database. Files are read locally by the browser; they are not uploaded to the RepoWorld API. Export/import do not call GitHub, BharatCode or any server endpoint. The file contains only whitelisted public map metadata (bounded modules, sampled filenames, short declarations and static import edges) without cookies, CSRF tokens, private credentials, issue reports or AI answers. Reject malformed files, unexpected formats, non-GitHub origins, unsafe paths and oversized payloads before changing any stored map. The file is not proof the current repository or issue state is unchanged. Re-import explicitly to restore live tools.

## Opt-in local city map backup (v0.9.14)

Render Free can delete its temporary SQLite guest workspaces when the server spins down, restarts or redeploys. RepoWorld now provides a deliberately **browser-only, opt-in map backup**: while viewing a real imported public GitHub city, open the top-left repository menu and select **Save city for offline viewing**. Only a bounded sanitized copy of the public city topology, grouped modules, short file paths and sampled declaration names is stored in **this browser's own local storage**. It saves **no cookies, CSRF tokens, API keys, private repositories, issue reports or AI answers**, and does not send anything to a backup server.

If the free backend later loses its city, the empty screen offers **Open saved map offline**. You can orbit and inspect its public buildings, browse sampled static imports, run a local filename/path search, and follow GitHub source links without re-importing. The city clearly says **LOCAL OFFLINE PREVIEW**. While offline, **Issue Radar, AI, change-impact API requests and source investigation are unavailable**; **Re-import to restore live tools** opens the ordinary import confirmation with the public repo name and spends normal import quota only after confirmation. The saved map may be stale, exists in only one browser, and disappears when the user clears site storage. It is **not** durable server storage, account sync or a confirmed current GitHub snapshot.

One local map is retained at a time (max 1.6 million characters). The user can explicitly clear it in the repository menu. Storage-blocked and oversized cases fail safely without changing the live city; no automatic GitHub refresh, model request, or browser persistence occurs without a user action.

## Clearer source investigation and useful issue briefs (v0.9.13)

The browser-only issue guide now separates public source files with **literal reported identifier matches** from files retrieved only as **filename/path search hints**. Finding a source file is evidence that it exists, not that the unverified issue affects it. The issue panel summarizes that distinction and preserves all original source links and bounded excerpts. No additional GitHub or BharatCode calls are performed.

**Copy investigation notes** now prefers the available full issue body over GitHub's shortened list snippet. Long reports are abbreviated near sentence/word boundaries with an explicit disclosure and an unchanged link to the original issue; Markdown is safely escaped. Notes qualify each fetched public file as either an identifier text observation or a search candidate, never a confirmed bug or fix.

## Independent source lookup for browser-only issue reports (v0.9.12)

If GitHub limits the server's shared IP, Issue Radar can still display a **browser-fetched public issue feed**, explicitly marked unverified by RepoWorld's server. Open a reported issue and choose **Inspect public source** to *explicitly* look for matching identifiers or files in the saved public repository. The new CSRF-protected endpoint reads a bounded source sample through the existing public HEAD archive path on Render Free (or an authenticated GitHub tree when configured). It does not trust browser-provided URLs, independently establish that the issue exists/is still open, run code, invoke BharatCode, or place a new "verified issue" marker. Fetched source excerpts are real code evidence but **not proof the reported defect affects that file**. If a source is found, the existing **Copy investigation notes** button includes the links with this distinction; it never upgrades the browser issue feed to server-verified.

This feature is on-demand only, with independent per-guest and global hourly source-lookup budgets (defaults: 2 per guest, 8 globally); provider throttling, large repositories and unavailable archives can still yield zero excerpts. No new permanent panels, user account, or paid infrastructure are required.

## Portable issue investigation notes (v0.9.11)

Within **Issue Radar**, select a real public GitHub issue and choose **Copy investigation notes** in its existing issue panel. RepoWorld composes a bounded Markdown brief locally in your browser: the canonical issue URL, unverified report context, qualified path references, and the current assistant's suggested steps, proposed tests, and genuine linked excerpts when available. It makes **no additional GitHub or BharatCode requests**, does not save the notes to a server, and does not post comments on your behalf. Browser-only GitHub issue fallback notes remain explicitly server-unverified and never reuse a previously generated assistant response. AI output is always labeled as unverified guidance; no export claims bug reproduction, a working fix or executed tests.

## Try RepoWorld (no account)

1. Open RepoWorld. A new browser sees **Add GitHub repository**; a returning browser with saved cities sees its last city.
2. Import a **public** GitHub repository such as `https://github.com/openwisp/openwisp-utils`.
3. Click buildings to inspect modules, sampled declarations and import connections. Open **Explore code** (or `⌘ K`) to locate code, ask questions, and browse open issues.
4. Click an issue marker to open its original report and a source-scoped investigation. The assistant proposes where to inspect, not an automatically verified fix.

There is **no login**, GitHub OAuth, or Google signup. After a successful import, the browser also saves **only the most recent validated public owner/repo name** in localStorage. If the free server loses its temporary city after a restart, the empty screen can offer a **Re-import** shortcut; it opens the ordinary confirmation dialog and does not restore the old snapshot, fetch GitHub automatically, retain source code locally, or bypass import quotas. Clear this site's browser storage to erase that shortcut. Each browser receives an anonymous HttpOnly session cookie. Existing browsers may preserve previously imported public snapshots for 14 days (unless the cookie is cleared). Switching devices or losing the cookie loses access to those saved cities. This is a demonstration, not an account system; never use it for sensitive or private repositories.

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

## v0.9.8: read-only Issue Radar fallback for shared GitHub API limits

The normal Issue Radar remains **server-backed**, including path-reference matching and source-scoped investigation. When that route returns a **GitHub provider HTTP 429**, RepoWorld uses GitHub's officially documented public **browser CORS** support to fetch at most 30 open issue records directly from the visitor's browser. GitHub quota then applies to the visitor's IP rather than Render's shared outbound IP. This is a no-login, no-token, no-paid-service fallback and never contacts private repositories. GitHub or the visitor's network may still rate-limit the request.

**Evidence qualifications:** The browser feed is NOT independently verified by RepoWorld's server. Pull requests are excluded. It only suggests building locations for exact reported file-path mentions, never reports source-observed locations, and never triggers server-verified issue AI investigation from browser-provided content. Users can open canonical GitHub issue links and ask a non-issue-bound question about the imported file map. If RepoWorld's own guest request quota is reached, the fallback is **not** used, preserving the existing safety budget.

For this read-only feature, the CSP's `connect-src` permits only `https://api.github.com` in addition to same-origin. Browser requests use `credentials: omit`; the server's `GITHUB_TOKEN` and `BHARATCODE_API_KEY` are never sent to visitors. Up to 30 issue records on the first page are displayed, so the feed may be partial. There is no claim of full GitHub issue coverage or validated fixes.

**Render Free cold starts remain:** Hosting can take about a minute to wake after 15 minutes idle, and ephemeral SQLite sessions/saved cities reset after sleep, restart, or redeployment. This update helps provider-specific Issue Radar failures; it does not eliminate hosting cold starts or enable BharatCode AI without its private server key.

## v0.9.7: real public-repository cities without REST quota

The **free Render demonstration** uses GitHub's public source ZIP distribution endpoint to import smaller repositories when no server-side `GITHUB_TOKEN` is configured. A single bounded archive download is processed **in memory only**; RepoWorld never executes repository files or extracts them to disk. The archive is capped at 12 MB compressed, 65 MB expanded, 13,000 entries and three sampled source files. Any larger or unavailable archive results in an honest error. This is a real GitHub source snapshot, **not** the fictional offline demo.

This improves **initial repository imports**, which no longer consume the shared unauthenticated GitHub **REST** allowance on this free-hosting path. GitHub may independently throttle source archives; the app never blindly retries or bypasses such restrictions. The imported graph has `branch: HEAD` and explicitly discloses that the exact default branch name, commit SHA, stars, and GitHub issues were not verified. Import graphs do not prove runtime architecture.

**Issue Radar and source-specific AI investigations still use GitHub REST** and may display a quota error until a server-side `GITHUB_TOKEN` with minimal read-only privileges is configured privately in Render. A token-backed import continues using GitHub REST, including live metadata and source sampling. The free service's ephemeral workspaces and quotas still disappear upon spin-down or redeploy. Public source archives are not suitable for giant repositories.

## GitHub API quota behavior on free hosting

Render's shared outbound IP may already be near GitHub's unauthenticated 60-requests/hour allowance; waiting for a cooldown cannot guarantee the next visitor will have quota. A short-lived read-only GitHub personal access token can be set privately as `GITHUB_TOKEN` in the Render Environment settings to obtain the higher authenticated GitHub API budget. Never commit or display this token, and prefer minimum permissions and expiry.

Without a token, the free demo now imports a bounded public ZIP archive (up to three inspected source files, no REST metadata/tree calls). The archive endpoint can impose separate restrictions or reject oversized repositories. In that case the import dialog offers **Explore a fictional demo city (offline)**: it loads an explicitly labeled fictional graph from RepoWorld itself, **not** a live GitHub repository, and does not contact GitHub or claim the issue data is real.

## Free public hosting (ephemeral hackathon preview)

`render.yaml` now requests a **Render Free Python service** in Singapore, with one web worker and **no persistent disk or paid services**. This is explicitly a temporary hackathon preview. It uses an SQLite file at `/tmp/repoworld.sqlite3` and `REPOWORLD_EPHEMERAL_DEMO=1`. The preview works during an active browser session, but **all saved cities, guest sessions and usage quotas can disappear** when Render spins down after 15 minutes idle, restarts or redeploys. Returning visitors might need to import the public repository again. There is no cross-browser account synchronization.

Render Free includes hosting within its monthly compute, bandwidth and build allowances. See https://render.com/docs/free. A payment method may be charged for bandwidth/build overages, so configure the workspace's billing limits and monitor usage; do not assume all possible traffic is free. It can take roughly a minute to wake from idle.

The public site runs in `APP_ENV=production`, with HTTPS-only cookie and CSRF protections, strict Origin checks, and bounded requests. SQLite-backed quotas remain enabled, but **do not persist across restarts in Free hosting**. The global API budgets in `render.yaml` are intentionally conservative. This free demo is not suitable for production users or long-term storage.

**Deployment:** Use Render → New → Web Service or New → Blueprint and select the public GitHub `main` branch with **Free**, no persistent disk. The checked-in Blueprint uses the free profile. Set the `BHARATCODE_API_KEY` **privately** in the Render Environment panel only if the optional live model is needed. Without it, the web app starts and labels its deterministic navigation fallback; it must never claim that model inference ran. An optional `GITHUB_TOKEN` can improve public GitHub API limits, but is not required.

Do not set `APP_BASE_URL` to a local address in Render: the platform supplies `RENDER_EXTERNAL_URL` (HTTPS). The free `/api/ready` checks HTTPS, an absolute SQLite path and DB connectivity without requiring a paid disk or optional AI key. Durable production still requires a real mount and model key (unless the explicit free-demo flag is set). Check the service status with `python scripts/smoke_hosted.py https://YOUR-SERVICE.onrender.com`; `--import-repo openwisp/openwisp-utils` additionally checks live GitHub importing and Issue Radar but spends GitHub API quota. Test BharatCode separately after setting the private key. The hostname is public only when Render confirms deployment.

For an entirely free student demo, do **not** create a Starter service, attach a paid disk, or enable paid add-ons. Render free Postgres expires after 30 days; it is not configured for this release. A future free external database may add durable storage, but needs new code and separate validation.

## Hackathon submission

`BharatCode.txt` is included at the repository root. Update the live site/source links **only after they exist**, confirm current contest rules, publish a clean repository without `.env` or `.data`, record a truthful demo, and submit through the official hackathon portal. Neither a packaged ZIP nor local test counts constitute an actual submission.
