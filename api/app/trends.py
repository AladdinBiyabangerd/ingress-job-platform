"""Public skill market trends from skill_trend_daily (plan §7.1)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

DEFAULT_LIMIT = 30
MAX_LIMIT = 100
DEFAULT_WINDOW_DAYS = 7
MAX_WINDOW_DAYS = 56
MIN_ADS_FOR_GROWTH = 20
GROWTH_EPS = 1e-6

DISCLAIMER = {
    "az": "Trendlər yalnız Ingress Job-un izlədiyi elanlar əsasında hesablanır, bütün bazarı əks etdirmir.",
    "en": "Trends reflect only listings Ingress Job tracks — not the whole market.",
    "ru": "Тренды считаются только по вакансиям, которые отслеживает Ingress Job, а не по всему рынку.",
}

SOURCE_NOTE = {
    "az": "Ingress Job-un izlədiyi elanlar əsasında",
    "en": "Based on listings tracked by Ingress Job",
    "ru": "На основе вакансий, отслеживаемых Ingress Job",
}


def _pick_locale(lang: str | None) -> str:
    code = (lang or "az").strip().lower()[:2]
    return code if code in DISCLAIMER else "az"


def _row_get(row, key: str, index: int):
    if row is None:
        return None
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return row[index]


def _parse_json_list(raw: object) -> list:
    if isinstance(raw, list):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def clamp_limit(value: int | None) -> int:
    if value is None:
        return DEFAULT_LIMIT
    try:
        n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, n))


def clamp_window(value: int | None) -> int:
    if value is None:
        return DEFAULT_WINDOW_DAYS
    try:
        n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_WINDOW_DAYS
    return max(1, min(MAX_WINDOW_DAYS, n))


def ensure_trend_tables(conn) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS skill_trend_daily (
            day TEXT NOT NULL,
            skill_id INTEGER NOT NULL REFERENCES skill_dictionary(id),
            category TEXT NOT NULL DEFAULT '',
            region TEXT NOT NULL DEFAULT '',
            remote INTEGER NOT NULL DEFAULT 0,
            relocation INTEGER NOT NULL DEFAULT 0,
            ad_count INTEGER NOT NULL DEFAULT 0,
            salary_median REAL,
            PRIMARY KEY (day, skill_id, category, region, remote, relocation)
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS skill_trend_daily_skill_day ON skill_trend_daily(skill_id, day)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS skill_trend_daily_day ON skill_trend_daily(day)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS skill_trend_daily_category_day ON skill_trend_daily(category, day)"
    )


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _as_of_day(conn) -> date:
    try:
        row = conn.execute("SELECT MAX(day) FROM skill_trend_daily").fetchone()
    except Exception:
        return _utc_today()
    raw = _row_get(row, "MAX(day)", 0) if row is not None else None
    if not raw:
        return _utc_today()
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return _utc_today()


def _window_bounds(as_of: date, window_days: int) -> tuple[str, str]:
    start = as_of - timedelta(days=window_days - 1)
    return start.isoformat(), as_of.isoformat()


def _skill_counts(
    conn,
    *,
    start: str,
    end: str,
    category: str,
    region: str,
) -> dict[int, int]:
    clauses = ["day >= ?", "day <= ?"]
    params: list[Any] = [start, end]
    if category:
        clauses.append("category = ?")
        params.append(category)
    if region:
        clauses.append("region = ?")
        params.append(region)
    sql = f"""
        SELECT skill_id, SUM(ad_count) AS ad_count
        FROM skill_trend_daily
        WHERE {' AND '.join(clauses)}
        GROUP BY skill_id
    """
    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception:
        return {}
    out: dict[int, int] = {}
    for row in rows:
        skill_id = int(_row_get(row, "skill_id", 0) or 0)
        ad_count = int(_row_get(row, "ad_count", 1) or 0)
        if skill_id > 0 and ad_count > 0:
            out[skill_id] = ad_count
    return out


def _category_job_count(
    conn,
    *,
    start: str,
    end: str,
    category: str,
    region: str,
) -> int:
    """Distinct published jobs in the calendar window (denominator for share)."""
    del region  # jobs have no region column yet; reserved for API filter parity
    clauses = [
        "status = 'published'",
        "COALESCE(hidden, 0) = 0",
        "substr(created_at, 1, 10) >= ?",
        "substr(created_at, 1, 10) <= ?",
    ]
    params: list[Any] = [start, end]
    if category:
        clauses.append("COALESCE(category, '') = ?")
        params.append(category)
    sql = f"SELECT COUNT(*) FROM jobs WHERE {' AND '.join(clauses)}"
    try:
        row = conn.execute(sql, params).fetchone()
    except Exception:
        return 0
    return int(_row_get(row, "COUNT(*)", 0) or 0)


def _skill_meta(conn, skill_ids: list[int]) -> dict[int, dict]:
    if not skill_ids:
        return {}
    placeholders = ",".join("?" for _ in skill_ids)
    try:
        rows = conn.execute(
            f"""
            SELECT id, canonical_name, category_hint, academy_course_ids
            FROM skill_dictionary
            WHERE id IN ({placeholders})
            """,
            skill_ids,
        ).fetchall()
    except Exception:
        return {}
    out: dict[int, dict] = {}
    for row in rows:
        skill_id = int(_row_get(row, "id", 0) or 0)
        courses = [
            str(x).strip()
            for x in _parse_json_list(_row_get(row, "academy_course_ids", 3))
            if str(x).strip()
        ]
        out[skill_id] = {
            "name": str(_row_get(row, "canonical_name", 1) or ""),
            "category_hint": str(_row_get(row, "category_hint", 2) or ""),
            "academy_courses": courses,
        }
    return out


def growth_wow(current_share: float, prior_share: float, *, ad_count: int) -> float | None:
    if ad_count < MIN_ADS_FOR_GROWTH:
        return None
    prior = max(float(prior_share), GROWTH_EPS)
    return round((float(current_share) - float(prior_share)) / prior, 4)


def trends_payload(
    conn,
    *,
    category: str | None = None,
    region: str | None = None,
    limit: int | None = None,
    window_days: int | None = None,
    lang: str | None = None,
) -> dict:
    ensure_trend_tables(conn)
    locale = _pick_locale(lang)
    chosen_limit = clamp_limit(limit)
    chosen_window = clamp_window(window_days)
    cat = (category or "").strip()
    reg = (region or "").strip()
    as_of = _as_of_day(conn)
    cur_start, cur_end = _window_bounds(as_of, chosen_window)
    prior_end = as_of - timedelta(days=chosen_window)
    prior_start, prior_end_s = _window_bounds(prior_end, chosen_window)

    current = _skill_counts(conn, start=cur_start, end=cur_end, category=cat, region=reg)
    prior = _skill_counts(conn, start=prior_start, end=prior_end_s, category=cat, region=reg)
    denom = _category_job_count(conn, start=cur_start, end=cur_end, category=cat, region=reg)
    prior_denom = _category_job_count(
        conn, start=prior_start, end=prior_end_s, category=cat, region=reg
    )

    ranked = sorted(current.items(), key=lambda kv: (-kv[1], kv[0]))[:chosen_limit]
    meta = _skill_meta(conn, [skill_id for skill_id, _ in ranked])
    items: list[dict] = []
    for skill_id, ad_count in ranked:
        info = meta.get(skill_id) or {}
        name = str(info.get("name") or "").strip()
        if not name:
            continue
        share = round(ad_count / denom, 4) if denom > 0 else 0.0
        prior_ads = int(prior.get(skill_id) or 0)
        prior_share = (prior_ads / prior_denom) if prior_denom > 0 else 0.0
        items.append(
            {
                "skill_id": skill_id,
                "name": name,
                "ad_count": ad_count,
                "share": share,
                "growth_wow": growth_wow(share, prior_share, ad_count=ad_count),
                "category_hint": str(info.get("category_hint") or ""),
                "academy_courses": list(info.get("academy_courses") or []),
            }
        )

    return {
        "items": items,
        "as_of": as_of.isoformat(),
        "window_days": chosen_window,
        "category": cat,
        "region": reg,
        "job_count": denom,
        "disclaimer": DISCLAIMER[locale],
        "source_note": SOURCE_NOTE[locale],
    }


def list_trends(
    *,
    category: str | None = None,
    region: str | None = None,
    limit: int | None = None,
    window_days: int | None = None,
    lang: str | None = None,
) -> dict:
    from app.cabinet_store import _LOCK, _connect

    with _LOCK:
        conn = _connect()
        try:
            return trends_payload(
                conn,
                category=category,
                region=region,
                limit=limit,
                window_days=window_days,
                lang=lang,
            )
        finally:
            conn.close()


def trend_metrics_for_skills(
    conn,
    *,
    skill_ids: list[int],
    category: str | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> dict[int, dict]:
    """share / growth_wow for skill-gap enrichment."""
    ensure_trend_tables(conn)
    if not skill_ids:
        return {}
    chosen_window = clamp_window(window_days)
    cat = (category or "").strip()
    as_of = _as_of_day(conn)
    cur_start, cur_end = _window_bounds(as_of, chosen_window)
    prior_end = as_of - timedelta(days=chosen_window)
    prior_start, prior_end_s = _window_bounds(prior_end, chosen_window)
    current = _skill_counts(conn, start=cur_start, end=cur_end, category=cat, region="")
    prior = _skill_counts(conn, start=prior_start, end=prior_end_s, category=cat, region="")
    denom = _category_job_count(conn, start=cur_start, end=cur_end, category=cat, region="")
    prior_denom = _category_job_count(
        conn, start=prior_start, end=prior_end_s, category=cat, region=""
    )
    out: dict[int, dict] = {}
    for skill_id in skill_ids:
        ad_count = int(current.get(skill_id) or 0)
        if ad_count <= 0 and skill_id not in current:
            continue
        share = round(ad_count / denom, 4) if denom > 0 else 0.0
        prior_ads = int(prior.get(skill_id) or 0)
        prior_share = (prior_ads / prior_denom) if prior_denom > 0 else 0.0
        out[skill_id] = {
            "share": share,
            "growth": growth_wow(share, prior_share, ad_count=ad_count),
            "ad_count": ad_count,
        }
    return out
