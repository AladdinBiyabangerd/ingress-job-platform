# Current task

## Completed
- Auto AI score after crawl (earlier this session)
- Collected **Gizlət** → Rejected tab (2026-10-15):
  - `POST /api/v1/admin/crawled/{id}/hide` now sets `status=rejected`, `hidden=0`, reason `Staff gizlətdi (toplananlar)`
  - Leaves Collected list; appears on Rejected / Ləğv edilmişlər
  - **Göstər** unchanged for soft-hidden / merge rows still on Collected
  - Test + AZ/EN/RU copy notes updated

## Current state
Uncommitted: auto-score worker + crawled hide→reject + prior crawl_rejects admin fixes.

## Decisions
- Hide is reject, not soft-hide (staff asked explicitly)
- Merge still uses `hidden=1` + `merged_into`

## Remaining work
- Deploy API (+ frontend for copy) on Railway
- Deploy worker for auto-score if not done

## Relevant files
- `api/app/crawled_admin.py`
- `api/tests/test_admin.py`
- `frontend/lib/copy.js`
- `.cursor/context/business-rules.md`
