# Current task

## Completed
- Phase 0–1: CV parse → profile → roles → OCR → AI #1 → export/delete
- Phase 2.1–2.5: matches, feedback, skill-gap, `/me/recommendations`
- Phase 2.6: skill trends engine (`skill_trend_daily`, `/trends`, gap enrichment)
- Phase 2.7: email program (plan §8)
- Phase 2.8: AI #4 digest intro
- Phase 2.9: email click tracking `/r/<token>`
- Phase 2.10: `/me/skills` (plan §13.2)
  - Dedicated page az/en/ru: target role picker → gap (missing + have) + Academy links
  - Uses existing `GET /api/v1/me/skill-gap` via BFF `/api/auth/me/skill-gap`
  - Trends honesty disclaimer on page
  - Gap UI moved off `/me/recommendations` (link teaser remains)
  - Nav: account menu + mobile shell

## Decisions
- Digests run in API (matching + contact email); worker only HTTP-triggers
- AI #4 uses API-local `ai_gateway` copy (worker copy unchanged; consolidate later)
- Plan `/api/email-prefs` → `/api/v1/email-prefs`; unsubscribe same
- High-match threshold default `0.75` (`HIGH_MATCH_MIN_SCORE`)
- No send when `EMAIL_HOST` unset (same as transactional mail)
- Click tokens reuse `EMAIL_UNSUBSCRIBE_SECRET`; redirect target rebuilt server-side from job_id+lang
- `/me/skills` is the gap+Academy surface; recommendations stays roles+jobs+feedback

## Remaining (Phase 2+)
- AI #2 re-rank when Postgres + pgvector + embeddings available
- SPF/DKIM/DMARC / bounce handling (ops)
- Populate `academy_course_ids` in skill dictionary for real Academy URLs (needs Academy course ↔ skill map)
- Optional: skill-pair matrix; salary signals on trends
- Consolidate worker + API `ai_gateway` into one shared package

## Relevant files
- `frontend/components/me-skills.js`
- `frontend/app/me/skills/page.js` (+ `en/`, `ru/`)
- `frontend/components/recommendations.js`, `shell.js`, `account-bar.js`
- `frontend/lib/copy.js`
- `api/app/skill_gap.py`
- `docs/ingress-job-cv-ai-plan.pdf` (§7.2, §13.2)

## Continue prompt (new chat)
Phase 2 left: AI #2 blocked (pgvector); next useful: populate `academy_course_ids`, skill-pair matrix, or salary signals. Read `.cursor/context/current-task.md`.
