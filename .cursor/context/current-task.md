# Current task

## Completed
- Job detail desktop: company about card removed
- Analiz et + Müraciət mətni moved to single right `jd-aside` (CTA above)
- Mobile: same aside stacks under JD (no double mount)
- Aside sticky + max-height scroll when report is tall
- Fix: `.jd-aside > * { flex-shrink: 0 }` so CTA apply button is not clipped when analyze is open

## Current state
- CTA crush bug fixed locally; commit/deploy still needed if not pushed

## Decisions
- One aside column (not duplicate desktop/mobile mounts) so analyze fetch runs once
- Apply form stays in main under description
- Scroll the aside; never flex-shrink the CTA card

## Remaining work
- Visual QA: open Analiz et — “Orijinal elanı aç” / apply CTA still fully visible above

## Relevant files
- `frontend/components/job-detail/job-detail-view.js`
- `frontend/components/job-detail/job-detail-company-sidebar.js`
- `frontend/app/globals.css`
