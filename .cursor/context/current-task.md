# Current task

## Goal
Fix CV parse "Ləğv et" so stuck analysis UI actually clears.

## Completed
- Root cause: late poll response re-applied `pending` after cancel
- Frontend: optimistic cancel + `pollEpoch` to ignore stale polls
- API: cancel always fails open jobs, commit then return payload
- Worker: do not revive cancelled jobs as `done`/`pending`

## Remaining
- Deploy frontend + API (+ worker if separate)
- Spot-check: upload CV → Ləğv et → chooser returns immediately

## Relevant files
- `frontend/components/profile-review.js`, `frontend/lib/copy.js`
- `api/app/cv_profile.py`, `api/tests/test_cv_profile.py`
- `worker/worker/cv_queue.py`
