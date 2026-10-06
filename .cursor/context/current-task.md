# Current task

## Goal
Public job list SQL: correlated subquery-ləri çıxar, JOIN + index.

## Completed
- `_LIST_SELECT_CORE` LEFT JOIN: `job_sources` agg (`MIN(id)`, `has_original`) + `crawl_sources`.
- Count/facet sorğuları join etmir (cəm çoxalmasın).
- Index: `jobs_public_list`, `job_sources_job` (API schema + worker).

## Remaining
- Railway private-net env hələ dashboard-da (əvvəlki tapşırıq).

## Relevant files
- `api/app/sqlite_jobs.py`, `api/app/cabinet_store.py`
- `worker/worker/db.py`
- `api/tests/test_jobs_list_query.py`
