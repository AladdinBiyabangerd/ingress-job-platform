# Current task

## Completed
- Diagnosed email `/r/<token>` HTTP 500 on production
- Fixed frontend click redirect + unsubscribe `await params`

## Current state
Root cause: `noStore(Response.redirect(...))` — `Response.redirect` headers are immutable → TypeError → empty 500.
Fix uses `NextResponse.redirect` + `await params` + same-origin `/jobs/{id}` only.
Uncommitted; needs **frontend deploy** to Railway for the email link to work.

## Decisions
- Email clicks must 302 only to on-site `/{az|en|ru}/jobs/{id}`
- Empty API `APP_URL` → 503 `app_url_unconfigured` (not blank Location)

## Remaining work
- Deploy frontend (and API if email_prefs change desired)
- Smoke: open email `/r/...` → lands on job detail

## Relevant files
- `frontend/app/r/[token]/route.js`
- `frontend/app/api/unsubscribe/[token]/route.js`
- `api/app/routers/email_prefs.py`
