"""Daily skill market aggregates (plan §7.1).

Counts published jobs per skill per UTC calendar day from job_skill × jobs.
No AI — pure SQL aggregation.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

SCHEMA = """
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

INDEXES = (
    "CREATE INDEX IF NOT EXISTS skill_trend_daily_skill_day ON skill_trend_daily(skill_id, day)",
    "CREATE INDEX IF NOT EXISTS skill_trend_daily_day ON skill_trend_daily(day)",
    "CREATE INDEX IF NOT EXISTS skill_trend_daily_category_day ON skill_trend_daily(category, day)",
)

BACKFILL_DAYS = 56


def ensure_skill_trend_tables(conn) -> None:
    conn.executescript(SCHEMA)
    for sql in INDEXES:
        conn.execute(sql)


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _parse_day(value: str | date | None) -> date:
    if value is None:
        return _utc_today()
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    raw = str(value).strip()
    if len(raw) >= 10:
        return date.fromisoformat(raw[:10])
    raise ValueError(f"invalid day: {value!r}")


def aggregate_skill_trends(conn, day: str | date | None = None) -> int:
    """Upsert ad_count for one UTC calendar day. Returns number of groups written."""
    ensure_skill_trend_tables(conn)
    chosen = _parse_day(day)
    day_key = chosen.isoformat()

    # Jobs store created_at as ISO text; first 10 chars are YYYY-MM-DD.
    rows = conn.execute(
        """
        SELECT
            js.skill_id AS skill_id,
            COALESCE(j.category, '') AS category,
            COALESCE(j.remote, 0) AS remote,
            COALESCE(j.relocation, 0) AS relocation,
            COUNT(DISTINCT j.id) AS ad_count
        FROM job_skill js
        JOIN jobs j ON j.id = js.job_id
        WHERE j.status = 'published'
          AND COALESCE(j.hidden, 0) = 0
          AND substr(j.created_at, 1, 10) = ?
        GROUP BY js.skill_id, COALESCE(j.category, ''),
                 COALESCE(j.remote, 0), COALESCE(j.relocation, 0)
        """,
        (day_key,),
    ).fetchall()

    # Clear the day first so removed skills do not linger after re-aggregate.
    conn.execute("DELETE FROM skill_trend_daily WHERE day = ?", (day_key,))

    sql = """
        INSERT INTO skill_trend_daily (
            day, skill_id, category, region, remote, relocation, ad_count, salary_median
        ) VALUES (?, ?, ?, '', ?, ?, ?, NULL)
    """
    written = 0
    for row in rows:
        try:
            skill_id = int(row["skill_id"] if hasattr(row, "keys") else row[0])
            category = str(row["category"] if hasattr(row, "keys") else row[1] or "")
            remote = int(row["remote"] if hasattr(row, "keys") else row[2] or 0)
            relocation = int(row["relocation"] if hasattr(row, "keys") else row[3] or 0)
            ad_count = int(row["ad_count"] if hasattr(row, "keys") else row[4] or 0)
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        if skill_id <= 0 or ad_count <= 0:
            continue
        conn.execute(
            sql,
            (day_key, skill_id, category, remote, relocation, ad_count),
        )
        written += 1
    return written


def backfill_skill_trends(conn, *, days: int = BACKFILL_DAYS) -> int:
    """Aggregate the last N UTC days (inclusive of today). Returns total groups written."""
    ensure_skill_trend_tables(conn)
    today = _utc_today()
    total = 0
    span = max(1, int(days))
    for offset in range(span):
        day = today - timedelta(days=offset)
        total += aggregate_skill_trends(conn, day)
    return total


def refresh_skill_trends(conn) -> dict:
    """Daily hook: backfill when empty; otherwise refresh yesterday + today."""
    ensure_skill_trend_tables(conn)
    today = _utc_today()
    yesterday = today - timedelta(days=1)
    count_row = conn.execute("SELECT COUNT(*) FROM skill_trend_daily").fetchone()
    existing = int(count_row[0] if count_row is not None else 0)
    if existing == 0:
        written = backfill_skill_trends(conn, days=BACKFILL_DAYS)
        return {"mode": "backfill", "days": BACKFILL_DAYS, "groups": written}

    y_groups = aggregate_skill_trends(conn, yesterday)
    t_groups = aggregate_skill_trends(conn, today)
    return {
        "mode": "refresh",
        "days": 2,
        "groups": y_groups + t_groups,
        "yesterday": yesterday.isoformat(),
        "today": today.isoformat(),
    }
