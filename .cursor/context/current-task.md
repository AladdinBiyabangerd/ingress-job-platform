# Current task

## Goal
CV upload stuck on “Növbə / Təhlil gedir” — parse never left pending.

## Completed
- Cause: Postgres jobs-db cursor had no `rowcount`. Drain `_claim` crashed, jobs stayed `pending`.
- Adapter now reports `rowcount` (api + worker). Claim/cancel treat missing rowcount as affected.
- GET `/profile` while pending/processing re-kicks in-process drain (recovers stranded queue).

## Remaining
- Deploy api + worker (same commit — API image installs worker from SHA).
- After deploy, reopen `/profile/review` (poll GET will drain the stuck PDF).

## Relevant files
- `api/app/jobs_db.py`, `worker/worker/jobs_db.py`, `worker/worker/cv_queue.py`
- `api/app/routers/profile.py`, `api/app/cv_profile.py`
