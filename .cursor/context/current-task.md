# Current task

## Completed
- Phase 0–2.12 (matches, trends, digests, skill pairs, etc.)
- Profile review UX + Sıfırla; CV parse v1.5–v1.6
- Academy skill↔course + role↔career-path maps
- Role scoring v1.1 (OR-groups, thin-role dampen, headline affinity)
- CV parse on API async
- **`/me/recommendations` UI/UX** aligned with `/me/skills` master/detail

## Decisions
- Recommendations page: left role picker (score badges) + right detail (selected role skills + job cards)
- Job cards show score badge, meta, have/missing, feedback actions
- Scores remain rules-based; disclaimer under lede

## Remaining
- Redeploy API on Railway for async CV parse
- Spot-check Aladdin CV on `/profile/review`
- AI #2 re-rank when Postgres + pgvector available
- Ops SPF/DKIM; consolidate worker+API `ai_gateway`

## Relevant files
- `frontend/components/recommendations.js`
- `frontend/app/globals.css` (recommendations-* / reco-* blocks)
- `frontend/lib/copy.js` (lede, disclaimer, selectedRole)

## Continue prompt (new chat)
Recommendations UI shipped like skills page. Next: redeploy Railway API and spot-check `/profile/review`. Read `.cursor/context/current-task.md`.
