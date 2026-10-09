# Current task

## Completed
- Role coach `role-coach-v5`: Az orthography (tələblərə etc.) in system + az user prompt
- Sibling-lang warm: after current locale coach is ready, prefetch other `az`/`en`/`ru` so language switch does not wait
- Prompt bump invalidates bad v4 Az cache (e.g. "talablara")

## Current state
- Cache hit → instant coach + sibling warm scheduled (1h cooldown)
- Cache miss → warm current lang; on success → warm siblings
- Same-day refresh still hits `ai_cache` per locale

## Remaining
- Deploy api (+ frontend if needed)
- Smoke: coach in az loads → switch en/ru without "Preparing…"

## Relevant files
- `api/app/role_coach.py`, `api/app/ai_warm.py`, `api/app/skill_gap.py`
- `api/tests/test_role_coach.py`, `api/tests/test_ai_warm.py`
