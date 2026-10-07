# Current task

## Completed
- Diagnosed production refresh crash: `Cookies can only be modified in a Server Action or Route Handler` (digest `3689583221`).
- Root cause: `ensureRscSession` / `getMe` called `cookies().set()` from RSC (root layout); illegal in Next.js 15.

## Current state
- Middleware refreshes session cookies on HTML navigations and forwards `x-job-access`.
- RSC `getMe` / `ensureRscSession` only read (forwarded header or `job_at`); Server Actions may still write via `next-action`.
- Needs Job **web** redeploy on Railway.

## Decisions
- Cookie mutation stays in middleware (and Route Handlers / Server Actions); never in RSC.

## Remaining
- Redeploy Job frontend (`web`) on Railway; hard-refresh a logged-in page near token expiry to verify.
- (Prior) Redeploy Job API if consent-copy packaging not yet live.

## Relevant files
- `frontend/middleware.js`
- `frontend/lib/server/me.js`
- `frontend/lib/server/oidc.js`
