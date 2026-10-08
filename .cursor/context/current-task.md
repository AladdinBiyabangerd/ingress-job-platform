# Current task

## Completed
- Hybrid 2 Faza 0–6
- Recommendations density polish
- **List-out pattern:** heavy job lists moved to button→subpages

## Current state
- `/me/recommendations` — roles + coach/gap + CTA `Uyğun elanlara bax (N)`
- `/me/recommendations/jobs?role=` — matching jobs + feedback (+ role chips)
- `/me/insights` — near section is CTA only
- `/me/insights/near` — full near-miss list

## Decisions
- Many inline job cards → dedicated page opened by button (no long scroll on hub pages)
- `hrefFor` modes: `recommendationJobs` (+ optional `role`), `insightsNear`

## Remaining
- Manual smoke: login → recommendations CTA → jobs; insights CTA → near
- (opsional) company/home lists already purpose-built list pages — leave as-is

## Relevant files
- `frontend/components/recommendations.js` (`Recommendations`, `RecommendationJobs`)
- `frontend/components/insights.js` (`Insights`, `InsightsNear`)
- `frontend/app/{,en/,ru/}me/recommendations/jobs/page.js`
- `frontend/app/{,en/,ru/}me/insights/near/page.js`
- `frontend/lib/copy.js` (`hrefFor`, open copy)
- `frontend/lib/server/recommendations.js`
