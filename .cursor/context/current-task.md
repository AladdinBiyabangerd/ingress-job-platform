# Current task

## Completed
- Phase 0–2.12; CV parse; Academy course/path maps
- Role scoring OR-groups / thin-role dampen
- Railway web healthcheck removed (dashboard must clear path too)
- **Role taxonomy v1.2:** 40 → 61 roles; denser signature skills/synonyms

## Decisions
- Taxonomy source: `docs/cv-ai/role-taxonomy-v1.json` (+ worker packaged copy)
- Rebuild helper: `scripts/build_role_taxonomy_v12.py`
- Soft roles (Product/Design/Manual QA) stay lighter on tech weights

## Remaining
- Re-seed / restart worker so live DB picks up taxonomy v1.2
- Spot-check `/me/recommendations` + `/me/skills`
- AI #2 re-rank; ops SPF/DKIM; ai_gateway consolidate

## Relevant files
- `docs/cv-ai/role-taxonomy-v1.json` / `worker/worker/role_taxonomy_v1.json`
- `docs/cv-ai/academy-career-path-role-map-v1.json`
- `scripts/build_role_taxonomy_v12.py`
- `worker/tests/test_roles.py`
