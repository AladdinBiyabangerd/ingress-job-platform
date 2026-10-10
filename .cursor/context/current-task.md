# Current task

## Completed
- Job detail desktop: company about card removed
- Analiz et + Müraciət mətni moved to single right `jd-aside` (CTA above)
- Mobile: same aside stacks under JD (no double mount)
- Aside sticky + max-height scroll when report is tall

## Current state
- Local frontend change; needs web deploy for prod

## Decisions
- One aside column (not duplicate desktop/mobile mounts) so analyze fetch runs once
- Apply form stays in main under description

## Remaining work
- Visual QA desktop + mobile on a live job detail

## Relevant files
- `frontend/components/job-detail/job-detail-view.js`
- `frontend/components/job-detail/job-detail-company-sidebar.js`
- `frontend/app/globals.css`
