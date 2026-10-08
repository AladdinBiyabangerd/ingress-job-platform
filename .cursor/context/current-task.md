# Current task

## Completed
- Trends salary: multi-currency (prior)
- **Engagement Phase 1 (schema/prefs/kinds):**
  - `notifications.payload` JSON column + engagement kinds + az/en/ru templates
  - `engagement_log` + `push_subscriptions` DDL; prefs `match_near` / `coach_weekly` / `push_enabled`
  - Frontend LINES/destinations + email settings toggles
- **Engagement Phase 2 (engine + worker):**
  - `run_engagement_jobs` / `process_user_engagement`: `match_new` (≥0.75) + `match_near` (0.45–0.75, ≤3 missing)
  - Fanout: in-app `insert_notification` + email (`high_match` merged into match_new; `match_near` own kind) + `engagement_log` dedup
  - `build_growth_cta`: Academy course → career-path → roadmap stub (`utm_medium=notification`)
  - `POST /api/v1/internal/engagement-jobs`; worker hourly `trigger_engagement_jobs` after email-jobs
  - Digests `run_email_jobs` no longer sends high_match (owned by engagement)
  - Tests: `api/tests/test_engagement.py` phase 2 + `worker/tests/test_engagement_trigger.py`
- **Engagement Phase 3 (AI copy):**
  - `api/app/engagement_copy.py`: `engagement-copy-v1` via `ai_gateway`; soft-fail az/en/ru templates
  - Flag `engagement_copy` / env `ENGAGEMENT_AI_COPY_ENABLED` (api + worker ai_flags + admin UI)
  - Fanout always writes `payload.ai_title` / `ai_body`; `ai_applied` stats; near-miss body must cite a missing skill
  - Tests: `api/tests/test_engagement_copy.py` + fanout AI case in `test_engagement.py`
- **Engagement Phase 4 (nudge/coach/UI):**
  - `profile_nudge` (draft / &lt;3 skills / stale ≥14d; period `YYYY-Www`) + `coach_weekly` (top role + skill-gap; CTA `/me/insights`)
  - Fanout in-app + email; weekly `engagement_log` dedup; included in `process_user_engagement` / stats
  - `GET /api/v1/me/insights` + BFF + `/me/insights` (coach, near-miss, Academy/roadmap)
  - Rich `/notifications` cards (score, have/missing, CTA, roadmap)
  - `/settings/notifications` (+ `/settings/emails` → redirect); copy/nav for insights + notification settings
  - Tests: phase 4 cases in `api/tests/test_engagement.py`
- **Engagement Phase 5 (Web Push):**
  - Env `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_SUBJECT`; dep `pywebpush`
  - `api/app/push.py`: subscribe upsert/delete, `send_web_push`, 404/410 row cleanup
  - API: `GET /me/push-vapid-key`, `POST|DELETE /me/push-subscription` + BFF `/api/auth/me/push-*`
  - Fanout `_maybe_send_push` on match/nudge/coach when `push_enabled` (channel `push` in `engagement_log`)
  - `frontend/public/sw.js` + `lib/web-push.js`; settings enable/disable UX
  - Account delete clears `push_subscriptions` / `engagement_log`
  - Tests: `api/tests/test_push_subscriptions.py`
- **Engagement Phase 6 (docs polish):**
  - `docs/customer-journey.md` § Retention — engagement kinds, channels, Insights, push, limits
  - `.cursor/context/architecture.md` — high_match ownership, lookback, VAPID integrations
  - Plan todo `docs-tests` closed via phases 2–6 tests + this docs pass

## Current state
- Engagement Phases 1–6 complete (shipped locally; docs synced)
- No active engagement sub-task

## Decisions
- Engagement kinds share in-app `notifications` + `payload` JSON
- Dedup via `engagement_log(user_id, kind, period_key, job_id)`
- Near-miss band: 0.45–0.75, ≤3 missing; lookback `ENGAGEMENT_LOOKBACK_HOURS` (default 26)
- match_new email uses prefs/`email_log` kind `high_match` (merged); in-app kind stays `match_new`
- Channels: in-app + email + Web Push (`push_enabled` + subscription + VAPID)
- ≤1 engagement email/user/UTC day; ≤3 engagement in-app/user/UTC day
- AI copy soft-fails to templates; title/body always stored on payload for channel sync
- Nudge eligible without matching consent (profile owners + matching users in job list); coach/match need matching + confirmed
- Insights prefers last `coach_weekly` / `match_near` notifications, falls back to live skill-gap / near select
- Push soft-fails (missing VAPID / pywebpush / send error); 410/404 deletes subscription; push-only events still log

## Remaining
- (none for engagement plan)

## Relevant files
- `docs/customer-journey.md` (§ Retention)
- `.cursor/context/architecture.md`
- `api/app/{engagement,engagement_copy,push,digests,notifications,email_prefs,ai_flags,me_data}.py`
- `api/app/routers/me.py` (`/insights`, `/push-vapid-key`, `/push-subscription`)
- `api/tests/test_engagement.py`, `test_engagement_copy.py`, `test_push_subscriptions.py`
- `worker/worker/{engagement,ai_flags,runner}.py`
- `frontend/public/sw.js`, `frontend/lib/web-push.js`
- `frontend/components/{notifications-page,insights,email-settings,account-bar,shell}.js`
- `frontend/app/{,en/,ru/}me/insights/`, `frontend/app/{,en/,ru/}settings/notifications/`
- Plan: `/Users/mac/.cursor/plans/engagement_notifications_ff695e9e.plan.md`
