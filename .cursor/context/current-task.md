# Current task

## Completed
- Job detail: «Posted today» moved from meta row into actions (desktop: right of primary CTA; mobile header: under primary)
- `job_tailored_cv` AI flow: POST `/api/v1/me/jobs/{id}/tailored-cv` + warm + flag `AI_JOB_TAILORED_CV_ENABLED` / `job_tailored_cv`
- FE: BFF, «Elana uyğun CV» button, ATS HTML preview panel + Print/PDF
- API tests: `api/tests/test_job_tailored_cv.py` (9 ok)

## Current state
- Local change; needs deploy + staff flag on (follows gateway when no DB row)
- Contact/name always from profile; AI reorders/rephrases only

## Decisions
- No server PDF — browser print on `#jd-tcv-print-root`
- Same consent/skills gates as apply-draft

## Remaining work
- Manual QA: generate CV on a job, print, AZ/EN/RU
- Enable flag in admin if gateway off

## Relevant files
- `api/app/job_tailored_cv.py`, `api/app/ai_warm.py`, `api/app/ai_flags.py`, `api/app/routers/me.py`
- `frontend/components/job-detail/job-detail-tailored-cv-panel.js`
- `frontend/components/job-detail/job-detail-actions.js`, `job-detail-meta.js`, `job-detail-view.js`
- `frontend/app/api/auth/me/jobs/[jobId]/tailored-cv/route.js`
