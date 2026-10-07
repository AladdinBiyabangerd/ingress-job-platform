# Railway

Academy deploys from a Dockerfile and `nixpacks.toml`. This repo does the same
for each service, and `.railway/railway.ts` names the three services so they
do not have to be clicked together in the dashboard.

Do not create the Railway project from this document's steps if you only wanted
the files. Nothing here has been applied.

## Services

| Service | Directory | What a push builds | Process |
|---|---|---|---|
| api | `api/` | `api/Dockerfile` | `uvicorn` on `$PORT`; installs `worker` from the same git commit for in-process CV parse + tesseract |
| web | `frontend/` | `frontend/Dockerfile` (or `frontend/nixpacks.toml`) | `next start` on `$PORT` (no healthcheck) |
| worker | `worker/` | `worker/Dockerfile` | `python -m worker` once per hour, then exit (job crawl; CV drain only as backup) |

CV parse runs in the API after upload (background thread drains `parse_cv_queue`).
The API image pulls the `worker` package from this GitHub repo at
`$RAILWAY_GIT_COMMIT_SHA` (subdirectory `worker/`) because the Docker build
context is only `api/`. The worker cron is for crawling ads (`0 * * * *` UTC)
and must exit. Local Mac scheduling is still `python -m worker schedule`.

`.railway/railway.ts` also creates:

- bucket `cvs` in `ams`, and copies its credentials into the Academy bucket variables
- Postgres service `postgres`

The API service and the hourly worker both get `DATABASE_URL` from that Postgres
service. Crawled jobs, cabinet ads, and applications are rows in that one
database, so a crawl is visible to the API. There is no jobs volume. A Railway
volume can be mounted on only one service, so two volumes would be two sqlite
files, not one shared file.

Leave `DATABASE_URL` unset on the Mac. The API and the worker then keep sharing
`worker/data/jobs.sqlite`, or `JOBS_DB_PATH` when that variable is set.
`JOBS_DB_PATH` is ignored when `DATABASE_URL` is set.

Company and candidate profiles stay in the API file `api/data/accounts.sqlite`.
That file is not the jobs database.

## Apply once, then push

There is no git remote in this repo yet. After one exists:

```bash
npm install railway
railway login
railway link
railway config plan
railway config apply
```

`plan` and `apply` were not run here. A later push deploys the connected services.
Local `npm run dev` still uses port 3010 when `PORT` is unset, and the API still
listens on 8010 when started the usual way.

## Variables you set

No values are stored in git. Leave these unset on the Mac. The app keeps the
current local behavior: CVs in `api/data/cvs/`, Sentry off, traces off.

Set on the API (the bucket variables are wired by `.railway/railway.ts` when
that file is applied; set them yourself only if you use another bucket):

