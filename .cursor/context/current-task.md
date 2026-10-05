# Current task

## Completed
- Phase 0–1: CV parse → profile → roles → OCR → AI #1 → export/delete
- Phase 2.1–2.5: matches, feedback, skill-gap, `/me/recommendations`
- Phase 2.6: skill trends engine (`skill_trend_daily`, `/trends`, gap enrichment)
- Phase 2.7: email program (plan §8)
- Phase 2.8: AI #4 digest intro
- Phase 2.9: email click tracking `/r/<token>`
- Phase 2.10: `/me/skills` (plan §13.2)
- Phase 2.11: salary signals on trends (plan §7.1)
  - Worker `salary_parse`: unambiguous currency+period → annualize (no FX)
  - `skill_trend_daily`: `salary_median/currency/n/low/high` filled on aggregate
  - `GET /api/v1/trends` exposes `salary` when `n >= 5` (same currency window merge)
  - `/trends` UI shows median, range, sample count (az/en/ru)

## Decisions
- Digests run in API (matching + contact email); worker only HTTP-triggers
- AI #4 uses API-local `ai_gateway` copy (worker copy unchanged; consolidate later)
- Plan `/api/email-prefs` → `/api/v1/email-prefs`; unsubscribe same
- High-match threshold default `0.75` (`HIGH_MATCH_MIN_SCORE`)
- No send when `EMAIL_HOST` unset (same as transactional mail)
- Click tokens reuse `EMAIL_UNSUBSCRIBE_SECRET`; redirect target rebuilt server-side from job_id+lang
- `/me/skills` is the gap+Academy surface; recommendations stays roles+jobs+feedback
- Salary: no FX; skip hourly; suppress API display below `MIN_SALARY_SAMPLES=5`

## Remaining (Phase 2+)
- AI #2 re-rank when Postgres + pgvector + embeddings available
- SPF/DKIM/DMARC / bounce handling (ops)
- Populate `academy_course_ids` in skill dictionary for real Academy URLs (needs Academy course ↔ skill map)
- Optional: skill-pair matrix (“Kafka share among Java ads”)
- Consolidate worker + API `ai_gateway` into one shared package

## Relevant files
- `worker/worker/salary_parse.py`, `worker/worker/skill_trends.py`
- `api/app/trends.py`, `api/app/cabinet_store.py`
- `frontend/components/trends.js`, `frontend/lib/copy.js`
- `worker/tests/test_salary_parse.py`, `worker/tests/test_skill_trends.py`
- `api/tests/test_trends.py`
- `docs/ingress-job-cv-ai-plan.pdf` (§7.1)

## Continue prompt (new chat)
Phase 2 left: AI #2 blocked (pgvector); next useful: skill-pair matrix, or `academy_course_ids` map with Academy. Read `.cursor/context/current-task.md`.
