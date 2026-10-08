# Current task

## Completed
- Trends salary: group by currency (no FX mix). Worker stores `salary_by_currency` JSON; API exposes `salaries[]` + primary `salary`; UI lists each currency group separately

## Current state
- Local changes ready; needs deploy + worker refresh so daily rows rewrite with multi-currency JSON (until then API falls back to primary columns only)

## Decisions
- Never convert or merge different currencies into one median/range
- Show every currency group with `n >= 5`; primary = most samples (tie → A→Z)

## Remaining
- Deploy + confirm worker re-aggregates trends
- Prior backlog: şəhər filteri + URL state; talent contact-requests; companies slug merge

## Relevant files
- `worker/worker/{salary_parse,skill_trends}.py`, `worker/tests/test_{salary_parse,skill_trends}.py`
- `api/app/{trends,cabinet_store}.py`, `api/tests/test_trends.py`
- `frontend/components/{trends,trend-detail}.js`
