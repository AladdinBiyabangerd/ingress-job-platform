# Current task

## Completed
- Gemini + NVIDIA model cascades (pushed)
- Recheck: surface first AI miss reason in job `error` + WARNING logs + UI note

## Current state
- Flags all on; still "limit/off" — likely `ai_budget_exceeded` (default daily 200) or all providers fail
- After deploy, UI note will show `[ai_budget_exceeded]` etc.

## Remaining work
- Commit/push diagnostic fix when asked
- Production: raise `AI_GATEWAY_DAILY_CALL_LIMIT` on api+worker (e.g. 1000); recheck and read `[reason]`

## Relevant files
- `worker/worker/market_fit.py`
- `api/app/market_fit_recheck_jobs.py`
- `frontend/components/admin.js`, `collected-admin.js`
