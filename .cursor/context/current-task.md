# Current task

## Completed
- Phase A: Cloudflare edge checklist in `docs/railway.md`; `.tmp/` gitignored
- Phase B1: API Redis/memory rate limits + human `slow_down` JSON (`api/app/rate_limit.py`)
- Phase B2: Web BFF rate limits + `copy.js` rateLimit.* + home SlowDownBanner
- Phase B3: TrustedHost, docs-off, body size, `FORWARDED_ALLOW_IPS`, internal token compare_digest
- Phase C: Turnstile login gate + cabinet create Turnstile/quota; logout revoke if `JOB_OIDC_REVOKE_URL`
- Phase D: skill installed; triage report in `.tmp/security-audit/` (not full fleet hunt)

## Current state
- Local: limits off unless `RATE_LIMIT_ENABLED=1`; Railway auto-on when `RAILWAY_ENVIRONMENT` set
- Need ops: CF Proxied, Redis on api+web, Turnstile keys, optional revoke URL

## Decisions
- IP-first limits; benefit-framed UX (`slow_down` / never ban language)
- Fail-open public GET when Redis down; fail-closed auth writes by bucket
- Turnstile only when `TURNSTILE_SECRET_KEY` set (HTML gate on login)

## Remaining work
- Ops: Cloudflare dashboard + Railway Redis/env
- Optional: full `security-audit` skill 6-phase run in a **new chat**
- Optional: wire Turnstile token into employer post UI when posting re-enabled

## Relevant files
- `api/app/rate_limit.py`, `api/app/turnstile.py`, `api/app/main.py`, `api/start.py`
- `api/app/account.py`, `routers/jobs.py`, `cabinet.py`, `email_prefs.py`
- `frontend/lib/server/rate-limit.js`, `turnstile.js`, `app/api/auth/login/route.js`
- `frontend/lib/copy.js`, `components/slow-down-banner.js`, `components/home.js`
- `docs/railway.md`, `.tmp/security-audit/REPORT.md`
