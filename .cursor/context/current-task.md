# Current task

## Completed
- Job ops status API + Academy staff page (prior)
- Profile review density pass (`refine` strip + surface)
- `/settings/notifications` density pass (surface): match profile Option A / review scale

## Current state
- Notifications settings scoped under `.email-settings`
- Channel cards → divider list rows (no 64px min card grid)
- Selects 36px; switches 36×20; actions 32px
- Summary rail merged (stat + plan in one panel); push nested in channels panel
- Guest gate compact (~320px) with Sign in / Create account (same as profile/review)

## Decisions
- Density owned under `.email-settings` so `.h2-candidate` / `.btn` base sizes do not re-inflate
- Settings pattern: list rows + switches, not marketing channel cards

## Remaining work
- Optional: verify authenticated form live once logged in (CSS already scoped)

## Relevant files
- `frontend/components/email-settings.js`
- `frontend/app/globals.css` (email-settings block)
