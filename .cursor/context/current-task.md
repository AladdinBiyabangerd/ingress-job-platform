# Current task

## Completed
- Candidate → employer upgrade CTAs → `/company`
- Signed-in role upgrade goes straight to Academy authorize (`existing_account=1`), not job-account
- Copy: same account adds employer; denied text no longer says the role was revoked

## Current state
- Production still shows the old gate: candidate body + “Şirkət hesabı aktivləşdirilə bilmədi…”
- That screen is `employer_denied=1`: OAuth finished, token has no `job:employer`
- This person was candidate-only (applied to ads) and now wants to post. Namizəd rolu qalmalıdır; `JOB_EMPLOYER` üstünə əlavə olunur, sonra şirkət forması
- Academy already does that on authorize unless `JobRoleStaffBlock` exists for `JOB_EMPLOYER`

## Decisions
- Already-signed-in role upgrades skip job-account; guests still use it
- Roles still only come from Academy groups / token scopes
- Staff revoke still blocks self-service restore

## Remaining work
- Deploy Job frontend (login redirect + copy)
- Retry: candidate → Şirkət hesabı ilə davam et → company form
- If still denied: Academy staff user → Job Employer toggle on (clears the block)

## Relevant files
- `frontend/app/api/auth/login/route.js`
- `frontend/lib/oidc-authorize.js`
- `frontend/lib/copy.js`
- Academy: `portal/job_access.py`, `portal/oidc/views.py`
