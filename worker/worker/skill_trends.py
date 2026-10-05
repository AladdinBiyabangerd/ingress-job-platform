"""Daily skill market aggregates (plan §7.1).

Counts published jobs per skill per UTC calendar day from job_skill × jobs.
Salary median/range from free-text job.salary when currency+period are clear.
Skill pairs: co-occurrence counts for “Kafka share among Java ads”.
No AI — pure SQL aggregation + parse.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from worker.salary_parse import parse_salary_annual, pick_currency_values, salary_stats

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
    salary_currency TEXT NOT NULL DEFAULT '',
    salary_n INTEGER NOT NULL DEFAULT 0,
    salary_low REAL,
    salary_high REAL,
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

INDEXES = (
    "CREATE INDEX IF NOT EXISTS skill_trend_daily_skill_day ON skill_trend_daily(skill_id, day)",
    "CREATE INDEX IF NOT EXISTS skill_trend_daily_day ON skill_trend_daily(day)",
    "CREATE INDEX IF NOT EXISTS skill_trend_daily_category_day ON skill_trend_daily(category, day)",
    "CREATE INDEX IF NOT EXISTS skill_pair_daily_base_day ON skill_pair_daily(base_skill_id, day)",
    "CREATE INDEX IF NOT EXISTS skill_pair_daily_day ON skill_pair_daily(day)",
)

# Cap skills per job when building ordered pairs (avoids N² blow-ups on noisy stacks).
MAX_SKILLS_PER_JOB_FOR_PAIRS = 20

_SALARY_COLUMNS = (
    ("salary_currency", "TEXT NOT NULL DEFAULT ''"),
    ("salary_n", "INTEGER NOT NULL DEFAULT 0"),
    ("salary_low", "REAL"),
    ("salary_high", "REAL"),
)

BACKFILL_DAYS = 56


def ensure_skill_trend_tables(conn) -> None:
    conn.executescript(SCHEMA)
    for sql in INDEXES:
        conn.execute(sql)
    existing = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info(skill_trend_daily)").fetchall()
    }
    for name, decl in _SALARY_COLUMNS:
        if name not in existing:
            conn.execute(f"ALTER TABLE skill_trend_daily ADD COLUMN {name} {decl}")


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


def _row_get(row, key: str, index: int):
    if row is None:
        return None
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return row[index]


def _aggregate_skill_pairs(conn, day_key: str, rows) -> int:
    """Ordered co-occurrence: among jobs with base skill, count those also having pair."""
    conn.execute("DELETE FROM skill_pair_daily WHERE day = ?", (day_key,))

    job_skills: dict[tuple[int, str], set[int]] = defaultdict(set)
    for row in rows:
        try:
            skill_id = int(_row_get(row, "skill_id", 0) or 0)
            category = str(_row_get(row, "category", 1) or "")
            job_id = int(_row_get(row, "job_id", 4) or 0)
        except (TypeError, ValueError):
            continue
        if skill_id <= 0 or job_id <= 0:
            continue
        job_skills[(job_id, category)].add(skill_id)

    pair_counts: dict[tuple[int, int, str], int] = defaultdict(int)
    for (_job_id, category), skills in job_skills.items():
        ordered = sorted(skills)[:MAX_SKILLS_PER_JOB_FOR_PAIRS]
        if len(ordered) < 2:
            continue
        for i, base_id in enumerate(ordered):
            for j, pair_id in enumerate(ordered):
                if i == j:
                    continue
                pair_counts[(base_id, pair_id, category)] += 1

    sql = """
        INSERT INTO skill_pair_daily (
            day, base_skill_id, pair_skill_id, category, co_ad_count
        ) VALUES (?, ?, ?, ?, ?)
    """
    written = 0
    for (base_id, pair_id, category), co_count in pair_counts.items():
        if co_count <= 0:
            continue
        conn.execute(sql, (day_key, base_id, pair_id, category, co_count))
        written += 1
    return written


def aggregate_skill_trends(conn, day: str | date | None = None) -> int:
    """Upsert ad_count (+ salary + skill pairs) for one UTC calendar day."""
    ensure_skill_trend_tables(conn)
    chosen = _parse_day(day)
    day_key = chosen.isoformat()

    rows = conn.execute(
        """
        SELECT
            js.skill_id AS skill_id,
            COALESCE(j.category, '') AS category,
            COALESCE(j.remote, 0) AS remote,
            COALESCE(j.relocation, 0) AS relocation,
            j.id AS job_id,
            COALESCE(j.salary, '') AS salary
        FROM job_skill js
        JOIN jobs j ON j.id = js.job_id
        WHERE j.status = 'published'
          AND COALESCE(j.hidden, 0) = 0
          AND substr(j.created_at, 1, 10) = ?
        """,
        (day_key,),
    ).fetchall()

    # Clear the day first so removed skills do not linger after re-aggregate.
    conn.execute("DELETE FROM skill_trend_daily WHERE day = ?", (day_key,))

    groups: dict[tuple[int, str, int, int], dict[str, Any]] = {}
    for row in rows:
        try:
            skill_id = int(_row_get(row, "skill_id", 0) or 0)
            category = str(_row_get(row, "category", 1) or "")
            remote = int(_row_get(row, "remote", 2) or 0)
            relocation = int(_row_get(row, "relocation", 3) or 0)
            job_id = int(_row_get(row, "job_id", 4) or 0)
            salary = str(_row_get(row, "salary", 5) or "")
        except (TypeError, ValueError):
            continue
        if skill_id <= 0 or job_id <= 0:
            continue
        key = (skill_id, category, remote, relocation)
        bucket = groups.get(key)
        if bucket is None:
            bucket = {"job_ids": set(), "parsed": []}
            groups[key] = bucket
        if job_id in bucket["job_ids"]:
            continue
        bucket["job_ids"].add(job_id)
        parsed = parse_salary_annual(salary)
        if parsed is not None:
            bucket["parsed"].append(parsed)

    sql = """
        INSERT INTO skill_trend_daily (
            day, skill_id, category, region, remote, relocation, ad_count,
            salary_median, salary_currency, salary_n, salary_low, salary_high
        ) VALUES (?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?)
    """
    written = 0
    for (skill_id, category, remote, relocation), bucket in groups.items():
        ad_count = len(bucket["job_ids"])
        if ad_count <= 0:
            continue
        currency, values = pick_currency_values(bucket["parsed"])
        stats = salary_stats(values, currency)
        conn.execute(
            sql,
            (
                day_key,
                skill_id,
                category,
                remote,
                relocation,
                ad_count,
                None if stats is None else stats["median"],
                "" if stats is None else stats["currency"],
                0 if stats is None else stats["n"],
                None if stats is None else stats["low"],
                None if stats is None else stats["high"],
            ),
        )
        written += 1

    _aggregate_skill_pairs(conn, day_key, rows)
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
