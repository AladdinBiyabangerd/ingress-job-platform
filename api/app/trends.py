"""Public skill market trends from skill_trend_daily (plan §7.1)."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import median
from threading import Lock
from typing import Any

DEFAULT_LIMIT = 30
MAX_LIMIT = 100
DEFAULT_WINDOW_DAYS = 7
MAX_WINDOW_DAYS = 56
MIN_ADS_FOR_GROWTH = 20
# Salary is scarcer than skill mentions — show only with enough parseable samples.
MIN_SALARY_SAMPLES = 5
# Pair share needs enough base-skill ads (e.g. Java) to avoid noisy companions.
MIN_PAIR_BASE_ADS = 10
DEFAULT_PAIR_LIMIT = 3
MAX_PAIR_LIMIT = 10
# Prior week must have a real baseline; near-zero prior turns WoW into millions %.
MIN_PRIOR_SHARE_FOR_GROWTH = 0.001

_SALARY_COLUMNS = (
    ("salary_currency", "TEXT NOT NULL DEFAULT ''"),
    ("salary_n", "INTEGER NOT NULL DEFAULT 0"),
    ("salary_low", "REAL"),
    ("salary_high", "REAL"),
    ("salary_by_currency", "TEXT NOT NULL DEFAULT '[]'"),
)

# Schema DDL is also applied by cabinet_store.ensure_schema; cache so hot
# GET /trends does not re-run PRAGMA / ALTER / CREATE INDEX every request.
_TRENDS_ENSURED: set[str] = set()
_TRENDS_LOCK = Lock()


def _trends_ensure_key() -> str:
    if os.environ.get("DATABASE_URL", "").strip():
        return "postgres"
    try:
        from app.sqlite_jobs import DB_PATH

        return str(DB_PATH)
    except Exception:
        configured = os.environ.get("JOBS_DB_PATH", "").strip()
        return configured or "sqlite-default"

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
    key = _trends_ensure_key()
    if key in _TRENDS_ENSURED:
        return
    with _TRENDS_LOCK:
        if key in _TRENDS_ENSURED:
            return
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
                salary_currency TEXT NOT NULL DEFAULT '',
                salary_n INTEGER NOT NULL DEFAULT 0,
                salary_low REAL,
                salary_high REAL,
                salary_by_currency TEXT NOT NULL DEFAULT '[]',
                PRIMARY KEY (day, skill_id, category, region, remote, relocation)
            );
            CREATE TABLE IF NOT EXISTS skill_pair_daily (
                day TEXT NOT NULL,
                base_skill_id INTEGER NOT NULL REFERENCES skill_dictionary(id),
                pair_skill_id INTEGER NOT NULL REFERENCES skill_dictionary(id),
                category TEXT NOT NULL DEFAULT '',
                co_ad_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (day, base_skill_id, pair_skill_id, category)
            );
            """
        )
        try:
            existing = {
                str(row[1])
                for row in conn.execute("PRAGMA table_info(skill_trend_daily)").fetchall()
            }
        except Exception:
            existing = set()
        for name, decl in _SALARY_COLUMNS:
            if name not in existing:
                try:
                    conn.execute(f"ALTER TABLE skill_trend_daily ADD COLUMN {name} {decl}")
                except Exception:
                    pass
        conn.execute(
            "CREATE INDEX IF NOT EXISTS skill_trend_daily_skill_day ON skill_trend_daily(skill_id, day)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS skill_trend_daily_day ON skill_trend_daily(day)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS skill_trend_daily_category_day ON skill_trend_daily(category, day)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS skill_pair_daily_base_day ON skill_pair_daily(base_skill_id, day)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS skill_pair_daily_day ON skill_pair_daily(day)")
        _TRENDS_ENSURED.add(key)


def clamp_pair_limit(value: int | None) -> int:
    if value is None:
        return DEFAULT_PAIR_LIMIT
    try:
        n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_PAIR_LIMIT
    return max(1, min(MAX_PAIR_LIMIT, n))


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


def _day_after(day: str) -> str:
    """Exclusive upper bound for ISO created_at comparisons (YYYY-MM-DD inclusive end)."""
    return (date.fromisoformat(str(day)[:10]) + timedelta(days=1)).isoformat()


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


