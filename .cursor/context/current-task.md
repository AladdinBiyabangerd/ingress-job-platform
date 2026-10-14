# Current task

## Completed
- Published unfit AI recheck → `status=rejected` (not hide-only) — `recheck_one` in `cabinet_store.py`
- One-shot sweep: legacy `published` + `hidden=1` AI unfit rows → `rejected` + `hidden=0`
  - Step: `sweep-published-ai-hidden-to-rejected-2026-10-14`
  - API: `api/app/cabinet_store.py` (`sweep_published_ai_hidden_to_rejected`, runs in `_apply_schema`)
  - Worker: `worker/worker/db.py` (same step on Store init)
  - Skips system hides: `title_rule_2026_10_13`, `expired_not_seen`, `non_it_title`
  - Tests: `test_sweep_published_ai_hidden_to_rejected`, `test_crawled_recheck_rejects_published_unsuitable`
  - `business-rules.md` updated

## Current state
Sweep + recheck path done (uncommitted). Ready for next feature or commit.

## Next (separate chat)
Replace `/admin?tab=categories` with **Crawl rejects** tab (`crawl_rejects`): list + AI recheck + threshold publish.
See prior plan notes if needed — schema today is URL-only (`source_url, reason, decided_at, via_ai`).

## Relevant files
- `api/app/cabinet_store.py`
- `worker/worker/db.py`
- `api/tests/test_admin.py`
- `.cursor/context/business-rules.md`

## Continuation prompt (next feature)
`Kateqoriyalar tabını sil, yerinə crawl_rejects tabı: siyahı + AI yoxla + faiz ≤/≥ ilə publish. Plan: .cursor/context/current-task.md`
