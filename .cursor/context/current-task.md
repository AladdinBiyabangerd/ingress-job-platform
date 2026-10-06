# Current task

## Completed
- Job OIDC: `prompt=login` only after logout (`job_guest`); SSO reused otherwise.
- Exchange checks Academy `id_token` nonce; JWKS cache 1h.
- Academy: `openid` on job-web/interview-web allowed scopes; SSO test without prompt.

## Remaining
- Deploy Academy so `job-web` rows pick up `openid` on next client sync.

## Relevant files
- `frontend/lib/oidc-authorize.js`, `frontend/app/api/auth/login/route.js`
- `api/app/account.py`, `api/app/auth_oidc.py`
- `ingress-academy/portal/oidc/{views,clients,tokens}.py`
