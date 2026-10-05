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
- Phase 1.2: `parse_cv_queue` + worker drain + profile storage stub
  - Tables (shared jobs DB): `parse_cv_queue`, `candidate_profile` (draft JSON; not accounts.sqlite)
  - API: enqueue on application CV upload (`api/app/cv_queue.py`)
  - Worker: one-time enqueue of existing application CVs; drain in each pass via `parse_bytes`
  - CV bytes: local `CV_ROOT` / `api/data/cvs` or S3 (`boto3` on worker)
  - Tests: `worker/tests/test_cv_queue.py`; apply test asserts queue row

## Decisions
- Principle: deterministic first; AI only at the 4 named points in the plan
- One small commit per step; do not mix unrelated frontend WIP
- Parser skills reuse curated `techstack` patterns (same canonical names as skill_dictionary)
- `candidate_profile` (jobs DB) ≠ `candidate_profiles` (accounts.sqlite contact fields)
- Confirmed profiles are never overwritten by automatic parse
- No profile confirm UI / consent API / AI #1 in 1.2

## Remaining
- Phase 1.3: consent API/UI using `consent-copy-v1.json`
- Later in Phase 1: profile confirm screen, role suggestions, OCR, AI #1 fallback
- Optional: real anonymized test CV set (plan §17.2) — not inventable in-repo
- Optional later: dedicated 1–5 min CV-parse schedule (plan §4 / §13.3); currently runs on hourly pass

## Relevant files
- `worker/worker/cv_queue.py`, `worker/worker/cv_files.py`
- `worker/worker/cv_parse/`, `worker/worker/runner.py`, `worker/worker/db.py`
- `api/app/cv_queue.py`, `api/app/applications.py`, `api/app/cabinet_store.py`
- `worker/tests/test_cv_queue.py`
- `docs/cv-ai/consent-copy-v1.json`
- `docs/ingress-job-cv-ai-plan.pdf`

## Continue prompt (new chat)
Phase 1.3: consent API/UI using `docs/cv-ai/consent-copy-v1.json`. Read `.cursor/context/current-task.md` and plan §12 consent / §13.1 `/api/consents`.
