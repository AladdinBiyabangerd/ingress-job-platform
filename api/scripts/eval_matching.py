#!/usr/bin/env python3
"""Offline eval of the matches ranking: nDCG@10, P@5, Recall@20, MRR.

Usage (from api/):
  # Score a saved ranking (no DB access):
  .venv/bin/python scripts/eval_matching.py --labels eval/labels.jsonl --run eval/run.json

  # Rank live with the current code (rule + cached AI only, never calls a provider,
  # rolls back instead of committing), optionally saving the ranking:
  .venv/bin/python scripts/eval_matching.py --labels eval/labels.jsonl --live --save-run eval/run.json

Fixture format: docs/eval-matching.md. Labels must come from people; none ship with the repo.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ranking_metrics import DEFAULT_RELEVANT_MIN, aggregate, evaluate_query  # noqa: E402


def query_key(row: dict) -> str:
    role = str(row.get("role") or "").strip()
    return f"{row['user_id']}|{role}"


def load_labels(path: Path) -> list[dict]:
    out: list[dict] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        row = json.loads(line)
        if not isinstance(row, dict) or not str(row.get("user_id") or "").strip():
            raise ValueError(f"{path}:{n}: user_id required")
        labels = row.get("labels")
        if not isinstance(labels, dict) or not labels:
            raise ValueError(f"{path}:{n}: labels must be a non-empty object job_id -> 0..3")
        clean: dict[str, int] = {}
        for jid, rel in labels.items():
            rel_i = int(rel)
            if rel_i < 0 or rel_i > 3:
                raise ValueError(f"{path}:{n}: label for job {jid} must be 0..3")
            clean[str(int(jid))] = rel_i
        out.append({"user_id": str(row["user_id"]).strip(), "role": row.get("role") or "", "labels": clean})
    return out


def live_rankings(queries: list[dict], *, limit: int) -> dict[str, list[str]]:
    from app.cabinet_store import _LOCK, _connect
    from app.matching import matches_payload

    out: dict[str, list[str]] = {}
    with _LOCK:
        conn = _connect()
        try:
            for q in queries:
                payload = matches_payload(
                    conn,
                    user_id=q["user_id"],
                    limit=limit,
                    lang="en",
                    role=q["role"] or None,
                    allow_ai_provider=False,
                )
                out[query_key(q)] = [str(m["job_id"]) for m in payload.get("matches") or []]
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            conn.close()
    return out


def run_eval(queries: list[dict], run: dict[str, list], *, relevant_min: int) -> dict:
    per_query = []
    for q in queries:
        ranking = [str(j) for j in run.get(query_key(q), [])]
        metrics = evaluate_query(ranking, q["labels"], relevant_min)
        per_query.append({"query": query_key(q), "returned": len(ranking), **metrics})
    return {"summary": aggregate(per_query), "per_query": per_query}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels", required=True, type=Path)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--run", type=Path, help='JSON {"user_id|role": [job_id, ...]} ranked best first')
    src.add_argument("--live", action="store_true", help="rank with the current code against the configured DB")
    ap.add_argument("--save-run", type=Path)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--relevant-min", type=int, default=DEFAULT_RELEVANT_MIN)
    args = ap.parse_args(argv)

    queries = load_labels(args.labels)
    if args.live:
        run = live_rankings(queries, limit=args.limit)
    else:
        run = json.loads(args.run.read_text(encoding="utf-8"))
    if args.save_run:
        args.save_run.write_text(json.dumps(run, indent=2), encoding="utf-8")
    report = run_eval(queries, run, relevant_min=args.relevant_min)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
