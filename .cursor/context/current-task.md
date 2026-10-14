# Current task

## Completed
- Viewed jobs: mark on detail, badge on list+detail, board filter `viewed`
- Original opens: count unique users who opened original/external apply URL; show on list+detail

## Current state
- Tables: `viewed_jobs`, `job_original_opens`
- APIs: `POST/GET /me/viewed-jobs…`, `GET /jobs?viewed=true`, opens recorded on `/original` + external `/apply`
- Frontend: filter chip, card/detail badges, interest count

## Decisions
- Unique openers (not raw click count)
- Guests with `viewed=true` get empty list (no 401 on public proxy)
- Prefer `original_opens` over on-site `applications` when both could apply

## Remaining work
- Manual QA on board + detail while logged in
- Commit when asked

## Relevant files
- `api/app/viewed_jobs.py`, `original_opens.py`, `sqlite_jobs.py`, `routers/jobs.py`, `routers/me.py`
- `frontend/components/viewed-jobs.js`, `job-board-card.js`, `home.js`, `job-detail/*`
- `frontend/lib/jobs-params.js`, `copy.js`
