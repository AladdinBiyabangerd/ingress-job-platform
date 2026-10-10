# Current task

## Completed
- `/company` expanded: address, website, industry, size (+ API/DB)
- Account menu “Şirkət məlumatları” for employer/staff
- Profile no longer edits company inline → link card to `/company`
- Form uses full page width with sectioned layout

## Current state
- Required: name, city, about → complete / post gate
- Optional: address, website, industry, size
- First save → `/post`; later saves stay on `/company`

## Decisions
- Company owned on `/company` page, not Profile form

## Remaining work
- Restart API if long-lived process so column migration runs
- Live check while logged in

## Relevant files
- `api/app/profiles.py`, `api/app/account.py`
- `frontend/components/company-form.js`, `account-bar.js`, `profile-form.js`
- `frontend/lib/copy.js`, `frontend/app/globals.css`
