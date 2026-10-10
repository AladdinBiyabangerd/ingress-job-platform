# Current task

## Completed
- `job-analyze-v3` + `job-apply-draft-v3`: natural AZ prose rules (no TR/EN bleed, no “Siz … sizə”)
- Deterministic `facts.remote` / `facts.relocation` → Bəli/Xeyr (az), Yes/No (en), Да/Нет (ru)

## Current state
- Local API change; needs deploy. User should refresh analyze (`?refresh=1` / reopen) to bust v2 cache.

## Decisions
- Prompt hardening + locale yes/no override; not a full grammar rewriter

## Remaining work
- Manual QA AZ analyze summary after refresh

## Relevant files
- `api/app/job_analyze.py`
- `api/app/job_apply_draft.py`
- `api/tests/test_job_analyze.py`
