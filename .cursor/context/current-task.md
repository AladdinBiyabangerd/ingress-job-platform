# Current task

## Completed
- Root cause found on **ingress-academy**, not leftover job cookies
- Academy fix: `prompt=login` now forces logout unless `existing_account=1`

## Current state
User confirmed job cookies clear on logout. Portal = Test Aladdin, Job still
reopened Tofig after login because Academy intentionally skipped `prompt=login`
whenever `registration_intent` was set (Job always sends employer/candidate
intent from the register menu). Portal session was reused silently.

## Decisions
- Academy: logout on `prompt=login` unless job intent + `existing_account=1`
- Job: keep always sending `prompt=login`; send `existing_account=1` only when
  job itself still has a live session and is adding a role
- Prior job-side cookie hardening (guest lock, `job_at`/`job_rt`) still useful

## Remaining
- Restart Academy (`runserver`) so the OIDC authorize change is live
- Verify: Job logout → register again → Academy asks for account → Test Aladdin
  (or whoever you sign in) appears on Job, not Tofig
- CV/AI Phase 1 next: profile confirm screen (`/profile/review`)

## Relevant files
- `ingress-academy/portal/oidc/views.py`
- `ingress-academy/portal/tests/test_job_oidc.py`
- `ingress-job/frontend/app/api/auth/login/route.js`
- `ingress-job/frontend/lib/server/oidc.js`
