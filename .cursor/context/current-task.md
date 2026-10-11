# Current task

## Completed
- Tailored CV AZ/RU/EN language quality parity (`job-tailored-cv-v5`)
- Split shared ATS system prompt from locale-specific AZ/RU/EN blocks via `_system_for`
- RU + EN banned/prefer + voice rules; `_build_user` reinforcement for all three locales
- Tests updated for v5 + locale isolation

## Current state
- AZ rules no longer injected into RU/EN system prompts
- Cache bust via `PROMPT_VERSION = job-tailored-cv-v5`

## Decisions
- Same depth for AZ/RU/EN language appendices (not minimal EN)
- No few-shot / model change / post-edit — prompt structure only

## Remaining work
- Deploy/refresh so live RU/EN tailored CVs regenerate under v5
- Spot-check same job with `lang=ru` and `lang=en`

## Relevant files
- `api/app/job_tailored_cv.py`
- `api/tests/test_job_tailored_cv.py`
