# Current task

## Completed
- Reco Design A polish + coach null UI
- Coach soft-fail diagnostics: `coach_error` + warning logs + UI hint

## Current state
- skill-gap returns `coach_error` (e.g. `ai_no_key`, `role_coach_disabled`)
- API logs `role_coach soft-fail role=… reason=…`
- Recommendations empty coach shows mapped message + raw code

## Decisions
- Soft-fail stays non-blocking; expose reason instead of silent null

## Remaining
- After deploy: open `/me/recommendations`, read `coach_error` / Railway warning

## Relevant files
- `api/app/role_coach.py`
- `api/app/skill_gap.py`
- `api/tests/test_role_coach.py`
- `frontend/components/recommendations.js`
- `frontend/lib/copy.js`
