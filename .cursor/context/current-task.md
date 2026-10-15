# Current task

## Completed
- Trends **list** Pulse implementasiya
- Trends **detail** Pulse implementasiya (`trend-detail.js` + copy + CSS)
- Detail CTA map: jobs, login, companions, academy

## Current state
Pulse list + detail lokalda işləyir (`localhost:3010/trends`, `/trends/1`).
Uncommitted: prior admin/worker + trends Pulse (list+detail).

## Decisions
- List + detail = Pulse vizual ailə
- Companion kartları → `/trends/{skill_id}`
- Jobs CTA / KPI → `/trends/{id}/jobs`
- Compare/login → OIDC `job_candidate` + returnTo detail

## Remaining work
- Visual QA (mobile) + deploy frontend Railway
- Prior admin/worker deploy if needed

## Relevant files
- `frontend/components/trends.js`
- `frontend/components/trend-detail.js`
- `frontend/lib/copy.js`
- `frontend/app/globals.css`
- `.design/trends-detail/CTA-MAP.md`
