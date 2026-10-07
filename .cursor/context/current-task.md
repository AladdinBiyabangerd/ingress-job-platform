# Current task

## Completed
- Trends detail + Recommendations gaps (`recommendations_enrichment` plan)
  - Shared `skill-gap-bits.js` (AcademyCourseLinks / CareerPathLink / SkillRow)
  - `GET /api/v1/trends/{skill_id}`: market, often_with, academy_courses, jobs (5–10), optional `you`
  - Clickable TrendCard → `/trends/[skillId]` (az/en/ru); guest CTA + OIDC safe-return
  - `GET /me/matches?role=`: signature skill filter + soft boost; limit 10
  - Recommendations: full market-ranked gap + academy/career path; no coach.slice(0,3); role-scoped jobs + SSR gap

## Current state
- Done; ready for optional manual UI smoke (`/trends` → detail, `/me/recommendations` role switch).

## Decisions
- No hardcoded 3-skill checklist as primary learn signal.
- Trend `you` from profile × often_with (dynamic); guest gets market+jobs+login CTA.
- Shared academy/gap UI extracted once for me-skills, trends detail, recommendations.

## Remaining
- None for this plan.

## Relevant files
- `api/app/trends.py`, `api/app/routers/trends.py`, `api/app/matching.py`, `api/app/routers/me.py`
- `frontend/components/skill-gap-bits.js`, `trend-detail.js`, `trends.js`, `recommendations.js`, `me-skills.js`
- `frontend/lib/server/trends.js`, `frontend/lib/server/recommendations.js`, `frontend/lib/copy.js`
- `frontend/app/trends/[skillId]/page.js` (+ en/ru)
