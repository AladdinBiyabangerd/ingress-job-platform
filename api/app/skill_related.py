"""Related skill suggestions for profile review.

Primary path: ``app.skill_reco`` session vector + 60/25/15 hybrid mix over
the skill dictionary (synthetic category/name embeddings). Fallback: legacy
family → pair → role → category round-robin with source quotas.

Category compatibility still filters hub skills (Git, SQL) so they do not
pull unrelated stacks (CSS/React from every role that lists Git).
"""

from __future__ import annotations

from typing import Any

DEFAULT_LIMIT = 12
MAX_LIMIT = 24
NAME_MAX = 60
# Conditional co-occurrence floor (lenient enough for sparse local markets).
MIN_PAIR_SHARE = 0.08
MIN_PAIR_CO_COUNT = 2
# Role peers: allow lighter weights; category filter blocks cross-stack noise.
MIN_FOCUS_ROLE_WEIGHT = 0.15
MIN_PEER_ROLE_WEIGHT = 0.15

# Compatible category_hint buckets (empty = unknown, allowed with anything).
_CATEGORY_COMPAT: dict[str, frozenset[str]] = {
    # Note: hub categories (devops) do not absorb generic "language" peers —
    # otherwise Git pulls JavaScript from every role that lists both.
    "frontend": frozenset({"frontend", "design"}),
    "backend": frozenset({"backend", "devops", "data", "database", "cloud"}),
    "devops": frozenset({"devops", "backend", "cloud"}),
    "mobile": frozenset({"mobile", "frontend"}),
    "data": frozenset({"data", "backend", "database", "ai"}),
    "database": frozenset({"database", "backend", "data"}),
    "language": frozenset(
        {"language", "backend", "frontend", "mobile", "devops", "data", "database", "ai"}
    ),
    "ai": frozenset({"ai", "data", "backend"}),
    "design": frozenset({"design", "frontend"}),
    "cloud": frozenset({"cloud", "devops", "backend"}),
    "qa": frozenset({"qa", "backend", "frontend"}),
    "security": frozenset({"security", "backend", "devops"}),
}


def clamp_limit(value: int | None) -> int:
    if value is None:
        return DEFAULT_LIMIT
    try:
        n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, n))


def _norm_exclude(exclude: list[str] | None) -> set[str]:
    out: set[str] = set()
    if not exclude:
        return out
    for item in exclude:
        name = str(item or "").strip().lower()
        if name:
            out.add(name)
    return out


def _parse_exclude_query(raw: str | None) -> list[str]:
    if not raw or not str(raw).strip():
        return []
    parts: list[str] = []
    for chunk in str(raw).split(","):
        name = chunk.strip()
        if name:
            parts.append(name[:NAME_MAX])
    return parts


def _row_get(row, key: str, index: int):
    if row is None:
        return None
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return row[index]


def _norm_category(raw: object) -> str:
    return str(raw or "").strip().lower()


def categories_compatible(focus_cat: str, other_cat: str) -> bool:
    """True when categories can sensibly co-recommend."""
    a = _norm_category(focus_cat)
    b = _norm_category(other_cat)
    if not a or not b:
        return True
    if a == b:
        return True
    allowed = _CATEGORY_COMPAT.get(a)
    if allowed is None:
        return a == b
    return b in allowed


def _resolve(conn, name: str) -> tuple[int | None, str, str]:
    """Return (skill_id, canonical_name, category_hint)."""
    cleaned = str(name or "").strip()[:NAME_MAX]
    if not cleaned:
        return None, "", ""
    from app.role_suggestions import _build_skill_lookup

    lookup = _build_skill_lookup(conn)
    hit = lookup.get(cleaned.lower())
    if not hit:
        return None, cleaned, ""
    skill_id = int(hit[0])
    canonical = str(hit[1])
    category = ""
    try:
        row = conn.execute(
            "SELECT category_hint FROM skill_dictionary WHERE id = ?",
            (skill_id,),
        ).fetchone()
        category = _norm_category(_row_get(row, "category_hint", 0) if row else "")
    except Exception:
        category = ""
    return skill_id, canonical, category


