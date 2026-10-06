# Ingress Job — Architecture

Job board (Ingress Job). Companies post jobs; candidates browse/apply. Hourly crawler aggregates remote/IT listings. No payments in this version.

## Stack

- Frontend: Next.js 15, React 19 (`frontend/`, port 3010)
- API: FastAPI / Uvicorn (`api/`, port 8010)
- Worker: Python crawler (`worker/`, hourly schedule)
- Auth: Ingress Academy OIDC (no separate password). Account bar reads `me` from SSR `getMe()` in the root layout (guests skip FastAPI; access cookie → `GET /api/v1/me?lang=` once on the server). `/me` includes `unread_notifications` (header bell) and candidate `consents` (profile privacy) so those pages skip extra fetches. `/me/recommendations` SSR-loads `GET /me/roles` + `GET /me/matches`; `/me/skills` SSR-loads `GET /me/roles` + `GET /me/skill-gap` for the top role; `/applications` SSR-loads compact `GET /applications` (same access cookie; guests/non-candidates skip); `/notifications` SSR-loads `GET /notifications` (guests skip) and hydrates the client so first paint skips the BFF; `/settings/emails` SSR-loads `GET /email-prefs` (guests/non-candidates skip) so first paint skips the prefs BFF; `/post` SSR-loads `GET /cabinet/jobs` + `GET /cabinet/applications` (guests/candidate-only/incomplete company skip) so first paint skips the list BFF; `/profile/review` SSR-loads `GET /profile` + `GET /me/roles` (guests/non-candidates skip) so first paint skips the cv-profile and roles BFFs; `/admin` SSR-loads `GET /admin/jobs` + `GET /admin/applications` + `GET /admin/crawled` + `GET /admin/ai-flags` (guests/non-staff skip) so first paint and crawled/AI tabs skip the list BFF. After admin/cabinet/applications/notifications/skills/email/company/profile-review mutations, writes and list refresh use server actions to FastAPI (`frontend/lib/server/refresh.js`), not the client BFF (approve/reject/edit/close, crawled hide/show/edit/merge, cabinet create/edit/close, application decide/withdraw, mark-read, AI-flag PUT, manual ad create, skill-gap on role change, email-prefs save, CV profile save/upload/poll/cancel/reset, company save). One accounts-DB open for company/candidate/academy/email; unread+consents share one jobs-DB open. `/company` RSC hydrates the employer profile form from that same `GET /me` (`company_profile`); save is a FastAPI POST server action. Client `/api/auth/me` BFF remains for token refresh, logout, privacy delete, and expired-access retry
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

