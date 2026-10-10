# Current task

## Completed
- Rules-first CV parse (prior commit `c8defa8`)
- Root cause of remaining stall: `done` was uncommitted until AI/embed finished
- Mid-drain `_commit()` after rules `done` so `/profile` poll sees it
- Export `any_provider_key` from worker/api `ai_gateway` (fixes tidy ImportError)

## Current state
- Local tests green (`tests.test_cv_queue`)
- Needs commit + Railway redeploy (API installs worker from git SHA)

## Decisions
- Commit before optional AI/embed so UI unblocks immediately

## Remaining work
- Commit/push and redeploy API + worker
- Re-upload CV to verify “Təhlil” clears within seconds

## Relevant files
- `worker/worker/cv_queue.py`
- `worker/worker/ai_gateway/__init__.py`
- `api/app/ai_gateway/__init__.py`
- `worker/tests/test_cv_queue.py`
