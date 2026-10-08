# Current task

## Completed
- Saved jobs: table + `/api/v1/me/saved-jobs` CRUD/ids + tests; `/saved` pages; card/detail toggle; account/menu links
- Talent browse MVP: `GET /api/v1/talent` + consent/visibility gate + redaction + tests; `/talent` UI + employer menu; company incomplete gate in middleware
- Docs: customer-journey backlog + architecture notes

## Current state
- Committing saved jobs + talent MVP to `main` (push requested).

## Remaining
- Backlog: şəhər filteri + URL state; talent contact-requests; companies slug merge

## Decisions
- Saved: any authenticated user (not candidate-only)
- Talent: employer/staff + complete company profile; opaque card id = `candidate_profile.id`; no contact-request in MVP

## Relevant files
- `api/app/{saved_jobs,talent}.py`, `api/app/routers/{me,talent}.py`, `api/tests/test_{saved_jobs,talent}.py`
- `frontend/components/{save-job-button,my-saved,talent-search,job-card,job-detail,account-bar,shell}.js`
- `frontend/app/{saved,talent,en/...,ru/...}/page.js`, `frontend/lib/server/{saved-jobs,talent}.js`, `copy.js`
- `docs/customer-journey.md`, `.cursor/context/architecture.md`
