# RepoWorld — Current development and release gates (November 5, 2026)

## Shipped and tested in source
- Interactive 3D City of Code with precision camera, static import links and code-path explorer.
- Anonymous, read-only public repository imports: official bounded source ZIP on Render Free, REST mode when a private server-side GitHub token is present.
- Issue Radar with server-verified public issue metadata when available; v0.9.8 browser-public CORS fallback when the shared Render GitHub provider quota returns HTTP 429. Browser-only suggestions are not source observations.
- Optional source-scoped BharatCode guidance, with honest fallback when unavailable.
- Production HTTPS/CSRF/CSP protections, body limits and global/guest budgets.
- Published GitHub source and hosted Render Free endpoint: https://repoworld-3b9e.onrender.com (actual deployed version must be checked).

- Free static cold-start launcher: https://repoworld-launch.onrender.com, backed by an independent CDN site with a direct link to the real explorer and checked-in CI tests. Its SVG image probe now checks **actual backend readiness**, not merely successful static asset delivery; live rollout remains to be verified.
- Same-browser, client-only **last public repository** reminder allows explicit re-import after ephemeral database loss; it never caches code or secretly replays imports. This does not solve durable graph/workspace storage.

## v0.9.9 — readability and existing-city improvements

- Keep the older near-black floating city and minimal overlay structure. Rebalance real module towers versus decorative blocks, add stronger roofs and camera-visible window faces, and enlarge labels and key text.
- Add district jump, most-connected-module camera focus, and zoom buttons **inside existing map options**, preserving the uncluttered default view. Sampled static imports remain the only link evidence.
- CI and actual hosted visual/mobile verification are separate gates; monitor overlap and render performance across large repositories.

## Layout QA hardening

- Collision-safe real building and island placement for a full 72-module graph; intentional decorative streets are not code.
- Bounds-based district camera focus and lower-detail rendering for tiny/mobile facades; throttle idle and mobile repaints.
- Tests cover 72-module multi-district layouts, dense single-district layouts and small canvases. Browser screenshots and real-device performance still need independent validation.

## Public-source fallback for the free demo

- An optional source-evidence retrieval can use one bounded codeload public HEAD ZIP for up to 4 actual files when an ephemeral free deployment has no GitHub API token, rather than relying on the shared server-IP REST quota. No archive is executed or trusted as instructions.
- This produces **un-pinned live-branch** evidence, not a verified commit SHA, and must not be confused with a confirmed bug or fix. Model availability still requires a valid BharatCode key.

## Contribution-ready issue notes

- New read-only **Copy investigation notes** action exports a small, explicitly qualified Markdown issue research brief with the canonical original GitHub URL.
- Preserve provenance distinctions: path referenced by issue, browser-only unverified suggestion, fetched source excerpt and AI suggestion are not equivalent. Switching issues cannot copy a previous issue's guide.
- No repository token, sign-in, GitHub posting, server persistence or additional inference required.

## Browser issue lead to public source (v0.9.12)
- Explicit opt-in **Inspect public source** in the existing issue drawer when the GitHub issue feed comes from the browser due to server provider quota.
- Source inspection is a separate saved-repo/CSRF-scoped API with strict body and hourly source I/O budgets, bounded archive/tree retrieval, and no AI call or automatic request. It never verifies the browser issue or upgrades a speculative city pin.
- Copy notes retain independently fetched source references, marked as such; source excerpts are code facts but not issue causality. Empty/error states remain honest.
- Browser-only and regular source workflows have distinct provenance; full hosted real-GitHub test remains an outstanding release gate.

## Issue investigation clarity (v0.9.13)
- Prefer complete received issue-body context over the short list snippet when copying notes; keep a bounded, disclosed partial report when necessary.
- Group independent public source results into literal identifier text observations versus weaker filename/path hints; do not treat candidates as proof of defect relevance.
- Preserve current original issue links, source references, explicit no-AI disclosure, and the minimalist existing Issue Radar drawer. No new backend requests or permanent panels.

## Offline browser city map (v0.9.14)
- Explicit one-city public map backup in browser localStorage, with structural/URL/path validation, whitelisted metadata and size bounds. No credential or full source text capture.
- User can open a read-only local 3D preview after Render Free loses server-side SQLite; tool calls for issue feeds, AI, and server impact analysis are disabled. Browser-only filenames/path search and sampled building inspection remain.
- Reconnect requires explicit re-import under existing quotas, and local storage can be cleared. This is **not** cross-device, durable server persistence or a server-authenticated graph restoration.

## Open release gates (not assumed complete)
1. **v0.9.8 live check:** GitHub CI, Render deployed commit, public /api/health and /api/ready, and a real browser Issue Radar test. Local fixture tests cannot certify GitHub CORS/network access for every visitor.
2. **Authenticated provider reliability:** Add a least-privilege server-side GITHUB_TOKEN privately on Render if source-verified issue investigations must work when the server's shared GitHub IP is rate-limited; verify behavior and 401/403 handling.
3. **BharatCode live inference:** Configure BHARATCODE_API_KEY privately in Render; prove live answers, citations, timeouts and budget enforcement against the actual hosted service. Do not claim AI inference from deterministic fallbacks.
4. **Free-tier limitations:** Cold starts after inactivity and deletion of temporary SQLite sessions/cities/quotas when the app spins down, restarts or redeploys. Durable free storage or a static/serverless migration needs separate architectural work and real tests.
5. **Release QA:** Test fresh and returning browsers, mobile layouts, large/small repos, Issue Radar, source links, source-grounded assistant, and intentional failure/429 scenarios.
6. **Submission:** Verify official event deadline and required artifacts, record an accurate short demo, add any required screenshots, and submit source and hosted URL. Do not claim it has been submitted.

Avoid gratuitous redesigns or paid infrastructure changes before these gates.
