# Current task

## Completed
- Admin moderation queue redesigned from bulky cards to a compact table list
- Queue API now returns `source_name` (first crawl source) and omits body text
- Columns: ingested date, title, source, approve/reject (original-date column removed — never stored)

## Current state
- `/admin` queue tab is a thin table; title click opens edit; approve/reject stay on the row

## Decisions
- `created_at` = when the ad was ingested into Ingress Job
- No original-post-date column until the field exists in the DB
- Company ads without `job_sources` show source label "Şirkət" / Company
- Bulk select + bulk approve kept above the table

## Remaining work
- Manual QA on `/admin` with a full pending queue

## Relevant files
- `frontend/components/admin.js`
- `frontend/app/globals.css`
- `frontend/lib/copy.js`
- `api/app/cabinet_store.py`
- `api/tests/test_admin.py`
