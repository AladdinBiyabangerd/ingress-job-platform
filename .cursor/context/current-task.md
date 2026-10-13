# Current task

## Completed
- Profile review: dinamik skill tövsiyələri (family + pair + role)
- `GET /api/v1/skills/related` + BFF `/api/skills/related`
- UI: fokus pill → suggest chips → kliklə əlavə

## Current state
- Ready for browser QA on `/profile/review` Experience tab

## Decisions
- Hybrid ranking: dictionary family → skill_pair_daily → role_skill_weight
- Focus click selects; second click on focused pill edits (draft + remove)
- “Spring Boot” is synonym of Spring — family shows Spring* siblings

## Remaining work
- Browser QA (Spring / CI/CD focus)
- Commit when asked

## Relevant files
- `api/app/skill_related.py`
- `api/app/routers/trends.py`
- `api/tests/test_skill_related.py`
- `frontend/app/api/skills/related/route.js`
- `frontend/components/profile-review.js`
- `frontend/lib/copy.js`
- `frontend/app/globals.css`