def _skill_counts_windows(
    conn,
    *,
    cur_start: str,
    cur_end: str,
    prior_start: str,
    prior_end: str,
    category: str,
    region: str,
) -> tuple[dict[int, int], dict[int, int]]:
    """Current + prior skill ad counts in one scan of skill_trend_daily."""
    clauses = ["day >= ?", "day <= ?"]
    params: list[Any] = [prior_start, cur_end]
    if category:
        clauses.append("category = ?")
        params.append(category)
    if region:
        clauses.append("region = ?")
        params.append(region)
    sql = f"""
        SELECT
            skill_id,
            SUM(CASE WHEN day >= ? AND day <= ? THEN ad_count ELSE 0 END) AS current_count,
            SUM(CASE WHEN day >= ? AND day <= ? THEN ad_count ELSE 0 END) AS prior_count
        FROM skill_trend_daily
        WHERE {' AND '.join(clauses)}
        GROUP BY skill_id
    """
    try:
        rows = conn.execute(
            sql, [cur_start, cur_end, prior_start, prior_end, *params]
        ).fetchall()
    except Exception:
        return {}, {}
    current: dict[int, int] = {}
    prior: dict[int, int] = {}
    for row in rows:
        skill_id = int(_row_get(row, "skill_id", 0) or 0)
        if skill_id <= 0:
            continue
        cur = int(_row_get(row, "current_count", 1) or 0)
        prev = int(_row_get(row, "prior_count", 2) or 0)
        if cur > 0:
            current[skill_id] = cur
        if prev > 0:
            prior[skill_id] = prev
    return current, prior


def _category_job_count(
    conn,
    *,
    start: str,
    end: str,
    category: str,
    region: str,
) -> int:
    """Published jobs in the calendar window (denominator for share).

    Uses created_at range (not substr) so jobs_public_list can apply.
    """
    del region  # jobs have no region column yet; reserved for API filter parity
    clauses = [
        "status = 'published'",
        "COALESCE(hidden, 0) = 0",
        "(merged_into IS NULL OR merged_into = 0)",
        "created_at >= ?",
        "created_at < ?",
    ]
    params: list[Any] = [start, _day_after(end)]
    if category:
        clauses.append("COALESCE(category, '') = ?")
        params.append(category)
    sql = f"SELECT COUNT(*) AS total FROM jobs WHERE {' AND '.join(clauses)}"
    try:
        row = conn.execute(sql, params).fetchone()
    except Exception:
        return 0
    return int(_row_get(row, "total", 0) or 0)


def _category_job_counts_windows(
    conn,
    *,
    cur_start: str,
    cur_end: str,
    prior_start: str,
    prior_end: str,
    category: str,
    region: str,
) -> tuple[int, int]:
    """Current + prior published job counts in one jobs scan."""
    del region
    cur_hi = _day_after(cur_end)
    prior_hi = _day_after(prior_end)
    clauses = [
        "status = 'published'",
        "COALESCE(hidden, 0) = 0",
        "(merged_into IS NULL OR merged_into = 0)",
        "created_at >= ?",
        "created_at < ?",
    ]
    params: list[Any] = [prior_start, cur_hi]
    if category:
        clauses.append("COALESCE(category, '') = ?")
        params.append(category)
    sql = f"""
        SELECT
            SUM(CASE WHEN created_at >= ? AND created_at < ? THEN 1 ELSE 0 END) AS current_n,
            SUM(CASE WHEN created_at >= ? AND created_at < ? THEN 1 ELSE 0 END) AS prior_n
        FROM jobs
        WHERE {' AND '.join(clauses)}
    """
    try:
        row = conn.execute(
            sql, [cur_start, cur_hi, prior_start, prior_hi, *params]
        ).fetchone()
    except Exception:
        return 0, 0
    if row is None:
        return 0, 0
    return (
        int(_row_get(row, "current_n", 0) or 0),
        int(_row_get(row, "prior_n", 1) or 0),
    )


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
    prior = float(prior_share)
    if prior < MIN_PRIOR_SHARE_FOR_GROWTH:
        return None
    return round((float(current_share) - prior) / prior, 4)


