# Current task

## Completed
- Phase 0–2.12 (matches, trends, digests, skill pairs, etc.)
- Profile review UX + Sıfırla; CV parse v1.5–v1.6
- Academy skill↔course + role↔career-path maps
- **Role scoring v1.1:** OR-groups (`group_key`), thin-role dampen, headline affinity; skill-gap skips satisfied OR siblings

## Decisions
- Courses → skills; career paths → roles (DB-seeded)
- Polyglot signature skills use `group` in taxonomy JSON → `role_skill_weight.group_key` (OR = max weight)
- Thin roles (`total_weight < 1.0`) dampened; headline/title affinity ×1.15
- No AI for role scoring yet

## Remaining
- Re-seed / restart worker so live DB picks up taxonomy v1.1 groups
- Spot-check Aladdin-like profile on `/me/recommendations` + `/me/skills`
- AI #2 re-rank when Postgres + pgvector available
- Ops SPF/DKIM; consolidate worker+API `ai_gateway`

## Relevant files
- `docs/cv-ai/role-taxonomy-v1.json` / `worker/worker/role_taxonomy_v1.json` (v1.1)
- `worker/worker/roles.py` (`group_key` seed + migrate)
- `api/app/role_suggestions.py` / `api/app/skill_gap.py` / `api/app/cabinet_store.py`
- `api/tests/test_role_suggestions.py` / `worker/tests/test_roles.py`

## Continue prompt (new chat)
Role scoring OR-groups shipped. Next: restart worker to reseed, spot-check Java backend ranking; or AI #2 / ops. Read `.cursor/context/current-task.md`.
