# Current task

## Completed
- Login always redirects to Academy `/portal/job-account/` (no skip to authorize on live Job session)

## Current state
`buildLoginRedirectUrl` always uses `buildJobAccountLoginUrl`. Live sessions may still set `existing_account=1` on the authorize query inside `next=`.

## Decisions
- Never auto-authorize from Job when a portal/Job session exists; always land on job-account

## Remaining work
- Deploy frontend; if Academy job-account itself auto-continues without confirm, that is Academy-side

## Relevant files
- `frontend/lib/oidc-authorize.js`
- `frontend/app/api/auth/login/route.js`
- `frontend/lib/oidc-authorize.test.mjs`
