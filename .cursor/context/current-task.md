# Current task

## Completed
- Phase 0–1: CV parse → profile → roles → OCR → AI #1 → export/delete (see prior notes)
- Phase 2.1–2.5: matches, feedback, skill-gap (role weights), `/me/recommendations`
- Phase 2.6: skill trends engine
  - Worker: `worker/worker/skill_trends.py` → `skill_trend_daily`; hooked in `runner._run_pass`
  - First empty run backfills 56 days; then refreshes yesterday + today
  - Public `GET /api/v1/trends` (`api/app/trends.py`) — share, WoW growth (min 20 ads), disclaimer
  - Skill-gap fills `share`/`growth` when trends exist; source `role_skill_weight+skill_trend_daily`
  - UI: `/trends` (az/en/ru) + gap share% on recommendations
  - Tests: `worker/tests/test_skill_trends.py`, `api/tests/test_trends.py`

## Decisions
- Plan `/api/trends` → `/api/v1/trends`
- Day key = `substr(created_at,1,10)` (jobs have no `first_seen_at` / `region`)
- `region` stored as `''` until a real region field exists
- Share denominator = distinct published jobs in window (not sum of skill rows)
- Skill-gap targets still from `role_skill_weight`; trends only enrich/sort
- Salary median / skill-pair matrix deferred

## Remaining (Phase 2+)
- AI #2 re-rank when Postgres + embeddings available
- Email digests / high-match alerts / unsubscribe (plan §8)
- Academy course deep-links on gap UI (`academy_course_ids` already returned)
- Optional: `/me/skills`; skill-pair matrix; salary signals

## Relevant files
- `worker/worker/skill_trends.py`, `worker/worker/runner.py`
- `api/app/trends.py`, `api/app/routers/trends.py`, `api/app/skill_gap.py`
- `api/app/cabinet_store.py`, `api/app/main.py`
- `frontend/components/trends.js`, `frontend/app/trends/page.js` (+ en/ru)
- `frontend/components/recommendations.js`, `frontend/lib/api.js`, `copy.js`
- `docs/ingress-job-cv-ai-plan.pdf` (§7.1–7.2, §13)

## Continue prompt (new chat)
Phase 2 remaining: email digests (plan §8), or AI #2 if Postgres/pgvector ready. Read `.cursor/context/current-task.md`.
