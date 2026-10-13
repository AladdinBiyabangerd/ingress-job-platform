"""Lightweight vector math (stdlib only — drop-in for numpy later).

Scaling note
------------
Today embeddings live in process memory as ``list[float]``.
For 10k–100k+ skills, store the same float vectors in Pinecone / ChromaDB /
pgvector and replace ``cosine_similarity`` loops with ANN queries
(``query(vector=session_vec, top_k=k)``), then apply the 60/25/15 mix in
application code on the returned neighbors.
"""

from __future__ import annotations

import math
from typing import Sequence

Vector = Sequence[float]


def normalize(vec: Vector) -> list[float]:
    """L2-normalize; zero vector stays zero."""
    values = [float(x) for x in vec]
    norm = math.sqrt(sum(v * v for v in values))
    if norm <= 1e-12:
        return values
    return [v / norm for v in values]


def cosine_similarity(a: Vector, b: Vector) -> float:
    """Cosine similarity in [-1, 1]. Assumes same dimensionality."""
    if len(a) != len(b):
        raise ValueError(f"dim mismatch: {len(a)} vs {len(b)}")
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=True):
        xf = float(x)
        yf = float(y)
        dot += xf * yf
        na += xf * xf
        nb += yf * yf
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return dot / math.sqrt(na * nb)


def weighted_average(vectors: Sequence[Vector], weights: Sequence[float]) -> list[float]:
    """Weighted mean of vectors (not normalized)."""
    if not vectors:
        raise ValueError("vectors required")
    if len(vectors) != len(weights):
        raise ValueError("weights length must match vectors")
    dim = len(vectors[0])
    total_w = sum(float(w) for w in weights)
    if total_w <= 1e-12:
        raise ValueError("weights sum to zero")
    out = [0.0] * dim
    for vec, weight in zip(vectors, weights, strict=True):
        if len(vec) != dim:
            raise ValueError("ragged vectors")
        w = float(weight) / total_w
        for i, value in enumerate(vec):
            out[i] += w * float(value)
    return out
