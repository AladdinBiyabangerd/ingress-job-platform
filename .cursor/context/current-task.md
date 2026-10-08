# Current task

## Completed
- Trend detail design variants A/B/C (PNG mocks in `designs/trend-detail/`)
- User chose **Variant A** — implemented

## Current state
- Trend detail page: full-width KPI strip + 2-col learn cards + aside (courses/CTA) + have chip strip
- Files changed: `frontend/components/trend-detail.js`, `frontend/app/globals.css`

## Decisions
- Variant A layout (not B rank table / C bento)
- KPI strip always shown; as_of moved under aside disclaimer
- Have companions as horizontal chips, not tall rows

## Remaining
- Visual smoke on logged-in `/trends/{python}` and guest state
- User pick deploy / commit when ready

## Relevant files
- `frontend/components/trend-detail.js`
- `frontend/app/globals.css`
- `designs/trend-detail/A-kpi-strip-cards.png`
