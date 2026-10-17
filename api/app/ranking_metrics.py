"""Offline ranking metrics for the matches list (no labels are shipped here).

Graded relevance labels (0 = not relevant … 3 = perfect) come from humans; see
docs/eval-matching.md for the fixture format.

- nDCG@k: gain 2^rel − 1, discount log2(rank + 1) (Järvelin & Kekäläinen,
  "Cumulated gain-based evaluation of IR techniques", ACM TOIS 2002).
- P@k, Recall@k, MRR: a job counts as relevant when rel >= ``relevant_min``.
Unlabeled jobs in a ranking count as rel 0.
"""

from __future__ import annotations

import math
from typing import Iterable, Mapping, Sequence

DEFAULT_RELEVANT_MIN = 2


def _rel(labels: Mapping[str, int], job_id: object) -> int:
    try:
        return max(0, int(labels.get(str(job_id), 0)))
    except (TypeError, ValueError):
        return 0


def dcg_at_k(gains: Sequence[int], k: int) -> float:
    return sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(gains[:k]))


def ndcg_at_k(ranking: Sequence[object], labels: Mapping[str, int], k: int = 10) -> float | None:
    """None when the query has no positive label (nDCG undefined)."""
    ideal = sorted((max(0, int(v)) for v in labels.values()), reverse=True)
    idcg = dcg_at_k(ideal, k)
    if idcg <= 0:
        return None
    return dcg_at_k([_rel(labels, j) for j in ranking], k) / idcg


def precision_at_k(
    ranking: Sequence[object], labels: Mapping[str, int], k: int = 5, relevant_min: int = DEFAULT_RELEVANT_MIN
) -> float:
    if k <= 0:
        return 0.0
    hits = sum(1 for j in ranking[:k] if _rel(labels, j) >= relevant_min)
    return hits / k


def recall_at_k(
    ranking: Sequence[object], labels: Mapping[str, int], k: int = 20, relevant_min: int = DEFAULT_RELEVANT_MIN
) -> float | None:
    """None when the query has no relevant label."""
    relevant = {jid for jid, v in labels.items() if int(v) >= relevant_min}
    if not relevant:
        return None
    hits = sum(1 for j in ranking[:k] if str(j) in relevant)
    return hits / len(relevant)


def reciprocal_rank(
    ranking: Sequence[object], labels: Mapping[str, int], relevant_min: int = DEFAULT_RELEVANT_MIN
) -> float:
    for i, j in enumerate(ranking):
        if _rel(labels, j) >= relevant_min:
            return 1.0 / (i + 1)
    return 0.0


def evaluate_query(
    ranking: Sequence[object], labels: Mapping[str, int], relevant_min: int = DEFAULT_RELEVANT_MIN
) -> dict[str, float | None]:
    return {
        "ndcg@10": ndcg_at_k(ranking, labels, 10),
        "p@5": precision_at_k(ranking, labels, 5, relevant_min),
        "recall@20": recall_at_k(ranking, labels, 20, relevant_min),
        "mrr": reciprocal_rank(ranking, labels, relevant_min),
    }


def aggregate(per_query: Iterable[Mapping[str, float | None]]) -> dict[str, float | int | None]:
    """Mean of each metric over queries where it is defined (+ counts)."""
    rows = list(per_query)
    out: dict[str, float | int | None] = {"queries": len(rows)}
    for name in ("ndcg@10", "p@5", "recall@20", "mrr"):
        vals = [float(r[name]) for r in rows if r.get(name) is not None]
        out[name] = round(sum(vals) / len(vals), 4) if vals else None
        out[f"{name}_n"] = len(vals)
    return out
