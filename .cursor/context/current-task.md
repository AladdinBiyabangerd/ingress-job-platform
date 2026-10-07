# Current task

## Completed
- Profile review densify (prior commit `6b868d9`)
- Profile review → 3 tabs + softer UI:
  - Tabs: Əsas | Təcrübə | Təhsil və dillər (`reviewTab` state)
  - Basics: contact + links + basics; Experience: skills + work; More: education + languages + roles
  - Softer page bg `#e9edf2` (not warm cream `#f6f5f1`); panels `#f4f6f8`
  - Labels/headings weight 500–600 (was 700); softer focus ring
  - State / CV upload / save logic unchanged

## Current state
- Implemented locally; not committed yet.
- Files: `profile-review.js`, `globals.css`, `copy.js` (az/en/ru tab labels)

## Decisions
- Tab warn dots when low-confidence fields in that tab
- Sticky save/confirm stays under all tabs

## Remaining
1. Visual check `/profile/review`
2. Commit when approved

## Relevant files
- `frontend/components/profile-review.js`
- `frontend/app/globals.css`
- `frontend/lib/copy.js`
