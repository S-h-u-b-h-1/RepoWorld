## v0.9.8 — Read-only browser Issue Radar fallback

- When a server-backed public GitHub issue fetch returns a **GitHub provider** HTTP 429, the browser requests up to 30 open issues directly through GitHub's documented cross-origin public REST API. The request includes **no credentials** and consumes the visitor IP's public allowance, not Render's shared quota.
- A dedicated `browser-radar.js` module validates exact public GitHub repository URLs, drops pull requests, clips untrusted issue fields and uses canonical GitHub links. Invalid GitHub URLs and failing browser API requests produce visible errors, not fake issue data.
- Browser-fetched issues are labeled **BROWSER GITHUB FEED · UNVERIFIED BY SERVER**. Paths found in issue text create only `suggested` markers, never verified source observations. Server-verified issue AI investigation is suppressed for this feed; the original report remains accessible.
- The fallback cannot bypass RepoWorld's own visitor quotas. The unchanged server-backed issue route remains the primary path.
- CSP remains restrictive while adding `https://api.github.com` to `connect-src`; the new script revalidates on deployment.
- Desktop and mobile Chromium smoke checks and unit regressions were executed against local fixtures. GitHub CI and actual public API behavior are separate release gates.
- This does **not** fix Render Free's idle cold starts, ephemeral storage, or the need for private `GITHUB_TOKEN` / `BHARATCODE_API_KEY` for server-verified source investigations and live AI.

## v0.9.7 — Bounded archive import for public code cities

- Free Render installations **without** `GITHUB_TOKEN` import smaller public GitHub repositories from the official source ZIP endpoint, without spending GitHub REST API quota on initial imports. This is the **primary** free-tier source import path, not a repeated retry after REST rate limiting.
- Archive inputs are capped at 12 MB compressed / 65 MB expanded / 13,000 members; sampled code is read in memory without extraction or execution, with traversal/symlink and redirect checks.
- Source-archive graphs are actual public source snapshots but do **not** claim a pinned commit, verified branch, GitHub stars, current issue status or runtime dependencies. Unverified details are explicitly disclosed.
- GitHub Issue Radar and source-specific AI investigations still need REST access, preferably via a privately configured, least-privilege `GITHUB_TOKEN`.
- No change to the 3D UI, anonymous workspaces, free Render plan or modeled AI behavior.
- Regression coverage includes legitimate archive import, CSRF-protected saved city, malicious zip paths/symlinks, size/redirect caps, corrupt ZIPs, private/unavailable archives and preservation of REST visibility checks.
- Tests: 161 Python and 40 Node tests pass locally in the corresponding release source. Live codeload connectivity from Render requires a separate hosted check.

## GitHub shared-IP rate-limit mitigation (free hosting hotfix)

- A Render Free service can exhaust GitHub's public IP-based API limit even with a healthy website. This does not indicate an invalid repository.
- For the explicit free-demo setting only, anonymous imports sample 2 source blobs rather than 6, reducing optional API calls; authenticated imports retain the full sample.
- If GitHub returns HTTP 429, the import modal offers an explicitly fictional local demo city. The fictional city does not call GitHub and is visibly labeled `DEMO CITY`. It must not be presented as a genuine repo import.
- **Still required for reliable live imports:** a private server-side `GITHUB_TOKEN` with minimal read permissions and limited expiry. This is free but requires account-owner setup. Do not publish the token or treat extra quota as unlimited.
- The free Render service, guest sessions, production security policy and 3D appearance are unchanged.

## Free Render hosting profile (post-v0.9.6 publication)

- Retained all v0.9.6 application UI and behavior.
- Replaced paid Starter+disk Blueprint with **Free** Python service and explicit ephemeral SQLite mode (`REPOWORLD_EPHEMERAL_DEMO=1`).
- Free readiness permits absent *optional* BharatCode key while retaining HTTPS and absolute SQLite requirements, strict browser Origin and CSRF, and returning `aiConfigured:false`.
- Full/durable deployment still enforces BharatCode readiness and the mounted disk guard when requested.
- WARNING: Render free sleeping after 15 minutes idle, restarts and redeploys erase saved cities, sessions and persistent usage budgets. This profile is for hackathon demonstrations, **not durable production or open-ended public AI usage**.
- No cost-generating database, disk, or paid service is part of this profile. Render account bandwidth/build overages can still be billable if the workspace has a payment method.
- Source published: https://github.com/S-h-u-b-h-1/RepoWorld. The live site must be verified separately.

# RepoWorld v0.9.6 — Public launch hardening

**Scope:** no visual redesign, no login, no code execution, no private repositories. Derived from v0.9.5.

