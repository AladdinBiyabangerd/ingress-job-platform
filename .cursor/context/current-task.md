# Current task

## Completed
- Browser tab title unread badge: `(N) …` via `document.title` (like Instagram/YouTube)
- Prior (uncommitted): Notifications Design C + growth rail

## Current state
- Logged-in users with unread > 0 get `(2) Ingress Job — …` in the Chrome tab
- Bell + notifications page stay in sync via `ingress:unread-notifications` event
- Title prefix survives Next.js client navigations (MutationObserver on `<title>`)

## Decisions
- Prefix only; no favicon badge
- Cap display at `99+` (matches bell UI)

## Remaining
1. User verify live: tab shows `(2)` when bell shows 2; clears after mark-all-read
2. Commit when user asks (includes prior Design C + this title badge if desired)

## Relevant files
- `frontend/lib/unread-document-title.js`
- `frontend/components/notifications-bell.js`
- `frontend/components/notifications-page.js` (publish on unread change)
