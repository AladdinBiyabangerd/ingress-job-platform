# Current task

## Completed
- For-you Chat 1: Hunt score+confidence engine + matches ungate + tests
- For-you Chat 2: home For-you pill (All-dan sonra) + JobBoardCard match % + honest empty/copy (az/en/ru)

## Current state
- Home For-you tab: signed-in candidate/staff only; `GET /api/auth/me/matches?limit=500`
- Card shows `%` when confidence ≥ 0.35; otherwise “uyğunluq dəqiq deyil” / equiv.
- Empty: consent CTA → profile; no skills → profile review; else honest ≥33% empty
- Sort hidden on For-you; API returns all gated matches (cap 500); board paginates PAGE_SIZE

## Decisions
- Flag A: matches/For-you only; hub stays hide
- UI never invents %; backend floor already applied; card still softens low confidence
- Other filters / search exit For-you mode

## Remaining work
- Manual QA: guest (no tab), consent off, no skills, good matches with %
- Plan todos: mark chat2 complete in `~/.cursor/plans/for-you_match_tab_947649d6.plan.md` if desired

## Relevant files
- `frontend/components/home.js`
- `frontend/components/job-board-card.js`
- `frontend/lib/copy.js`
- `frontend/app/globals.css` (`.job-board-card-match`)
- `api/app/hunt_scoring.py` / `matching.py` / `me.py` (Chat 1, untouched in Chat 2)