## Engineering changes
- Fixed proxy-shared short-window AI limits: legitimate anonymous workspaces are isolated while persistent global quotas remain.
- Added streaming-safe body caps (18 KB for assistant requests, 16 KB for repository imports and 160 KB for other API writes). Oversized uploads fail before JSON parsing.
- Added production HSTS and frontend no-cache revalidation to avoid stale JS across releases.
- Added `REPOWORLD_REQUIRE_MOUNTED_DB=1` deployment readiness guard. Render's SQLite volume must be mounted or readiness fails.
- Added support for Render's built-in `RENDER_EXTERNAL_URL` when `APP_BASE_URL` is not set. Explicit custom-domain origins still take precedence.
- Updated `render.yaml` to Singapore region, a single Starter web instance and a 1 GB persistent disk. This is a paid deployment template; no hosting service was created or purchased.
- Added `scripts/smoke_hosted.py` (default read-only/zero provider spending) and `scripts/audit_public_release.py` for prepublication checks.

## Verification and limitations
- Python and JavaScript suites, local loopback HTTP smoke, Chromium shared-link + precision-zoom checks, YAML configuration parse and ZIP integrity scan run locally.
- Provider and deployment behavior are not claimed as verified live. Render connection, GitHub repo publication, real BharatCode hosted inference and hackathon submission remain pending.
- Earlier versions remain untouched. Copy `.env` and `.data` from v0.9.5 to retain credentials and saved cities locally.

---

# RepoWorld v0.9.5 — Shareable public cities and import quota boundary

### What changed
- Added **Copy public city link** to the existing top-left repository dropdown. The URL contains a public `owner/repo` name only; never a session, database ID, CSRF value, or API key.
- First-time visitors arriving through a city link see a prefilled import dialog. There is **no automatic GitHub import or AI request**, avoiding background API spending. Returning visitors with that repository already saved open its city directly.
- Retired unused `GET /api/repository` (HTTP 410), which did not use the persistent import quota. The main authenticated-by-guest-cookie `POST /api/my-repos` importer remains the supported endpoint and retains its CSRF and rate protections.
- Existing perspective city, camera zoom, issue markers, source-to-city navigation, and charcoal panels are unchanged.

### Verification
- **145 Python tests and 40 JavaScript tests pass**, including a controlled anonymous import → issue → assistant integration, workspace isolation, deep-link parsing, no-background-import behavior, and the retired endpoint's refusal to fetch GitHub.
- An offline Chromium fixture renders the shared-link prompt at 1440×900 and 390×844 and the saved city at 1440×900. No JavaScript errors or horizontal overflow were observed. Browser navigation to the real localhost server was restricted in this test environment, so that specific navigation was **not** claimed as tested.
- No live BharatCode completion, production hosting, GitHub repository publication, or hackathon submission was performed in this release.

### Upgrade from v0.9.4
Stop the previous server, extract `RepoWorld-v0.9.5.zip` beside v0.9.4, copy v0.9.4's `.env` and `.data` directories (if present), install requirements, and run `./run.sh`. Local copied links are not externally reachable until deployment.

---

# RepoWorld v0.9.4 — Source-to-city issue evidence

### What changed
- Source-scoped AI investigations now return `observedLocations` only when an identifier from an open issue is observed in **fetched public GitHub source bytes**. The location is mapped to the exact group of an existing city building, including code files absent from the original six-file import sample.
- The current issue panel, not a new permanent sidebar, shows **Code located in the city**. Selecting it focuses the building and opens the existing inspector.
- The map updates issue pins in the current browser session, distinguishing source-observed identifiers from paths merely mentioned in an issue and heuristic suggestions. A better source observation supersedes a speculative building placement for that issue.
- If BharatCode times out after source discovery, the deterministic fallback still exposes observed source locations and says the model did not respond.
- No new GitHub scopes, login, data schema, city camera, colors, dependencies, or secret requirements.

### Verification
- **142 Python and 36 JavaScript tests passing**, including OpenWISP #717 path-to-city mapping, unsupported-match negative tests, the model-timeout fallback, and issue pin navigation.
- Offline Chromium at 1440×900 and 390×844 confirms the source-observed issue sheet, its city jump, and no uncaught browser errors/overflow. Existing import-error and precision-zoom Chromium checks also pass.
- No real BharatCode calls or GitHub import were executed for this new release in the build environment. GitHub provider access on the user's Mac was verified previously; live v0.9.4 end-to-end verification is **pending**.

