# Current task

## Completed
- Phase 0–1: CV parse → profile → roles → OCR → AI #1 → export/delete
- Phase 2.1–2.5: matches, feedback, skill-gap, `/me/recommendations`
- Phase 2.6: skill trends engine (`skill_trend_daily`, `/trends`, gap enrichment)
- Phase 2.7: email program (plan §8)
  - `email_prefs` + `email_log` (jobs DB); `GET/PUT /api/v1/email-prefs`
  - Public `GET/POST /api/v1/unsubscribe/{token}` (HMAC; List-Unsubscribe headers on send)
  - Digests + high-match alerts in `api/app/digests.py`; empty digests skipped; 1 marketing mail/user/UTC day; idempotent `(user_id, kind, period_key)`
  - Worker triggers `POST /api/v1/internal/email-jobs` when `INTERNAL_JOB_TOKEN` set
  - UI: `/settings/emails` (az/en/ru), `/unsubscribe/[token]`, account menu + profile link
  - Emails consent → seeds weekly prefs if none exist
  - Academy course deep-links on gap UI via `NEXT_PUBLIC_ACADEMY_COURSE_BASE`
  - Tests: `api/tests/test_email_prefs.py`, `worker/tests/test_digests_trigger.py`
- Phase 2.8: AI #4 digest intro
  - API `ai_gateway` (mirror worker; shared `ai_cache` / `ai_usage_daily` on jobs DB)
  - `digest_intro.maybe_digest_intro` → optional 2–3 sentence intro; soft-fail to static COPY
  - Flag `DIGEST_AI_INTRO_ENABLED` (default on when gateway can run)
  - `email_log.meta.ai_intro`: `applied|skipped:<reason>`
  - Tests: `api/tests/test_digest_intro.py`
- Phase 2.9: email click tracking `/r/<token>`
  - `email_clicks`: HMAC token (user + job + kind + lang); `email_click` table
  - Digests + high-match bodies use `tracked_job_url` (no open redirect; only on-site `/jobs/{id}`)
  - `GET /api/v1/r/{token}` → log + 302; frontend `app/r/[token]/route.js` proxies
  - Hard-delete clears `email_click`
  - Tests in `api/tests/test_email_prefs.py`

## Decisions
- Digests run in API (matching + contact email); worker only HTTP-triggers
- AI #4 uses API-local `ai_gateway` copy (worker copy unchanged; consolidate later)
- Plan `/api/email-prefs` → `/api/v1/email-prefs`; unsubscribe same
- High-match threshold default `0.75` (`HIGH_MATCH_MIN_SCORE`)
- No send when `EMAIL_HOST` unset (same as transactional mail)
- Click tokens reuse `EMAIL_UNSUBSCRIBE_SECRET`; redirect target rebuilt server-side from job_id+lang

## Remaining (Phase 2+)
- AI #2 re-rank when Postgres + pgvector + embeddings available
- SPF/DKIM/DMARC / bounce handling (ops)
- Optional: `/me/skills`; skill-pair matrix; salary signals
- Populate `academy_course_ids` in skill dictionary for real Academy URLs
- Consolidate worker + API `ai_gateway` into one shared package

## Relevant files
- `api/app/email_clicks.py`, `api/app/digests.py`, `api/app/routers/email_prefs.py`
- `frontend/app/r/[token]/route.js`
- `api/app/ai_gateway/`, `api/app/digest_intro.py`
- `api/app/email_prefs.py`, `api/app/me_data.py`
- `docs/ingress-job-cv-ai-plan.pdf` (§8, §11, §13)

## Continue prompt (new chat)
Phase 2 left: AI #2 blocked (pgvector); else academy_course_ids, `/me/skills`, skill-pair matrix, or email DNS ops. Read `.cursor/context/current-task.md`.