def _pair_co_counts(
    conn,
    *,
    start: str,
    end: str,
    category: str,
    base_skill_ids: list[int],
) -> dict[tuple[int, int], int]:
    """Sum co_ad_count for (base, pair) over the window."""
    if not base_skill_ids:
        return {}
    clauses = [
        "day >= ?",
        "day <= ?",
        f"base_skill_id IN ({','.join('?' for _ in base_skill_ids)})",
    ]
    params: list[Any] = [start, end, *base_skill_ids]
    if category:
        clauses.append("category = ?")
        params.append(category)
    sql = f"""
        SELECT base_skill_id, pair_skill_id, SUM(co_ad_count) AS co_ad_count
        FROM skill_pair_daily
        WHERE {' AND '.join(clauses)}
        GROUP BY base_skill_id, pair_skill_id
    """
    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception:
        return {}
    out: dict[tuple[int, int], int] = {}
    for row in rows:
        base_id = int(_row_get(row, "base_skill_id", 0) or 0)
        pair_id = int(_row_get(row, "pair_skill_id", 1) or 0)
        co_count = int(_row_get(row, "co_ad_count", 2) or 0)
        if base_id > 0 and pair_id > 0 and co_count > 0:
            out[(base_id, pair_id)] = co_count
    return out


def companions_for_skills(
    conn,
    *,
    base_skill_ids: list[int],
    skill_counts: dict[int, int],
    start: str,
    end: str,
    category: str,
    pair_limit: int = DEFAULT_PAIR_LIMIT,
) -> dict[int, list[dict]]:
    """Top companions: share of base-skill ads that also require the pair skill."""
    chosen_limit = clamp_pair_limit(pair_limit)
    eligible = [
        sid
        for sid in base_skill_ids
        if int(skill_counts.get(sid) or 0) >= MIN_PAIR_BASE_ADS
    ]
    if not eligible:
        return {}
    co = _pair_co_counts(
        conn, start=start, end=end, category=category, base_skill_ids=eligible
    )
    pair_ids = sorted({pair_id for (_base, pair_id) in co})
    meta = _skill_meta(conn, pair_ids)
    by_base: dict[int, list[tuple[float, int, int]]] = defaultdict(list)
    for (base_id, pair_id), co_count in co.items():
        base_ads = int(skill_counts.get(base_id) or 0)
        if base_ads < MIN_PAIR_BASE_ADS or co_count <= 0:
            continue
        if not str((meta.get(pair_id) or {}).get("name") or "").strip():
            continue
        share = round(co_count / base_ads, 4)
        by_base[base_id].append((share, co_count, pair_id))

    out: dict[int, list[dict]] = {}
    for base_id, ranked in by_base.items():
        ranked.sort(key=lambda row: (-row[0], -row[1], row[2]))
        companions: list[dict] = []
        for share, co_count, pair_id in ranked[:chosen_limit]:
            info = meta.get(pair_id) or {}
            companions.append(
                {
                    "skill_id": pair_id,
                    "name": str(info.get("name") or ""),
                    "share": share,
                    "co_ad_count": co_count,
                }
            )
        if companions:
            out[base_id] = companions
    return out


