# Current task

## Completed
- Insights vs Recommendations vs roadmap stub izahı
- Roadmap planı kilidlənib: Academy-first + AI fallback; Insights + `/me/insights/roadmap`
- UI nümunələri; seçim **K** (`docs/design-samples/roadmap-k-native-week.png`)
- **Implement:** `api/app/learning_roadmap.py` + `build_growth_cta` / `insights_payload` rich shape
- Insights Growth preview + `/me/insights/roadmap` (az/en/ru) K week-bento
- Overflow-safe CSS + responsive stack; command palette; notifications rich preview
- Tests: `tests/test_learning_roadmap.py` + updated growth CTA test

## Current state
- Learning Roadmap hub shipped in this branch (not committed unless asked)
- Academy course + career path together; unmapped skills → AI/template milestones
- Insights HTTP uses `allow_ai_provider=False` (cache/template); coach_weekly keeps provider on

## Decisions
- Yer: Insights overview + `/me/insights/roadmap` (az/en/ru)
- Fallback: AI (`complete_json`, PURPOSE `learning_roadmap`) + locale templates
- UI: K week-bento (orijinal K; K2/K3 yox)
- Flag: `learning_roadmap` / `AI_LEARNING_ROADMAP_ENABLED` (follows gateway)
- Legacy `roadmap[]` saxlanılır (notifications); rich `learning_roadmap` əsas UI mənbəyi

## Remaining
- Manual smoke in browser: mapped Academy rol (Java → path) + unmapped AI/template path
- Commit/PR when requested

## Relevant files
- `api/app/learning_roadmap.py`, `api/app/engagement.py`, `api/app/ai_flags.py`
- `api/tests/test_learning_roadmap.py`
- `frontend/components/roadmap.js`, `frontend/components/insights.js`
- `frontend/app/me/insights/roadmap/page.js` (+ en/ru)
- `frontend/lib/copy.js`, `frontend/app/globals.css`
- Plan: `~/.cursor/plans/learning_roadmap_hub_a225b00f.plan.md`
