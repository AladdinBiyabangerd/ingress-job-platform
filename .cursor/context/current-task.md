# Current task

## Completed
- Hot pages SSR-hydrate lists so first paint skips the matching BFF: recommendations, skills, applications, notifications, emails, post, profile/review, company (`me`), admin (queue jobs + applications + crawled ads + AI flags).
- Mutation list refresh skips the client BFF: admin queue, crawled, cabinet, applications withdraw, notifications mark-read (FastAPI server actions in `frontend/lib/server/refresh.js`). AI-flag save is a FastAPI PUT server action.
- Writes for those same flows skip the client BFF: approve/reject/edit/close, crawled hide/show/edit/merge, cabinet create/edit/close, application decide/withdraw, mark-read.
- Remaining listed writes now skip the client BFF: skills role skill-gap, email-prefs save, CV profile save/upload/poll/cancel/reset, company save, admin manual-ad create.

## Remaining
- `/api/auth/*` mutation routes still exist; clients above no longer call them. Token refresh on expired access remains the client `/api/auth/me` BFF.
- Unseeded GET fallbacks still use the client BFF: skills roles, email-prefs, recommendations roles/matches.
- Candidate contact save, consents, apply, match feedback, privacy delete, and data export still use the client BFF.
- CV download still uses `GET /api/auth/applications/:id/cv`.

## Decisions
- Guests/non-staff skip FastAPI admin list calls.
- Seed jobs + applications because `Admin.load()` always fetches both on mount.
- Seed crawled + AI flags on the same RSC load so those tabs skip the BFF on open; keep the tab panels mounted after first visit so remount does not show a stale SSR snapshot after a mutation.
- Post-mutation GET and the listed writes use server actions + access cookie, not `/api/auth/*`. Token refresh on expired access remains the client `/api/auth/me` BFF.

## Relevant files
- `frontend/lib/server/refresh.js`
- `frontend/components/me-skills.js`
- `frontend/components/email-settings.js`
- `frontend/components/company-form.js`
- `frontend/components/profile-form.js`
- `frontend/components/profile-review.js`
- `frontend/components/manual-ad.js`
