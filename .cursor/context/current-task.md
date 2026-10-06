# Current task

## Goal
Railway home: UI var, Network-də API yox, data yox.

## Completed (code, not deployed)
- Home SSR `force-dynamic`; empty/error olanda client `/api/jobs` çağırır (DevTools-da görünməlidir).
- `JOB_API_BASE_URL` portsuz olsa `:8080` əlavə olunur (prod).
- Node `--dns-result-order=ipv6first` (Dockerfile + instrumentation).
- Web logs: `[home] getJobs failed` / `[api/jobs] upstream failed`.

## Remaining
- Web + api redeploy. Yoxla: `https://<web>/api/jobs` JSON `items`.
- `JOB_API_BASE_URL=http://${{api.RAILWAY_PRIVATE_DOMAIN}}:8080` (port şərtdir).

## Relevant files
- `frontend/components/home.js`, `frontend/lib/api.js`, `frontend/app/api/jobs/route.js`
- `frontend/app/page.js`, `frontend/instrumentation.js`, `frontend/Dockerfile`
