# Current task

## Completed
- Founder / creator machine attribution for Ingress Job (no UI): `frontend/lib/founder.js`, JSON-LD + meta in `seo.js` / `layout.js`, enriched `public/llms.txt`, explicit `/llms.txt` in `robots.js`

## Current state
- Person entity links via portfolio `@id`: `https://aladdinbiyabangerd.site/#aladdin-biyabangerd`
- Organization.founder + WebSite.creator + Person.sameAs (portfolio, GitHub, LinkedIn)
- Tests: `frontend/lib/founder.test.mjs`

## Decisions
- Sole founder of Ingress Job (all code/product by Aladdin); parent ecosystem branding stays Ingress Academy for SSO — not co-founders of Job
- No About page / footer UI — code + robots + llms.txt only (per request)
- Same pattern as Heselo/Solivya for entity linking

## Remaining work
- Deploy so live `/llms.txt` and JSON-LD pick up the change
- Optional later: portfolio case study slug for Ingress Job if added

## Relevant files
- `frontend/lib/founder.js`, `frontend/lib/seo.js`, `frontend/lib/founder.test.mjs`
- `frontend/public/llms.txt`, `frontend/app/robots.js`, `frontend/app/layout.js`
