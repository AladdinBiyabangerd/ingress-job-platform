# Current task

## Completed
- CV/AI plan accepted: `docs/ingress-job-cv-ai-plan.pdf`
- Phase 0.1–0.4: skill dictionary, job_skill, role taxonomy, consent copy stubs
- Phase 1.1: rules-only CV parser (`worker/worker/cv_parse/`)
- Phase 1.2: `parse_cv_queue` + worker drain → jobs-DB `candidate_profile` draft
- Phase 1.3: consent API/UI (`GET/PUT /api/v1/consents`, privacy on `/profile`)
- Phase 1.4: profile confirm screen (`/profile/review`)
- Phase 1.5: role suggestions (`GET /api/v1/me/roles`)
  - Deterministic score: matched signature weights × years_factor / Σ weights (plan §6.1)
  - Matching consent gate; draft or confirmed skills; skill_dictionary synonym resolve
  - BFF `/api/auth/me/roles`; compact list on `/profile/review`
  - Tests: `api/tests/test_role_suggestions.py`

## Decisions
- Deterministic first; AI only at the 4 named plan points
- `candidate_profile` (jobs DB) ≠ `candidate_profiles` (accounts.sqlite contact)
- Confirmed profiles are never overwritten by automatic parse
- Contact BFF stays `/api/auth/profile`; structured CV profile is `/api/auth/cv-profile`
- Low-confidence threshold: 0.55 (pilot-tunable)
- Role years_factor: missing → 1.0; else clamp(years/5, 0.5, 1.5)
- Plan path `/api/me/roles` → `/api/v1/me/roles` (v1 convention)
- No matching consent → empty roles + `matching_consent: false` (not 403)

## Remaining
- Later Phase 1: OCR, AI #1 fallback, export/delete
- Phase 2+: `/me/matches`, skill-gap, feedback, `/me/recommendations` page
- Optional: `/profile/cv` upload page (plan §13.2); parse still enqueue on apply
- Optional: dedicated `/settings/privacy`; privacy lives on `/profile` for now
- Optional: anonymized test CV set (plan §17.2)

## Relevant files
- `api/app/role_suggestions.py`, `api/app/routers/me.py`, `api/tests/test_role_suggestions.py`
- `frontend/app/api/auth/me/roles/route.js`
- `frontend/components/profile-review.js`, `frontend/lib/copy.js`
- `api/app/cv_profile.py`, `api/app/routers/profile.py`
- `docs/ingress-job-cv-ai-plan.pdf` (§6.1 / §13.1)

## Continue prompt (new chat)
Phase 1 next: OCR for scanned CVs, or AI #1 parse fallback when rules confidence is low. Read `.cursor/context/current-task.md` and plan §5.
