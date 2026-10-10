# Current task

## Completed
- Hunt-v3 reuse review + product decision (port/adapt, not copy)
- Plan: `~/.cursor/plans/job_detail_analyze_24c3bd32.plan.md`
- **API** `GET /api/v1/me/jobs/{id}/analyze?lang=&refresh=`
  - `api/app/job_analyze.py` — gates, zero-overlap fit, AI schema/prompt
  - Route on `me.py` (no `_require_recommendations`)
  - Tests: `api/tests/test_job_analyze.py` (9 ok)
- **AI warm**: `schedule_job_analyze_ai_warm` + fail cooldown; flag `job_analyze` / `AI_JOB_ANALYZE_ENABLED`
  - Gateway `bypass_cache` for refresh; admin + ops labels; worker flag mirror
- **UI**: BFF `frontend/app/api/auth/me/jobs/[jobId]/analyze/route.js`
  - Analiz et in `job-detail-actions.js` (Save/Share yanında)
  - Panel `job-detail-analyze-panel.js` under header; copy az/en/ru; `.jd-analyze-*` CSS

## Current state
- Implementation landed; **manual QA** on a live job detail still recommended
- Parked: employer upgrade CTAs (unrelated)

## Decisions
- Port into platform; no hunt-v3 vendoring
- Independent of `PRODUCT_RECOMMENDATIONS_ENABLED`
- Deterministic fit always; AI soft-fails when flag/key off
- Report language = UI locale; JD not translated

## Remaining work
1. Manual QA: consent/skills gates, 3 locales, weak-fit, flag off / `ai_pending`
2. Optional: refresh button in panel (`?refresh=1` already supported by API)

## Relevant files
- `api/app/job_analyze.py`, `api/app/routers/me.py`, `api/app/ai_warm.py`, `api/app/ai_flags.py`
- `api/tests/test_job_analyze.py`
- `frontend/components/job-detail/job-detail-{actions,view,analyze-panel,header,mobile-sticky}.js`
- `frontend/app/api/auth/me/jobs/[jobId]/analyze/route.js`
- `frontend/lib/copy.js`, `frontend/app/globals.css`
