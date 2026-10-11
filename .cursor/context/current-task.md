# Current task

## Completed
- For-you hunt-ingress-v3 + hide match % on board cards
- Home board filters persist in URL (`replaceState` + SSR `searchParams`) so job detail → back keeps filters

## Current state
- Board query keys: `q`, `remote`, `stack`, `language`, `tab=foryou`, `page`, …

## Decisions
- Filters live in the URL (not sessionStorage) so browser Back restores them

## Remaining work
- Manual QA: set filters → open job → Back → filters still on

## Relevant files
- `frontend/lib/jobs-params.js`
- `frontend/components/home.js`
- `frontend/lib/server/jobs.js`
- `frontend/app/page.js`, `en/page.js`, `ru/page.js`
