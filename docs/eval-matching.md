# Offline eval of matches ranking

Script: `api/scripts/eval_matching.py`. Metrics: `api/app/ranking_metrics.py`.
No labels ship with the repo: they must be made by people who read the CV and the job ad.

## Labels file (JSONL, one query per line)

```json
{"user_id": "<cabinet subject>", "role": "", "labels": {"<job_id>": 3, "<job_id>": 0}}
```

- `user_id`: the candidate whose profile is ranked (must have matching consent and a profile).
- `role`: optional role filter (same as `?role=`), empty for the default list.
- `labels`: graded relevance per job id. `3` = would apply right away, `2` = relevant,
  `1` = borderline, `0` = not relevant. Unlabeled jobs count as `0`.
- Label a pool, not just the current top: the union of the top 20 from each variant you compare
  (rule-only, rule+semantic, rule+semantic+LLM), so Recall@20 is meaningful.
- Lines starting with `#` are ignored. Keep label files out of git if they contain real user ids.

## Run file (JSON)

`{"<user_id>|<role>": ["<job_id>", ...]}` ranked best first. `--live --save-run` writes one.

## Metrics

- **nDCG@10**: gain `2^rel − 1`, discount `log2(rank + 1)` (Järvelin & Kekäläinen, ACM TOIS 2002).
  Undefined (skipped) for queries without any positive label.
- **P@5**, **Recall@20**, **MRR**: relevant means `rel >= 2` (`--relevant-min`).
  Recall@20 is skipped for queries without relevant labels.

## Live mode

`--live` calls `matches_payload(allow_ai_provider=False)` against the configured DB: rule score,
plus semantic/LLM signals only when they are already cached. It never calls a model provider and
rolls back instead of committing. Compare variants by toggling `AI_RERANK_ENABLED` /
`AI_LLM_RERANK_ENABLED` between runs.
