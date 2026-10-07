# Current task

## Completed
- Profile review densify + tabs (local, uncommitted)
- Trend detail UI rewrite (Academy / job-detail composition):
  - Removed blue hero + nested metric chips
  - Head: back pill → kicker → h1 → lede (Academy career-path pattern)
  - Layout: main (you + jobs) + sticky facts aside (same as job detail)
  - Mobile: facts aside `order: -1` so market numbers come first
  - Guest CTA only in facts card (no duplicate primary)
  - Also fixed earlier `.hero:has(.hero-tools)` mobile specificity bug on `/trends` list

## Current state
- Local only; not committed. Verified localhost mobile + desktop.

## Remaining
1. User visual OK on `/trends/1`
2. Commit when approved

## Relevant files
- `frontend/components/trend-detail.js`
- `frontend/app/globals.css`
- `frontend/lib/copy.js` (trendsDetailKicker, trendsAsOfLabel)
- (prior uncommitted) `frontend/components/profile-review.js`
