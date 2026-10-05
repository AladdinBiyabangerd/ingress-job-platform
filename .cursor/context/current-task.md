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
  - Images (png/jpg/…) via Pillow + pytesseract
  - Low-text PDFs (<40 chars digital extract) → pypdfium2 render + OCR
  - Soft-fail: `ocr_unavailable` / `ocr_disabled` / `ocr_empty` in `parse_meta.error`
  - `parse_meta.text_extract`: `pdf` | `docx` | `text` | `ocr` | `pdf+ocr`
  - Env: `CV_OCR_ENABLED` (default on), `CV_OCR_LANG` (default `eng`), `CV_OCR_SCALE`
  - Worker Docker installs `tesseract-ocr`; deps in `worker/pyproject.toml`
  - Tests: `worker/tests/test_cv_parse.py` (mocked OCR paths)

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
- Parser version bumped to `1.1` (extract path metadata)

## Remaining
- Later Phase 1: AI #1 fallback (low confidence), export/delete
- Phase 2+: `/me/matches`, skill-gap, feedback, `/me/recommendations` page
- Optional: `/profile/cv` upload page (plan §13.2); parse still enqueue on apply
- Optional: dedicated `/settings/privacy`; privacy lives on `/profile` for now
- Optional: anonymized test CV set (plan §17.2); aze/rus Tessdata packs in Docker
- Optional: local `brew install tesseract` for real OCR smoke tests

## Relevant files
- `worker/worker/cv_parse/ocr.py`, `text.py`, `pipeline.py`
- `worker/Dockerfile`, `worker/pyproject.toml`, `worker/uv.lock`
- `worker/tests/test_cv_parse.py`
- `api/app/role_suggestions.py`, `api/app/routers/me.py`
- `docs/ingress-job-cv-ai-plan.pdf` (§5.1 / §14 / §17)

## Continue prompt (new chat)
Phase 1 next: AI #1 parse fallback when rules confidence is low (PII mask → structured LLM JSON → dictionary filter). Or export/delete (`GET/DELETE /api/v1/me`). Read `.cursor/context/current-task.md` and plan §5.1 AI #1 rules + §11 ai_gateway.
