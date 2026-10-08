# Current task

## Completed
- Diagnosed silent notifications: fresh-only lookback (was 26h) + complete profiles skip nudge + push needs VAPID/subscribe; worker needs `INTERNAL_JOB_TOKEN`
- Catalog fallback for `match_new` / `match_near` (unseen jobs → in-app + push; email stays fresh-only)
- Lookback default `ENGAGEMENT_LOOKBACK_HOURS` → 72
- `/notifications` push enable CTA when not subscribed
- Tests + architecture / railway docs

## Current state
- Code ready; **prod still needs** same `INTERNAL_JOB_TOKEN` on api+worker, `JOB_API_BASE_URL` on worker, and VAPID trio on api
- User must click push permission (now prompted on `/notifications`)

## Remaining
- Deploy API + web (+ worker if env-only)
- Confirm Railway vars; smoke: dry-run `POST /internal/engagement-jobs`, enable push, wait for hourly run or trigger once
- Optional: verify account has confirmed profile + matching consent

## Relevant files
- `api/app/engagement.py`, `api/app/digests.py`
- `api/tests/test_engagement.py`
- `frontend/components/notifications-page.js`, `frontend/lib/copy.js`, `frontend/app/globals.css`
- `docs/railway.md`, `.cursor/context/architecture.md`
