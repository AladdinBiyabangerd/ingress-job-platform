# Current task

## Completed
- Phase 0–2.12 (matches, trends, digests, skill pairs, etc.)
- Profile review UX + Sıfırla; CV parse v1.5–v1.6
- Academy skill↔course + role↔career-path maps
- Role scoring v1.1 (OR-groups, thin-role dampen, headline affinity)
- **CV parse on API async:** upload → `parse_cv_queue` → `app.cv_parse_jobs` background drain
- **Fix worker Postgres boot crash:** `_NO_ID_TABLES` now includes `role_skill_weight` (and other composite-PK tables) so the adapter does not append `RETURNING id`

## Decisions
- Courses → skills; career paths → roles (DB-seeded)
- Polyglot signature skills use `group` in taxonomy JSON → `role_skill_weight.group_key` (OR = max weight)
- Thin roles (`total_weight < 1.0`) dampened; headline/title affinity ×1.15
- No AI for role scoring yet
- CV parse primary path is API in-process; Railway api `root: "."` + `RAILWAY_DOCKERFILE_PATH=api/Dockerfile`
- Postgres `RETURNING id` only for tables with integer `id` PK; composite-PK tables listed in `_NO_ID_TABLES`

## Remaining
- Redeploy worker (and API) on Railway so production picks up `_NO_ID_TABLES` fix
- Spot-check Aladdin CV on `/profile/review` (should leave Növbə in seconds)
- AI #2 re-rank when Postgres + pgvector available
- Ops SPF/DKIM; consolidate worker+API `ai_gateway`

## Relevant files
- `worker/worker/jobs_db.py`, `api/app/jobs_db.py`, `api/tests/test_jobs_db.py`
- `api/app/cv_parse_jobs.py`, `api/app/cv_profile.py`, `api/app/applications.py`
- `api/Dockerfile`, `.railway/railway.ts`, `docs/railway.md`

## Continue prompt (new chat)
Worker Postgres boot crash fixed (`role_skill_weight` in `_NO_ID_TABLES`). Redeploy worker/API; then spot-check `/profile/review`. Read `.cursor/context/current-task.md`.
