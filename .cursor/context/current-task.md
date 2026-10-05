# Current task

## Completed
- Logout fix attempt 2 (this chat): cookie rotation + always prompt=login

## Current state
User report: Portal = Test Aladdin (İşçi), Job = Tofig Mikayilzada (İşəgötürən).
After logout + login, Job still opens Tofig. Portal session is a different person —
so Job was restoring leftover cookies, not following Portal.

## Decisions
- Stop trusting legacy cookies (`job_access_token` / `job_refresh_token`).
  New names only: `job_at`, `job_rt`, `job_st`. Legacy names are expired on auth
  responses but never read for session.
- Always send `prompt=login` to Academy (do not skip for existing_account).
- Keep `job_guest` through login start; callback accepts only matching `job_st`.
- Logout returns 200 HTML + JS redirect so Set-Cookie applies before navigation.

## Remaining
- User verify: logout → login as Test Aladdin → Job shows Test Aladdin, not Tofig
- Hard-refresh / restart `npm run dev` if old bundle still serves legacy cookie names
- CV/AI Phase 1 next: profile confirm screen (`/profile/review`)

## Relevant files
- `frontend/lib/server/oidc.js`
- `frontend/app/api/auth/login/route.js`
- `frontend/app/api/auth/callback/route.js`
- `frontend/app/api/auth/logout/route.js`
- `frontend/middleware.js`
