# Current task

## Completed
- Recommendations AI quality plan (full):
  1. CV prompt v2 (`cv-parse-ai1-v2`) + evidence/confidence filter + thin-skills force
  2. Richer `profile_embed_text` / `job_embed_text` (API + worker)
  3. `match_llm_rerank` + feedback demotion ×0.4 + flags/admin
  4. `match-why-v2` richer context
  5. `role_coach` + skill-gap `coach`/`ai_coach`
  6. `/me/recommendations` + `/me/skills` coach UI + az/en/ru copy
  7. architecture.md + this file
- Local smoke (unit, 2026-10-07):
  - CV thin-skills: `worker/tests/test_cv_ai_fallback.py` (10 OK) — `ai_force_reason=thin_skills`
  - `ai_llm_rerank` + demotion: `api/tests/test_embeddings_rerank.py` LlmRerankTests OK
  - skill-gap coach: `api/tests/test_role_coach.py` (6 OK) — `coach`/`ai_coach`
  - admin toggles: `AdminAiFlagsTests` asserts `llm_rerank` + `role_coach` GET/PUT

## Current state
- Code ready; **not committed / not on Railway**. Live prod `web-production-dba98.up.railway.app` still old build — live staging smoke blocked until commit+deploy.
- Production açılsın staff flags ilə: `llm_rerank`, `role_coach` (plus mövcud `rerank` / `match_why` / `cv_fallback`).

## Decisions
- Final match: struct → optional cosine 0.7/0.3 → LLM top-10 0.55/0.45 → why; down vote ×0.4.
- LLM re-rank struct top-10 üzərində də işləyir (pgvector olmasa belə).
- Coach skill adları have/missing set intersection ilə post-validate.

## Remaining
1. Optional: git commit + PR + Railway deploy.
2. **Live** staging smoke (post-deploy checklist):
   - `/admin` → AI flags: toggle `llm_rerank` / `role_coach` on/off + save
   - CV with <3 dictionary skills + high rules confidence → `parse_meta.ai_force_reason=thin_skills`
   - `/me/recommendations` matches: `ai_llm_rerank: true` when flag on
   - `/me/skills` skill-gap: `ai_coach: true` + coach sections when `role_coach` on
3. Staff flags-i tədricən yandır.

## Relevant files
- `worker/worker/cv_parse/ai_fallback.py`, `worker/tests/test_cv_ai_fallback.py`
- `api/app/embeddings.py`, `worker/worker/embeddings.py`, `api/tests/test_embeddings_rerank.py`
- `api/app/match_llm_rerank.py`, `api/app/matching.py`, `api/app/match_why.py`
- `api/app/role_coach.py`, `api/app/skill_gap.py`, `api/tests/test_role_coach.py`
- `api/app/ai_flags.py`, `worker/worker/ai_flags.py`, `api/tests/test_admin.py`
- `frontend/components/{recommendations,me-skills,admin-ai-flags}.js`, `frontend/lib/copy.js`, `frontend/app/globals.css`
