# Current task

## Completed
- HTML notification email templates (all kinds)
- Plaintext without raw URLs; production `app_base_url` (no localhost when DEBUG=False)
- One-shot sample send to `aladdin19.11.21@gmail.com` (5 emails, once-flag in `.tmp/`)

## Current state
- Samples sent with subject prefix `[test]`; APP_URL was production web
- Script: `api/scripts/send_notification_email_samples.py`
- Once-flag: `.tmp/notification-email-samples.sent` (blocks re-run with same flag)

## Decisions
- SMTP taken from Academy `.env` for the one-shot only (not written into Job `.env`)

## Remaining work
- Commit email template + URL fixes when asked
- Ensure live API has `APP_URL` / `WEB_PUBLIC_DOMAIN` = public web origin

## Relevant files
- `api/app/email_templates.py`
- `api/app/email_prefs.py`
- `api/app/digests.py` / `api/app/engagement.py`
- `api/scripts/send_notification_email_samples.py`
