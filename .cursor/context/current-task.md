# Current task

## Completed
- Cyber skill coverage: 12 security skills in `techstack._TECH` + dictionary export (209 skills)
- Academy course map for new security skills
- `REEXTRACT_STACK_STEP` → `reextract-tech-stack-dict-v3-2026-10-11`
- Security Engineer + SOC Analyst signature_skills updated (docs + packaged taxonomy)
- Analyze score guard: skill evidence dampening (`n/4`) + confidence × (`n/3`); UI soft ring when conf &lt; 0.35

## Current state
- Worker hourly will reextract scraped `tech_stack` once on next pass
- Analyze sparse 1-skill overlap no longer shows ~80% with high confidence

## Decisions
- MAX_STACK stays 12; dense cyber JDs may drop lower-priority chips (e.g. ISO after SIEM/EDR/…)
- Hunt / For-you scoring untouched; guard is Analyze-only

## Remaining work
- Optional: run `./scripts/dev-worker.sh once` locally/prod to apply reextract immediately
- Manual QA: cyber JD Analyze with backend-only CV → uncertain / lower %, not AWS-only 80%

## Relevant files
- `worker/worker/techstack.py`
- `worker/worker/db.py` (`REEXTRACT_STACK_STEP`)
- `docs/cv-ai/skill-dictionary-v1.json` / `worker/worker/skill_dictionary_v1.json`
- `docs/cv-ai/role-taxonomy-v1.json` / `worker/worker/role_taxonomy_v1.json`
- `api/app/job_analyze.py`
- `frontend/components/job-detail/job-detail-analyze-panel.js`
- `frontend/lib/copy.js`
- `worker/tests/test_techstack_security.py`
- `api/tests/test_job_analyze.py`
