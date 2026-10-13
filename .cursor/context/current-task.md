# Current task

## Completed
- Related skills relevance harden + density pass for ~2k users

## Current state
- More suggestions (limit 12–16): family compounds (Git→GitHub), reverse pairs, softer role weights, same-category popularity fill
- Still blocks cross-stack hub noise (Git ↛ React/CSS/JS)

## Decisions
- Density via category peers + softer thresholds; quality via category compatibility (devops excludes generic language)
- UI shows up to 12 chips

## Remaining work
- Browser QA; commit when asked

## Relevant files
- `api/app/skill_related.py`
- `api/tests/test_skill_related.py`
- `frontend/components/profile-review.js`
