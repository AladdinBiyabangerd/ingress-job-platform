# Current task

## Completed
- Contact/company profiles were wiped on every API redeploy: they lived only in ephemeral `api/data/accounts.sqlite`.
- Moved accounts tables to jobs DB when `DATABASE_URL` is set (same pattern as cabinet/jobs): Postgres on Railway, `accounts.sqlite` locally.

## Current state
- `api/app/profiles.py` uses `jobs_db.connect()` when postgres enabled; schema ensure keyed by `schema_cache_key()`.
- `jobs_db._NO_ID_TABLES` includes account tables (TEXT PKs).
- Docs: `docs/railway.md`, `.cursor/context/architecture.md`.

## Decisions
- Same DB as jobs when Postgres — not a separate volume (Railway volume is one-service-only).
- Keep local `accounts.sqlite` when `DATABASE_URL` unset so existing tests (`patch DATA_PATH`) stay valid.

## Remaining
1. Redeploy API; verify Görünən ad / Telefon / E-poçt survive restart.
2. Optional one-time copy from old container sqlite if any production rows still matter (usually empty after wipe).

## Relevant files
- `api/app/profiles.py`
- `api/app/jobs_db.py` (`_NO_ID_TABLES`)
- `docs/railway.md`
- `api/tests/test_candidate_profile.py`
