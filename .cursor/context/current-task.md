# Current task

## Completed
- CV/AI plan accepted: `docs/ingress-job-cv-ai-plan.pdf`
- Phase 0.1–0.4: skill dictionary, job_skill, role taxonomy, consent copy stubs
- Phase 1.1: rules-only CV parser (`worker/worker/cv_parse/`)
- Phase 1.2: `parse_cv_queue` + worker drain → jobs-DB `candidate_profile` draft
- Phase 1.3: consent API/UI (`GET/PUT /api/v1/consents`, privacy on `/profile`)
- Phase 1.4: profile confirm screen (`/profile/review`)
- Phase 1.5: role suggestions (`GET /api/v1/me/roles`)
- Phase 1.6: OCR text extract for scans (Tesseract)
- Phase 1.7: AI #1 fallback + `ai_gateway` skeleton
- Phase 1.8: export/delete (plan §10.3)
  - `GET /api/v1/me/export` → zip (`export.json` + original CV files)
  - `DELETE /api/v1/me` → hard-delete profile, parse queue, consents/email prefs, contact profile, CV files; applications anonymized; `profile_edit_log` → pseudonym
  - BFF: `/api/auth/me/export`, `DELETE /api/auth/me`
  - Privacy rights UI on `/profile` (from `consent-copy` `privacy_rights`)
  - Tests: `api/tests/test_me_data.py`

## Decisions
- Deterministic first; AI only at the 4 named plan points
- `candidate_profile` (jobs DB) ≠ `candidate_profiles` (accounts.sqlite contact)
- Confirmed profiles are never overwritten by automatic parse
- Contact BFF stays `/api/auth/profile`; structured CV profile is `/api/auth/cv-profile`
- Low-confidence threshold: 0.55 (pilot-tunable)
- Role years_factor: missing → 1.0; else clamp(years/5, 0.5, 1.5)
- Plan path `/api/me/roles` → `/api/v1/me/roles` (v1 convention)
- No matching consent → empty roles + `matching_consent: false` (not 403)
- OCR before AI #1 (plan §17: measure rules/OCR first, then add LLM fallback)
- OCR optional at runtime: digital CVs still parse if Tesseract missing
- AI gateway default-on only when `OPENAI_API_KEY` set; over-budget → AI-less mode
- LLM never receives raw PII; skills not in dictionary or CV text are dropped
- Plan GET `/api/me` export collides with account `GET /api/v1/me` → export at `/api/v1/me/export`
- Audit pseudonym: `anon_` + sha256(`ingress-job-audit:{user_id}`)[:32]
- Applications kept for employers but PII/CV cleared and `candidate_subject` → pseudonym
- `who_viewed` privacy right is stub-only (Phase 3)

## Remaining
- Phase 1 complete for core CV→profile→privacy path
- Phase 2+: `/me/matches`, skill-gap, feedback, `/me/recommendations` page
- Optional: `/profile/cv` upload page (plan §13.2); parse still enqueue on apply
- Optional: dedicated `/settings/privacy`; privacy lives on `/profile` for now
- Optional: anonymized test CV set (plan §17.2); aze/rus Tessdata packs in Docker
- Optional: local `brew install tesseract` for real OCR smoke tests
- Optional: copy `ai_gateway` into API when matching/embeddings need it

## Relevant files
- `api/app/me_data.py`, `api/app/routers/me.py`
- `api/app/applications.py` (`normalize_cv_key`, `read_stored_cv`, `delete_stored_cv`)
- `api/app/consents.py` (`privacy_rights` in payload)
- `frontend/app/api/auth/me/export/route.js`, `frontend/app/api/auth/me/route.js`
- `frontend/components/profile-form.js`
- `api/tests/test_me_data.py`
- `docs/ingress-job-cv-ai-plan.pdf` (§10.3)

## Continue prompt (new chat)
Phase 2 start (or pick): matching `/me/matches` / skill-gap / recommendations UI. Read `.cursor/context/current-task.md` and plan Phase 2 overview. Phase 1 export/delete is done.
