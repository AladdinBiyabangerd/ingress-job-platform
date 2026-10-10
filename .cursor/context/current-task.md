# Current task

## Completed
- Job ops status API + Academy staff page (prior)
- Profile review density pass (`refine` strip + surface)
- `/settings/notifications` density pass (surface)
- `/saved` density pass (surface): match applications / notifications gate + list density

## Current state
- Guest gate: compact `.h2-panel.my-saved-gate` (~320px) with Sign in / Create account (no RegisterChoice mega empty)
- Page chrome title 1.125rem; actions 32px
- List rows: 28px avatar, 8×10 padding, 13/11 type; preview padding 14×16, title 1.125rem, no soft shadow / no 280px min-height
- Empty authenticated state: compact `.my-saved-empty` (not dashed `h2-empty`)

## Decisions
- Density owned under `.my-saved` so `.h2-candidate` / `.btn` base sizes do not re-inflate
- Catalogue work pattern: scan list → select → preview; dense rows, quiet preview

## Remaining work
- Optional: verify authenticated list+preview live once logged in (CSS already scoped)

## Relevant files
- `frontend/components/my-saved.js`
- `frontend/components/saved-job-panel.js`
- `frontend/app/globals.css` (`.my-saved` / `.saved-*` block)
