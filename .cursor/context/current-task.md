# Current task

## Completed
- Education dedupe: same school+degree+year merges into one row; fields joined with ` / `
- Applied in `cv_profile.normalize_profile_data` (fixes profile review on read) and CV parser
- Tailored CV prompt → `job-tailored-cv-v4` (include field in degree; no duplicate school+degree+year)

## Current state
- Local fix ready; needs API (+ worker) redeploy
- Existing profile shows 1 merged education after refresh (merge on read); Saxla persists it
- Regenerated tailored CV after deploy uses v4 cache key

## Decisions
- Dual majors from same school/year = one education entry, not two cards

## Remaining work
- Deploy API/worker; refresh `/profile/review`; regenerate tailored CV if still duplicated

## Relevant files
- `api/app/cv_profile.py`
- `worker/worker/cv_parse/pipeline.py`
- `api/app/job_tailored_cv.py`
- `api/tests/test_cv_profile.py`
- `worker/tests/test_cv_parse.py`