def _skill_categories(conn, skill_ids: list[int]) -> dict[int, str]:
    if not skill_ids:
        return {}
    placeholders = ",".join("?" for _ in skill_ids)
    try:
        rows = conn.execute(
            f"""
            SELECT id, category_hint
            FROM skill_dictionary
            WHERE id IN ({placeholders})
            """,
            skill_ids,
        ).fetchall()
    except Exception:
        return {}
    return {
        int(_row_get(row, "id", 0) or 0): _norm_category(_row_get(row, "category_hint", 1))
        for row in rows
        if int(_row_get(row, "id", 0) or 0) > 0
    }


def _family_skills(conn, *, canonical: str, exclude: set[str], limit: int) -> list[dict]:
    """Dictionary siblings: '{canonical} …' and CamelCase compounds (Git→GitHub)."""
    if not canonical.strip() or limit <= 0:
        return []
    # Avoid Java→JavaScript style false friends for short language stems.
    allow_compound = len(canonical) != 4 or canonical.lower() not in {
        "java",
        "type",
        "node",
        "ruby",
        "rust",
        "perl",
        "bash",
        "dart",
    }
    try:
        rows = conn.execute(
            """
            SELECT id, canonical_name
            FROM skill_dictionary
            WHERE lower(canonical_name) != lower(?)
              AND (
                lower(canonical_name) LIKE lower(?) || ' %'
                OR lower(canonical_name) LIKE lower(?) || '/%'
                OR lower(canonical_name) LIKE lower(?) || '-%'
                OR (
                    ? = 1
                    AND lower(canonical_name) LIKE lower(?) || '%'
                    AND length(canonical_name) > length(?)
                )
              )
            ORDER BY length(canonical_name), canonical_name
            LIMIT ?
            """,
            (
                canonical,
                canonical,
                canonical,
                canonical,
                1 if allow_compound else 0,
                canonical,
                canonical,
                max(limit * 5, 40),
            ),
        ).fetchall()
    except Exception:
        return []
    out: list[dict] = []
    stem = canonical.lower()
    for row in rows:
        skill_id = int(_row_get(row, "id", 0) or 0)
        name = str(_row_get(row, "canonical_name", 1) or "").strip()
        if not name or name.lower() in exclude:
            continue
        lower = name.lower()
        if lower.startswith(stem + " ") or lower.startswith(stem + "/") or lower.startswith(stem + "-"):
            pass
        elif allow_compound and lower.startswith(stem) and len(name) > len(canonical):
            nxt = name[len(canonical) : len(canonical) + 1]
            # GitHub / GitLab / GitOps — next char uppercase (or digit).
            if not (nxt.isupper() or nxt.isdigit()):
                continue
        else:
            continue
        out.append({"skill_id": skill_id, "name": name, "source": "family"})
        if len(out) >= limit:
            break
    return out


