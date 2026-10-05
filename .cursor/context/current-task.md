# Current task

## Goal
Trends page UI polish: cards, pagination, selectable window (presets + custom days).

## Completed
- Redesigned `/trends` cards (share bar, chips)
- Growth cold-start fix (API + frontend cap)
- Pagination `?page=` (10/page)
- Window: presets 7/14/28/56 + custom number input 1–56 (`?days=`)

## Remaining
- Deploy when ready
- AI #2 re-rank ops still separate

## Relevant files
- `frontend/components/trends.js`, `frontend/app/globals.css`, `frontend/lib/copy.js`
- `frontend/app/{,en/,ru/}trends/page.js`
- `api/app/trends.py`
