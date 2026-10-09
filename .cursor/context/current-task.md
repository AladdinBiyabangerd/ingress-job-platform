# Current task

## Completed
- Roadmap path-only empty fix (backend `_sections` + path-aware hero/week/next)
- Path-only unit test + existing learning_roadmap tests green
- `/me/insights` → redirect `/me/insights/roadmap` (az/en/ru)
- Nav / command palette / notifications / engagement `cta_href` → roadmap
- Roadmap UI gates (profile/consent) + empty copy separation; course fallback for week

## Current state
- Learning Roadmap is the insights hub (overview page removed via redirect)
- Path-only users see actionable week/next + Academy path, not “confirm profile” empty hero

## Decisions
- Hub URL retired; API `GET /api/v1/me/insights` kept as data
- `/me/insights/near` kept; back → roadmap
- Roadmap back → recommendations

## Remaining
- Manual smoke on Railway after deploy
- Commit/PR when requested

## Relevant files
- `api/app/learning_roadmap.py`, `api/app/engagement.py`
- `api/tests/test_learning_roadmap.py`, `api/tests/test_engagement.py`
- `frontend/components/roadmap.js`, `frontend/lib/copy.js`
- `frontend/app/{,en/,ru/}me/insights/page.js` (redirects)
- `frontend/components/{shell,account-bar,command-palette,notifications-page,insights}.js`
