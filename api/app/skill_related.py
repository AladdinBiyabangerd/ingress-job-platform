"""Related skill suggestions for profile review (family + market pairs + role co-skills)."""

from __future__ import annotations

from typing import Any

DEFAULT_LIMIT = 8
MAX_LIMIT = 16
NAME_MAX = 60


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


def _resolve(conn, name: str) -> tuple[int | None, str]:
    """Return (skill_id, canonical_name). Unresolved → (None, trimmed input)."""
    cleaned = str(name or "").strip()[:NAME_MAX]
    if not cleaned:
        return None, ""
    from app.role_suggestions import _build_skill_lookup

    lookup = _build_skill_lookup(conn)
    hit = lookup.get(cleaned.lower())
    if hit:
        return int(hit[0]), str(hit[1])
    return None, cleaned


def _family_skills(conn, *, canonical: str, exclude: set[str], limit: int) -> list[dict]:
    """Dictionary siblings: names that start with '{canonical} '."""
    prefix = f"{canonical} "
    if not prefix.strip() or limit <= 0:
        return []
    try:
        rows = conn.execute(
            """
            SELECT id, canonical_name
            FROM skill_dictionary
            WHERE lower(canonical_name) LIKE lower(?)
              AND lower(canonical_name) != lower(?)
            ORDER BY length(canonical_name), canonical_name
            LIMIT ?
            """,
            (f"{prefix}%", canonical, limit * 3),
        ).fetchall()
    except Exception:
        return []
    out: list[dict] = []
    prefix_l = prefix.lower()
    for row in rows:
        skill_id = int(_row_get(row, "id", 0) or 0)
        name = str(_row_get(row, "canonical_name", 1) or "").strip()
        if not name or name.lower() in exclude:
            continue
        if not name.lower().startswith(prefix_l):
            continue
        out.append({"skill_id": skill_id, "name": name, "source": "family"})
        if len(out) >= limit:
            break
    return out


def _pair_skills(
    conn,
    *,
    skill_id: int,
    exclude: set[str],
    limit: int,
) -> list[dict]:
    """Top co-occurring skills from skill_pair_daily (lenient for suggestions)."""
    if skill_id <= 0 or limit <= 0:
        return []
    from app.trends import (
        DEFAULT_WINDOW_DAYS,
        _as_of_day,
        _pair_co_counts,
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
    co = _pair_co_counts(
        conn,
        start=start,
        end=end,
        category="",
        base_skill_ids=[skill_id],
    )
    if not co:
        return []
    ranked = sorted(
        ((pair_id, count) for (_base, pair_id), count in co.items() if count > 0),
        key=lambda row: (-row[1], row[0]),
    )
    pair_ids = [pair_id for pair_id, _ in ranked[: limit * 3]]
    meta = _skill_meta(conn, pair_ids)
    out: list[dict] = []
    for pair_id, _count in ranked:
        info = meta.get(pair_id) or {}
        name = str(info.get("name") or "").strip()
        if not name or name.lower() in exclude:
            continue
        out.append({"skill_id": pair_id, "name": name, "source": "pair"})
        if len(out) >= limit:
            break
    return out


def _role_skills(conn, *, skill_id: int, exclude: set[str], limit: int) -> list[dict]:
    """Skills that share roles with the focus skill, ranked by summed weight."""
    if skill_id <= 0 or limit <= 0:
        return []
    try:
        rows = conn.execute(
            """
            SELECT s.id AS skill_id, s.canonical_name AS name, SUM(w.weight) AS score
            FROM role_skill_weight w
            JOIN skill_dictionary s ON s.id = w.skill_id
            WHERE w.role_id IN (
                SELECT role_id FROM role_skill_weight WHERE skill_id = ?
            )
              AND w.skill_id != ?
            GROUP BY s.id, s.canonical_name
            ORDER BY score DESC, s.canonical_name
            LIMIT ?
            """,
            (skill_id, skill_id, limit * 3),
        ).fetchall()
    except Exception:
        return []
    out: list[dict] = []
    for row in rows:
        sid = int(_row_get(row, "skill_id", 0) or 0)
        name = str(_row_get(row, "name", 1) or "").strip()
        if not name or name.lower() in exclude:
            continue
        out.append({"skill_id": sid, "name": name, "source": "role"})
        if len(out) >= limit:
            break
    return out


def related_skills_for_conn(
    conn,
    *,
    name: str,
    exclude: list[str] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    chosen = clamp_limit(limit)
    skill_id, canonical = _resolve(conn, name)
    blocked = _norm_exclude(exclude)
    if canonical:
        blocked.add(canonical.lower())

    if not canonical:
        return {"name": "", "skill_id": None, "items": []}

    items: list[dict] = []
    seen: set[str] = set(blocked)

    def _take(rows: list[dict]) -> None:
        for row in rows:
            key = str(row.get("name") or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "skill_id": row.get("skill_id"),
                    "name": str(row.get("name") or "").strip(),
                    "source": str(row.get("source") or ""),
                }
            )
            if len(items) >= chosen:
                return

    remaining = chosen
    _take(_family_skills(conn, canonical=canonical, exclude=seen, limit=remaining))
    if len(items) < chosen and skill_id:
        remaining = chosen - len(items)
        _take(_pair_skills(conn, skill_id=skill_id, exclude=seen, limit=remaining))
    if len(items) < chosen and skill_id:
        remaining = chosen - len(items)
        _take(_role_skills(conn, skill_id=skill_id, exclude=seen, limit=remaining))

    # Unresolved free-text: still try family by raw prefix.
    if not skill_id and len(items) < chosen:
        remaining = chosen - len(items)
        _take(_family_skills(conn, canonical=canonical, exclude=seen, limit=remaining))

    return {
        "name": canonical,
        "skill_id": skill_id,
        "items": items[:chosen],
    }


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
