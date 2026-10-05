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

## Decisions
- Digests run in API (matching + contact email); worker only HTTP-triggers
- AI #4 personal intro deferred
- Plan `/api/email-prefs` → `/api/v1/email-prefs`; unsubscribe same
- High-match threshold default `0.75` (`HIGH_MATCH_MIN_SCORE`)
- No send when `EMAIL_HOST` unset (same as transactional mail)

## Remaining (Phase 2+)
- AI #2 re-rank when Postgres + embeddings available
- AI #4 optional digest intro paragraph
- SPF/DKIM/DMARC / bounce handling (ops)
- Optional: `/me/skills`; skill-pair matrix; salary signals; click tracking `/r/<token>`
- Populate `academy_course_ids` in skill dictionary for real Academy URLs

## Relevant files
- `api/app/email_prefs.py`, `api/app/digests.py`, `api/app/routers/email_prefs.py`
- `api/app/consents.py`, `api/app/me_data.py`, `api/app/main.py`
- `worker/worker/digests.py`, `worker/worker/runner.py`
- `frontend/components/email-settings.js`, `unsubscribe-page.js`, `recommendations.js`
- `frontend/app/settings/emails/`, `frontend/app/unsubscribe/`, BFF routes
- `docs/ingress-job-cv-ai-plan.pdf` (§8, §13)

## Continue prompt (new chat)
Phase 2 left: AI #2 if Postgres/pgvector ready, else AI #4 digest intro or ops email DNS. Read `.cursor/context/current-task.md`.
