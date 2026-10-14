# Current task

## Completed
- For You: CV vs öz filterləri (sidebar radio)
- Filter persistensiya **əsas board `/` + For You**: localStorage + URL
- Logo / Elanlar / bottom+side nav → `PersistedBrowseLink` (saved query saxlayır)

## Current state
- Key: `ingress.job.board.v1`; Clear silənə qədər qalır
- Hydrate: `useLayoutEffect`; URL sync `persistReady` sonra

## Decisions
- Browse linkləri LS filterlərini `?` ilə aparır ki, SSR də eyni qalsın

## Remaining work
- Deploy + production QA
- Commit when asked

## Relevant files
- `frontend/lib/board-persist.js`
- `frontend/components/persisted-browse-link.js`
- `frontend/components/home.js`
- `frontend/components/shell.js`
- `frontend/components/board-side-nav.js`
- `frontend/components/command-palette.js`
- `frontend/components/job-detail/job-detail-header.js`
