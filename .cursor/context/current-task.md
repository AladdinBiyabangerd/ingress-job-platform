# Current task

## Completed
- Recommendations Option D (Bento) implemented
- Saved Jobs design options A–D (PNG)
- **Saved Jobs Option B (split) implemented**

## Current state
- `/saved` is master–detail: scrollable left list + sticky preview (≥960px)
- Mobile (&lt;960): list ↔ preview swap with “Siyahıya qayıt”
- Load more via existing `refreshSavedJobs(page)` pagination
- Preview uses list fields only (no detail fetch)

## Decisions
- Option B chosen; left pane independent scroll + compact truncate so many items don’t break layout
- No new API; client aggregates not needed (unlike Option D)

## Remaining
- Manual smoke: desktop/mobile, empty, load more, unsave handoff
- (opsional) polish vs `docs/design-samples/saved-b-split-preview.png`

## Relevant files
- `frontend/components/my-saved.js`
- `frontend/components/saved-job-panel.js`
- `frontend/app/globals.css` (`.saved-split` …)
- `frontend/lib/copy.js` (`savedJobsLoadMore`, `savedJobsBackToList`, …)
- `docs/design-samples/saved-b-split-preview.png`
