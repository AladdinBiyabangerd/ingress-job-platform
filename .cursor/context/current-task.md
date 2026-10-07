# Current task

## Completed
- Auth session unify (Job + Academy confidential + ensureSession).
- Academy: `client_secret_hash` on `OidcClient`; token endpoint requires secret for confidential clients; `sync_job_web_client` is confidential + PKCE from `OIDC_JOB_CLIENT_SECRET`; migration `0129`; tests.
- Job API: `OIDC_CLIENT_SECRET` on exchange/refresh body; fail-closed when empty; tests assert secret in upstream form.
- Frontend: `ensureSession` + `job_exp`; wired into `authorizedApi`, `getMe` / `sessionAccess`, `refresh.js` bearer, RSC seeders, middleware company gate, login callback.
- Local deploy sync: matching secrets in Academy + Job `.env`; Academy `portal.0129` migrated; `sync_oidc_job_client` updated `job-web`.
- Academy start (Dockerfile + Nixpacks) runs `sync_oidc_job_client` after migrate (with interview sync).
- BFF write migration: apply, consents PUT, data export → FastAPI server actions (`applyToJob`, `saveConsents`, `exportMyData`).
- **Fix: staff-deactivated Job role re-granted on login**
  - Root cause: OIDC `registration_intent` → `apply_registration_intent` re-added `JOB_EMPLOYER`; `/company` login also sent `intent=job_employer`.
  - Academy: `JobRoleStaffBlock` + migration `0130`; staff revoke blocks intent restore; staff grant clears block.
  - Job: company session login without employer intent.
  - Tests: `test_job_oidc`, `test_staff_users` (38 OK).

## Remaining
- Deploy Academy (migrate `0130`) + Job frontend; for already-revoked users, staff must toggle Job Employer off once more so the block row is created.
- Production Railway: matching `OIDC_JOB_CLIENT_SECRET` / `OIDC_CLIENT_SECRET` if not done.
- Remaining client BFF: privacy delete, match feedback, CV download; unseeded GET fallbacks.

## Decisions
- Staff revoke of Job groups survives OIDC intent; public “become employer” cannot undo staff revoke until staff re-grants.
- Company page login is session restore only (no `registration_intent`).

## Relevant files
- `ingress-academy/portal/{job_access,models,views}.py`
- `ingress-academy/portal/migrations/0130_jobrolestaffblock.py`
- `ingress-academy/portal/tests/{test_job_oidc,test_staff_users}.py`
- `frontend/lib/server/company.js`
- `frontend/components/company-form.js`
