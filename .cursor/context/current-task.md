# Current task

## Completed
- Profile review form enriched (option A): About, city/country, links, work location+summary, education, languages.
- Backend `summary` field on candidate profile JSON; CV parse stores About/Summary section; AI #1 schema/merge includes summary.
- Embeddings text includes summary snippet.
- Locales az/en/ru + CSS grids for new sections.
- Tests: `api/tests/test_cv_profile.py`, `worker/tests/test_cv_parse.py`, `worker/tests/test_cv_ai_fallback.py`.

## Current state
- UI `/profile/review` saves/loads the richer fields via existing GET/PUT `/api/v1/profile`.
- No DB migration — fields live in `candidate_profile.data` JSON.

## Decisions
- Field name in JSON is `summary` (CV section name); UI label is About / Haqqında / О себе. `about` accepted as alias on save.
- Languages: fixed common codes (az/en/ru/tr/de/fr) + CEFR/native levels.

## Remaining
1. Deploy API + web; smoke-test `/profile/review` with CV upload and manual fill.
2. Optional later: desired roles / remote prefs / salary on the same form.

## Relevant files
- `frontend/components/profile-review.js`
- `frontend/lib/copy.js`
- `frontend/app/globals.css`
- `api/app/cv_profile.py`
- `api/app/embeddings.py`
- `worker/worker/cv_parse/pipeline.py`
- `worker/worker/cv_parse/ai_fallback.py`