def _pair_skills(
    conn,
    *,
    skill_id: int,
    focus_category: str,
    exclude: set[str],
    limit: int,
) -> list[dict]:
    """Top co-occurring skills by conditional share (forward + reverse edges)."""
    if skill_id <= 0 or limit <= 0:
        return []
    from app.trends import (
        DEFAULT_WINDOW_DAYS,
        _as_of_day,
        _pair_co_counts,
        _skill_counts,
        _skill_meta,
        _window_bounds,
        ensure_trend_tables,
    )

    try:
        ensure_trend_tables(conn)
    except Exception:
        return []
    as_of = _as_of_day(conn)
    start, end = _window_bounds(as_of, DEFAULT_WINDOW_DAYS)
    counts = _skill_counts(conn, start=start, end=end, category="", region="")
    base_ads = int(counts.get(skill_id) or 0)
    scores: dict[int, tuple[float, int]] = {}

    if base_ads > 0:
        co = _pair_co_counts(
            conn,
            start=start,
            end=end,
            category="",
            base_skill_ids=[skill_id],
        )
        for (_base, pair_id), count in co.items():
            co_count = int(count or 0)
            if co_count < MIN_PAIR_CO_COUNT:
                continue
            share = co_count / base_ads
            if share < MIN_PAIR_SHARE:
                continue
            pid = int(pair_id)
            prev = scores.get(pid)
            if prev is None or share > prev[0]:
                scores[pid] = (share, co_count)

    # Reverse: ads of other skills that also list this skill.
    try:
        rev_rows = conn.execute(
            """
            SELECT base_skill_id, SUM(co_ad_count) AS co_ad_count
            FROM skill_pair_daily
            WHERE day >= ? AND day <= ? AND pair_skill_id = ?
            GROUP BY base_skill_id
            """,
            (start, end, skill_id),
        ).fetchall()
    except Exception:
        rev_rows = []
    for row in rev_rows:
        other_id = int(_row_get(row, "base_skill_id", 0) or 0)
        co_count = int(_row_get(row, "co_ad_count", 1) or 0)
        if other_id <= 0 or other_id == skill_id or co_count < MIN_PAIR_CO_COUNT:
            continue
        other_ads = int(counts.get(other_id) or 0)
        if other_ads <= 0:
            continue
        share = co_count / other_ads
        if share < MIN_PAIR_SHARE:
            continue
        prev = scores.get(other_id)
        # Slightly discount reverse edges vs forward.
        ranked_share = share * 0.85
        if prev is None or ranked_share > prev[0]:
            scores[other_id] = (ranked_share, co_count)

    if not scores:
        return []
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1][0], -kv[1][1], kv[0]))
    pair_ids = [pid for pid, _ in ranked[: limit * 5]]
    meta = _skill_meta(conn, pair_ids)
    cats = _skill_categories(conn, pair_ids)
    out: list[dict] = []
    for pair_id, score in ranked:
        info = meta.get(pair_id) or {}
        name = str(info.get("name") or "").strip()
        if not name or name.lower() in exclude:
            continue
        if not categories_compatible(focus_category, cats.get(pair_id, "")):
            continue
        share = float(score[0])
        out.append(
            {
                "skill_id": pair_id,
                "name": name,
                "source": "pair",
                "strength": max(0.0, min(1.0, share)),
            }
        )
        if len(out) >= limit:
            break
    return out


def _category_peers(
    conn,
    *,
    focus_category: str,
    focus_skill_id: int | None,
    exclude: set[str],
    limit: int,
) -> list[dict]:
    """Popular same-category skills — dense fill without crossing stacks."""
    cat = _norm_category(focus_category)
    if not cat or limit <= 0:
        return []
    try:
        rows = conn.execute(
            """
            SELECT
                s.id AS skill_id,
                s.canonical_name AS name,
                COALESCE(SUM(t.ad_count), 0) AS ads
            FROM skill_dictionary s
            LEFT JOIN skill_trend_daily t ON t.skill_id = s.id
            WHERE lower(s.category_hint) = ?
              AND (? IS NULL OR s.id != ?)
            GROUP BY s.id, s.canonical_name
            ORDER BY ads DESC, s.canonical_name
            LIMIT ?
            """,
            (cat, focus_skill_id, focus_skill_id, max(limit * 4, 48)),
        ).fetchall()
    except Exception:
        try:
            rows = conn.execute(
                """
                SELECT id AS skill_id, canonical_name AS name, 0 AS ads
                FROM skill_dictionary
                WHERE lower(category_hint) = ?
                  AND (? IS NULL OR id != ?)
                ORDER BY canonical_name
                LIMIT ?
                """,
                (cat, focus_skill_id, focus_skill_id, max(limit * 4, 48)),
            ).fetchall()
        except Exception:
            return []
    out: list[dict] = []
    for row in rows:
        sid = int(_row_get(row, "skill_id", 0) or 0)
        name = str(_row_get(row, "name", 1) or "").strip()
        if not name or name.lower() in exclude:
            continue
        out.append({"skill_id": sid, "name": name, "source": "category"})
        if len(out) >= limit:
            break
    return out


