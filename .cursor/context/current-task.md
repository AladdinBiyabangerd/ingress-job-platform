# Current task

## Completed
- Moderasiya: Academy `job-ops-status` dizaynı ilə Status tabı
- Proxy: `GET /api/auth/admin/ops-status?days=`
- KPI, LinkedIn extension, mənbələr / AI detalları (Academy layout)

## Current state
- Uncommitted: ops status tab + prior admin queue polish

## Decisions
- Staff Moderasiya tabı; eyni `/api/v1/admin/ops-status` payload
- Period: 1/7/30 + custom → rolling `days` (API 1–90)
- Visual: Job tokenləri, Academy strukturu (KPI grid, chips, tables, pills)

## Remaining work
- Browser QA on `/admin` → Status
- Commit when asked

## Relevant files
- `frontend/components/admin-ops-status.js`
- `frontend/components/admin.js`
- `frontend/app/api/auth/admin/ops-status/route.js`
- `frontend/lib/copy.js`
- `frontend/app/globals.css`
- `api/app/ops_status.py`
