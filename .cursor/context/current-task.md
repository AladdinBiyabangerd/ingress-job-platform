# Current task

## Completed
- Postgres TEXT id fix for market-fit recheck
- Persist recheck progress across refresh
- Recheck = missing AI score only; oldest→newest; backfill ASC + UI limit 40

## Current state
- “AI ilə yenidən yoxla” ignores threshold UI; only `ai_confidence` null

## Decisions
- Publish-by-% still uses score/op/threshold
- Recheck/backfill process oldest id first

## Remaining work
- Commit when asked
- QA: empty AI rows get picked; order oldest first

## Relevant files
- `frontend/components/admin.js`, `collected-admin.js`
- `frontend/lib/recheck-market-fit.js`
- `api/app/cabinet_store.py` (backfill ORDER BY id ASC)
