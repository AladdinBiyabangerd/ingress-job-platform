# Current task

## Completed
- Language filter uses JD body (not only EN title / stored `en`)
- Score-based detection for all facet langs: az, en, ru, uk, de, fr, es, pt, tr
- AZ no longer misreads German `ü/ö` as Azerbaijani

## Current state
- `listing_language` scores stopwords + distinctive letters; min score 3 → else `en`
- Script shortcuts: AZ (`ə`), UK letters, Cyrillic → `ru`
- List/filter/facets use `language_sample` (~2000 chars of cleaned_text/text)
- Tests: `tests/test_listing_language.py`, German case in `test_jobs_list_query.py`

## Decisions
- Body inference beats stored `en`
- Stored cabinet `az`/`ru` stay trusted
- Diacritics optional — ASCII-heavy DE/FR/ES bodies still classify via stopwords

## Remaining work
- Deploy API so prod language filter picks up the fix
- Optional: backfill `jobs.language` on worker ingest

## Relevant files
- `api/app/sqlite_jobs.py`
- `api/tests/test_listing_language.py`
- `api/tests/test_jobs_list_query.py`
