# Current task

## Completed
- Hybrid 2 Faza 0–6
- Recommendations density polish
- Insights design options A–D + Option A implemented
- Recommendations design options A–D (PNG in `docs/design-samples/recommendations-*.png`)
- **Recommendations Option D (Bento) implemented**

## Current state
- `/me/recommendations` overview is a 5-tile bento:
  - selected role (score ring + Academy + CTA + collapsible coach)
  - roles 2×N grid
  - have skills
  - learn skills (horizontal cards)
  - jobs preview (top 3) + CTA to full jobs page
- Responsive: 1-col mobile → 2-col tablet (720–1099) → 3-col desktop (≥1100)
- `RecommendationJobs` full list page unchanged

## Decisions
- Option D chosen over A/B/C
- Coach lives in selected tile as `<details>` (does not break bento)
- Jobs on overview are preview only; feedback stays on jobs page
- No new API/copy required

## Remaining
- Manual smoke: `/me/recommendations` desktop/tablet/mobile with roles + gap + matches
- Empty states: no roles, no jobs, no gap
- (opsional) visual polish vs `docs/design-samples/recommendations-d-bento.png`

## Relevant files
- `frontend/components/recommendations.js`
- `frontend/app/globals.css` (`.recommendations-bento`, `.recommendations-tile-*`)
- `docs/design-samples/recommendations-d-bento.png`
