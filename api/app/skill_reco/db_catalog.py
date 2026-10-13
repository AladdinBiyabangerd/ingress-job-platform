"""Build a ``SkillCatalog`` from ``skill_dictionary`` (+ trend popularity).

Embeddings are synthetic (category one-hot + hashed name features) so the
hybrid recommender works without pgvector skill rows. Swap for real model
vectors later; keep the same ``Skill.embedding`` shape.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from app.skill_reco.catalog import Skill, SkillCatalog, _skill
from app.skill_reco.vectors import normalize

log = logging.getLogger("ingress-job.api.skill_reco.db_catalog")

# Align with profile-review category_hint values (+ a few dictionary extras).
_CATEGORY_AXES: tuple[str, ...] = (
    "frontend",
    "backend",
    "devops",
    "mobile",
    "data",
    "database",
    "language",
    "ai",
    "design",
    "cloud",
    "qa",
    "security",
    "concept",
    "methodology",
    "web3",
    "embedded",
    "gamedev",
    "other",
)

# Dictionary uses ``ml``; related-skills compat uses ``ai``.
_CATEGORY_ALIASES: dict[str, str] = {
    "ml": "ai",
    "machine learning": "ai",
}

_NAME_FEATURE_DIMS = 12
_CATALOG_MEMO: tuple[Any, ...] | None = None


def clear_catalog_memo() -> None:
    """Drop process cache (tests / after dictionary reseed)."""
    global _CATALOG_MEMO
    _CATALOG_MEMO = None


def _norm_category(raw: object) -> str:
    key = str(raw or "").strip().lower()
    return _CATEGORY_ALIASES.get(key, key)


def adjacency_from_compat(
    compat: dict[str, frozenset[str]],
) -> dict[str, frozenset[str]]:
    """Adjacent = compatible peers excluding self (25% bucket)."""
    out: dict[str, frozenset[str]] = {}
    for key, peers in compat.items():
        canon = _norm_category(key)
        cleaned = frozenset(_norm_category(p) for p in peers if _norm_category(p) != canon)
        out[canon] = cleaned
    return out


def _name_features(name: str, dims: int = _NAME_FEATURE_DIMS) -> list[float]:
    """Stable hashed character-bigram bag — clusters Git/GitHub, Spring/*."""
    text = f"^{str(name or '').strip().lower()}$"
    bins = [0.0] * dims
    if len(text) < 2:
        return bins
    for i in range(len(text) - 1):
        gram = text[i : i + 2]
        digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=4).digest()
        idx = int.from_bytes(digest, "big") % dims
        bins[idx] += 1.0
    return normalize(bins)


def _embedding_for(category: str, name: str) -> list[float]:
    cat = _norm_category(category)
    cat_vec = [0.0] * len(_CATEGORY_AXES)
    if cat in _CATEGORY_AXES:
        cat_vec[_CATEGORY_AXES.index(cat)] = 1.0
    # Category dominates; name features pull family/prefix siblings together.
    name_vec = [0.55 * x for x in _name_features(name)]
    return normalize(cat_vec + name_vec)


def _fingerprint(conn) -> tuple[int, int]:
    try:
        row = conn.execute(
            "SELECT COUNT(*), COALESCE(MAX(id), 0) FROM skill_dictionary"
        ).fetchone()
        return int(row[0] or 0), int(row[1] or 0)
    except Exception:
        return 0, 0


def _load_popularity(conn) -> dict[int, float]:
    """Normalize trend ad_count into [0.05, 1.0]."""
    try:
        rows = conn.execute(
            """
            SELECT skill_id, SUM(ad_count) AS ads
            FROM skill_trend_daily
            GROUP BY skill_id
            """
        ).fetchall()
    except Exception:
        return {}
    raw: dict[int, int] = {}
    for row in rows:
        try:
            sid = int(row[0] if not hasattr(row, "keys") else row["skill_id"])
            ads = int(row[1] if not hasattr(row, "keys") else row["ads"] or 0)
        except (TypeError, ValueError, KeyError, IndexError):
            continue
        if sid > 0 and ads > 0:
            raw[sid] = ads
    if not raw:
        return {}
    peak = max(raw.values()) or 1
    return {
        sid: max(0.05, min(1.0, ads / peak))
        for sid, ads in raw.items()
    }


def build_catalog_from_conn(
    conn,
    *,
    compat: dict[str, frozenset[str]] | None = None,
) -> SkillCatalog:
    """Load dictionary rows into a recommender catalog (uncached)."""
    from app.skill_related import _CATEGORY_COMPAT

    adjacency = adjacency_from_compat(compat or _CATEGORY_COMPAT)
    popularity = _load_popularity(conn)
    try:
        rows = conn.execute(
            """
            SELECT id, canonical_name, COALESCE(category_hint, '') AS category_hint
            FROM skill_dictionary
            ORDER BY id
            """
        ).fetchall()
    except Exception as exc:
        log.warning("skill_dictionary load failed: %s", exc)
        return SkillCatalog(skills=[], adjacency=adjacency)

    skills: list[Skill] = []
    for row in rows:
        try:
            if hasattr(row, "keys"):
                skill_id = int(row["id"] or 0)
                name = str(row["canonical_name"] or "").strip()
                category = _norm_category(row["category_hint"])
            else:
                skill_id = int(row[0] or 0)
                name = str(row[1] or "").strip()
                category = _norm_category(row[2])
        except (TypeError, ValueError, KeyError, IndexError):
            continue
        if skill_id <= 0 or not name:
            continue
        pop = popularity.get(skill_id, 0.35)
        emb = _embedding_for(category, name)
        skills.append(
            _skill(
                skill_id,
                name,
                category or "other",
                (),
                pop,
                emb,
            )
        )
    return SkillCatalog(skills=skills, adjacency=adjacency)


def catalog_from_conn(conn) -> SkillCatalog:
    """Process-cached catalog keyed by dictionary fingerprint."""
    global _CATALOG_MEMO
    fp = _fingerprint(conn)
    key = id(getattr(conn, "execute", None))
    # Prefer DB path when available so shared SQLite files share one cache.
    db_key = None
    try:
        row = conn.execute("PRAGMA database_list").fetchone()
        if row is not None:
            db_key = str(row[2] if not hasattr(row, "keys") else row["file"] or "")
    except Exception:
        db_key = None
    cache_key = db_key or key
    memo = _CATALOG_MEMO
    if memo is not None and memo[0] == cache_key and memo[1] == fp:
        return memo[2]
    catalog = build_catalog_from_conn(conn)
    _CATALOG_MEMO = (cache_key, fp, catalog)
    return catalog
