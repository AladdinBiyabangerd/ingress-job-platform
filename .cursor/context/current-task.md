# Current task

## Completed
- Auth session unify (Job + Academy confidential + ensureSession).
- Academy: `client_secret_hash` on `OidcClient`; token endpoint requires secret for confidential clients; `sync_job_web_client` is confidential + PKCE from `OIDC_JOB_CLIENT_SECRET`; migration `0129`; tests.
- Job API: `OIDC_CLIENT_SECRET` on exchange/refresh body; fail-closed when empty; tests assert secret in upstream form.
- Frontend: `ensureSession` + `job_exp`; wired into `authorizedApi`, `getMe` / `sessionAccess`, `refresh.js` bearer, RSC seeders, middleware company gate, login callback.
- Local deploy sync: matching secrets in Academy + Job `.env`; Academy `portal.0129` migrated; `sync_oidc_job_client` updated `job-web`.
- Academy start (Dockerfile + Nixpacks) runs `sync_oidc_job_client` after migrate (with interview sync).
- BFF write migration: apply, consents PUT, data export → FastAPI server actions (`applyToJob`, `saveConsents`, `exportMyData`).

## Remaining
- Production Railway: set matching `OIDC_JOB_CLIENT_SECRET` (Academy) + `OIDC_CLIENT_SECRET` (Job api), push/redeploy Academy + Job API (CLI not logged in on this machine).
- Remaining client BFF: privacy delete, match feedback, CV download; unseeded GET fallbacks (skills roles, email-prefs, recommendations).

## Decisions
- `job-web` is confidential; `interview-web` stays public PKCE.
- PKCE kept as defense-in-depth alongside `client_secret`.
- One session path (`ensureSession`); refresh is not limited to `/api/auth/me` BFF.
- Guest lock / legacy cookie expire behavior unchanged.
- Export zip returns base64 from the server action (no BFF hop).

## Relevant files
- `ingress-academy/portal/oidc/{models,views,clients,tokens}.py`
- `ingress-academy/{Dockerfile,nixpacks.toml,DEPLOY.md}`
- `api/app/{config,account}.py`
- `frontend/lib/server/{oidc,ensure-session-logic,me,refresh}.js`
- `frontend/components/{account-actions,profile-form}.js`
- `frontend/middleware.js`
- `frontend/app/api/auth/callback/route.js`
