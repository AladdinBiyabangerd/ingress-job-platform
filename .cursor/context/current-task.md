# Current task

## Completed
- `/company` no longer redirects completed profiles to `/profile`
- `/company` is create + edit page; first save → `/post`, later saves stay with note

## Current state
- Guest → login; authenticated → form always (complete or not)
- CTA: incomplete “Davam et”, complete “Saxla”

## Decisions
- Company details stay on `/company` as a separate page

## Remaining work
- Optional: remove duplicate company block from Profile if product wants single owner

## Relevant files
- `frontend/components/company-form.js`
- `frontend/app/{,en/,ru/}company/page.js`
- `frontend/lib/server/company.js`
