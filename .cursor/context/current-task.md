# Current task

## Completed
- CV/AI plan accepted as source of truth: `docs/ingress-job-cv-ai-plan.pdf`
- Phase 0.1: skill dictionary seed from curated `techstack.py` + local job frequencies
  - `scripts/export_skill_dictionary.py`
  - `docs/cv-ai/skill-dictionary-v1.json` (98 skills)
  - `docs/cv-ai/skill-frequency-snapshot.json`

## Decisions
- Principle: deterministic first; AI only at the 4 named points in the plan
- Reuse existing `worker/worker/techstack.py` vocabulary as skill_dictionary v1 (no new synonym invention yet)
- One small commit per step; do not mix unrelated frontend WIP

## Remaining (Phase 0 → then Phase 1)
- 0.2: `skill_dictionary` + `job_skill` DB schema / migration + backfill from `tech_stack`
- 0.3: role taxonomy v1 (~30–40 roles under existing categories)
- 0.4: consent/privacy copy stubs (AZ/EN/RU) — legal review later
- Then Phase 1: CV parse queue (rules-only prototype first, AI #1 later)

## Relevant files
- `docs/ingress-job-cv-ai-plan.pdf`
- `docs/cv-ai/skill-dictionary-v1.json`
- `scripts/export_skill_dictionary.py`
- `worker/worker/techstack.py`
- `worker/worker/db.py` (next: schema)

## Continue prompt (new chat)
Phase 0.2: add `skill_dictionary` + `job_skill` tables (SQLite + Postgres path), seed from `docs/cv-ai/skill-dictionary-v1.json`, backfill `job_skill` from existing `jobs.tech_stack`. No AI yet.
