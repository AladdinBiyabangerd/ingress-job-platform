# Current task

## Completed
- Admin **Səliqə növbəsi** tab (`job_tidy`):
  - Lists published messy ads without `cleaned_text`
  - Start all / start selected + Stop (async job like market-fit recheck)
  - Tab order: queue → collected → rejected → crawl_rejects → tidy → AI → status (+ manual last)
- API: `GET /admin/job-tidy`, `POST/GET/cancel /admin/job-tidy/run…`
- Worker: `tidy_one()` shared by hourly sync + staff run

## Current state
- Ready for local QA on `/admin?tab=tidy`
- Academy ops-status `usage_today` parity still pending (prior chat)

## Decisions
- Queue = published + empty `cleaned_text` + `messy()` (same gate as worker)
- Stop keeps already-saved `cleaned_text`
- Manual tab kept after Status (not in the user’s named order)

## Remaining
1. Local QA: open tidy tab, start/stop, confirm detail UI uses `cleaned_text`
2. Commit when asked
3. (Other) Academy `job-ops-status` usage table parity — new chat

## Relevant files
- `frontend/components/admin-job-tidy.js`, `admin.js`, `lib/copy.js`, `lib/job-tidy-run.js`, `lib/server/refresh.js`
- `api/app/job_tidy_admin.py`, `job_tidy_jobs.py`, `routers/admin.py`
- `worker/worker/tidy.py` (`tidy_one`)
- Tests: `api/tests/test_job_tidy_admin.py`