### Upgrade
Unzip `RepoWorld-v0.9.4.zip` next to v0.9.3, stop the old server, and copy v0.9.3's `.env` and `.data` to preserve your key and saved cities. Install Python dependencies and run `./run.sh`. See README for exact commands.

### Release blockers unchanged
Public HTTPS hosting, persistent production storage, hosted security validation, public source publication, and hackathon submission remain **not completed**. No claim that an issue is a reproduced defect or that its suggested fix was tested.

---

# RepoWorld v0.9.3 — Browser Origin / Import Hotfix

The screenshot showed a **403 origin rejection before GitHub was called**, not a GitHub repository error.

### Changes
- In local development only, `localhost` and `127.0.0.1` can refer to the same configured loopback port even if request Host and Origin use different names. v0.9.2 still rejected that edge case.
- Cross-site requests, wrong ports, malformed origins and missing CSRF tokens are still rejected. Production continues to require the exact configured origin.
- Local 403 responses now explain how to correct the browser address/APP_BASE_URL mismatch without displaying secrets.
- Added `scripts/diagnose_origin.py` (no GitHub or BharatCode calls). It checks the running server's version, both loopback origins, and rejection of a foreign origin.
- Preserved the v0.9.2 import-reliability fixes. **No city renderer, UI layout, API key, or database schema changes.**

### Caution
The user's screenshot alone does not tell us the running server version or actual browser Origin. This patch reproduces and fixes an additional origin mismatch under controlled tests, but a live browser retest is still required. If the diagnostic reports an older server, stop that server before trying the new package.

# RepoWorld v0.9.3 — Local Import / Origin Repair

**Purpose:** Repair common failures in the public GitHub import path, preserving the v0.9 city and AI flows.

## Prior v0.9.2 changes retained

- Resolved local-dev `localhost` versus `127.0.0.1` Origin rejection, with explicit loopback-host and same-port restrictions. Cross-site Origin and production checks remain strict.
- Added full-import diagnostic with browser-style cookies, CSRF, and Origin.

## Verified changes

- Default unauthenticated import reduced from up to 24 GitHub API calls (metadata + tree + 22 source blobs) to at most 8 calls (metadata + tree + six sampled blobs). Server-side authenticated imports use 16 sampled sources by default. Source limits remain configurable with `REPOWORLD_IMPORT_SOURCE_LIMIT` up to 22; zero disables source sampling.
- Source file inspection is concurrent (max three at once), with a bounded overall fetch window and safe partial-graph behavior if GitHub blobs are slow or fail. Tree/API errors still fail clearly rather than generating a fake map.
- GitHub API HTTP 403/429 rate-limit detection now respects `Retry-After` and rate reset headers; invalid server-side tokens return an explicit diagnostic without revealing any secret. Ordinary permission-denied 403s are distinguished from rate limits. Empty and malformed repository responses generate readable errors.
- Invalid repository names are rejected before importing and debiting a budget. Terminal logs summarize sanitized public repo names, import status, and elapsed time.
- The import form shows specific errors and an optional retry cooldown. A long-running import displays a short progress message without adding permanent UI controls.
- Added a safe `scripts/diagnose_github.py` command: 1 metadata request by default, optional second tree request; never prints secret values or response bodies.
- Expanded sampled file extension recognition for common code and HDL projects; static-import edges remain limited to the languages supported by the parser.

## Testing scope

- 138 Python tests and 33 JavaScript tests pass (including new import failures, status propagation, session isolation, rate limits, and city controls).
- Focused Chromium checks of the import error modal pass at 1440×900 and 390×844, with no JavaScript exceptions or horizontal overflow.
- Local server `/api/health` and guest session tests pass when exercised with an isolated SQLite database.
- **Not verified:** Live import from the user's Mac or the public GitHub API from this container. The test environment has no outbound DNS. A live GitHub rate limit, token rejection, unsupported file tree, or network issue may still prevent importing.

## Upgrade from v0.9

Extract this ZIP as `RepoWorld-v0.9.3`. Stop v0.9.2 and copy `../RepoWorld-v0.9.2/.env` and `../RepoWorld-v0.9.2/.data` (if present) to preserve the BharatCode key and saved public cities. Then create/activate a virtualenv, install `requirements.txt`, and run `./run.sh`.

Run `python scripts/check_local_import.py openwisp/openwisp-utils` with the server running to test the entire local guest-session/CSRF/import path, or `python scripts/diagnose_github.py openwisp/openwisp-utils --tree` to test just GitHub access; share only the diagnostic status and redacted server error log, never credentials.

## Unchanged

No new account system, visual redesign, permanent sidebar, AI behavior changes, or external deployment. Public launch and hackathon submission remain uncompleted.
