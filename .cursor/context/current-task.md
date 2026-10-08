# Current task

## Completed
- Reco Design A polish + coach null UI
- Coach soft-fail diagnostics (`coach_error` + logs + UI hint)
- Skill icons: Devicon CDN map covers all 197 dictionary skills + synonyms

## Current state
- Icons: `frontend/lib/skill-icons.js` (in-code map → jsDelivr Devicon SVG)
- Lazy `<img loading="lazy">` — map size does not slow page; only visible icons fetch

## Remaining
- After deploy: smoke `/me/recommendations` icon coverage

## Relevant files
- `frontend/lib/skill-icons.js`
- `frontend/components/skill-icon.js`
