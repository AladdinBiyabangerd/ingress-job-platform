# Current task

## Completed
- Phase 1 ATS slug expansion (2026-10-10 probe): Greenhouse +~30 boards; Workable +mercari/huggingface; Recruitee +effectory
- Phase 2 connectors: **Jobgether** (official_api) + **RemoteYeah** (rss); catalog + BUILDERS + tests
- Listing-rule samples for Worldwide keep / US-only + Africa-SA remote reject (existing rules OK, no gap fix needed)
- Probe: Jobgether + RemoteYeah `status=ok`
- Phase 3 ATS slug expansion (2026-10-10 wave2): +34 probed boards (Greenhouse +27, Lever cred, Teamtailor bambuser, Workable +3, Recruitee +2)

## Current state
- Ashby crawl: **NO-GO** — `api.ashbyhq.com/robots.txt` HTTP 401 → PoliteClient `SourceBlocked` (no ROBOTS_EXCEPTION without owner approval)
- The Muse: **skipped** (US-heavy, low remote/relocation ROI per plan default)
- Remotive: **NO-GO** — robots `Disallow: /api/*` (WildcardRobots); needs owner-approved exception like Reed if wanted later
- Landing.jobs: **NO-GO** — robots `Disallow: /api/`
- DevITjobs UK / GermanTechJobs: **NO-GO** — `/api/jobsLight` returns JobCopilot signup HTML, not JSON
- NoFluffJobs / JustJoin / etc.: deny list (robots/Cloudflare) — not implemented
- Second ATS probe: ~1400 candidates → 34 OK (rest 404/empty/wrong ATS); no robots exceptions added

## Decisions
- Safest volume = ATS slug expansion (done this pass)
- Do not add Remotive/Landing/Ashby robots exceptions without explicit owner approval
- Jobgether uses `detail=True` (JSON has no description)
- Only add slugs that answer + robots allow + ≥1 tech role

## Remaining work
- Optional later: owner-approved Remotive/Landing robots exceptions; Ashby if robots fixed
- Deploy worker so catalog seed + new BUILDERS / ATS slugs run in prod

## Relevant files
- `worker/worker/ats_boards.py`
- `worker/worker/connectors/ats.py` (Workable/Recruitee boards)
- `worker/worker/connectors/apis.py` (JobgetherConnector)
- `worker/worker/connectors/rssboards.py` (RemoteYeahConnector)
- `worker/worker/catalog.py`, `worker/worker/runner.py`
- `worker/tests/test_new_sources.py`
- Probe results: `.tmp/ats_slug_probe.json`, `.tmp/ats_slug_probe_wave2.json`

## Plan
- `.cursor/plans/new_crawl_sources_61ad9645.plan.md`
