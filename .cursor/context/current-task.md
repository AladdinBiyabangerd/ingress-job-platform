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
- Phase 0.3: role taxonomy v1 (40 roles under CATEGORIES + signature skill weights)
  - `docs/cv-ai/role-taxonomy-v1.json` (+ packaged `worker/worker/role_taxonomy_v1.json`)
  - `worker/worker/roles.py` → `role_taxonomy` + `role_skill_weight`
  - Wired in `worker/worker/db.py` + table create in `api/app/cabinet_store.py`
  - Tests: `worker/tests/test_roles.py`
- Phase 0.4: consent/privacy copy stubs (AZ/EN/RU)
  - `docs/cv-ai/consent-copy-v1.json`
  - kinds: matching / emails / recruiter_visibility (all default off)
  - visibility levels + export/delete/who-viewed stubs
  - status: `stub_pending_legal_review` (not wired to UI/API yet)

## Decisions
- Principle: deterministic first; AI only at the 4 named points in the plan
- Reuse existing `worker/worker/techstack.py` vocabulary as skill_dictionary v1 (no new synonym invention yet)
- One small commit per step; do not mix unrelated frontend WIP
- `job_skill` links only known dictionary names; unknown `tech_stack` values are skipped
- Seed JSON is packaged under `worker/worker/` so the Railway worker image can load it
- One-time backfill via `maintenance_steps`; ongoing sync when worker writes `tech_stack`
- Role signature skills must match `skill_dictionary.canonical_name`; unknown names skipped at seed
- Hand weights for v1 (plan §6.1); later refresh from ad frequencies (TF-style, no AI)
- Product/Design/Manual QA roles intentionally sparse on tech weights until non-tech signals exist
- Consent copy is versioned stub JSON only; lawyer review before product use; wire into `/api/consents` + UI in Phase 1

## Remaining
- Optional Phase 0 leftover (manual): test CV set (plan §17.2) — needs real anonymized CVs with consent; not inventable in-repo
- Phase 1: CV parse queue (rules-only prototype first, AI #1 later) + consent UI/API using `consent-copy-v1.json`

## Relevant files
- `docs/cv-ai/consent-copy-v1.json`
- `docs/cv-ai/role-taxonomy-v1.json`
- `docs/cv-ai/skill-dictionary-v1.json`
- `worker/worker/roles.py`
- `worker/worker/skills.py`
- `docs/ingress-job-cv-ai-plan.pdf`

## Continue prompt (new chat)
Phase 1 start: CV parse queue rules-only prototype (text extract + regex + skill dictionary). No AI #1 yet. Read `.cursor/context/current-task.md` and plan §5.1 first.
