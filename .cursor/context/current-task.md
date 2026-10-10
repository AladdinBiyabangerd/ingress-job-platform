# Current task

## Completed
- Candidate → employer upgrade: CTAs grant `job_employer` via Academy and open `/company`

## Current state
- Upgrade / “Elan paylaşan” / post become-employer links use `returnTo=/company`
- Company form gates candidate-only users with become-employer LoginLink (no 403 form)
- Guest `/company` login path includes `intent=job_employer`
- Mobile nav shows employer upgrade for candidates

## Decisions
- Roles still come from Academy (`registration_intent` + `existing_account` when signed in)
- Session restore on company page stays plain login (no re-grant after staff revoke)
- Incomplete profile still forced to `/company` in auth callback

## Remaining work
- Manual: candidate account → “Elan paylaşan” → Academy grants role → company form

## Relevant files
- `frontend/components/account-bar.js`
- `frontend/components/company-form.js`
- `frontend/components/post-page.js`
- `frontend/components/register-choice.js`
- `frontend/components/shell.js`
- `frontend/lib/server/company.js`
