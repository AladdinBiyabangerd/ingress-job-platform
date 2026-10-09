# Ingress Job — Architecture

Job board (Ingress Job). Companies post jobs; candidates browse/apply. Hourly crawler aggregates remote/IT listings. No payments in this version.

## Stack

- Frontend: Next.js 15, React 19 (`frontend/`, port 3010)
- API: FastAPI / Uvicorn (`api/`, port 8010)
- Worker: Python crawler (`worker/`, hourly schedule)
- Auth: Ingress Academy OIDC confidential client `job-web` (PKCE + `client_secret` on Job API only; never in the frontend). One session helper `ensureSession` (`frontend/lib/server/oidc.js` + `ensure-session-logic.js`) refreshes near-exp access via `POST /api/v1/auth/refresh` and sets `job_at` / `job_rt` / `job_exp`. Middleware owns cookie writes on HTML navigations and forwards access as `x-job-access` for RSC (RSC must not call `cookies().set()`). `authorizedApi`, company-gate middleware, and Server Actions (via `sessionAccess` / `next-action`) also ensure. Account bar reads `me` from SSR `getMe()` (guests skip FastAPI). `/me` includes `unread_notifications` and candidate `consents`. SSR seeders for recommendations, skills, applications, notifications, emails, post/cabinet, profile/review, admin use `sessionAccess` after ensure. Mutations use server actions to FastAPI (`frontend/lib/server/refresh.js`) including apply, consents PUT, and data export. Client `/api/auth/*` BFF remains for logout, privacy delete, match feedback, CV download, and unseeded GET fallbacks. Deploy: matching `OIDC_JOB_CLIENT_SECRET` (Academy) + `OIDC_CLIENT_SECRET` (Job API); Academy start runs `sync_oidc_job_client` after migrate.
- DB: SQLite locally if `DATABASE_URL` empty; Postgres when set (API + worker share it). Contact/company profiles + OIDC transactions use the same Postgres when set; otherwise `api/data/accounts.sqlite`
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
- Notifications list (`GET /notifications`); `/notifications` RSC hydrates items+unread so first paint skips the BFF; mark-read is a FastAPI POST server action, then list refresh via FastAPI. Schema supports engagement kinds (`match_new`, `match_near`, `profile_nudge`, `coach_weekly`) + optional `payload` JSON; `engagement_log` / `push_subscriptions`
- Engagement engine (`api/app/engagement.py`): hourly `POST /internal/engagement-jobs` selects `match_new` (≥0.75), `match_near` (0.45–0.75, ≤3 missing), `profile_nudge` (draft / &lt;3 skills / stale 14d, max 1/ISO week), `coach_weekly` (top role + skill-gap, max 1/ISO week); fanout in-app + email + Web Push (`push_enabled` + VAPID/`pywebpush`, 410 cleanup), Academy/roadmap CTA, `engagement_log` dedup; worker triggers after digests. Fresh ads use lookback `ENGAGEMENT_LOOKBACK_HOURS` (default **72**); if none qualify, catalog fallback picks best unseen match (lifetime `job_ever_logged` dedup) for **in-app + push only** (email stays fresh-only). `engagement_copy` AI title/body (`ENGAGEMENT_AI_COPY_ENABLED`, soft-fail → payload `ai_title`/`ai_body`). Subscribe: `GET/POST/DELETE /me/push-*` + `frontend/public/sw.js`; `/notifications` shows push enable CTA when not subscribed
- `GET /api/v1/me/insights` — coach summary + near-miss + Academy/roadmap hub; UI `/me/insights`
- Email prefs also store `match_near`, `coach_weekly`, `push_enabled` (all default on with `profile_nudge` / `high_match`); marketing daily cap includes those kinds; UI `/settings/notifications` (legacy `/settings/emails` redirects). Push still needs browser subscribe + VAPID.
- Staff moderation (manual role): approve/reject/edit, crawled job tools; `/admin` RSC hydrates queue jobs + applications + crawled ads + AI flags so first paint and those tabs skip the list BFF; queue/crawled/application writes and list refresh are FastAPI server actions; AI-flag save is a FastAPI PUT server action; manual ad create is a FastAPI POST server action. AI flow toggles (`GET/PUT /api/v1/admin/ai-flags`, jobs-DB `ai_feature_flags`) so staff can turn CV/tidy/embed/rerank/llm_rerank/why/role_coach/digest on or off without deleting provider keys
- Aggregation: remote/relocation IT sources (API/RSS/ATS); Jooble/Reed gated by API keys + monthly budgets
- CV parse: API enqueues `parse_cv_queue` then drains in-process (`app.cv_parse_jobs` background thread → `worker.cv_parse` + OCR + AI #1 `cv-parse-ai1-v2` when confidence < 0.55 or dictionary skills < 3 → jobs-DB `candidate_profile`); skill items carry evidence/confidence; soft skills stay out of matching list; hourly crawl worker may drain stranded rows; contact-only `candidate_profiles` (display/phone/email) shares jobs Postgres when `DATABASE_URL` is set, else `accounts.sqlite`
- `ai_gateway` (worker package, also loaded by API): PII redact, `ai_cache`, daily call budget, cost log, OTEL spans; `complete_json` (CV #1, digest #4, match why, LLM re-rank, role coach) + `embed()` (AI #2). Multi-provider fallback: chat `gemini→groq→nvidia→openrouter→openai` (`AI_CHAT_PROVIDERS`); embed `nvidia→openai` (`AI_EMBED_PROVIDERS`). Keys: `GEMINI_API_KEY`, `GROQ_API_KEY`, `NVIDIA_API_KEY`, `OPENROUTER_API_KEY`, `OPENAI_API_KEY`. Chat defaults: Gemini `gemini-3.8-flash`, NVIDIA `nvidia/nemotron-3-super-120b-a12b`, OpenRouter `openrouter/free`. NVIDIA embed default `nvidia/nemotron-3-embed-1b` (2048-dim via `AI_EMBEDDING_DIMS`). Successful calls **commit** cache/usage immediately so read paths (`skill-gap`, matches) that close without a caller commit still reuse DB cache on the next request
- Consents (`consent` in jobs DB; `GET/PUT /api/v1/consents`); copy from `docs/cv-ai/consent-copy-v1.json`; visibility on `candidate_profile`
- Saved jobs: `saved_jobs` table; `GET/POST/DELETE /api/v1/me/saved-jobs` (+ `/ids`); UI `/saved` + card/detail toggle (`SaveJobButton`); any signed-in user; list skips unpublished
- Talent search MVP: `GET /api/v1/talent` for employer/staff with complete company profile; index = confirmed + `recruiter_visibility` + visibility `anonymous|public`; redacts name unless `public`; no contact requests yet; UI `/talent`
- CV profile review: `GET/PUT /api/v1/profile` + `/profile/review`; form covers contact (incl. city/country), links, headline, about/`summary`, seniority/years, skills, work (location+summary), education, languages; RSC hydrates profile + roles so first paint skips the BFF; save/upload/poll/cancel/reset are FastAPI server actions; `profile_edit_log`; status draft→confirmed; CV/consent/profile DDL is process-cached (no CREATE TABLE per request); CV parse fills `summary` from About/Summary section
- Role suggestions: `GET /api/v1/me/roles` (signature skill weights × years_factor; matching consent; BFF `/api/auth/me/roles`); one `role_skill_weight` scan + process-cached skill lookup/weights/taxonomy until taxonomy counts change
- Job matches: `GET /api/v1/me/matches` structured score (skills/seniority/location/language/freshness); published jobs + `job_skill` are process-cached until catalog fingerprint changes; match_feedback DDL is process-cached; AI #2 pipeline: embed text (richer profile/job builders) → optional cosine blend `0.7×struct + 0.3×cosine` → optional LLM re-rank top-10 `0.55×blended + 0.45×(relevance/5)` (`match_llm_rerank`, flag `llm_rerank` / `AI_LLM_RERANK_ENABLED`; works on struct top-10 even without pgvector) → top-5 match-why v2; down-vote feedback demotes `score × 0.4` (stays listed); flags `AI_RERANK_ENABLED`, `AI_MATCH_WHY_ENABLED` plus staff DB toggles; feedback `POST .../matches/{id}/feedback` → `match_feedback`
- Skill gap: `GET /api/v1/me/skill-gap?role=` from `role_skill_weight`; role resolve uses cached taxonomy (canonical + synonyms); share/growth from `skill_trend_daily` when present; optional `role_coach` AI (`coach`, `ai_coach`; flag `AI_ROLE_COACH_ENABLED`) with post-validated must_learn / already_strong / transferable; coach prompt is per-role (`Role:` in user message) and includes rounded market `share`/`growth` for quality (`role-coach-v4`); cards sort by weight×name; TopSkills alphabetical — same-day refresh hits `ai_cache`; daily trend refresh may regenerate once; Academy course links from `skill_dictionary.academy_course_ids` (map → seed); Academy career-path from `role_taxonomy.academy_career_path_id` (map `docs/cv-ai/academy-career-path-role-map-v1.json` → worker seed; base `/career-paths/`); role change on `/me/recommendations` loads gap + full coach via a FastAPI server action
- Request-path AI is non-blocking: `skill-gap` / `matches` use `complete_json(allow_provider=False)` (cache hit only). Cache miss → `coach_error=ai_pending` / `ai_pending=true` + daemon warm via `app.ai_warm` (re-runs payload with providers on). UI polls until ready. Background jobs (`coach_weekly`) pass `allow_ai_provider=True`
- Skill trends: worker `skill_trends.refresh_skill_trends` → `skill_trend_daily` + `skill_pair_daily`; public `GET /api/v1/trends`; detail `GET /api/v1/trends/{skill_id}` (market + top jobs via `job_skill` + optional auth `you` vs often_with); UI `/trends` + `/trends/[skillId]`
- Recommendations detail: market-ranked skill-gap `missing` + Academy course/career-path links; `GET /me/matches?role=` filters/re-ranks by `role_skill_weight` overlap (limit ~10); shared UI in `frontend/components/skill-gap-bits.js`
- Trend salary signals: worker `salary_parse` annualizes free-text `jobs.salary` (currency+period required, no FX) into per-currency groups in `salary_by_currency` JSON (+ primary `salary_median/currency/n/low/high`); API returns `salaries[]` (and `salary` = top group) when a currency has `n >= 5` — currencies never mixed/converted
- Skill pairs: ordered co-occurrence in `skill_pair_daily`; trends items expose top `often_with` (share among base-skill ads, min 10 base ads); skill-gap missing skills get best pair vs candidate’s have skills
- UI: `/me/recommendations` (roles + Öyrənmək üçün / Sizdə var gap + full coach + matching jobs + 👍/👎; RSC hydrates from FastAPI); `/me/skills` redirects to recommendations; `/me/insights` (coach + near-miss + growth); `/notifications` rich engagement cards (score/chips/CTA); BFF under `/api/auth/me/*`
- Email program: `email_prefs` / `email_log`; `GET/PUT /api/v1/email-prefs`; public unsubscribe; digests via `POST /api/v1/internal/email-jobs` (`INTERNAL_JOB_TOKEN`); high-match email owned by engagement (`match_new` → prefs kind `high_match`); UI `/settings/notifications` RSC hydrates prefs so first paint skips the BFF; save is a FastAPI PUT server action
- Email click tracking: HMAC `/r/<token>` (frontend proxy → `GET /api/v1/r/{token}` → 302 job page); logs `email_click`; digests/engagement emails use tracked URLs only
- AI #4 digest intro: API `ai_gateway` + `digest_intro` (optional 2–3 sentences; `DIGEST_AI_INTRO_ENABLED`; soft-fail to static copy; shares jobs-DB `ai_cache`/`ai_usage_daily` with worker CV AI #1)
- Engagement AI copy: API `engagement_copy` via `ai_gateway` (`engagement-copy-v1`; flag `engagement_copy` defaults on with `OPENAI_API_KEY`, hard-off via `ENGAGEMENT_AI_COPY_ENABLED=0` or staff toggle; cache+budget; soft-fail az/en/ru templates); lookback `ENGAGEMENT_LOOKBACK_HOURS` (default 72) + catalog fallback
- AI #2: worker `embed_stale_jobs` hourly; API embeds profile on save; compose image `pgvector/pgvector:pg16`; Railway needs `CREATE EXTENSION vector`
- Academy cross-sell: ~135 skills mapped to training slugs; UI/digest UTM `utm_source=ingress_job`
- Data rights: `GET /api/v1/me/export` (zip: export.json + CVs); `DELETE /api/v1/me` (hard-delete; audit → pseudonym). Account identity remains `GET /api/v1/me`

## Integrations

- Ingress Academy OIDC
- Job source APIs / RSS / ATS boards (`worker/worker/catalog.py`, `ats_boards.py`)
- Object storage for uploads (when configured)
- Optional `JOOBLE_API_KEY`, `REED_API_KEY`, `HH_API_KEY`
- Optional AI keys: `GEMINI_API_KEY` / `GROQ_API_KEY` / `NVIDIA_API_KEY` / `OPENROUTER_API_KEY` / `OPENAI_API_KEY` (job tidy + CV AI #1 + engagement_copy + embeddings via `ai_gateway`)
- Optional Web Push: `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_SUBJECT` (API `pywebpush`; public key also exposed to browser via `/me/push-vapid-key`)

## Notes

- Prefer scoped reads: `frontend/app|components`, `api/app`, `worker/worker`
- Locales and guest vs logged-in link rules are product constraints — see README
- `.cursor/context/current-task.md` for active work
