# Current task

## Completed
- Skill-first roadmap (Academy funnel fix)

## Current state
- Coach/insights skill-gap uses `DEFAULT_TOP` (15), not `top=5`
- Roadmap hero/week/path lead with missing skill names; Academy CTA only on path card
- Path-only copy is practice-oriented (no “Academy yoluna bax” checklist)

## Decisions
- Academy links stay as secondary (path card + footer), not removed
- Digests `top=3` left unchanged (out of scope)

## Remaining
1. User verify live `/me/insights/roadmap` for Backend Engineer + Java shows SQL/Docker/Kafka etc.
2. Commit when asked

## Relevant files
- `api/app/engagement.py`
- `api/app/learning_roadmap.py`
- `frontend/components/roadmap.js`
- `frontend/lib/copy.js`
- `api/tests/test_learning_roadmap.py`
- `api/tests/test_engagement.py`
