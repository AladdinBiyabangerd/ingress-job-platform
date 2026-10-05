# Ingress Job — Architecture

Job board (Ingress Job). Companies post jobs; candidates browse/apply. Hourly crawler aggregates remote/IT listings. No payments in this version.

## Stack

- Frontend: Next.js 15, React 19 (`frontend/`, port 3010)
- API: FastAPI / Uvicorn (`api/`, port 8010)
- Worker: Python crawler (`worker/`, hourly schedule)
- Auth: Ingress Academy OIDC (no separate password)
- DB: SQLite locally if `DATABASE_URL` empty; Postgres when set (API + worker share it)
- Locales: az / en / ru
- Deploy: Docker / Railway / Nixpacks per service

## Layout

```text
frontend/          # Next.js public site + cabinets
api/app/           # FastAPI (jobs, auth, companies, applications, admin)
worker/worker/     # Sources catalog, ATS boards, schedule, probe
scripts/           # dev.sh, per-service runners
docs/
compose.yaml
```

## Runtime

- All: `./scripts/dev.sh` → `[api]` `[web]` `[worker]`
- API: `http://127.0.0.1:8010`
- Web: `http://localhost:3010`
- Worker once: `./scripts/dev-worker.sh once`

## Domains

- Public job list / search / detail (guest: no original URL)
- Company jobs (moderation: pending → published)
- Candidate applications + CV upload
- Staff moderation (manual role): approve/reject/edit, crawled job tools
- Aggregation: remote/relocation IT sources (API/RSS/ATS); Jooble/Reed gated by API keys + monthly budgets
- CV parse queue (`parse_cv_queue` → rules `worker.cv_parse` + Tesseract OCR + AI #1 if confidence < 0.55 → jobs-DB `candidate_profile` stub); accounts.sqlite `candidate_profiles` remains contact-only
- `ai_gateway` (worker): PII redact, `ai_cache`, daily call budget, cost log, OTEL spans; OpenAI small model for CV fallback
- Consents (`consent` in jobs DB; `GET/PUT /api/v1/consents`); copy from `docs/cv-ai/consent-copy-v1.json`; visibility on `candidate_profile`
- CV profile review: `GET/PUT /api/v1/profile` + `/profile/review`; `profile_edit_log`; status draft→confirmed
- Role suggestions: `GET /api/v1/me/roles` (signature skill weights × years_factor; matching consent; BFF `/api/auth/me/roles`)
- Job matches: `GET /api/v1/me/matches` structured score (skills/seniority/location/language/freshness); AI #2 off on SQLite; feedback `POST .../matches/{id}/feedback` → `match_feedback`
- Skill gap: `GET /api/v1/me/skill-gap?role=` from `role_skill_weight`; share/growth from `skill_trend_daily` when present
- Skill trends: worker `skill_trends.refresh_skill_trends` → `skill_trend_daily`; public `GET /api/v1/trends`; UI `/trends`
- UI: `/me/recommendations` (roles + matches + 👍/👎); `/me/skills` (gap + Academy course links); BFF under `/api/auth/me/*`
- Email program: `email_prefs` / `email_log`; `GET/PUT /api/v1/email-prefs`; public unsubscribe; digests + high-match via `POST /api/v1/internal/email-jobs` (`INTERNAL_JOB_TOKEN`); UI `/settings/emails`
- Email click tracking: HMAC `/r/<token>` (frontend proxy → `GET /api/v1/r/{token}` → 302 job page); logs `email_click`; digests/high-match use tracked URLs only
- AI #4 digest intro: API `ai_gateway` + `digest_intro` (optional 2–3 sentences; `DIGEST_AI_INTRO_ENABLED`; soft-fail to static copy; shares jobs-DB `ai_cache`/`ai_usage_daily` with worker CV AI #1)
- AI #2 re-rank still off (needs pgvector + embeddings; not implemented)
- Data rights: `GET /api/v1/me/export` (zip: export.json + CVs); `DELETE /api/v1/me` (hard-delete; audit → pseudonym). Account identity remains `GET /api/v1/me`

## Integrations

- Ingress Academy OIDC
- Job source APIs / RSS / ATS boards (`worker/worker/catalog.py`, `ats_boards.py`)
- Object storage for uploads (when configured)
- Optional `JOOBLE_API_KEY`, `REED_API_KEY`, `HH_API_KEY`
- Optional `OPENAI_API_KEY` (job tidy + CV AI #1 via `ai_gateway`)

## Notes

- Prefer scoped reads: `frontend/app|components`, `api/app`, `worker/worker`
- Locales and guest vs logged-in link rules are product constraints — see README
- `.cursor/context/current-task.md` for active work
