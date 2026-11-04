# RepoWorld — Remaining public-launch gates

## v0.9.6 implemented and locally verified
- Same existing 3D city, Issue Radar, source-scoped BharatCode assistant, precision zoom and minimal navigation.
- Anonymous/guest throttle isolation behind reverse proxies; persistent global quota intact.
- Bounded HTTP request bodies including streaming requests.
- Production HTTPS security and frontend revalidation headers.
- Render self-URL configuration, persistent-disk readiness guard and Singapore Starter Blueprint.
- Safe hosted smoke tool and public ZIP sanitization audit.

## Still not completed
1. **Public source** — Create the actual GitHub RepoWorld repository and push the audited source; no repo was created by this release.
2. **Hosting** — Connect Render, review the paid Starter + persistent disk configuration, set the BharatCode secret server-side, deploy and check `/api/ready`.
3. **Live hosted flow** — Verify fresh visitor import, existing-visitor persistence, issue markers, source links, AI answer with valid code evidence, anonymous quota enforcement and real browser responsive zoom.
4. **Abuse/ops** — Configure edge rate limiting/bot protection, monitor AI spending, confirm service restarts retain data, and review logs without secrets.
5. **Submission** — Record accurate demo footage and submit public URL/source to official hackathon; `BharatCode.txt` should reflect real published links only once they exist.

**Do not expand UI or reintroduce login before these gates close.**
