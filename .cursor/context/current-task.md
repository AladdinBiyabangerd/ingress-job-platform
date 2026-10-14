# Current task

## Completed
- Admin **Kateqoriyalar** → **Crawl rəddləri** (`crawl_rejects`)
- Collected tab excludes `status=rejected`
- **List filter bar** on queue, rejected, collected, crawl_rejects:
  - AI score ≥/≤ + number (empty score = no match when filter active)
  - Rule score ≥/≤ + number (same)
  - Source name substring (`source_name`, case-insensitive)
  - Client-side only; threshold publish/recheck still use full tab dataset

## Current state
Filter UI shipped in working tree (uncommitted). Viewing is filtered; bulk/% actions are not.

## Decisions
- Shared helpers: `frontend/lib/admin-list-filter.js`
- Shared bar: `frontend/components/admin-list-filter-bar.js`
- Filter for viewing only; publish-by-% / recheck stay on full list

## Remaining
- Manual QA on the four tabs
- Commit when asked

## Relevant files
- `frontend/lib/admin-list-filter.js`
- `frontend/components/admin-list-filter-bar.js`
- `frontend/components/admin.js`
- `frontend/components/collected-admin.js`
- `frontend/components/admin-crawl-rejects.js`
- `frontend/lib/copy.js`
- `frontend/app/globals.css`
