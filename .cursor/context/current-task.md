# Current task

## Completed (this chat)
- **Job Detail mockup rebuild** — old `.h2-detail` / PageChrome ribbon layout removed.
- Shared components under `frontend/components/job-detail/`.
- Design preview: `/design/job-detail?state=company_signed_in|company_guest|external_signed_in|external_guest`
- Production `/jobs/[id]` (+ en/ru) uses the same view model + components.
- CTAs: Apply / Sign in to apply / Open original listing; Save + Share; guest gate; onsite form reveals on Apply.
- Board bottom nav hidden when `jobId` is set (avoids clash with mobile sticky CTA).
- Screenshots: `.design/job-detail-qa/` (`desktop-signed-in`, `desktop-guest`, `desktop-external`, `mobile-signed-in`, `mobile-guest`).

## Current state
- Visual fidelity is close to the reference collage; global Shell nav still differs from mockup (Jobs / For Employers / Academy vs mockup’s Companies / Learning) — intentional out of scope.
- Live jobs omit missing fields (size / industry / cover / experience / languages); fixtures carry full sample content.

## Decisions
- Apply reveals existing onsite form (not always-visible form).
- Preview fixtures for pixel QA; production maps API → same UI.
- Plain CSS `.jd-*` (no Tailwind).

## Remaining work (other chats)
1. Jobs shell IA — 3-col board + tokens (from prior home plan)
2. Job cards / tabs polish
3. Home front door vs `/jobs`
4. Me page
5. Optional: tighter pixel pass on job detail after board header matches mockup

## Relevant files
- `frontend/components/job-detail.js` + `frontend/components/job-detail/*`
- `frontend/lib/job-detail-view-model.js`, `job-detail-fixtures.js`
- `frontend/app/design/job-detail/page.js`
- `frontend/app/globals.css` (`.jd-*` block)
- `frontend/lib/copy.js` (jd* keys)
- QA: `.design/job-detail-qa/*.png`
