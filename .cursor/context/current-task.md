# Current task

## Completed
- Fix AI market-fit recheck stuck on «Dayandırılır…» (orphaned cancelling jobs)

## Current state
- Backend: stale jobs (`queued`/`running`/`cancelling` with no progress >90s) finalize on GET poll
- Backend: cancel-while-queued no longer overwritten by `running`
- Frontend: client stale timeout (~105s) + cancel failure resets stopping UI

## Decisions
- Stop waits for in-flight AI ad; dead worker is healed via stale finalize → `cancelled`/`failed`

## Remaining work
- Deploy API + frontend
- Unstick live UI now: hard refresh, or clear `sessionStorage` key `ij:marketFitRecheck:crawled`

## Relevant files
- `api/app/market_fit_recheck_jobs.py`
- `frontend/lib/recheck-market-fit.js`
- `frontend/components/collected-admin.js`
- `frontend/components/admin.js`
- `frontend/components/admin-crawl-rejects.js`
- `api/tests/test_admin.py`