- Public job list / search / detail (guest: no original URL); `GET /api/v1/jobs` is paginated (`page`/`per_page`, filters, `facets`/`catalog_total`); Home SSR loads page 1, client refetches via `/api/jobs` BFF; list SQL LEFT JOINs first `job_sources` row (`MIN(id)`) + `crawl_sources`, not per-row subqueries; facets GROUP BY stored language/category and only title-scan rows without az|en|ru language; facets+catalog_total are process-cached until the published catalog fingerprint (count/max id/created_at, sqlite mtime) changes
- Company directory (`GET /api/v1/companies`, `/companies/{slug}`) groups published jobs in Python (slug from name); catalog SQL skips `job_sources`; company page hydrates only the current job page with the list JOIN; grouped summaries are process-cached until catalog or applications fingerprint changes
- Skill trends (`GET /api/v1/trends`): current+prior skill/job counts in one scan each; job denom uses `created_at` range (not `substr`) for `jobs_public_list`; trend DDL ensure is process-cached (no PRAGMA/ALTER per request)
- Company jobs (moderation: pending → published); `/company` RSC hydrates the profile form from `GET /me` so first paint skips the me BFF; save is a FastAPI POST server action. `/post` RSC hydrates owner jobs + applications so first paint skips the list BFF; create/edit/close and list refresh are FastAPI server actions
- Candidate applications + CV upload; candidate `GET /applications` list is compact (no message/answers/phone/email; UI paginates client-side); `/applications` RSC hydrates that list so first paint skips the BFF; withdraw is a FastAPI DELETE server action, then list refresh via FastAPI
- Notifications list (`GET /notifications`); `/notifications` RSC hydrates items+unread so first paint skips the BFF; mark-read is a FastAPI POST server action, then list refresh via FastAPI
- Staff moderation (manual role): approve/reject/edit, crawled job tools; `/admin` RSC hydrates queue jobs + applications + crawled ads + AI flags so first paint and those tabs skip the list BFF; queue/crawled/application writes and list refresh are FastAPI server actions; AI-flag save is a FastAPI PUT server action; manual ad create is a FastAPI POST server action. AI flow toggles (`GET/PUT /api/v1/admin/ai-flags`, jobs-DB `ai_feature_flags`) so staff can turn CV/tidy/embed/rerank/why/digest on or off without deleting `OPENAI_API_KEY`
- Aggregation: remote/relocation IT sources (API/RSS/ATS); Jooble/Reed gated by API keys + monthly budgets
- CV parse: API enqueues `parse_cv_queue` then drains in-process (`app.cv_parse_jobs` background thread → `worker.cv_parse` + OCR + AI #1 if confidence < 0.55 → jobs-DB `candidate_profile`); hourly crawl worker may drain stranded rows; accounts.sqlite `candidate_profiles` remains contact-only
- `ai_gateway` (worker package, also loaded by API): PII redact, `ai_cache`, daily call budget, cost log, OTEL spans; `complete_json` (CV #1, digest #4, match why) + `embed()` (OpenAI embeddings for AI #2)
- Consents (`consent` in jobs DB; `GET/PUT /api/v1/consents`); copy from `docs/cv-ai/consent-copy-v1.json`; visibility on `candidate_profile`
- CV profile review: `GET/PUT /api/v1/profile` + `/profile/review`; RSC hydrates profile + roles so first paint skips the BFF; save/upload/poll/cancel/reset are FastAPI server actions; `profile_edit_log`; status draft→confirmed; CV/consent/profile DDL is process-cached (no CREATE TABLE per request)
- Role suggestions: `GET /api/v1/me/roles` (signature skill weights × years_factor; matching consent; BFF `/api/auth/me/roles`); one `role_skill_weight` scan + process-cached skill lookup/weights/taxonomy until taxonomy counts change
- Job matches: `GET /api/v1/me/matches` structured score (skills/seniority/location/language/freshness); published jobs + `job_skill` are process-cached until catalog fingerprint changes; match_feedback DDL is process-cached; AI #2 re-rank on Postgres+pgvector (`embeddings` table, `0.7×struct + 0.3×cosine`, top-5 LLM why); off on SQLite / missing vectors (`ai_rerank: false`); flags `AI_RERANK_ENABLED`, `AI_MATCH_WHY_ENABLED` plus staff DB toggles; feedback `POST .../matches/{id}/feedback` → `match_feedback`
- Skill gap: `GET /api/v1/me/skill-gap?role=` from `role_skill_weight`; role resolve uses cached taxonomy (canonical + synonyms); share/growth from `skill_trend_daily` when present; Academy course links from `skill_dictionary.academy_course_ids` (map → seed); Academy career-path from `role_taxonomy.academy_career_path_id` (map `docs/cv-ai/academy-career-path-role-map-v1.json` → worker seed; base `/career-paths/`); role change on `/me/skills` loads gap via a FastAPI server action
- Skill trends: worker `skill_trends.refresh_skill_trends` → `skill_trend_daily` + `skill_pair_daily`; public `GET /api/v1/trends`; UI `/trends`
- Trend salary signals: worker `salary_parse` annualizes free-text `jobs.salary` (currency+period required, no FX) into `salary_median/currency/n/low/high`; API shows `salary` on trends when `n >= 5`
- Skill pairs: ordered co-occurrence in `skill_pair_daily`; trends items expose top `often_with` (share among base-skill ads, min 10 base ads); skill-gap missing skills get best pair vs candidate’s have skills
- UI: `/me/recommendations` (roles + matches + 👍/👎; RSC hydrates from FastAPI); `/me/skills` (gap + Academy course links; RSC hydrates roles + top-role gap); `/notifications` (RSC hydrates list); BFF under `/api/auth/me/*`
- Email program: `email_prefs` / `email_log`; `GET/PUT /api/v1/email-prefs`; public unsubscribe; digests + high-match via `POST /api/v1/internal/email-jobs` (`INTERNAL_JOB_TOKEN`); UI `/settings/emails` RSC hydrates prefs so first paint skips the BFF; save is a FastAPI PUT server action
- Email click tracking: HMAC `/r/<token>` (frontend proxy → `GET /api/v1/r/{token}` → 302 job page); logs `email_click`; digests/high-match use tracked URLs only
- AI #4 digest intro: API `ai_gateway` + `digest_intro` (optional 2–3 sentences; `DIGEST_AI_INTRO_ENABLED`; soft-fail to static copy; shares jobs-DB `ai_cache`/`ai_usage_daily` with worker CV AI #1)
- AI #2: worker `embed_stale_jobs` hourly; API embeds profile on save; compose image `pgvector/pgvector:pg16`; Railway needs `CREATE EXTENSION vector`
- Academy cross-sell: ~135 skills mapped to training slugs; UI/digest UTM `utm_source=ingress_job`
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
