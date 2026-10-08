# Current task

## Completed
- Profile Option A: fix broken labels (`display:grid` + field-label)
- Removed fluff: page lede, panel subs, save/applicant hints, consent intro/legal, retention stub
- Visibility pill+select; Export/Sil/Tezliklə short actions

## Current state
- Local fix ready; Railway still on previous deploy until push
- Smoke: `_smoke-profile-a.png` — labels no overlap

## Decisions
- ConsentFields on profile: `showVisibility={false}`, `showMeta={false}`
- Keep consent `short_help` + rights descriptions (API product copy, not draft disclaimers)

## Remaining
- Deploy / hard-refresh production `/profile` to verify

## Relevant files
- `frontend/components/profile-form.js`
- `frontend/components/consent-fields.js`
- `frontend/app/globals.css`
- `frontend/.profile-smoke.html`
