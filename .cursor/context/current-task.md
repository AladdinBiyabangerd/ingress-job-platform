# Current task

## Completed
- Parked recommendations + roadmap product surfaces (hide UI, block routes, stop backend work)

## Current state
- Default off via `frontend/lib/product-features.js` + `api/app/product_features.py`
- Re-enable: set `PRODUCT_RECOMMENDATIONS_ENABLED=1` + `PRODUCT_ROADMAP_ENABLED=1` on API, and `NEXT_PUBLIC_PRODUCT_RECOMMENDATIONS_ENABLED=1` + `NEXT_PUBLIC_PRODUCT_ROADMAP_ENABLED=1` on web

## Remaining
1. User verify live after deploy (nav + direct URL + no coach_weekly)
2. Commit when asked

## Relevant files
- `frontend/lib/product-features.js`
- `frontend/middleware.js`
- `api/app/product_features.py`
- `api/app/routers/me.py`
- `api/app/engagement.py`
- `frontend/components/{shell,account-bar,command-palette,home,notifications-page,email-settings,trend-detail}.js`
