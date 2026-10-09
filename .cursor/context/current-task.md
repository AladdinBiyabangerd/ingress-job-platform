# Current task

## Completed
- Worker `JOB_API_BASE_URL` fixed (connectivity)
- Root cause of engagement 500 found and fixed locally

## Current state
- **Bug:** `inapp_count_today` used `LIKE '%in_app%'` → psycopg saw `%i` as placeholder → `ProgrammingError`
- **Fix:** parameterized `LIKE ?` + `translate_sql` doubles `%` inside SQL string literals
- Awaiting deploy + worker re-run to verify `/notifications`

## Decisions
- Escape `%` in quoted SQL for Postgres adapter (psycopg requirement)
- Prefer bind params for LIKE patterns

## Remaining
1. Commit/deploy API fix
2. Re-trigger worker / engagement-jobs
3. Verify `/notifications` + optional email
4. AI quota (gemini 429 / groq 403) is separate — soft-fail for copy; not the 500

## Relevant files
- `api/app/engagement.py` (`inapp_count_today`)
- `api/app/jobs_db.py` (`translate_sql`)
- `api/tests/test_jobs_db.py`, `api/tests/test_engagement.py`
