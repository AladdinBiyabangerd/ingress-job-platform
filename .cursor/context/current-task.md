# Current task

## Completed
- CV/AI plan accepted: `docs/ingress-job-cv-ai-plan.pdf`
- Phase 0.1–0.4: skill dictionary, job_skill, role taxonomy, consent copy stubs
- Phase 1.1: rules-only CV parser (`worker/worker/cv_parse/`)
- Phase 1.2: `parse_cv_queue` + worker drain → jobs-DB `candidate_profile` draft
- Phase 1.3: consent API/UI (`GET/PUT /api/v1/consents`, privacy on `/profile`)
- Phase 1.4: profile confirm screen (`/profile/review`)
  - API: `GET/PUT /api/v1/profile` over jobs-DB `candidate_profile`
  - `profile_edit_log` on save/confirm; confirmed status for HR readiness
  - BFF `/api/auth/cv-profile`; UI az/en/ru with editable fields + skill chips
  - Low-confidence fields highlighted; link from `/profile`
  - Tests: `api/tests/test_cv_profile.py`

## Decisions
- Deterministic first; AI only at the 4 named plan points
- `candidate_profile` (jobs DB) ≠ `candidate_profiles` (accounts.sqlite contact)
- Confirmed profiles are never overwritten by automatic parse
- Contact BFF stays `/api/auth/profile`; structured CV profile is `/api/auth/cv-profile`
- Low-confidence threshold: 0.55 (pilot-tunable)

## Remaining
- Later Phase 1: role suggestions, OCR, AI #1 fallback, export/delete
- Optional: `/profile/cv` upload page (plan §13.2); parse still enqueue on apply
- Optional: dedicated `/settings/privacy`; privacy lives on `/profile` for now
- Optional: anonymized test CV set (plan §17.2)

## Relevant files
- `api/app/cv_profile.py`, `api/app/routers/profile.py`, `api/tests/test_cv_profile.py`
- `frontend/components/profile-review.js`, `frontend/app/**/profile/review/page.js`
- `frontend/app/api/auth/cv-profile/route.js`
- `frontend/components/profile-form.js`, `frontend/lib/copy.js`
- `docs/ingress-job-cv-ai-plan.pdf` (§5.3 / §13.1–13.2)

## Continue prompt (new chat)
Phase 1 next: role suggestions (`GET /api/me/roles`) using `role-taxonomy-v1.json` + confirmed/draft skills. Read `.cursor/context/current-task.md` and plan §6.
