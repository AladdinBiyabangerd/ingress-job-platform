# Current task

## Completed
- Graded `rule_confidence` (not flat 100/0): `rule_fit_confidence` in `worker/worker/market_fit.py`
- Wired into `acceptance.finish_item` + admin `backfill_moderation_confidence` (also re-grades legacy rule=100)
- Tests updated; business-rules note updated

## Current state
- Rule % reflects signal strength (board default ~64 → open worldwide/EMEA ~84–95 → AZ/CIS up to 100)
- AI path unchanged (`ai_confidence`)

## Decisions
- Strongest evidence wins + small multi-signal bonus; non-AZ capped at 95
- Backfill refreshes pending rows with `rule_confidence IS NULL OR = 100` and no AI score

## Remaining work
- Deploy; on admin click “Köhnə faizləri doldur” to re-grade flat 100s
- Commit when asked

## Relevant files
- `worker/worker/market_fit.py`, `worker/worker/acceptance.py`, `worker/worker/techstack.py`
- `api/app/cabinet_store.py`
- `worker/tests/test_market_fit.py`, `api/tests/test_admin.py`
