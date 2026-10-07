# Current task

## Completed
- Admin first-paint speedup: SSR loads only moderation queue (`/admin/jobs`).
- Applications, crawled, AI flags load after paint / on tab open.
- Crawled + moderation list APIs return text preview (400 chars); full body via GET by id on edit.
- Crawled `source_name` via join instead of per-row subquery.

## Current state
- Admin first-paint / list-preview changes ready to deploy.
- Profile-review enrichment already committed earlier on this branch.

## Decisions
- List endpoints stay unpaginated for now; payload size cut via text preview + lazy SSR tabs.
- Edit always fetches `GET /api/v1/admin/jobs/{id}` or `.../crawled/{id}` so form/full text stay correct.

## Remaining
1. Smoke-test `/admin` after deploy (queue open, edit job, collected tab, applications badge).
2. Optional later: server-side pagination for crawled/applications if lists grow further.

## Relevant files
- `frontend/lib/server/admin.js`
- `frontend/lib/server/refresh.js`
- `frontend/components/admin.js`
- `frontend/components/collected-admin.js`
- `api/app/crawled_admin.py`
- `api/app/cabinet_store.py`
- `api/app/routers/admin.py`
- `api/tests/test_admin.py`
