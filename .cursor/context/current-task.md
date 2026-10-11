# Current task

## Completed
- Country location facets + expanded `place_data.py` (~1200 cities / ~100 countries)
- Jooble SOSi DevOps stub: connector drops all API rows; purge hides every `source_name=Jooble` job

## Current state
- Jooble catalog already `enabled=False` / `go=no-go` (API = snippet only; `/desc/` robots-blocked)
- Existing Jooble rows (incl. rewritten `cleaned_text`) hidden by `market_purge` as `thin_description`
- SOSi listing cannot be “fixed” to full JD from Jooble — need employer ATS if re-ingested

## Decisions
- Never publish Jooble API snippets; prefer Greenhouse/ATS for full descriptions
- Purge by Jooble source, not only snippet heuristic (tidy can rewrite stubs)

## Remaining work
- **Deploy API + frontend** — country facets are local/unpushed; prod still shows city chips
- Deploy worker + run `purge-market` for Jooble stubs

## Relevant files
- `worker/worker/connectors/jooble.py`, `worker/worker/market_purge.py`
- `worker/worker/parsing.py` (`is_aggregator_snippet`), `worker/worker/catalog.py`
- `api/app/place.py`, `api/app/place_data.py`
- Tests: `test_jooble.py`, `test_market_purge.py`, `test_parsing.py`, `test_place.py`
