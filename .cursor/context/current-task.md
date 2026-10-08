# Current task

## Completed
- AI axınları: nə vaxt işləyir (izah)
- Reco Design A/B/C mockups (assets/)
- User chose **Design A** for `/me/recommendations`
- Design A polish + coach null handling

## Current state
- Design A: roles rail | selected + score ring label | coach hero | have / learn / jobs
- Coach always visible; `coach: null` → dashed empty panel (`skillsCoachEmpty`)
- Skill-gap fetch timeout 35s (coach LLM ~30s); gap/matches load independently
- Tech icons via Simple Icons CDN + fallback initials (`SkillIcon`)

## Decisions
- Layout Design A with brand tokens
- Null coach is soft-fail UI, not a crash; lists filter invalid items
- Do not clear matches if only skill-gap fails

## Remaining
- Visual smoke logged-in `/me/recommendations` with `role_coach` on (optional)

## Relevant files
- `frontend/components/recommendations.js`
- `frontend/components/skill-icon.js`
- `frontend/lib/skill-icons.js`
- `frontend/lib/server/refresh.js`
- `frontend/lib/server/recommendations.js`
- `frontend/app/globals.css`
- `frontend/lib/copy.js`
