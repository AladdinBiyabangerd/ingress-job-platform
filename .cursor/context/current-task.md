# Current task

## Completed
- Applications Option E (columns + detail) implemented + smoke
- Live smoke: empty, many, withdraw UI, AZ/EN/RU; guest gates on `/applications`
- Polish: shorter board labels; withdraw note kept on empty; mobile tabs no clip

## Current state
- Board labels: `applicationsColSubmitted/Seen/Rejected` (AZ Göndərilib/Baxılıb/Rədd)
- Empty after last withdraw keeps `appWithdrawn` note above `.h2-empty`
- Guest `/applications` (az/en/ru) shows gate copy correctly
- Authenticated withdraw API path not exercised (no session in browser)

## Decisions
- Option E retained; timeline keeps lowercase `appSubmitted`/`appSeen`/`appRejected`
- Board/tab headers use Title-case col labels matching design sample

## Remaining
- (optional) authenticated live withdraw on `/applications` after login
- (optional) drop `frontend/.applications-e-smoke.html` once signed off

## Relevant files
- `frontend/components/applications-board.js`
- `frontend/components/my-applications.js`
- `frontend/lib/copy.js`
- `frontend/app/globals.css` (`.apps-e*`)
- `frontend/.applications-e-smoke.html`
- `docs/design-samples/_smoke-applications-e*.png`
