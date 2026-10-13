# Current task

## Completed
- Scraped ads no longer auto-publish: worker upsert inserts `pending`
- Pending scraped ads appear in admin moderation queue
- Single + bulk approve (`approve-bulk`); reject without owner notification for scraped
- Collected tab shows pending/rejected status badges

## Current state
- New scrapes wait for staff approve before public board
- Existing published scraped rows stay published on re-scrape

## Decisions
- Queue includes company ads (all statuses) + scraped only while `pending`
- Bulk approve skips non-pending / unknown ids (partial success)

## Remaining work
- Manual QA: crawl or insert pending scraped → `/admin` queue → approve one / select-all → appears on board

## Relevant files
- `worker/worker/db.py`
- `api/app/cabinet_store.py`
- `api/app/routers/admin.py`
- `frontend/components/admin.js`
- `frontend/components/collected-admin.js`
- `frontend/lib/copy.js`
- `frontend/lib/server/refresh.js`
