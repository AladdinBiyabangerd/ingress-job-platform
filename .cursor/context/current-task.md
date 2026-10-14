# Current task

## Completed
- Moderasiya: `rule_confidence` + `ai_confidence` (+ reason)
- Threshold publish + sync AI recheck (admin queue)
- market_fit schema v2 (`confidence`)

## Current state
- Crawl: clear signal → rule=100; AI path → ai confidence
- Queue UI: iki % sütunu + skor/op/threshold + publish / tez / AI recheck
- Approve = publish; auto-publish yox

## Decisions
- Hər elan yenə pending queue-ya düşür
- NULL skor threshold match olmur
- Recheck unsuitable → rejected

## Remaining work
- Deploy + production QA
- Commit when asked

## Relevant files
- `worker/worker/market_fit.py`, `acceptance.py`, `db.py`
- `api/app/cabinet_store.py`, `api/app/routers/admin.py`
- `frontend/components/admin.js`, `frontend/lib/copy.js`, `frontend/lib/server/refresh.js`
