# Current task

## Completed
- Profile review densify + tabs (local, uncommitted)
- Trend detail layout:
  - Static hero/you copy removed; back right of breadcrumbs
  - Companions (learn/have) → two-col: companions left, facts right
  - Jobs button → `/trends/{id}/jobs` with server pagination (20/page)
  - Detail SSR skips jobs payload (`jobs_limit=0`)

## Current state
- Local only; not committed.

## Remaining
1. Visual OK (logged-in with companions + jobs page pager)
2. Commit when approved

## Relevant files
- `frontend/components/trend-detail.js`
- `frontend/components/trend-jobs.js`
- `frontend/app/{,en/,ru/}trends/[skillId]/jobs/page.js`
- `frontend/app/globals.css`
- `frontend/lib/{api,copy,server/trends}.js`
- `api/app/trends.py`, `api/app/routers/trends.py`
