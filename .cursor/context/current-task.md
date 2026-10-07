# Current task

## Completed
- Profile review densify + tabs (local, uncommitted)
- Trend detail layout:
  - Static hero/you copy removed; back right of breadcrumbs
  - Companions (learn/have) → two-col: companions left, facts right
  - Jobs button → `/trends/{id}/jobs` with server pagination (20/page)
  - Detail SSR skips jobs payload (`jobs_limit=0`)

## Current state
- Committed and pushed: `925c4e7` on `main`.

## Remaining
- None for this task (visual check on deploy optional)

## Relevant files
- `frontend/components/trend-detail.js`
- `frontend/components/trend-jobs.js`
- `frontend/app/{,en/,ru/}trends/[skillId]/jobs/page.js`
- `frontend/app/globals.css`
- `frontend/lib/{api,copy,server/trends}.js`
- `api/app/trends.py`, `api/app/routers/trends.py`
