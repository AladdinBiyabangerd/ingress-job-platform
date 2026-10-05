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
- Phase 2.12: skill-pair matrix (plan §7.1)
  - Worker writes `skill_pair_daily` (ordered co-occurrence per day/category)
  - `GET /api/v1/trends` items include `often_with` (top 3; min 10 base ads)
  - Skill-gap missing skills get `often_with` vs candidate’s have skills
  - `/trends` + `/me/skills` UI show companion share (az/en/ru)

## Decisions
- Digests run in API (matching + contact email); worker only HTTP-triggers
- AI #4 uses API-local `ai_gateway` copy (worker copy unchanged; consolidate later)
- Plan `/api/email-prefs` → `/api/v1/email-prefs`; unsubscribe same
- High-match threshold default `0.75` (`HIGH_MATCH_MIN_SCORE`)
- No send when `EMAIL_HOST` unset (same as transactional mail)
- Click tokens reuse `EMAIL_UNSUBSCRIBE_SECRET`; redirect target rebuilt server-side from job_id+lang
- `/me/skills` is the gap+Academy surface; recommendations stays roles+jobs+feedback
- Salary: no FX; skip hourly; suppress API display below `MIN_SALARY_SAMPLES=5`
- Pairs: `MIN_PAIR_BASE_ADS=10`; max 20 skills/job when building pairs; top 3 companions on trends

## Remaining (Phase 2+)
- AI #2 re-rank when Postgres + pgvector + embeddings available
- SPF/DKIM/DMARC / bounce handling (ops)
- Populate `academy_course_ids` in skill dictionary for real Academy URLs (needs Academy course ↔ skill map)
- Consolidate worker + API `ai_gateway` into one shared package

## Relevant files
- `worker/worker/skill_trends.py`
- `api/app/trends.py`, `api/app/skill_gap.py`, `api/app/cabinet_store.py`
- `frontend/components/trends.js`, `frontend/components/me-skills.js`, `frontend/lib/copy.js`
- `worker/tests/test_skill_trends.py`, `api/tests/test_trends.py`
- `docs/ingress-job-cv-ai-plan.pdf` (§7.1)

## Continue prompt (new chat)
Phase 2 left: AI #2 blocked (pgvector); next useful: `academy_course_ids` map with Academy, or ops SPF/DKIM. Read `.cursor/context/current-task.md`.