def best_pair_share_for_missing(
    conn,
    *,
    have_skill_ids: list[int],
    missing_skill_ids: list[int],
    category: str | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> dict[int, dict]:
    """For each missing skill, best pair_share among ads of skills the candidate has."""
    ensure_trend_tables(conn)
    have = [int(x) for x in have_skill_ids if int(x) > 0]
    missing = [int(x) for x in missing_skill_ids if int(x) > 0]
    if not have or not missing:
        return {}
    chosen_window = clamp_window(window_days)
    cat = (category or "").strip()
    as_of = _as_of_day(conn)
    start, end = _window_bounds(as_of, chosen_window)
    base_counts = _skill_counts(conn, start=start, end=end, category=cat, region="")
    co = _pair_co_counts(conn, start=start, end=end, category=cat, base_skill_ids=have)
    have_meta = _skill_meta(conn, have)
    out: dict[int, dict] = {}
    for missing_id in missing:
        best: dict | None = None
        for base_id in have:
            base_ads = int(base_counts.get(base_id) or 0)
            if base_ads < MIN_PAIR_BASE_ADS:
                continue
            co_count = int(co.get((base_id, missing_id)) or 0)
            if co_count <= 0:
                continue
            share = round(co_count / base_ads, 4)
            candidate = {
                "share": share,
                "co_ad_count": co_count,
                "base_skill_id": base_id,
                "base_name": str((have_meta.get(base_id) or {}).get("name") or ""),
            }
            if best is None or share > float(best["share"]):
                best = candidate
        if best is not None and str(best.get("base_name") or "").strip():
            out[missing_id] = best
    return out


def _salary_group_parts(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Bucket daily salary samples by currency. Never mixes currencies together."""
    by_currency: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        currency = str(row.get("currency") or "").strip().upper()
        n = int(row.get("n") or 0)
        med = row.get("median")
        if not currency or n <= 0 or not isinstance(med, (int, float)):
            continue
        by_currency[currency].append(
            {
                "median": float(med),
                "n": n,
                "low": float(row["low"]) if isinstance(row.get("low"), (int, float)) else float(med),
                "high": float(row["high"])
                if isinstance(row.get("high"), (int, float))
                else float(med),
            }
        )
    return by_currency


def _combine_currency_parts(currency: str, parts: list[dict[str, Any]]) -> dict[str, Any] | None:
    total_n = sum(int(p["n"]) for p in parts)
    if total_n < MIN_SALARY_SAMPLES:
        return None
    expanded: list[float] = []
    for part in parts:
        expanded.extend([float(part["median"])] * int(part["n"]))
    return {
        "median": round(float(median(expanded)), 2),
        "low": round(min(float(p["low"]) for p in parts), 2),
        "high": round(max(float(p["high"]) for p in parts), 2),
        "currency": currency,
        "period": "year",
        "n": total_n,
    }


def combine_salary_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge daily salary rows into one stats object per currency (majority first)."""
    by_currency = _salary_group_parts(rows)
    out: list[dict[str, Any]] = []
    for currency, parts in sorted(
        by_currency.items(), key=lambda kv: (-sum(p["n"] for p in kv[1]), kv[0])
    ):
        combined = _combine_currency_parts(currency, parts)
        if combined is not None:
            out.append(combined)
    return out


def combine_salary_days(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Merge daily salary rows for one skill. Same currency only; suppress if n low."""
    groups = combine_salary_groups(rows)
    return groups[0] if groups else None


def _salary_payload(entry: dict[str, Any] | None) -> dict[str, Any]:
    """Public salary fields: primary + all currency groups (never FX-mixed)."""
    if not entry:
        return {"salary": None, "salaries": []}
    groups = list(entry.get("groups") or [])
    primary = entry.get("primary") or (groups[0] if groups else None)
    return {"salary": primary, "salaries": groups}


def _skill_salaries(
    conn,
    *,
    start: str,
    end: str,
    category: str,
    region: str,
    skill_ids: list[int],
) -> dict[int, dict]:
    if not skill_ids:
        return {}
    clauses = [
        "day >= ?",
        "day <= ?",
        "COALESCE(salary_n, 0) > 0",
        f"skill_id IN ({','.join('?' for _ in skill_ids)})",
    ]
    params: list[Any] = [start, end, *skill_ids]
    if category:
        clauses.append("category = ?")
        params.append(category)
    if region:
        clauses.append("region = ?")
        params.append(region)
    sql = f"""
        SELECT skill_id, salary_median, salary_currency, salary_n, salary_low, salary_high,
               salary_by_currency
        FROM skill_trend_daily
        WHERE {' AND '.join(clauses)}
    """
    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception:
        # Older DBs without salary_by_currency — fall back to primary columns only.
        sql_legacy = f"""
            SELECT skill_id, salary_median, salary_currency, salary_n, salary_low, salary_high
            FROM skill_trend_daily
            WHERE {' AND '.join(clauses)}
        """
        try:
            rows = conn.execute(sql_legacy, params).fetchall()
        except Exception:
            return {}
    by_skill: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        skill_id = int(_row_get(row, "skill_id", 0) or 0)
        if skill_id <= 0:
            continue
        grouped = _parse_json_list(_row_get(row, "salary_by_currency", 6))
        if grouped:
            for item in grouped:
                if not isinstance(item, dict):
                    continue
                by_skill[skill_id].append(
                    {
                        "median": item.get("median"),
                        "currency": item.get("currency"),
                        "n": item.get("n"),
                        "low": item.get("low"),
                        "high": item.get("high"),
                    }
                )
            continue
        by_skill[skill_id].append(
            {
                "median": _row_get(row, "salary_median", 1),
                "currency": _row_get(row, "salary_currency", 2),
                "n": _row_get(row, "salary_n", 3),
                "low": _row_get(row, "salary_low", 4),
                "high": _row_get(row, "salary_high", 5),
            }
        )
    out: dict[int, dict] = {}
    for skill_id, parts in by_skill.items():
        groups = combine_salary_groups(parts)
        if groups:
            out[skill_id] = {"primary": groups[0], "groups": groups}
    return out


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

    current, prior = _skill_counts_windows(
        conn,
        cur_start=cur_start,
        cur_end=cur_end,
        prior_start=prior_start,
        prior_end=prior_end_s,
        category=cat,
        region=reg,
    )
    denom, prior_denom = _category_job_counts_windows(
        conn,
        cur_start=cur_start,
        cur_end=cur_end,
        prior_start=prior_start,
        prior_end=prior_end_s,
        category=cat,
        region=reg,
    )

    ranked = sorted(current.items(), key=lambda kv: (-kv[1], kv[0]))[:chosen_limit]
    skill_ids = [skill_id for skill_id, _ in ranked]
    meta = _skill_meta(conn, skill_ids)
    salaries = _skill_salaries(
        conn,
        start=cur_start,
        end=cur_end,
        category=cat,
        region=reg,
        skill_ids=skill_ids,
    )
    companions = companions_for_skills(
        conn,
        base_skill_ids=skill_ids,
        skill_counts=current,
        start=cur_start,
        end=cur_end,
        category=cat,
    )
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
                **_salary_payload(salaries.get(skill_id)),
                "often_with": companions.get(skill_id) or [],
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
    current, prior = _skill_counts_windows(
        conn,
        cur_start=cur_start,
        cur_end=cur_end,
        prior_start=prior_start,
        prior_end=prior_end_s,
        category=cat,
        region="",
    )
    denom, prior_denom = _category_job_counts_windows(
        conn,
        cur_start=cur_start,
        cur_end=cur_end,
        prior_start=prior_start,
        prior_end=prior_end_s,
        category=cat,
        region="",
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


DEFAULT_DETAIL_JOBS = 20
MAX_DETAIL_JOBS = 50
MIN_DETAIL_JOBS = 0


def clamp_detail_jobs(value: int | None) -> int:
    if value is None:
        return DEFAULT_DETAIL_JOBS
    try:
        n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_DETAIL_JOBS
    return max(MIN_DETAIL_JOBS, min(MAX_DETAIL_JOBS, n))


def clamp_jobs_page(value: int | None) -> int:
    if value is None:
        return 1
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 1
    return max(1, n)


def _jobs_for_skill(
    conn, *, skill_id: int, limit: int, offset: int = 0
) -> tuple[list[dict], int]:
    """Published jobs that require this skill, newest first. Returns (page, total)."""
    chosen = clamp_detail_jobs(limit)
    start = max(0, int(offset or 0))
    where = """
            FROM jobs j
            JOIN job_skill js ON js.job_id = j.id
            WHERE js.skill_id = ?
              AND j.status = 'published'
              AND COALESCE(j.hidden, 0) = 0
              AND (j.merged_into IS NULL OR j.merged_into = 0)
    """
    try:
        total_row = conn.execute(f"SELECT COUNT(*) AS n {where}", (skill_id,)).fetchone()
        total = int(_row_get(total_row, "n", 0) or 0) if total_row is not None else 0
    except Exception:
        return [], 0
    if chosen <= 0 or total <= 0:
        return [], total
    try:
        rows = conn.execute(
            f"""
            SELECT
                j.id, j.title, j.company, j.city,
                COALESCE(j.remote, 0) AS remote,
                COALESCE(j.relocation, 0) AS relocation,
                COALESCE(j.language, '') AS language,
                COALESCE(j.category, '') AS category,
                COALESCE(j.salary, '') AS salary,
                COALESCE(j.created_at, '') AS created_at
            {where}
            ORDER BY j.created_at DESC, j.id DESC
            LIMIT ? OFFSET ?
            """,
            (skill_id, chosen, start),
        ).fetchall()
    except Exception:
        return [], total
    out: list[dict] = []
    for row in rows:
        out.append(
            {
                "job_id": int(_row_get(row, "id", 0)),
                "title": str(_row_get(row, "title", 1) or ""),
                "company": str(_row_get(row, "company", 2) or ""),
                "city": str(_row_get(row, "city", 3) or ""),
                "remote": bool(int(_row_get(row, "remote", 4) or 0)),
                "relocation": bool(int(_row_get(row, "relocation", 5) or 0)),
                "language": str(_row_get(row, "language", 6) or ""),
                "category": str(_row_get(row, "category", 7) or ""),
                "salary": str(_row_get(row, "salary", 8) or ""),
                "created_at": str(_row_get(row, "created_at", 9) or ""),
            }
        )
    return out, total


def _you_vs_trend(
    conn,
    *,
    user_id: str,
    skill_id: int,
    skill_name: str,
    companions: list[dict],
    academy_courses: list[str],
) -> dict | None:
    """Personalized have/missing vs focus skill + often_with companions."""
    from app.cv_profile import _profile_payload, ensure_profile_tables
    from app.role_suggestions import (
        _build_skill_lookup,
        _candidate_skills,
        _matching_granted,
    )

    subject = (user_id or "").strip()
    if not subject:
        return None
    ensure_profile_tables(conn)
    matching = _matching_granted(conn, subject)
    if not matching:
        return {
            "matching_consent": False,
            "have_focus": False,
            "have": [],
            "missing": [],
            "learn_next": [],
        }

    profile_payload = _profile_payload(conn, user_id=subject)
    profile = profile_payload.get("profile") if isinstance(profile_payload.get("profile"), dict) else {}
    lookup = _build_skill_lookup(conn)
    candidate = _candidate_skills(profile, lookup)
    have_focus = skill_id in candidate

    companion_ids = [
        int(row.get("skill_id") or 0)
        for row in companions
        if int(row.get("skill_id") or 0) > 0
    ]
    metrics = trend_metrics_for_skills(conn, skill_ids=companion_ids) if companion_ids else {}
    companion_meta = _skill_meta(conn, companion_ids)

    have: list[dict] = []
    missing: list[dict] = []
    for row in companions:
        cid = int(row.get("skill_id") or 0)
        if cid <= 0:
            continue
        info = companion_meta.get(cid) or {}
        name = str(row.get("name") or info.get("name") or "").strip()
        if not name:
            continue
        metric = metrics.get(cid) or {}
        item = {
            "skill_id": cid,
            "name": name,
            "share": float(row.get("share")) if isinstance(row.get("share"), (int, float)) else metric.get("share"),
            "growth": metric.get("growth"),
            "co_ad_count": int(row.get("co_ad_count") or 0) or None,
            "academy_courses": list(info.get("academy_courses") or []),
            "often_with": {
                "base_name": skill_name,
                "share": float(row.get("share")) if isinstance(row.get("share"), (int, float)) else None,
            },
        }
        if cid in candidate:
            have.append(item)
        else:
            missing.append(item)

    learn_next = list(missing)
    if not have_focus:
        learn_next = [
            {
                "skill_id": skill_id,
                "name": skill_name,
                "share": None,
                "growth": None,
                "academy_courses": list(academy_courses or []),
                "focus": True,
            },
            *learn_next,
        ]

    return {
        "matching_consent": True,
        "have_focus": have_focus,
        "have": have,
        "missing": missing,
        "learn_next": learn_next,
    }


def trend_detail_payload(
    conn,
    *,
    skill_id: int,
    category: str | None = None,
    region: str | None = None,
    window_days: int | None = None,
    jobs_limit: int | None = None,
    jobs_page: int | None = None,
    lang: str | None = None,
    user_id: str | None = None,
) -> dict | None:
    """Single-skill market detail + jobs + optional you-vs-trend."""
    ensure_trend_tables(conn)
    sid = int(skill_id or 0)
    if sid <= 0:
        return None
    locale = _pick_locale(lang)
    chosen_window = clamp_window(window_days)
    cat = (category or "").strip()
    reg = (region or "").strip()
    as_of = _as_of_day(conn)
    cur_start, cur_end = _window_bounds(as_of, chosen_window)
    prior_end = as_of - timedelta(days=chosen_window)
    prior_start, prior_end_s = _window_bounds(prior_end, chosen_window)

    meta = _skill_meta(conn, [sid])
    info = meta.get(sid)
    if not info or not str(info.get("name") or "").strip():
        return None
    name = str(info.get("name") or "").strip()
    academy_courses = list(info.get("academy_courses") or [])

    current, prior = _skill_counts_windows(
        conn,
        cur_start=cur_start,
        cur_end=cur_end,
        prior_start=prior_start,
        prior_end=prior_end_s,
        category=cat,
        region=reg,
    )
    denom, prior_denom = _category_job_counts_windows(
        conn,
        cur_start=cur_start,
        cur_end=cur_end,
        prior_start=prior_start,
        prior_end=prior_end_s,
        category=cat,
        region=reg,
    )
    ad_count = int(current.get(sid) or 0)
    share = round(ad_count / denom, 4) if denom > 0 else 0.0
    prior_ads = int(prior.get(sid) or 0)
    prior_share = (prior_ads / prior_denom) if prior_denom > 0 else 0.0
    salaries = _skill_salaries(
        conn,
        start=cur_start,
        end=cur_end,
        category=cat,
        region=reg,
        skill_ids=[sid],
    )
    often_with = companions_for_skills(
        conn,
        base_skill_ids=[sid],
        skill_counts=current,
        start=cur_start,
        end=cur_end,
        category=cat,
        pair_limit=MAX_PAIR_LIMIT,
    ).get(sid) or []

    per_page = clamp_detail_jobs(jobs_limit)
    page = clamp_jobs_page(jobs_page)
    offset = (page - 1) * per_page if per_page > 0 else 0
    jobs, jobs_total = _jobs_for_skill(conn, skill_id=sid, limit=per_page, offset=offset)
    if per_page > 0 and jobs_total > 0:
        max_page = max(1, (jobs_total + per_page - 1) // per_page)
        if page > max_page:
            page = max_page
            offset = (page - 1) * per_page
            jobs, jobs_total = _jobs_for_skill(conn, skill_id=sid, limit=per_page, offset=offset)
    payload = {
        "skill_id": sid,
        "name": name,
        "ad_count": ad_count,
        "share": share,
        "growth_wow": growth_wow(share, prior_share, ad_count=ad_count),
        "category_hint": str(info.get("category_hint") or ""),
        "academy_courses": academy_courses,
        **_salary_payload(salaries.get(sid)),
        "often_with": often_with,
        "jobs": jobs,
        "jobs_total": jobs_total,
        "jobs_page": page,
        "jobs_per_page": per_page,
        "as_of": as_of.isoformat(),
        "window_days": chosen_window,
        "category": cat,
        "region": reg,
        "job_count": denom,
        "disclaimer": DISCLAIMER[locale],
        "source_note": SOURCE_NOTE[locale],
        "you": None,
    }
    if user_id:
        payload["you"] = _you_vs_trend(
            conn,
            user_id=user_id,
            skill_id=sid,
            skill_name=name,
            companions=often_with,
            academy_courses=academy_courses,
        )
    return payload


def get_trend_detail(
    *,
    skill_id: int,
    category: str | None = None,
    region: str | None = None,
    window_days: int | None = None,
    jobs_limit: int | None = None,
    jobs_page: int | None = None,
    lang: str | None = None,
    user_id: str | None = None,
) -> dict | None:
    from app.cabinet_store import _LOCK, _connect

    with _LOCK:
        conn = _connect()
        try:
            return trend_detail_payload(
                conn,
                skill_id=skill_id,
                category=category,
                region=region,
                window_days=window_days,
                jobs_limit=jobs_limit,
                jobs_page=jobs_page,
                lang=lang,
                user_id=user_id,
            )
        finally:
            conn.close()
