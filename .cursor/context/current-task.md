# Current task

## Completed
- CV/AI plan accepted as source of truth: `docs/ingress-job-cv-ai-plan.pdf`
- Phase 0.1: skill dictionary seed from curated `techstack.py` + local job frequencies
  - `scripts/export_skill_dictionary.py`
  - `docs/cv-ai/skill-dictionary-v1.json` (98 skills)
  - `docs/cv-ai/skill-frequency-snapshot.json`
- Phase 0.2: `skill_dictionary` + `job_skill` tables, seed, tech_stack backfill
  - `worker/worker/skills.py` (+ packaged `skill_dictionary_v1.json`)
  - Wired in `worker/worker/db.py` (init / upsert / backfill_derived)
  - Tables also created from `api/app/cabinet_store.py` when API opens DB first
  - Tests: `worker/tests/test_skills.py`

## Decisions
- Principle: deterministic first; AI only at the 4 named points in the plan
- Reuse existing `worker/worker/techstack.py` vocabulary as skill_dictionary v1 (no new synonym invention yet)
- One small commit per step; do not mix unrelated frontend WIP
- `job_skill` links only known dictionary names; unknown `tech_stack` values are skipped
- Seed JSON is packaged under `worker/worker/` so the Railway worker image can load it
- One-time backfill via `maintenance_steps`; ongoing sync when worker writes `tech_stack`

## Remaining (Phase 0 → then Phase 1)
- 0.3: role taxonomy v1 (~30–40 roles under existing categories)
- 0.4: consent/privacy copy stubs (AZ/EN/RU) — legal review later
- Then Phase 1: CV parse queue (rules-only prototype first, AI #1 later)

## Relevant files
- `worker/worker/skills.py`
- `worker/worker/skill_dictionary_v1.json`
- `worker/worker/db.py`
- `api/app/cabinet_store.py`
- `docs/cv-ai/skill-dictionary-v1.json`
- `scripts/export_skill_dictionary.py`

## Continue prompt (new chat)
Phase 0.3: role taxonomy v1 (~30–40 roles under existing job categories). Deterministic seed data only; no AI.
