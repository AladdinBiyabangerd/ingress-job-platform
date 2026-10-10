# Current task

## Completed
- Fixed Arbeitnow HTML leak (`&lt;h2 class=…` shown as text) — unescape mixed escaped+raw HTML
- Fixed Jooble truncated stubs (Twilio Observability `...About... Full-time`) — snippet-only API

## Current state
- **HTML:** `text_from_html` / `needs_html_unescape` in `worker/worker/parsing.py`; API `strip_leaked_html` in `public_text`; frontend `plainJobText`
- **Jooble:** catalog `enabled=False` / `go=no-go`; connector drops snippets (`<600` chars or aggregator shape); `finish_item` + `market_purge` reject `thin_description`
- Local purge hid 10 thin rows including Twilio id=341 and NetBox id=345

## Decisions
- Jooble cannot ship full JDs (robots block detail HTML) → do not publish; prefer Greenhouse/ATS
- Aggregator snippet heuristic: leading `...`, or ≥2 ellipses in short body, or ellipsis + job-type tail under 400 chars

## Remaining work
- Deploy worker + API + frontend so prod catalog disables Jooble and purge runs
- Optional: re-ingest Twilio Observability from Greenhouse board (`twilio` / job 8108771) for a full JD

## Relevant files
- `worker/worker/parsing.py` (`is_aggregator_snippet`, HTML unescape)
- `worker/worker/connectors/jooble.py`, `worker/worker/catalog.py`
- `worker/worker/acceptance.py`, `worker/worker/market_purge.py`
- `worker/worker/connectors/feed.py`, `api/app/sqlite_jobs.py`
- `frontend/lib/description.js`
- Tests: `test_parsing.py`, `test_jooble.py`, `test_market_purge.py`, `test_public_text.py`, `description.test.mjs`
