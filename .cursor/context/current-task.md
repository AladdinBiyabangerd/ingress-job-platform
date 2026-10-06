# Current task

## Completed
- Staff Moderasiya tab: per-flow AI toggles in jobs DB (`ai_feature_flags`). Env `0` still hard-off; no need to delete `OPENAI_API_KEY`.

## Remaining
- Deploy Academy so `job-web` rows pick up `openid` on next client sync (previous OIDC work).

## Relevant files
- `api/app/ai_flags.py`, `worker/worker/ai_flags.py`
- `api/app/routers/admin.py`, `frontend/components/admin-ai-flags.js`
- `frontend/app/api/auth/admin/ai-flags/route.js`
