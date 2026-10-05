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
  - `worker/worker/ai_gateway/`: redact, cache (`ai_cache`), daily budget (`ai_usage_daily`), cost estimate, OTEL span, feature flag
  - Trigger: rules `confidence` < `CV_AI_LOW_CONFIDENCE` (default 0.55)
  - PII mask → OpenAI structured JSON → skill dictionary + in-text filter
  - Contact always from rules; soft-fail keeps rules profile
  - `parse_meta.method`: `rules` | `llm`; `prompt_version`: `cv-parse-ai1-v1`
  - Parser version `1.2`
  - Env: `OPENAI_API_KEY`, `AI_GATEWAY_ENABLED`, `AI_GATEWAY_MODEL`, `AI_GATEWAY_DAILY_CALL_LIMIT`, `CV_AI_FALLBACK_ENABLED`, `CV_AI_LOW_CONFIDENCE`
  - Tests: `worker/tests/test_ai_gateway.py`, `test_cv_ai_fallback.py`

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

## Remaining
- Later Phase 1: export/delete (`GET/DELETE /api/v1/me`)
- Phase 2+: `/me/matches`, skill-gap, feedback, `/me/recommendations` page
- Optional: `/profile/cv` upload page (plan §13.2); parse still enqueue on apply
- Optional: dedicated `/settings/privacy`; privacy lives on `/profile` for now
- Optional: anonymized test CV set (plan §17.2); aze/rus Tessdata packs in Docker
- Optional: local `brew install tesseract` for real OCR smoke tests
- Optional: copy `ai_gateway` into API when matching/embeddings need it

## Relevant files
- `worker/worker/ai_gateway/` (`gateway.py`, `redact.py`)
- `worker/worker/cv_parse/ai_fallback.py`, `pipeline.py`
- `worker/worker/cv_queue.py`
- `worker/tests/test_ai_gateway.py`, `test_cv_ai_fallback.py`
- `docs/ingress-job-cv-ai-plan.pdf` (§5.1 / §11 / §17)

## Continue prompt (new chat)
Phase 1 next: export/delete (`GET/DELETE /api/v1/me` — JSON + original CV files; hard-delete profile/skills/embeddings/CV/email prefs; audit keeps pseudonym). Read `.cursor/context/current-task.md` and plan §10.3.
