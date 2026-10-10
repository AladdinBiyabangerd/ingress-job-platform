# Current task

## Completed
- **Location facet cleanup** (this chat): Yer filter no longer lists Remote/Worldwide/Uzaqdan variants; merges Tokyo≈Tokyo, Japan etc.
  - `api/app/place.py` — remote detection, place_key, aggregate_cities, filter variant matching
  - `api/app/sqlite_jobs.py` — facets + city filter use normalization; remote-looking city query → `remote=true`
  - `worker/worker/place.py` + `Store.normalize_cities` / upsert — storage cleanup on crawl
- Prior: worker Postgres `crawl_rejects` RETURNING fix; AI job tidy; board shell IA (uncommitted frontend bits may remain)

## Current state
- Facet cleanup is immediate on API restart (no crawl required).
- DB city backfill runs on next `./scripts/dev-worker.sh once` (`city normalize: N`).
- Restart local API if it was already running so facet cache refreshes.

## Decisions
- Remote labels belong only under the Remote checkbox (`remote_total`), not as city chips.
- City filter matches all stored aliases sharing `place_key`.

## Remaining work
1. Confirm Yer list in UI after API restart (+ optional worker once for DB cleanup)
2. Job cards / tabs polish, home front door, Me page

## Relevant files
- `api/app/place.py`, `api/app/sqlite_jobs.py`, `api/tests/test_place.py`
- `worker/worker/place.py`, `worker/worker/db.py`, `worker/worker/runner.py`
