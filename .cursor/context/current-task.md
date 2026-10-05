# Current task

## Completed
- CV/AI plan accepted as source of truth: `docs/ingress-job-cv-ai-plan.pdf`
- Phase 0.1–0.4: skill dictionary, job_skill, role taxonomy, consent copy stubs
- Phase 1.1: rules-only CV parser prototype (no AI #1)
  - `worker/worker/cv_parse/` — text extract (PDF/DOCX/txt), contact regex + phonenumbers,
    multilingual sections, date ranges + merged years, skills via `techstack.find_stack`,
    confidence, profile JSON (§5.2)
  - Deps: `pypdf`, `python-docx`, `phonenumbers` in `worker/pyproject.toml`
  - Tests: `worker/tests/test_cv_parse.py` + synthetic fixture `tests/fixtures/cv/sample_backend.txt`
  - OCR / legacy `.doc` explicitly unsupported for now

## Decisions
- Principle: deterministic first; AI only at the 4 named points in the plan
- One small commit per step; do not mix unrelated frontend WIP
- Parser skills reuse curated `techstack` patterns (same canonical names as skill_dictionary)
- No queue/DB/API/UI in 1.1 — pure library + unit tests first
- Consent copy remains stub until lawyer review; wire `/api/consents` + UI later in Phase 1

## Remaining
- Phase 1.2: `parse_cv_queue` table + worker drain (enqueue on CV upload / existing application CV)
- Phase 1.3: consent API/UI using `consent-copy-v1.json`
- Later in Phase 1: profile confirm screen, role suggestions, OCR, AI #1 fallback
- Optional: real anonymized test CV set (plan §17.2) — not inventable in-repo

## Relevant files
- `worker/worker/cv_parse/`
- `worker/tests/test_cv_parse.py`
- `worker/worker/techstack.py` (`find_stack`)
- `docs/cv-ai/consent-copy-v1.json`
- `docs/ingress-job-cv-ai-plan.pdf`

## Continue prompt (new chat)
Phase 1.2: `parse_cv_queue` (+ candidate profile storage stub) and worker drain calling `worker.cv_parse`. No AI #1. Read `.cursor/context/current-task.md` and plan §4 / §12 / §13.3.
