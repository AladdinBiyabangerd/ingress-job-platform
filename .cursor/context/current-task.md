# Current task

## Completed
- Phase 0–2.12 (matches, trends, digests, skill pairs, etc.) — see prior notes
- Profile review UX + Sıfırla; CV parse v1.5–v1.6
- `/profile` layout: sticky footer + split cards
- Academy skill↔course map v1 (~57 skills, `/trainings/` + UTM)
- Academy role↔career-path map v1 (~23 roles); seeded into `role_taxonomy.academy_career_path_id`; skill-gap/roles/`/me/skills`/digest

## Decisions
- Courses attach to skills (`academy_course_ids`); career paths attach to roles (`academy_career_path_id`) — both DB-seeded, not runtime-static JSON
- Prefer stable English career-path slugs when AZ transliteration duplicates exist

## Remaining
- AI #2 re-rank when Postgres + pgvector available
- Ops SPF/DKIM; consolidate worker+API `ai_gateway`
- Spot-check logged-in `/me/skills` course + career-path links in real session
- Extend course/path maps when Academy catalog grows

## Relevant files
- `docs/cv-ai/academy-career-path-role-map-v1.json`
- `api/app/academy_paths.py`
- `api/app/skill_gap.py` / `role_suggestions.py` / `digests.py`
- `frontend/lib/copy.js` (`academyCareerPathUrl`)
- `frontend/components/me-skills.js`

## Continue prompt (new chat)
Academy career-path links on `/me/skills` (role map v1). Next: AI #2 or ops SPF/DKIM / ai_gateway consolidate. Read `.cursor/context/current-task.md`.