def _role_skills(
    conn,
    *,
    skill_id: int,
    focus_category: str,
    exclude: set[str],
    limit: int,
) -> list[dict]:
    """High-weight peers from roles where the focus skill is a signature skill."""
    if skill_id <= 0 or limit <= 0:
        return []
    try:
        rows = conn.execute(
            """
            SELECT
                s.id AS skill_id,
                s.canonical_name AS name,
                COALESCE(s.category_hint, '') AS category_hint,
                SUM(peer.weight) AS score,
                MAX(focus.weight) AS focus_weight,
                MAX(peer.weight) AS peer_weight
            FROM role_skill_weight focus
            JOIN role_skill_weight peer
              ON peer.role_id = focus.role_id
             AND peer.skill_id != focus.skill_id
            JOIN skill_dictionary s ON s.id = peer.skill_id
            WHERE focus.skill_id = ?
              AND focus.weight >= ?
              AND peer.weight >= ?
            GROUP BY s.id, s.canonical_name, s.category_hint
            ORDER BY score DESC, s.canonical_name
            LIMIT ?
            """,
            (
                skill_id,
                MIN_FOCUS_ROLE_WEIGHT,
                MIN_PEER_ROLE_WEIGHT,
                limit * 4,
            ),
        ).fetchall()
    except Exception:
        return []
    out: list[dict] = []
    for row in rows:
        sid = int(_row_get(row, "skill_id", 0) or 0)
        name = str(_row_get(row, "name", 1) or "").strip()
        cat = _norm_category(_row_get(row, "category_hint", 2))
        if not name or name.lower() in exclude:
            continue
        if not categories_compatible(focus_category, cat):
            continue
        peer_w = float(_row_get(row, "peer_weight", 5) or 0.0)
        out.append(
            {
                "skill_id": sid,
                "name": name,
                "source": "role",
                "strength": max(0.0, min(1.0, peer_w)),
            }
        )
        if len(out) >= limit:
            break
    return out


