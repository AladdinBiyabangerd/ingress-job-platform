# Current task

## Completed
- Fixed production refresh crash: RSC no longer calls `cookies().set()`; middleware owns Set-Cookie + forwards `x-job-access` (`339bdb0` on `main`).
- Diagnosed “Namizəd” after hard refresh: `/me` name = access-token `name` OR `academy_identities`; identity remembered from id_token on exchange; refresh often has no id_token / no name claim → empty name → account bar falls back to role label `Namizəd`.
- Diagnosed login UX: Job redirected straight to `/portal/oauth/authorize`; desired flow is Academy `/portal/job-account/?next=<authorize…>&registration_intent=…&return_to=…`.
- **Name after refresh:** `_remember_access_identity` UPSERTs access-token `name` into `academy_identities` from `_tokens_from` (exchange/refresh) and `account_payload` (`/me`).
- **Login via job-account:** `/api/auth/login` redirects to `{issuer}portal/job-account/?next=<authorize…>&…` via `buildJobAccountLoginUrl` (`JOB_OIDC_JOB_ACCOUNT_URL` optional override).

## Current state
- Cookie fix shipped (`339bdb0`).
- Name UPSERT + job-account login implemented in working tree; need API + web redeploy and verify.

## Decisions
- Cookie mutation: middleware / Route Handlers / Server Actions only — never RSC.
- Prefer UPSERT identity in DB over delete/recreate; do **not** invent a parallel “active session in Job DB until RT expires” auth model.
- Keep `prompt=login` only after Job logout (`job_guest`).
- Login entry is job-account; authorize stays in `next=` (plus existing authorize query params).

## Remaining
1. Redeploy Job API + web; verify hard refresh keeps real name and “Daxil ol” hits job-account.
2. Optional UI: don’t prefer bare role label over a clearer fallback (account-bar already uses email before role).

## Relevant files
- `api/app/account.py` (`_remember_access_identity`, `_tokens_from`, `account_payload`)
- `api/app/auth_oidc.py` (`verify_access_token` name claim, `identity_from_id_token`)
- `api/app/profiles.py` (`remember_academy_name`, `academy_identities`)
- `api/tests/test_auth_refresh.py`
- `frontend/app/api/auth/login/route.js`
- `frontend/lib/oidc-authorize.js` / `frontend/lib/oidc-authorize.test.mjs`
- `frontend/lib/server/oidc.js`
- `frontend/middleware.js`, `frontend/lib/server/me.js` (cookie fix — done)
- `docs/railway.md`, `api/.env.example`
