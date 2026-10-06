# Current task

## Goal
Railway-də frontend UI gəlir, amma data yoxdur — private network web→api hop.

## Completed (code)
- API listen: `--host ::` (`api/Dockerfile`, `api/nixpacks.toml`, `.railway/railway.ts`) — IPv6 private net.
- Web URL: `JOB_API_BASE_URL=http://<api private>:<PORT>`; api `PORT=8080` fixed in IaC.
- BFF `/api/jobs` logs `[api/jobs] upstream failed` + `docs/railway.md` checklist.

## Current state
- Dəyişikliklər local; deploy + Railway dashboard env hələ təsdiqlənməyib.
- CLI login yoxdur (`railway whoami` → Unauthorized).

## Remaining (Railway dashboard / deploy)
1. **api** Variables: `PORT=8080` (service variable). Redeploy api (yeni `--host ::` image).
2. **web** Variables:
   `JOB_API_BASE_URL=http://${{api.RAILWAY_PRIVATE_DOMAIN}}:${{api.PORT}}`
   (`http`, not `https`). Redeploy web.
3. Check: `https://<web>/api/jobs` → `items` dolu; web logs-da upstream failed olmamalı.

## Relevant files
- `api/Dockerfile`, `api/nixpacks.toml`, `.railway/railway.ts`
- `frontend/lib/api.js`, `frontend/app/api/jobs/route.js`
- `docs/railway.md`