def _source_quotas(limit: int) -> dict[str, int]:
    """Cap each source so the list is a mix (family alone must not fill all 12)."""
    n = max(1, int(limit))
    family = max(2, min(4, (n + 2) // 3))
    pair = max(2, min(4, (n + 2) // 3))
    role = max(2, min(3, max(2, n // 4)))
    category = max(2, min(4, n - family - pair - role + 2))
    return {
        "family": family,
        "pair": pair,
        "role": role,
        "category": category,
    }


def _normalize_item(row: dict) -> dict | None:
    name = str(row.get("name") or "").strip()
    if not name:
        return None
    return {
        "skill_id": row.get("skill_id"),
        "name": name,
        "source": str(row.get("source") or ""),
    }


def _session_from_profile(
    catalog,
    *,
    focus,
    exclude_names: list[str],
):
    """Build a decaying session: older profile skills, then the focus skill."""
    from app.skill_reco import UserSession

    session = UserSession(decay=0.7, max_history=8)
    # Leave one slot for focus so it always anchors the newest click.
    history: list = []
    for raw in exclude_names:
        skill = catalog.get_by_name(raw)
        if skill is None or skill.id == focus.id:
            continue
        history.append(skill)
    for skill in history[-(session.max_history - 1) :]:
        session.click(skill)
    session.click(focus)
    return session


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _adjacent_category_peers(
    conn,
    *,
    focus_category: str,
    focus_skill_id: int | None,
    exclude: set[str],
    limit: int,
) -> list[dict]:
    """Top skills from categories adjacent to the focus (for mini-catalog)."""
    cat = _norm_category(focus_category)
    if not cat or limit <= 0:
        return []
    allowed = _CATEGORY_COMPAT.get(cat) or frozenset()
    peers = sorted(c for c in allowed if c and c != cat)
    if not peers:
        return []
    # Dictionary may store aliases (ml) while compat uses canonical (ai).
    query_cats = list(peers)
    if "ai" in peers and "ml" not in query_cats:
        query_cats.append("ml")
    placeholders = ",".join("?" for _ in query_cats)

    try:
        rows = conn.execute(
            f"""
            SELECT
                s.id AS skill_id,
                s.canonical_name AS name,
                COALESCE(SUM(t.ad_count), 0) AS ads
            FROM skill_dictionary s
            LEFT JOIN skill_trend_daily t ON t.skill_id = s.id
            WHERE lower(s.category_hint) IN ({placeholders})
              AND (? IS NULL OR s.id != ?)
            GROUP BY s.id, s.canonical_name
            ORDER BY ads DESC, s.canonical_name
            LIMIT ?
            """,
            (*query_cats, focus_skill_id, focus_skill_id, max(limit * 3, 36)),
        ).fetchall()
    except Exception:
        try:
            rows = conn.execute(
                f"""
                SELECT id AS skill_id, canonical_name AS name, 0 AS ads
                FROM skill_dictionary
                WHERE lower(category_hint) IN ({placeholders})
                  AND (? IS NULL OR id != ?)
                ORDER BY canonical_name
                LIMIT ?
                """,
                (*query_cats, focus_skill_id, focus_skill_id, max(limit * 3, 36)),
            ).fetchall()
        except Exception:
            return []
    out: list[dict] = []
    for row in rows:
        sid = int(_row_get(row, "skill_id", 0) or 0)
        name = str(_row_get(row, "name", 1) or "").strip()
        if not name or name.lower() in exclude:
            continue
        out.append({"skill_id": sid, "name": name, "source": "adjacent"})
        if len(out) >= limit:
            break
    return out


def _apply_popularity_boosts(catalog, boosts: dict[int, float]):
    """Return a catalog copy with max(popularity, boost) applied."""
    from app.skill_reco.catalog import Skill, SkillCatalog

    if not boosts:
        return catalog
    skills = []
    for skill in catalog.all():
        pop = max(float(skill.popularity_score), boosts.get(skill.id, 0.0))
        if pop == skill.popularity_score:
            skills.append(skill)
            continue
        skills.append(
            Skill(
                id=skill.id,
                name=skill.name,
                category=skill.category,
                tags=skill.tags,
                popularity_score=pop,
                embedding=skill.embedding,
            )
        )
    return SkillCatalog(skills=skills, adjacency=catalog.adjacency)


def _mini_catalog_for_reco(
    conn,
    base,
    *,
    skill_id: int | None,
    canonical: str,
    focus_category: str,
):
    """Prune to ~100 market-relevant candidates; apply graded family/pair/role boosts."""
    from app.skill_reco.catalog import SkillCatalog

    focus = None
    if skill_id:
        focus = base.get(int(skill_id))
    if focus is None:
        focus = base.get_by_name(canonical)
    if focus is None:
        return None, None

    pool_n = 32
    empty: set[str] = set()
    family_rows = _family_skills(
        conn, canonical=canonical, exclude=empty, limit=pool_n
    )
    pair_rows = (
        _pair_skills(
            conn,
            skill_id=int(skill_id),
            focus_category=focus_category,
            exclude=empty,
            limit=pool_n,
        )
        if skill_id
        else []
    )
    role_rows = (
        _role_skills(
            conn,
            skill_id=int(skill_id),
            focus_category=focus_category,
            exclude=empty,
            limit=pool_n,
        )
        if skill_id
        else []
    )
    category_rows = (
        _category_peers(
            conn,
            focus_category=focus_category,
            focus_skill_id=skill_id,
            exclude=empty,
            limit=pool_n,
        )
        if focus_category
        else []
    )
    adjacent_rows = (
        _adjacent_category_peers(
            conn,
            focus_category=focus_category,
            focus_skill_id=skill_id,
            exclude=empty,
            limit=24,
        )
        if focus_category
        else []
    )

    boosts: dict[int, float] = {}
    for row in family_rows:
        sid = int(row.get("skill_id") or 0)
        if sid > 0:
            boosts[sid] = max(boosts.get(sid, 0.0), 0.85)
    for row in pair_rows:
        sid = int(row.get("skill_id") or 0)
        if sid <= 0:
            continue
        strength = _clamp01(float(row.get("strength") or 0.0))
        boosts[sid] = max(boosts.get(sid, 0.0), 0.45 + 0.50 * strength)
    for row in role_rows:
        sid = int(row.get("skill_id") or 0)
        if sid <= 0:
            continue
        strength = _clamp01(float(row.get("strength") or 0.0))
        boosts[sid] = max(boosts.get(sid, 0.0), 0.35 + 0.40 * strength)

    candidate_ids: set[int] = {focus.id}
    for rows in (
        family_rows,
        pair_rows,
        role_rows,
        category_rows,
        adjacent_rows,
    ):
        for row in rows:
            sid = int(row.get("skill_id") or 0)
            if sid > 0:
                candidate_ids.add(sid)

    # Keep profile-session skills available for the decaying session vector.
    # (They are excluded from output via clicked_ids / blocked names.)
    skills = []
    for sid in candidate_ids:
        skill = base.get(sid)
        if skill is not None:
            skills.append(skill)
    if len(skills) < 2:
        return None, focus

    mini = SkillCatalog(skills=skills, adjacency=base.adjacency)
    return _apply_popularity_boosts(mini, boosts), focus


def _related_skills_reco_for_conn(
    conn,
    *,
    skill_id: int | None,
    canonical: str,
    focus_category: str,
    exclude: list[str] | None,
    chosen: int,
) -> dict[str, Any] | None:
    """Session-vector hybrid on a pruned candidate set. None → mix fallback."""
    from app.skill_reco import HybridRecommender
    from app.skill_reco.db_catalog import catalog_from_conn

    base = catalog_from_conn(conn)
    if not base.skills:
        return None
    catalog, focus = _mini_catalog_for_reco(
        conn,
        base,
        skill_id=skill_id,
        canonical=canonical,
        focus_category=focus_category,
    )
    if catalog is None or focus is None:
        return None

    # Session history may reference profile skills outside the mini set — pull
    # those embeddings from the full catalog so decay still works.
    exclude_names = [str(x).strip() for x in (exclude or []) if str(x).strip()]
    session_skills = list(catalog.all())
    for raw in exclude_names:
        skill = catalog.get_by_name(raw) or base.get_by_name(raw)
        if skill is None:
            continue
        if catalog.get(skill.id) is None:
            session_skills.append(skill)
    if len(session_skills) != len(catalog.skills):
        from app.skill_reco.catalog import SkillCatalog

        catalog = SkillCatalog(skills=session_skills, adjacency=catalog.adjacency)
        # Re-resolve focus after rebuild.
        focus = catalog.get(focus.id) or focus

    blocked = _norm_exclude(exclude)
    blocked.add(canonical.lower())
    session = _session_from_profile(
        catalog, focus=focus, exclude_names=exclude_names
    )
    engine = HybridRecommender(catalog)
    raw = engine.get_recommendations(session, top_n=max(chosen * 3, chosen + 8))
    items: list[dict] = []
    seen: set[str] = set(blocked)
    for row in raw:
        name = str(row.name or "").strip()
        key = name.lower()
        if not name or key in seen:
            continue
        if focus_category and not categories_compatible(
            focus_category, row.category
        ):
            continue
        seen.add(key)
        items.append(
            {
                "skill_id": row.skill.id,
                "name": name,
                "source": str(row.bucket),
            }
        )
        if len(items) >= chosen:
            break

    if not items:
        return None
    return {
        "name": canonical,
        "skill_id": skill_id,
        "items": items[:chosen],
    }


def _related_skills_mix_for_conn(
    conn,
    *,
    skill_id: int | None,
    canonical: str,
    focus_category: str,
    blocked: set[str],
    chosen: int,
) -> dict[str, Any]:
    """Legacy family/pair/role/category round-robin mix (fallback)."""
    pool_n = max(chosen * 2, 16)
    empty: set[str] = set()
    pools: dict[str, list[dict]] = {
        "family": _family_skills(
            conn, canonical=canonical, exclude=empty, limit=pool_n
        ),
        "pair": (
            _pair_skills(
                conn,
                skill_id=skill_id,
                focus_category=focus_category,
                exclude=empty,
                limit=pool_n,
            )
            if skill_id
            else []
        ),
        "role": (
            _role_skills(
                conn,
                skill_id=skill_id,
                focus_category=focus_category,
                exclude=empty,
                limit=pool_n,
            )
            if skill_id
            else []
        ),
        "category": (
            _category_peers(
                conn,
                focus_category=focus_category,
                focus_skill_id=skill_id,
                exclude=empty,
                limit=pool_n,
            )
            if focus_category
            else []
        ),
    }

    quotas = _source_quotas(chosen)
    cursors = {key: 0 for key in pools}
    taken = {key: 0 for key in pools}
    seen: set[str] = set(blocked)
    items: list[dict] = []
    order = ("family", "pair", "role", "category")

    def _next_from(src: str) -> dict | None:
        rows = pools.get(src) or []
        i = cursors[src]
        while i < len(rows):
            cand = _normalize_item(rows[i])
            i += 1
            cursors[src] = i
            if not cand:
                continue
            key = cand["name"].lower()
            if key in seen:
                continue
            return cand
        cursors[src] = i
        return None

    progress = True
    while len(items) < chosen and progress:
        progress = False
        for src in order:
            if len(items) >= chosen:
                break
            if taken[src] >= quotas.get(src, chosen):
                continue
            cand = _next_from(src)
            if not cand:
                continue
            seen.add(cand["name"].lower())
            items.append(cand)
            taken[src] += 1
            progress = True

    if len(items) < chosen:
        for src in ("pair", "role", "category", "family"):
            while len(items) < chosen:
                cand = _next_from(src)
                if not cand:
                    break
                seen.add(cand["name"].lower())
                items.append(cand)

    return {
        "name": canonical,
        "skill_id": skill_id,
        "items": items[:chosen],
    }


def related_skills_for_conn(
    conn,
    *,
    name: str,
    exclude: list[str] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    chosen = clamp_limit(limit)
    skill_id, canonical, focus_category = _resolve(conn, name)
    blocked = _norm_exclude(exclude)
    if canonical:
        blocked.add(canonical.lower())

    if not canonical:
        return {"name": "", "skill_id": None, "items": []}

    reco = _related_skills_reco_for_conn(
        conn,
        skill_id=skill_id,
        canonical=canonical,
        focus_category=focus_category,
        exclude=exclude,
        chosen=chosen,
    )
    if reco is not None:
        return reco

    return _related_skills_mix_for_conn(
        conn,
        skill_id=skill_id,
        canonical=canonical,
        focus_category=focus_category,
        blocked=blocked,
        chosen=chosen,
    )


def related_skills(
    *,
    name: str,
    exclude: list[str] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    from app.cabinet_store import _LOCK, _connect

    with _LOCK:
        conn = _connect()
        return related_skills_for_conn(
            conn, name=name, exclude=exclude, limit=limit
        )


def related_skills_from_query(
    *,
    name: str | None,
    exclude: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    return related_skills(
        name=str(name or "").strip()[:NAME_MAX],
        exclude=_parse_exclude_query(exclude),
        limit=limit,
    )
