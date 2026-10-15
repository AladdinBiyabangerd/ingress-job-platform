# Current task

## Completed
- Collected (`/admin?tab=collected`) now lists only scraped `status=published`

## Current state
`GET /api/v1/admin/crawled` filters `owner_subject='' AND status='published'`. Pending stays on moderation queue; rejected on Rejected.

## Decisions
- Collected ≠ “all scraped”; it is the live/published scraped inventory only

## Remaining work
- Deploy API + frontend when ready

## Relevant files
- `api/app/crawled_admin.py`
- `frontend/components/collected-admin.js`
- `api/tests/test_admin.py`
- `.cursor/context/business-rules.md`
