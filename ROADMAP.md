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

## Open release gates (not assumed complete)
1. **v0.9.8 live check:** GitHub CI, Render deployed commit, public /api/health and /api/ready, and a real browser Issue Radar test. Local fixture tests cannot certify GitHub CORS/network access for every visitor.
2. **Authenticated provider reliability:** Add a least-privilege server-side GITHUB_TOKEN privately on Render if source-verified issue investigations must work when the server's shared GitHub IP is rate-limited; verify behavior and 401/403 handling.
3. **BharatCode live inference:** Configure BHARATCODE_API_KEY privately in Render; prove live answers, citations, timeouts and budget enforcement against the actual hosted service. Do not claim AI inference from deterministic fallbacks.
4. **Free-tier limitations:** Cold starts after inactivity and deletion of temporary SQLite sessions/cities/quotas when the app spins down, restarts or redeploys. Durable free storage or a static/serverless migration needs separate architectural work and real tests.
5. **Release QA:** Test fresh and returning browsers, mobile layouts, large/small repos, Issue Radar, source links, source-grounded assistant, and intentional failure/429 scenarios.
6. **Submission:** Verify official event deadline and required artifacts, record an accurate short demo, add any required screenshots, and submit source and hosted URL. Do not claim it has been submitted.

Avoid gratuitous redesigns or paid infrastructure changes before these gates.