| Variable | Role |
|---|---|
| `BUCKET_NAME` | S3 bucket. Required together with the two keys. |
| `BUCKET_ACCESS_KEY` | S3 access key. |
| `BUCKET_SECRET_KEY` | S3 secret key. |
| `BUCKET_REGION` | Region. Academy uses this name. |
| `BUCKET_ENDPOINT` | S3-compatible endpoint, no trailing slash needed. |
| `SENTRY_DSN` | When empty, Sentry does not start. |
| `SENTRY_ENVIRONMENT` | Optional. Defaults from `DEBUG`. |
| `SENTRY_TRACES_SAMPLE_RATE` | Optional. Default `0.0`, same as Academy. |
| `DEBUG` | `False` on Railway. Unset locally means development. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | When empty, no traces are exported. Academy has no OTEL variables. |
| `OTEL_SERVICE_NAME` | Optional. Default `ingress-job-api` or `ingress-job-worker`. |
| `OTEL_TRACES_SAMPLER_ARG` | Optional sample ratio from 0 to 1. Default `1.0` only if an endpoint is set. |
| `OTEL_SDK_DISABLED` | Set true to force traces off. |
| `DATABASE_URL` | Shared Postgres URL for the jobs database. Wired from the `postgres` service onto the API and the worker. Unset locally keeps sqlite. |
| `JOBS_DB_PATH` | Optional sqlite path, used only when `DATABASE_URL` is unset. Unset locally uses `worker/data/jobs.sqlite`. Do not set this on Railway. |
| `CORS_ORIGINS` | Optional comma-separated browser origins. Localhost 3010 is always allowed. |
| `EMAIL_HOST` | Academy SMTP host. Unset means no mail is sent; in-site notifications are still saved. |
| `EMAIL_PORT` | Academy SMTP port. Default 587. |
| `EMAIL_HOST_USER` | Academy SMTP user. Also the From address when `DEFAULT_FROM_EMAIL` is unset. |
| `EMAIL_HOST_PASSWORD` | Academy SMTP password. Not stored in git. |
| `EMAIL_USE_TLS` | Academy STARTTLS flag. Default true. |
| `EMAIL_USE_SSL` | Academy SSL flag. Default false. |
| `EMAIL_TIMEOUT` | Academy SMTP timeout in seconds. Default 20. |
| `DEFAULT_FROM_EMAIL` | Academy From address. The display name sent by this API is Ingress Job. |
| `OIDC_ISSUER` | Same name the API already uses. |
| `OIDC_AUDIENCE` | Same name the API already uses. |
| `OIDC_JWKS_URL` | Same name the API already uses. |
| `OIDC_CLIENT_ID` | Same name the API already uses (`job-web`). |
| `OIDC_CLIENT_SECRET` | Same value as Academy `OIDC_JOB_CLIENT_SECRET`. API-only — never on the web service. Set before redeploying Academy (start runs `sync_oidc_job_client` and fails closed if missing). |
| `OIDC_AUTHORIZE_URL` | Same name the API already uses. |
| `OIDC_TOKEN_URL` | Same name the API already uses. |
| `OIDC_REDIRECT_URIS` | Include the deployed web callback. |
| `OPENAI_API_KEY` | Optional. Enables `ai_gateway` (CV AI #1, digest intro, embeddings, match why). |
| `AI_GATEWAY_ENABLED` | Optional. `0` forces AI off even when a key is set. Staff can also toggle flows in Moderasiya without changing env. |
| `AI_EMBEDDING_MODEL` | Optional. Default `text-embedding-3-small` (AI #2). |
| `AI_RERANK_ENABLED` | Optional. Default follows gateway; `0` keeps structured-only matches. |
| `AI_MATCH_WHY_ENABLED` | Optional. Default follows gateway; `0` skips LLM why sentences. |

Postgres for AI #2 must support `CREATE EXTENSION vector` (pgvector). Local compose uses `pgvector/pgvector:pg16`. Stock Railway Postgres may need a pgvector-capable image/plugin; without it matches stay structured-only.

Set on the web service if the private-host wiring is not applied:

| Variable | Role |
|---|---|
| `JOB_API_BASE_URL` | Full server-side API base. Preferred. Example: `http://${{api.RAILWAY_PRIVATE_DOMAIN}}:${{api.PORT}}`. Must be `http://`, never `https://`. Unset locally keeps `http://127.0.0.1:8010`. |
| `API_PRIVATE_HOST` | API private hostname only. Used when `JOB_API_BASE_URL` is unset. |
| `API_PORT` | API listen port. Must match the API service `PORT` variable (set `PORT=8080` on **api** yourself — `${{api.PORT}}` does not read Railway's runtime injection). |
| `APP_URL` | Public web origin for OIDC. Optional when `RAILWAY_PUBLIC_DOMAIN` is present. |
| `NEXT_PUBLIC_APP_URL` | Same fallback as `APP_URL`. |
| `JOB_OIDC_ISSUER` | Academy issuer. Unset locally keeps `http://127.0.0.1:8000/`. |
| `JOB_OIDC_CLIENT_ID` | Default `job-web`. |
| `JOB_OIDC_AUTHORIZE_URL` | Academy authorize URL (used as `next=` target). |
| `JOB_OIDC_JOB_ACCOUNT_URL` | Academy job-account entry. Default `{issuer}portal/job-account/`. Login redirects here, not bare authorize. |
| `JOB_OIDC_LOGOUT_URL` | Ignored. Job logout stays on the public site and does not call Academy. |

### Private network checklist (empty UI = web cannot reach API)

The browser only talks to the **web** public domain. Next.js (SSR + `/api/*` BFF)
calls the API over Railway private DNS. If that hop fails, the shell still
renders and job lists stay empty. DevTools Network will **not** show
`api.railway.internal` — only same-origin `/api/jobs` after the client retry
(SSR errors or an empty first payload). If even `/api/jobs` is missing, you
are on an old web deploy that skipped the client fetch.

1. On **api**: set `PORT=8080` as a service variable (not only runtime). Start
   command must be `python start.py` (Dockerfile default). Do **not** use
   `uvicorn ... --port $PORT` — Railway does not expand `$PORT`, uvicorn then
   crashes, and web `/api/jobs` returns 502. `start.py` listens on `::`.
2. On **web**: set
   `JOB_API_BASE_URL=http://${{api.RAILWAY_PRIVATE_DOMAIN}}:${{api.PORT}}`
   (same project + environment; `http`, not `https`). Include **`:8080`** —
   omitting the port talks to :80, not the API.
3. Keep a public domain on **web** only. API may stay private.
4. Redeploy **api** then **web**. In web logs, a failed BFF shows
   `[api/jobs] upstream failed` or `[home] getJobs failed` with the resolved base URL.
5. Quick check: open `https://<web-domain>/api/jobs` — JSON with `items` means
   private hop works; HTTP 502 with empty `items` means it does not.

Set the same `DATABASE_URL` on the worker. `.railway/railway.ts` wires the
Postgres service URL onto both services; do not point them at different
databases, and do not set `JOBS_DB_PATH` on Railway. Set the same `SENTRY_*`
and `OTEL_*` names on the worker if that process should report. `JOOBLE_API_KEY`,
`REED_API_KEY` and `HH_API_KEY` stay optional; those sources stay switched off
when the key is missing (hh.ru answers 403 to anonymous API calls). With
`JOOBLE_API_KEY` set, Jooble runs at most every 6 hours with 3 requests and
stops for the month at 450 counted requests (`JOOBLE_MONTHLY_BUDGET`, table
`api_usage`). The key's 500-request limit is shared by every environment that
uses it, so set it on one worker only. `REED_API_KEY` feeds the Reed.co.uk
connector (every 6 hours, soft monthly cap `REED_MONTHLY_BUDGET`, default
3000). www.reed.co.uk/robots.txt disallows `/api/`; the owner approved a
narrow exception for the official keyed API path `https://www.reed.co.uk/api/1.0/`
only (`ROBOTS_EXCEPTIONS` in `worker/worker/http.py`).

CV upload uses the bucket only when `BUCKET_NAME`, `BUCKET_ACCESS_KEY`, and
`BUCKET_SECRET_KEY` are all set. Otherwise files stay in `api/data/cvs/`.
