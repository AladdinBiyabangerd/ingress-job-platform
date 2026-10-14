# Current task

## Completed
- Job tidy prompt → `job-tidy-v3`: shorter bullets, drop CTA fluff, plain text only (no emoji/markdown/HTML)
- Output sanitizer strips emoji + light markdown decor from tidy JSON
- Job detail description UI polish: section hierarchy, why tint, left accent on key lists, custom bullets
- Test: `test_strips_emoji_and_markdown`

## Current state
- Ready for local QA on a tidied job detail page
- Prior admin tidy-queue work still pending commit/QA if not committed yet

## Decisions
- Visual polish stays in frontend CSS; AI must not add emoji/icons/colors
- Cache key changes via `PROMPT_VERSION=job-tidy-v3`

## Remaining
1. Local QA: open a published messy ad after tidy / re-tidy and check detail layout
2. Commit when asked
3. (Other) Academy `job-ops-status` usage table parity — new chat

## Relevant files
- `worker/worker/tidy.py`, `worker/tests/test_tidy_format.py`
- `frontend/components/job-detail/job-detail-description.js`
- `frontend/app/globals.css` (`.jd-desc-*`)
- `.cursor/context/architecture.md`
