# Current task

## Completed
- Phase 0–2.12 (matches, trends, digests, skill pairs, etc.)
- Profile review UX + Sıfırla; CV parse v1.5–v1.6
- Academy skill↔course + role↔career-path maps
- Role scoring v1.1 (OR-groups, thin-role dampen, headline affinity)
- **CV parse on API async:** upload → `parse_cv_queue` → `app.cv_parse_jobs` background drain (no hourly worker wait). API Docker installs `api`+`worker`+tesseract; crawl worker drains only as backup.

## Decisions
- Courses → skills; career paths → roles (DB-seeded)
- Polyglot signature skills use `group` in taxonomy JSON → `role_skill_weight.group_key` (OR = max weight)
- Thin roles (`total_weight < 1.0`) dampened; headline/title affinity ×1.15
- No AI for role scoring yet
- CV parse primary path is API in-process; Railway api `root: "."` + `RAILWAY_DOCKERFILE_PATH=api/Dockerfile`

## Remaining
- Redeploy API on Railway so production picks up async CV parse
- Spot-check Aladdin CV on `/profile/review` (should leave Növbə in seconds)
- AI #2 re-rank when Postgres + pgvector available
- Ops SPF/DKIM; consolidate worker+API `ai_gateway`

## Relevant files
- `api/app/cv_parse_jobs.py`, `api/app/cv_profile.py`, `api/app/applications.py`
- `api/Dockerfile`, `.railway/railway.ts`, `docs/railway.md`
- `api/tests/test_cv_profile.py`

## Continue prompt (new chat)
Async CV parse shipped in API. Next: redeploy Railway API and spot-check `/profile/review`. Read `.cursor/context/current-task.md`.
