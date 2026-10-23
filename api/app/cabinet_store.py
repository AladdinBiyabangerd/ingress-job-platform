"""Employer ads in the shared jobs database.

The Mac file is the worker SQLite database. On Railway, DATABASE_URL is the
same Postgres database the worker writes.

Statuses stored on jobs.status:
- pending: a company ad waiting for moderation. Not public.
- published: live. Staff ads are written here immediately. An approved company
  ad uses this status too. The owner may edit it. Salary and job type stay
  published. Title, text, company, city or remote, and language move it back
  to pending until staff approves again.
- rejected: staff rejected it with a short reason. Not public. The owner sees
  the reason, can edit, and that save returns the ad to pending.
- closed: the owner or staff closed it. The row stays. It is not public.

Staff edits never change status. Staff-authored ads stay published.
Changing the application form does not change status, including after
publication. Answers already stored on an application are not rewritten.

Scraped rows keep an empty owner_subject. New scrapes are inserted as pending
and appear in the staff moderation queue until approved. hidden=1 or
merged_into takes a scraped row off the public list without deleting it.
Ordinary cabinet creates do not write a source URL.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from threading import Lock

from app.apply_form import default_form, dump_form, parse_stored

_LOCK = Lock()
_ENSURED: set[str] = set()

LANGS = {"az", "en", "ru"}
JOB_TYPES = {"", "ofis", "hibrid", "uzaqdan"}
PENDING = "pending"
PUBLISHED = "published"
REJECTED = "rejected"
CLOSED = "closed"

_JOBS = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL DEFAULT '',
    cleaned_text TEXT,
    status TEXT NOT NULL DEFAULT 'published',
    created_at TEXT NOT NULL,
    norm_key TEXT NOT NULL UNIQUE
)
"""

_SOURCES = """
CREATE TABLE IF NOT EXISTS job_sources (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    external_id TEXT NOT NULL DEFAULT '',
    last_seen TEXT NOT NULL,
    credit_note TEXT NOT NULL DEFAULT ''
)
"""

_COLUMNS = {
    # Source posting date (worker.posted); NULL = unknown, lists fall back to created_at.
    "posted_at": "TEXT",
    "owner_subject": "TEXT NOT NULL DEFAULT ''",
    "language": "TEXT NOT NULL DEFAULT ''",
    "salary": "TEXT NOT NULL DEFAULT ''",
    "job_type": "TEXT NOT NULL DEFAULT ''",
    "remote": "INTEGER NOT NULL DEFAULT 0",
    "updated_at": "TEXT NOT NULL DEFAULT ''",
    "reject_reason": "TEXT NOT NULL DEFAULT ''",
    "hidden": "INTEGER NOT NULL DEFAULT 0",
    "merged_into": "INTEGER",
    "content_locked": "INTEGER NOT NULL DEFAULT 0",
    "apply_form": "TEXT NOT NULL DEFAULT ''",
    # Written by the worker for collected ads: JSON list of tech names, and
    # 1 when the ad offers visa sponsorship or relocation support.
    "tech_stack": "TEXT NOT NULL DEFAULT ''",
    "relocation": "INTEGER NOT NULL DEFAULT 0",
    # Normalized tech category from the worker ("Backend", "QA", ...).
    "category": "TEXT NOT NULL DEFAULT ''",
    # Market-fit confidence for staff moderation (NULL = not set).
    "rule_confidence": "INTEGER",
    "ai_confidence": "INTEGER",
    "market_fit_reason": "TEXT NOT NULL DEFAULT ''",
    # JSON for the Moderasiya "AI %" popover (worker.market_fit.fit_detail).
    "market_fit_detail": "TEXT NOT NULL DEFAULT ''",
}

_APP_COLUMNS = {
    # Source posting date (worker.posted); NULL = unknown, lists fall back to created_at.
    "posted_at": "TEXT",
    "status": "TEXT NOT NULL DEFAULT 'submitted'",
    "decision_reason": "TEXT NOT NULL DEFAULT ''",
    "phone": "TEXT NOT NULL DEFAULT ''",
    "email": "TEXT NOT NULL DEFAULT ''",
    "answers": "TEXT NOT NULL DEFAULT '[]'",
}

# Same table the worker seeds from worker/worker/catalog.py. Only the homepage
# is read here, for the visible "source" link on collected ads.
_CRAWL_SOURCES = """
CREATE TABLE IF NOT EXISTS crawl_sources (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    homepage TEXT NOT NULL,
    connector TEXT NOT NULL,
    entry_url TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    min_delay_seconds REAL NOT NULL DEFAULT 1,
    go_decision TEXT NOT NULL DEFAULT 'pending',
    go_decided_by TEXT NOT NULL DEFAULT '',
    go_decided_at TEXT NOT NULL DEFAULT '',
    credit_note TEXT NOT NULL DEFAULT '',
    api_key_env TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT ''
)
"""

_MERGES = """
CREATE TABLE IF NOT EXISTS job_merges (
    id INTEGER PRIMARY KEY,
    kept_id INTEGER NOT NULL,
    hidden_id INTEGER NOT NULL UNIQUE,
    created_at TEXT NOT NULL
)
"""

_APPLICATIONS = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL,
    candidate_subject TEXT NOT NULL,
    message TEXT NOT NULL,
    cv_name TEXT NOT NULL DEFAULT '',
    cv_stored TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'submitted',
    decision_reason TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    answers TEXT NOT NULL DEFAULT '[]',
    UNIQUE (job_id, candidate_subject)
)
"""

_SAVED_JOBS = """
CREATE TABLE IF NOT EXISTS saved_jobs (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    job_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (user_id, job_id)
)
"""

_VIEWED_JOBS = """
CREATE TABLE IF NOT EXISTS viewed_jobs (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    job_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (user_id, job_id)
)
"""

_JOB_ORIGINAL_OPENS = """
CREATE TABLE IF NOT EXISTS job_original_opens (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    job_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (user_id, job_id)
)
"""


class CabinetError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(detail)


def _db_path() -> Path:
    from app.sqlite_jobs import DB_PATH

    return DB_PATH


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# One-time maintenance: hide the ads collected from the retired domestic
# sources. Uses the same jobs.hidden flag as the staff "hide" button, so staff
# still see these rows in the collected-ads admin and can unhide them. Rows are
# never deleted. Only collected rows (empty owner_subject) whose every source
# is a retired one are touched; cabinet/company ads and ads also seen on a
# current source are left alone. The marker row in maintenance_steps makes it
# run once per database, so a later unhide by staff is not undone.
# The same step lives in worker/worker/db.py (worker start); whichever process opens the database first
# does it.
RETIRED_LOCAL_SOURCES = (
    "Busy.az", "Boss.az", "HelloJob", "Glorri", "JobSearch.az",
    "HRX", "Work.az", "eJob.az", "hh1.az", "hh.ru",
)
HIDE_RETIRED_STEP = "hide-retired-local-sources-2026-10-05"
# One-shot: old crawled AI recheck hid unfit published ads (hidden=1, status
# stayed published). Move them to rejected so they appear on the Rejected tab.
# Same step in worker/worker/db.py; whichever process opens the DB first runs it.
SWEEP_AI_HIDDEN_STEP = "sweep-published-ai-hidden-to-rejected-2026-10-14"
# System hides that must not be treated as AI market-fit rejects.
_NON_AI_HIDE_REASONS = (
    "title_rule_2026_10_13",
    "expired_not_seen",
    "non_it_title",
)

_MAINTENANCE = """
CREATE TABLE IF NOT EXISTS maintenance_steps (
    name TEXT PRIMARY KEY,
    done_at TEXT NOT NULL
)
"""


def hide_retired_local(conn) -> int:
    """Hide collected ads from RETIRED_LOCAL_SOURCES once. Returns rows hidden
    (0 when the step already ran). The caller commits."""
    conn.execute(_MAINTENANCE)
    done = conn.execute(
        "SELECT 1 FROM maintenance_steps WHERE name = ?", (HIDE_RETIRED_STEP,)
    ).fetchone()
    if done:
        return 0
    names = [name.lower() for name in RETIRED_LOCAL_SOURCES]
    marks = ", ".join("?" for _ in names)
    where = f"""
        WHERE COALESCE(j.owner_subject, '') = ''
          AND COALESCE(j.hidden, 0) = 0
          AND j.id IN (
              SELECT js.job_id FROM job_sources js WHERE LOWER(js.source_name) IN ({marks})
          )
          AND j.id NOT IN (
              SELECT js.job_id FROM job_sources js WHERE LOWER(js.source_name) NOT IN ({marks})
          )
    """
    ids = [int(row[0]) for row in conn.execute(f"SELECT j.id FROM jobs j {where}", names + names).fetchall()]
    for start in range(0, len(ids), 200):
        chunk = ids[start:start + 200]
        conn.execute(
            f"UPDATE jobs SET hidden = 1 WHERE id IN ({', '.join('?' for _ in chunk)})",
            chunk,
        )
    conn.execute(
        "INSERT INTO maintenance_steps (name, done_at) VALUES (?, ?) ON CONFLICT (name) DO NOTHING",
        (HIDE_RETIRED_STEP, datetime.now().astimezone().isoformat(timespec="seconds")),
    )
    return len(ids)


def sweep_published_ai_hidden_to_rejected(conn) -> int:
    """One-off: published+hidden scraped ads from the old AI recheck path → rejected.

    Fingerprint matches the former write: scraped, still published, hidden=1,
    ai_confidence set, reject_reason + market_fit_reason from the unfit verdict.
    Clears hidden (public board already excludes non-published). Returns rows
    updated (0 when the step already ran). The caller commits.
    """
    conn.execute(_MAINTENANCE)
    done = conn.execute(
        "SELECT 1 FROM maintenance_steps WHERE name = ?", (SWEEP_AI_HIDDEN_STEP,)
    ).fetchone()
    if done:
        return 0
    exclude = ", ".join("?" for _ in _NON_AI_HIDE_REASONS)
    ids = [
        int(row[0])
        for row in conn.execute(
            f"""
            SELECT id FROM jobs
            WHERE status = ?
              AND COALESCE(hidden, 0) = 1
              AND COALESCE(owner_subject, '') = ''
              AND merged_into IS NULL
              AND ai_confidence IS NOT NULL
              AND TRIM(COALESCE(reject_reason, '')) != ''
              AND TRIM(COALESCE(market_fit_reason, '')) != ''
              AND COALESCE(reject_reason, '') NOT IN ({exclude})
            """,
            (PUBLISHED, *_NON_AI_HIDE_REASONS),
        ).fetchall()
    ]
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    for start in range(0, len(ids), 200):
        chunk = ids[start : start + 200]
        marks = ", ".join("?" for _ in chunk)
        conn.execute(
            f"""
            UPDATE jobs
            SET status = ?, hidden = 0, updated_at = ?
            WHERE id IN ({marks})
            """,
            (REJECTED, now, *chunk),
        )
    conn.execute(
        "INSERT INTO maintenance_steps (name, done_at) VALUES (?, ?) ON CONFLICT (name) DO NOTHING",
        (SWEEP_AI_HIDDEN_STEP, now),
    )
    return len(ids)


def _apply_schema(conn) -> None:
    conn.execute(_JOBS)
    conn.execute(_SOURCES)
    conn.execute(_CRAWL_SOURCES)
    conn.execute(_MERGES)
    conn.execute(_APPLICATIONS)
    conn.execute(_SAVED_JOBS)
    conn.execute(_VIEWED_JOBS)
    conn.execute(_JOB_ORIGINAL_OPENS)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
    for name, decl in _COLUMNS.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {decl}")
    app_cols = {row[1] for row in conn.execute("PRAGMA table_info(applications)")}
    for name, decl in _APP_COLUMNS.items():
        if name not in app_cols:
            conn.execute(f"ALTER TABLE applications ADD COLUMN {name} {decl}")
    conn.execute("CREATE INDEX IF NOT EXISTS jobs_owner ON jobs(owner_subject)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS jobs_public_list ON jobs(status, hidden, merged_into, created_at, id)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS job_sources_job ON job_sources(job_id, id)")
    conn.execute("CREATE INDEX IF NOT EXISTS applications_job ON applications(job_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS applications_candidate ON applications(candidate_subject)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS saved_jobs_user ON saved_jobs(user_id, id)")
    conn.execute("CREATE INDEX IF NOT EXISTS saved_jobs_job ON saved_jobs(job_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS viewed_jobs_user ON viewed_jobs(user_id, id)")
    conn.execute("CREATE INDEX IF NOT EXISTS viewed_jobs_job ON viewed_jobs(job_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS job_original_opens_job ON job_original_opens(job_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS job_original_opens_user ON job_original_opens(user_id)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY,
            recipient_subject TEXT NOT NULL,
            kind TEXT NOT NULL,
            job_id INTEGER,
            job_title TEXT NOT NULL DEFAULT '',
            application_id INTEGER,
            status TEXT NOT NULL DEFAULT '',
            reason TEXT NOT NULL DEFAULT '',
            language TEXT NOT NULL DEFAULT '',
            read_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT ''
        )
        """
    )
    note_cols = {row[1] for row in conn.execute("PRAGMA table_info(notifications)")}
    if "payload" not in note_cols:
        conn.execute(
            "ALTER TABLE notifications ADD COLUMN payload TEXT NOT NULL DEFAULT ''"
        )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS notifications_recipient ON notifications(recipient_subject, id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS notifications_recipient_created"
        " ON notifications(recipient_subject, created_at)"
    )
    # Same skill/role tables the worker seeds (worker/worker/skills.py, roles.py).
    # API only ensures they exist when it opens the shared database first.
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS skill_dictionary (
            id INTEGER PRIMARY KEY,
            canonical_name TEXT NOT NULL UNIQUE,
            synonyms TEXT NOT NULL DEFAULT '[]',
            category_hint TEXT NOT NULL DEFAULT '',
            academy_course_ids TEXT NOT NULL DEFAULT '[]',
            updated_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS job_skill (
            job_id INTEGER NOT NULL REFERENCES jobs(id),
            skill_id INTEGER NOT NULL REFERENCES skill_dictionary(id),
            source TEXT NOT NULL DEFAULT 'tech_stack',
            PRIMARY KEY (job_id, skill_id)
        );
        CREATE TABLE IF NOT EXISTS role_taxonomy (
            id INTEGER PRIMARY KEY,
            canonical_name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            synonyms TEXT NOT NULL DEFAULT '[]',
            academy_career_path_id TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS role_skill_weight (
            role_id INTEGER NOT NULL REFERENCES role_taxonomy(id),
            skill_id INTEGER NOT NULL REFERENCES skill_dictionary(id),
            weight REAL NOT NULL,
            group_key TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (role_id, skill_id)
        );
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
    trend_cols = {row[1] for row in conn.execute("PRAGMA table_info(skill_trend_daily)")}
    for name, decl in (
        ("salary_currency", "TEXT NOT NULL DEFAULT ''"),
        ("salary_n", "INTEGER NOT NULL DEFAULT 0"),
        ("salary_low", "REAL"),
        ("salary_high", "REAL"),
        ("salary_by_currency", "TEXT NOT NULL DEFAULT '[]'"),
    ):
        if name not in trend_cols:
            conn.execute(f"ALTER TABLE skill_trend_daily ADD COLUMN {name} {decl}")
    role_cols = {row[1] for row in conn.execute("PRAGMA table_info(role_taxonomy)")}
    if "academy_career_path_id" not in role_cols:
        conn.execute(
            "ALTER TABLE role_taxonomy ADD COLUMN academy_career_path_id TEXT NOT NULL DEFAULT ''"
        )
    weight_cols = {row[1] for row in conn.execute("PRAGMA table_info(role_skill_weight)")}
    if "group_key" not in weight_cols:
        conn.execute(
            "ALTER TABLE role_skill_weight ADD COLUMN group_key TEXT NOT NULL DEFAULT ''"
        )
    conn.execute("CREATE INDEX IF NOT EXISTS job_skill_skill ON job_skill(skill_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS job_skill_job ON job_skill(job_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS role_taxonomy_category ON role_taxonomy(category)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS role_skill_weight_skill ON role_skill_weight(skill_id)"
    )
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
    # Same parse_cv_queue / candidate_profile tables the worker drains
    # (worker/worker/cv_queue.py). API ensures they exist when it opens first.
    from app.cv_queue import ensure_cv_queue_tables
    from app.consents import ensure_consent_tables
    from app.email_prefs import ensure_email_tables
    from app.engagement import ensure_engagement_tables

    ensure_cv_queue_tables(conn)
    ensure_consent_tables(conn)
    ensure_email_tables(conn)
    ensure_engagement_tables(conn)
    from app.matching import ensure_match_tables

    ensure_match_tables(conn)
    try:
        from app.embeddings import ensure_embedding_tables

        ensure_embedding_tables(conn)
    except Exception:
        pass
    hide_retired_local(conn)
    sweep_published_ai_hidden_to_rejected(conn)
    try:
        from worker.market_fit import ensure_rejects_table

        ensure_rejects_table(conn)
    except Exception:
        pass
    conn.commit()


def ensure_schema(*, create: bool = False) -> None:
    from app.jobs_db import connect, postgres_enabled

    if postgres_enabled():
        key = "postgres"
        if key in _ENSURED:
            return
        conn = connect()
        try:
            _apply_schema(conn)
        finally:
            conn.close()
        _ENSURED.add(key)
        return
    path = _db_path()
    key = str(path)
    if key in _ENSURED and path.is_file():
        return
    if not path.is_file():
        if not create:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5)
    try:
        _apply_schema(conn)
    finally:
        conn.close()
    _ENSURED.add(key)


def _connect():
    ensure_schema(create=True)
    from app.jobs_db import connect, postgres_enabled

    if postgres_enabled():
        return connect()
    conn = sqlite3.connect(_db_path(), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _score_or_none(row: sqlite3.Row, key: str) -> int | None:
    if key not in set(row.keys()):
        return None
    raw = row[key]
    if raw is None:
        return None
    try:
        return max(0, min(100, int(raw)))
    except (TypeError, ValueError):
        return None


def _owner(row: sqlite3.Row) -> dict:
    keys = set(row.keys())
    payload = {
        "id": int(row["id"]),
        "title": row["title"] or "",
        "company": row["company"] or "",
        "city": row["city"] or "",
        "remote": bool(int(row["remote"] or 0)),
        "text": row["text"] or "",
        "language": row["language"] or "",
        "salary": row["salary"] or "",
        "job_type": row["job_type"] or "",
        "status": row["status"] or "",
        "created_at": row["created_at"] or "",
        "updated_at": row["updated_at"] or "",
        "reject_reason": (row["reject_reason"] or "") if "reject_reason" in keys else "",
        "form": parse_stored(row["apply_form"] if "apply_form" in keys else ""),
    }
    if "owner_subject" in keys:
        payload["owner_subject"] = row["owner_subject"] or ""
    if "source_name" in keys:
        payload["source_name"] = row["source_name"] or ""
    if "source_url" in keys:
        payload["source_url"] = row["source_url"] or ""
    if "rule_confidence" in keys:
        payload["rule_confidence"] = _score_or_none(row, "rule_confidence")
    if "ai_confidence" in keys:
        payload["ai_confidence"] = _score_or_none(row, "ai_confidence")
    if "market_fit_reason" in keys:
        payload["market_fit_reason"] = row["market_fit_reason"] or ""
    if "market_fit_detail" in keys:
        payload["market_fit_detail"] = fit_detail_payload(row["market_fit_detail"])
    return payload


def fit_detail_payload(raw) -> dict | None:
    """Stored market_fit_detail JSON -> dict for the admin popover (None when absent/bad)."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def list_owned(subject: str) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT id, title, company, city, remote, text, language, salary,
                   job_type, status, created_at, updated_at, reject_reason, apply_form
            FROM jobs
            WHERE owner_subject = ? AND owner_subject != ''
            ORDER BY id DESC
            """,
            (subject,),
        ).fetchall()
    finally:
        conn.close()
    return [_owner(row) for row in rows]


def _insert(subject: str, fields: dict, status: str) -> dict:
    now = _now()
    key = f"cabinet:{subject}:{uuid.uuid4().hex}"
    conn = _connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, cleaned_text, status, created_at, norm_key,
                owner_subject, language, salary, job_type, remote, updated_at, apply_form
            ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fields["title"],
                fields["company"],
                fields["city"],
                fields["text"],
                status,
                now,
                key,
                subject,
                fields["language"],
                fields["salary"],
                fields["job_type"],
                1 if fields["remote"] else 0,
                now,
                dump_form(fields.get("form") or default_form()),
            ),
        )
        conn.commit()
        job_id = int(cur.lastrowid)
        row = conn.execute(
            """
            SELECT id, title, company, city, remote, text, language, salary,
                   job_type, status, created_at, updated_at, reject_reason, apply_form
            FROM jobs WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
    finally:
        conn.close()
    return _owner(row)


def count_ads_created_since(subject: str, since_iso: str) -> int:
    """Count owner-created ads with created_at >= since_iso (ISO-ish string compare)."""
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n FROM jobs
            WHERE owner_subject = ? AND owner_subject != ''
              AND created_at >= ?
            """,
            (subject, since_iso),
        ).fetchone()
    finally:
        conn.close()
    return int(row["n"] if row and row["n"] is not None else 0)


def create_ad(subject: str, fields: dict, *, staff: bool) -> dict:
    with _LOCK:
        return _insert(subject, fields, PUBLISHED if staff else PENDING)


def _owned_row(conn: sqlite3.Connection, subject: str, job_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, title, company, city, remote, text, language, salary,
               job_type, status, created_at, updated_at, reject_reason, apply_form, owner_subject
        FROM jobs
        WHERE id = ? AND owner_subject = ? AND owner_subject != ''
        """,
        (job_id, subject),
    ).fetchone()


def _significant(row: sqlite3.Row, fields: dict) -> bool:
    city = row["city"] or ""
    remote = bool(int(row["remote"] or 0))
    return any(
        (
            (row["title"] or "") != fields["title"],
            (row["company"] or "") != fields["company"],
            city != fields["city"],
            remote != bool(fields["remote"]),
            (row["text"] or "") != fields["text"],
            (row["language"] or "") != fields["language"],
        )
    )


def update_ad(subject: str, job_id: int, fields: dict, *, staff: bool) -> dict:
    note = None
    with _LOCK:
        conn = _connect()
        try:
            row = _owned_row(conn, subject, job_id)
            if row is None:
                raise CabinetError(404, "Elan tapılmadı")
            status = row["status"] or ""
            if status == CLOSED:
                raise CabinetError(409, "Bağlanmış elan dəyişdirilə bilməz")
            next_status = status
            reason = row["reject_reason"] or ""
            if not staff:
                if status == REJECTED:
                    next_status = PENDING
                    reason = ""
                elif status == PUBLISHED and _significant(row, fields):
                    next_status = PENDING
                    reason = ""
                elif status not in {PENDING, PUBLISHED}:
                    raise CabinetError(403, "Təsdiqlənmiş elan dəyişdirilə bilməz")
            form = fields["form"] if "form" in fields else parse_stored(row["apply_form"])
            conn.execute(
                """
                UPDATE jobs
                SET title = ?, company = ?, city = ?, text = ?, cleaned_text = NULL,
                    language = ?, salary = ?, job_type = ?, remote = ?, updated_at = ?,
                    status = ?, reject_reason = ?, apply_form = ?
                WHERE id = ?
                """,
                (
                    fields["title"],
                    fields["company"],
                    fields["city"],
                    fields["text"],
                    fields["language"],
                    fields["salary"],
                    fields["job_type"],
                    1 if fields["remote"] else 0,
                    _now(),
                    next_status,
                    reason,
                    dump_form(form),
                    job_id,
                ),
            )
            note = None
            if not staff and status == PUBLISHED and next_status == PENDING:
                from app.notifications import insert_notification

                note = insert_notification(
                    conn,
                    recipient=subject,
                    kind="ad_review",
                    job_id=job_id,
                    job_title=fields["title"],
                    application_id=None,
                    status=PENDING,
                    reason="",
                    language=fields["language"],
                )
            conn.commit()
            saved = _owned_row(conn, subject, job_id)
        finally:
            conn.close()
    if note:
        from app.notifications import deliver_email

        deliver_email(note)
    return _owner(saved)


def close_ad(subject: str, job_id: int) -> dict:
    with _LOCK:
        conn = _connect()
        try:
            row = _owned_row(conn, subject, job_id)
            if row is None:
                raise CabinetError(404, "Elan tapılmadı")
            if (row["status"] or "") != CLOSED:
                conn.execute(
                    "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
                    (CLOSED, _now(), job_id),
                )
                conn.commit()
                row = _owned_row(conn, subject, job_id)
        finally:
            conn.close()
    return _owner(row)


_MOD_COLS = """
    id, title, company, city, remote, text, language, salary,
    job_type, status, created_at, updated_at, reject_reason, apply_form, owner_subject,
    rule_confidence, ai_confidence, market_fit_reason, market_fit_detail
"""


def _cabinet_row(conn: sqlite3.Connection, job_id: int) -> sqlite3.Row | None:
    return conn.execute(
        f"""
        SELECT {_MOD_COLS}
        FROM jobs
        WHERE id = ? AND owner_subject != ''
        """,
        (job_id,),
    ).fetchone()


def _moderation_row(conn: sqlite3.Connection, job_id: int) -> sqlite3.Row | None:
    """Company ads, or scraped ads that are pending or staff-rejected."""
    return conn.execute(
        f"""
        SELECT {_MOD_COLS}
        FROM jobs
        WHERE id = ?
          AND (
            owner_subject != ''
            OR (COALESCE(owner_subject, '') = '' AND status IN (?, ?))
          )
        """,
        (job_id, PENDING, REJECTED),
    ).fetchone()


_MOD_SOURCE_JOIN = """
LEFT JOIN (
    SELECT job_id, source_name, source_url
    FROM job_sources
    WHERE id IN (SELECT MIN(id) FROM job_sources GROUP BY job_id)
) js ON js.job_id = j.id
"""


def list_moderation() -> list[dict]:
    """Pending company and scraped ads first, then other company statuses.

    Scraped rows appear while pending or staff-rejected. List rows omit
    body text; edit loads the full ad via get_moderation. Staff-only:
    includes the first crawl source_url when present (empty for
    company-only ads).
    """
    conn = _connect()
    try:
        rows = conn.execute(
            f"""
            SELECT j.id, j.title, j.company, j.city, j.remote,
                   '' AS text,
                   j.language, j.salary,
                   j.job_type, j.status, j.created_at, j.updated_at, j.reject_reason,
                   '' AS apply_form, j.owner_subject,
                   j.rule_confidence, j.ai_confidence,
                   COALESCE(j.market_fit_reason, '') AS market_fit_reason,
                   COALESCE(j.market_fit_detail, '') AS market_fit_detail,
                   COALESCE(js.source_name, '') AS source_name,
                   COALESCE(js.source_url, '') AS source_url
            FROM jobs j
            {_MOD_SOURCE_JOIN}
            WHERE j.owner_subject != ''
               OR (COALESCE(j.owner_subject, '') = '' AND j.status IN (?, ?))
            ORDER BY
                CASE j.status
                    WHEN 'pending' THEN 0
                    WHEN 'published' THEN 1
                    WHEN 'closed' THEN 2
                    WHEN 'rejected' THEN 3
                    ELSE 4
                END,
                j.id DESC
            """,
            (PENDING, REJECTED),
        ).fetchall()
    finally:
        conn.close()
    return [_owner(row) for row in rows]


def _score_passes(value: int | None, op: str, cut: int) -> bool:
    if value is None:
        return False
    return value <= cut if op == "lte" else value >= cut


def pending_ids_by_list_filter(
    *,
    ai_op: str = "gte",
    ai_value: int | None = None,
    rule_op: str = "gte",
    rule_value: int | None = None,
    source: str = "",
    limit: int | None = None,
) -> list[int]:
    """Pending ad ids matching the staff queue list filter, in table order (newest first).

    Mirrors ``frontend/lib/admin-list-filter.js``: a set AI/rule cut drops rows
    without that score; ``source`` is a case-insensitive substring of the first
    source name or URL.
    """
    needle = (source or "").strip().lower()
    conn = _connect()
    try:
        rows = conn.execute(
            f"""
            SELECT j.id, j.rule_confidence, j.ai_confidence,
                   COALESCE(js.source_name, '') AS source_name,
                   COALESCE(js.source_url, '') AS source_url
            FROM jobs j
            {_MOD_SOURCE_JOIN}
            WHERE j.status = ?
            ORDER BY j.id DESC
            """,
            (PENDING,),
        ).fetchall()
    finally:
        conn.close()
    out: list[int] = []
    for row in rows:
        if ai_value is not None and not _score_passes(
            _score_or_none(row, "ai_confidence"), ai_op, int(ai_value)
        ):
            continue
        if rule_value is not None and not _score_passes(
            _score_or_none(row, "rule_confidence"), rule_op, int(rule_value)
        ):
            continue
        if needle:
            name = str(row["source_name"] or "").lower()
            url = str(row["source_url"] or "").lower()
            if needle not in name and needle not in url:
                continue
        out.append(int(row["id"]))
        if limit is not None and len(out) >= limit:
            break
    return out


def get_moderation(job_id: int) -> dict:
    conn = _connect()
    try:
        row = _moderation_row(conn, job_id)
    finally:
        conn.close()
    if row is None:
        raise CabinetError(404, "Elan tapılmadı")
    return _owner(row)


def _approve_one(conn: sqlite3.Connection, job_id: int) -> tuple[sqlite3.Row, dict | None]:
    row = _moderation_row(conn, job_id)
    if row is None:
        raise CabinetError(404, "Elan tapılmadı")
    if (row["status"] or "") not in (PENDING, REJECTED):
        raise CabinetError(409, "Yalnız gözləyən və ya rədd olunmuş elan təsdiqlənə bilər")
    conn.execute(
        """
        UPDATE jobs
        SET status = ?, reject_reason = '', updated_at = ?
        WHERE id = ?
        """,
        (PUBLISHED, _now(), job_id),
    )
    row = conn.execute(
        f"SELECT {_MOD_COLS} FROM jobs WHERE id = ?",
        (job_id,),
    ).fetchone()
    owner = (row["owner_subject"] or "").strip()
    note = None
    if owner:
        from app.notifications import insert_notification

        note = insert_notification(
            conn,
            recipient=owner,
            kind="ad_approved",
            job_id=job_id,
            job_title=row["title"] or "",
            application_id=None,
            status=PUBLISHED,
            reason="",
            language=row["language"] or "",
        )
    return row, note


def approve_ad(job_id: int) -> dict:
    note = None
    with _LOCK:
        conn = _connect()
        try:
            row, note = _approve_one(conn, job_id)
            conn.commit()
        finally:
            conn.close()
    if note:
        from app.notifications import deliver_email

        deliver_email(note)
    return _owner(row)


def approve_ads(job_ids: list[int], *, max_ids: int | None = 200) -> dict:
    """Approve many pending/rejected ads. Skips unknown/other statuses without failing.

    ``max_ids`` caps checkbox bulk (default 200). Pass ``None`` for threshold
    publish of every matching row.
    """
    seen: set[int] = set()
    ordered: list[int] = []
    for raw in job_ids:
        try:
            job_id = int(raw)
        except (TypeError, ValueError):
            continue
        if job_id <= 0 or job_id in seen:
            continue
        seen.add(job_id)
        ordered.append(job_id)
    if max_ids is not None and len(ordered) > max_ids:
        raise CabinetError(422, f"Birdən çox {max_ids} elan seçilə bilər")
    notes: list[dict] = []
    approved: list[dict] = []
    with _LOCK:
        conn = _connect()
        try:
            for job_id in ordered:
                row = _moderation_row(conn, job_id)
                if row is None or (row["status"] or "") not in (PENDING, REJECTED):
                    continue
                row, note = _approve_one(conn, job_id)
                approved.append(_owner(row))
                if note:
                    notes.append(note)
            conn.commit()
        finally:
            conn.close()
    if notes:
        from app.notifications import deliver_email

        for note in notes:
            deliver_email(note)
    return {"approved": len(approved), "items": approved}


def _score_column(score: str) -> str:
    if score == "ai":
        return "ai_confidence"
    if score == "rule":
        return "rule_confidence"
    raise CabinetError(422, "Skor ai və ya rule olmalıdır")


def _threshold_match(
    value: int | None, op: str, threshold: int, *, include_unscored: bool = False
) -> bool:
    if value is None:
        # Never-scored rows only join «≤ N» when the caller asks (AI re-check):
        # «not checked yet» sits below every percent. Publish/reject keep them out.
        return include_unscored and op == "lte"
    if op == "gte":
        return value >= threshold
    if op == "lte":
        return value <= threshold
    raise CabinetError(422, "Operator gte və ya lte olmalıdır")


def _ids_by_threshold(
    conn: sqlite3.Connection,
    *,
    score: str,
    op: str,
    threshold: int,
    status: str = PENDING,
    limit: int | None = None,
    min_score: int | None = None,
    max_score: int | None = None,
    include_unscored: bool = False,
) -> list[int]:
    col = _score_column(score)
    if op not in ("gte", "lte"):
        raise CabinetError(422, "Operator gte və ya lte olmalıdır")
    if threshold < 0 or threshold > 100:
        raise CabinetError(422, "Faiz 0–100 arasında olmalıdır")
    if status not in (PENDING, REJECTED):
        raise CabinetError(422, "Status pending və ya rejected olmalıdır")
    if limit is not None and (limit < 1 or limit > 200):
        raise CabinetError(422, "Limit 1–200 arasında olmalıdır")
    rows = conn.execute(
        f"""
        SELECT id, {col} AS score
        FROM jobs
        WHERE status = ?
          AND (
            owner_subject != ''
            OR COALESCE(owner_subject, '') = ''
          )
        ORDER BY id DESC
        """,
        (status,),
    ).fetchall()
    matched: list[int] = []
    for row in rows:
        value = _score_or_none(row, "score")
        if min_score is not None or max_score is not None:
            if value is None:
                continue
            if min_score is not None and value < min_score:
                continue
            if max_score is not None and value > max_score:
                continue
        elif not _threshold_match(value, op, threshold, include_unscored=include_unscored):
            continue
        matched.append(int(row["id"]))
        if limit is not None and len(matched) >= limit:
            break
    return matched


def approve_ads_by_threshold(
    *,
    score: str,
    op: str,
    threshold: int,
    status: str = PENDING,
) -> dict:
    """Publish every pending/rejected ad whose rule/AI confidence matches the threshold."""
    with _LOCK:
        conn = _connect()
        try:
            ids = _ids_by_threshold(
                conn,
                score=score,
                op=op,
                threshold=threshold,
                status=status,
                limit=None,
            )
        finally:
            conn.close()
    return approve_ads(ids, max_ids=None)


def pending_ids_by_threshold(
    *, score: str, op: str, threshold: int, include_unscored: bool = False
) -> list[int]:
    """Pending queue ad ids whose AI/rule percent matches op+threshold (newest first).

    Same match as «Faizə görə dərc et»: rows without that score never match,
    unless ``include_unscored`` — then they also match «≤ N» (AI re-check of
    ads the AI has not scored yet, shown as «—»).
    """
    with _LOCK:
        conn = _connect()
        try:
            return _ids_by_threshold(
                conn,
                score=score,
                op=op,
                threshold=threshold,
                status=PENDING,
                include_unscored=include_unscored,
            )
        finally:
            conn.close()


def _threshold_reject_reason(score: str, op: str, threshold: int) -> str:
    kind = "AI" if score == "ai" else "Qayda"
    sign = "≤" if op == "lte" else "≥"
    return f"Faizə görə toplu rədd: {kind} {sign} {threshold}%"


def reject_ads_by_threshold(
    *,
    score: str,
    op: str,
    threshold: int,
    reason: str = "",
) -> dict:
    """Reject every pending ad whose AI/rule percent matches the threshold.

    Mirrors ``reject_ad`` per row (reason stored, owner notified) in one
    transaction; emails go out after commit. Non-pending rows are untouched.
    """
    cleaned = " ".join((reason or "").split())
    if len(cleaned) > 400:
        raise CabinetError(422, "Rədd səbəbi 400 simvoldan uzun ola bilməz")
    notes: list[dict] = []
    rejected: list[int] = []
    with _LOCK:
        conn = _connect()
        try:
            ids = _ids_by_threshold(
                conn,
                score=score,
                op=op,
                threshold=threshold,
                status=PENDING,
            )
            why = cleaned or _threshold_reject_reason(score, op, threshold)
            now = _now()
            for job_id in ids:
                updated = conn.execute(
                    """
                    UPDATE jobs
                    SET status = ?, reject_reason = ?, updated_at = ?
                    WHERE id = ? AND status = ?
                    """,
                    (REJECTED, why, now, job_id, PENDING),
                )
                if not updated.rowcount:
                    continue
                rejected.append(job_id)
                row = conn.execute(
                    f"SELECT {_MOD_COLS} FROM jobs WHERE id = ?",
                    (job_id,),
                ).fetchone()
                owner = (row["owner_subject"] or "").strip() if row is not None else ""
                if owner:
                    from app.notifications import insert_notification

                    note = insert_notification(
                        conn,
                        recipient=owner,
                        kind="ad_rejected",
                        job_id=job_id,
                        job_title=row["title"] or "",
                        application_id=None,
                        status=REJECTED,
                        reason=why,
                        language=row["language"] or "",
                    )
                    if note:
                        notes.append(note)
            conn.commit()
        finally:
            conn.close()
    if notes:
        from app.notifications import deliver_email

        for note in notes:
            deliver_email(note)
    return {"rejected": len(rejected), "ids": rejected}


def _recheck_eligible(row: sqlite3.Row, *, scope: str) -> bool:
    status = row["status"] or ""
    if scope == "queue":
        return status == PENDING
    if (row["owner_subject"] or "") != "" or row["merged_into"]:
        return False
    if scope == "crawl_rejects":
        # Purge / AI skip list may still point at hidden rows.
        return status in (PENDING, PUBLISHED, REJECTED)
    if int(row["hidden"] or 0) == 1:
        return False
    return status in (PENDING, PUBLISHED, REJECTED)


def _touch_crawl_reject_reason(conn: sqlite3.Connection, job_id: int, reason: str) -> None:
    """Refresh crawl_rejects.reason for URLs of this job (keep URL skip)."""
    from worker.market_fit import mark_rejected

    urls = conn.execute(
        """
        SELECT source_url FROM job_sources
        WHERE job_id = ? AND TRIM(COALESCE(source_url, '')) != ''
        """,
        (job_id,),
    ).fetchall()
    for url_row in urls:
        url = str(url_row["source_url"] or "").strip()
        if not url:
            continue
        exists = conn.execute(
            "SELECT 1 FROM crawl_rejects WHERE source_url = ?",
            (url,),
        ).fetchone()
        if exists:
            mark_rejected(conn, url, reason or "unsuitable", via_ai=True)


def recheck_one(job_id: int, *, scope: str = "queue", fresh: bool = False) -> str:
    """Re-run market_fit on one ad. Returns outcome token for job counters.

    ``fresh=True`` (staff «AI ilə yenidən yoxla») asks the AI again instead of
    reusing the cached answer for the same prompt; budget/cost limits still apply.

    Outcomes: checked | rejected | failed | skipped
    ``checked`` = AI answered suitable (scores updated), or already-rejected
    score refresh.
    ``rejected`` = AI answered unsuitable → status rejected (pending or
    published crawled ads). Counted as AI success.
    """
    from worker.market_fit import checked_verdict, store_fit_detail

    if scope not in ("queue", "crawled", "crawl_rejects"):
        return "skipped"

    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT id, title, company, city, text, status,
                       COALESCE((SELECT s.source_url FROM job_sources s WHERE s.job_id = jobs.id
                                 ORDER BY s.id LIMIT 1), '') AS source_url,
                       remote, relocation,
                       COALESCE(owner_subject, '') AS owner_subject,
                       COALESCE(hidden, 0) AS hidden,
                       merged_into
                FROM jobs WHERE id = ?
                """,
                (job_id,),
            ).fetchone()
            if row is None or not _recheck_eligible(row, scope=scope):
                return "skipped"
            snap = {
                "id": int(row["id"]),
                "title": row["title"] or "",
                "company": row["company"] or "",
                "city": row["city"] or "",
                "text": row["text"] or "",
                "source_url": row["source_url"] or "",
                "remote": bool(int(row["remote"] or 0)) or None,
                "relocation": bool(int(row["relocation"] or 0)) or None,
            }
        finally:
            conn.close()

    conn = _connect()
    try:
        verdict = checked_verdict(
            title=snap["title"],
            company=snap["company"],
            place=snap["city"],
            text=snap["text"],
            conn=conn,
            source_url=snap["source_url"],
            source_remote=snap["remote"],
            source_relocation=snap["relocation"],
            **({"fresh": True} if fresh else {}),
        )
    finally:
        conn.close()
    if verdict is None:
        return "failed"

    reason = str(verdict.get("reason") or "")[:800]
    confidence = int(verdict.get("confidence") or 0)
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT status, COALESCE(owner_subject, '') AS owner_subject,
                       COALESCE(hidden, 0) AS hidden, merged_into
                FROM jobs WHERE id = ?
                """,
                (job_id,),
            ).fetchone()
            if row is None or not _recheck_eligible(row, scope=scope):
                return "skipped"
            store_fit_detail(conn, job_id, verdict)  # committed with the score below
            status = row["status"] or ""
            if not verdict.get("suitable") and not verdict.get("unclear"):
                # Pending/published → rejected (shows on Rejected tab). Already
                # rejected → refresh scores only. Do not only-hide published.
                # crawl_rejects scope: score refresh + keep URL skip (hidden OK).
                if status == REJECTED or scope == "crawl_rejects":
                    conn.execute(
                        """
                        UPDATE jobs
                        SET rule_confidence = NULL, ai_confidence = ?,
                            market_fit_reason = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (confidence, reason, _now(), job_id),
                    )
                    if scope == "crawl_rejects" and status != REJECTED:
                        conn.execute(
                            """
                            UPDATE jobs
                            SET status = ?, reject_reason = ?
                            WHERE id = ? AND status != ?
                            """,
                            (REJECTED, (reason or "unsuitable")[:300], job_id, REJECTED),
                        )
                    if scope == "crawl_rejects":
                        _touch_crawl_reject_reason(conn, job_id, reason)
                    conn.commit()
                    return "checked" if status == REJECTED else "rejected"
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = ?, reject_reason = ?, rule_confidence = NULL,
                        ai_confidence = ?, market_fit_reason = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        REJECTED,
                        (reason or "unsuitable")[:300],
                        confidence,
                        reason,
                        _now(),
                        job_id,
                    ),
                )
                conn.commit()
                return "rejected"
            if verdict.get("unclear"):
                # No evidence either way (40%): keep source flags, staff decides.
                conn.execute(
                    """
                    UPDATE jobs
                    SET ai_confidence = ?, market_fit_reason = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (confidence, reason, _now(), job_id),
                )
                conn.commit()
                return "checked"
            remote = 1 if verdict.get("remote") else 0
            relocation = 1 if verdict.get("relocation") else 0
            conn.execute(
                """
                UPDATE jobs
                SET remote = ?, relocation = ?, ai_confidence = ?,
                    market_fit_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (remote, relocation, confidence, reason, _now(), job_id),
            )
            conn.commit()
            return "checked"
        finally:
            conn.close()


def recheck_market_fit(job_ids: list[int], *, scope: str = "queue") -> dict:
    """Sync batch helper (tests). Prefer start_recheck_job + poll in the UI."""
    if scope not in ("queue", "crawled", "crawl_rejects"):
        raise CabinetError(422, "scope queue, crawled və ya crawl_rejects olmalıdır")
    seen: set[int] = set()
    ordered: list[int] = []
    for raw in job_ids:
        try:
            job_id = int(raw)
        except (TypeError, ValueError):
            continue
        if job_id <= 0 or job_id in seen:
            continue
        seen.add(job_id)
        ordered.append(job_id)
    if not ordered:
        raise CabinetError(422, "Elan seçilməyib")
    if len(ordered) > 25:
        raise CabinetError(422, "Bir sorğuda ən çox 25 elan yoxlanıla bilər")

    checked = 0
    rejected = 0
    hidden = 0
    failed = 0
    skipped = 0
    for job_id in ordered:
        outcome = recheck_one(job_id, scope=scope)
        if outcome == "checked":
            checked += 1
        elif outcome == "rejected":
            checked += 1
            rejected += 1
        elif outcome == "hidden":
            checked += 1
            hidden += 1
        elif outcome == "failed":
            failed += 1
        else:
            skipped += 1
    return {
        "checked": checked,
        "rejected": rejected,
        "hidden": hidden,
        "failed": failed,
        "skipped": skipped,
        "requested": len(ordered),
        "items": [],
    }


def backfill_moderation_confidence(*, ai_limit: int = 40) -> dict:
    """Fill missing rule/AI confidence on pending scraped ads.

    1) Rule market signal → graded ``rule_confidence`` (all matching rows, no AI).
    2) Still unscored → sync market_fit for up to ``ai_limit`` rows.
    Company/manual ads (owner_subject set) are skipped.
    """
    from worker.market_fit import checked_rule_fit, checked_verdict, store_fit_detail

    if ai_limit < 0 or ai_limit > 50:
        raise CabinetError(422, "AI limit 0–50 arasında olmalıdır")

    rule_filled = 0
    remaining_for_ai: list[dict] = []

    with _LOCK:
        conn = _connect()
        try:
            # Missing scores + legacy flat "clear market signal" → 100 (re-grade).
            rows = conn.execute(
                """
                SELECT id, title, company, city, text, remote, relocation,
                       COALESCE((SELECT s.source_url FROM job_sources s WHERE s.job_id = jobs.id
                                 ORDER BY s.id LIMIT 1), '') AS source_url,
                       rule_confidence, ai_confidence, market_fit_reason
                FROM jobs
                WHERE status = ?
                  AND COALESCE(owner_subject, '') = ''
                  AND ai_confidence IS NULL
                  AND (
                    rule_confidence IS NULL
                    OR (
                      rule_confidence = 100
                      AND COALESCE(market_fit_reason, '') = 'clear market signal'
                    )
                  )
                ORDER BY id ASC
                """,
                (PENDING,),
            ).fetchall()
            for row in rows:
                title = row["title"] or ""
                place = row["city"] or ""
                text = row["text"] or ""
                pre_remote = bool(int(row["remote"] or 0))
                pre_reloc = bool(int(row["relocation"] or 0))
                had_rule = row["rule_confidence"] is not None
                rule_fit = checked_rule_fit(
                    title,
                    place,
                    text,
                    pre_remote=True if pre_remote else None,
                    pre_relocation=True if pre_reloc else None,
                    source_url=row["source_url"] or "",
                )
                if rule_fit:
                    conn.execute(
                        """
                        UPDATE jobs
                        SET rule_confidence = ?, market_fit_reason = ?, updated_at = ?
                        WHERE id = ? AND status = ? AND ai_confidence IS NULL
                          AND (
                            rule_confidence IS NULL
                            OR (
                              rule_confidence = 100
                              AND COALESCE(market_fit_reason, '') = 'clear market signal'
                            )
                          )
                        """,
                        (
                            int(rule_fit["confidence"]),
                            str(rule_fit.get("reason") or "rule market signal")[:800],
                            _now(),
                            int(row["id"]),
                            PENDING,
                        ),
                    )
                    rule_filled += 1
                elif not had_rule:
                    remaining_for_ai.append(
                        {
                            "id": int(row["id"]),
                            "title": title,
                            "company": row["company"] or "",
                            "city": place,
                            "text": text,
                            "source_url": row["source_url"] or "",
                            "remote": True if pre_remote else None,
                            "relocation": True if pre_reloc else None,
                        }
                    )
            conn.commit()
        finally:
            conn.close()

    ai_snapshots = remaining_for_ai[:ai_limit]
    still_unscored = max(0, len(remaining_for_ai) - len(ai_snapshots))
    checked = 0
    rejected = 0
    failed = 0

    for snap in ai_snapshots:
        job_id = snap["id"]
        conn = _connect()
        try:
            verdict = checked_verdict(
                title=snap["title"],
                company=snap["company"],
                place=snap["city"],
                text=snap["text"],
                conn=conn,
                source_url=snap["source_url"],
                source_remote=snap["remote"],
                source_relocation=snap["relocation"],
            )
        finally:
            conn.close()
        if verdict is None:
            failed += 1
            continue
        checked += 1
        reason = str(verdict.get("reason") or "")[:800]
        confidence = int(verdict.get("confidence") or 0)
        with _LOCK:
            conn = _connect()
            try:
                row = conn.execute(
                    """
                    SELECT status, rule_confidence, ai_confidence
                    FROM jobs WHERE id = ?
                    """,
                    (job_id,),
                ).fetchone()
                if row is None or (row["status"] or "") != PENDING:
                    continue
                if row["rule_confidence"] is not None or row["ai_confidence"] is not None:
                    continue
                store_fit_detail(conn, job_id, verdict)  # committed with the score below
                if verdict.get("unclear"):
                    conn.execute(
                        """
                        UPDATE jobs
                        SET ai_confidence = ?, market_fit_reason = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (confidence, reason, _now(), job_id),
                    )
                elif not verdict.get("suitable"):
                    conn.execute(
                        """
                        UPDATE jobs
                        SET status = ?, reject_reason = ?, rule_confidence = NULL,
                            ai_confidence = ?, market_fit_reason = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            REJECTED,
                            (reason or "unsuitable")[:300],
                            confidence,
                            reason,
                            _now(),
                            job_id,
                        ),
                    )
                    rejected += 1
                else:
                    remote = 1 if verdict.get("remote") else 0
                    relocation = 1 if verdict.get("relocation") else 0
                    conn.execute(
                        """
                        UPDATE jobs
                        SET remote = ?, relocation = ?, ai_confidence = ?,
                            market_fit_reason = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (remote, relocation, confidence, reason, _now(), job_id),
                    )
                conn.commit()
            finally:
                conn.close()

    return {
        "rule_filled": rule_filled,
        "ai_checked": checked,
        "ai_rejected": rejected,
        "ai_failed": failed,
        "still_unscored": still_unscored + failed,
    }


def reject_ad(job_id: int, reason: str) -> dict:
    cleaned = " ".join((reason or "").split())
    note = None
    with _LOCK:
        conn = _connect()
        try:
            row = _moderation_row(conn, job_id)
            if row is None:
                raise CabinetError(404, "Elan tapılmadı")
            if (row["status"] or "") != PENDING:
                raise CabinetError(409, "Yalnız gözləyən elan rədd edilə bilər")
            if not cleaned or len(cleaned) > 400:
                raise CabinetError(422, "Rədd səbəbi yazılmalıdır")
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, reject_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (REJECTED, cleaned, _now(), job_id),
            )
            row = conn.execute(
                f"SELECT {_MOD_COLS} FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            owner = (row["owner_subject"] or "").strip()
            if owner:
                from app.notifications import insert_notification

                note = insert_notification(
                    conn,
                    recipient=owner,
                    kind="ad_rejected",
                    job_id=job_id,
                    job_title=row["title"] or "",
                    application_id=None,
                    status=REJECTED,
                    reason=cleaned,
                    language=row["language"] or "",
                )
            conn.commit()
        finally:
            conn.close()
    if note:
        from app.notifications import deliver_email

        deliver_email(note)
    return _owner(row)


def staff_close_ad(job_id: int) -> dict:
    with _LOCK:
        conn = _connect()
        try:
            row = _moderation_row(conn, job_id)
            if row is None:
                raise CabinetError(404, "Elan tapılmadı")
            if (row["status"] or "") != CLOSED:
                conn.execute(
                    "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
                    (CLOSED, _now(), job_id),
                )
                conn.commit()
                row = conn.execute(
                    f"SELECT {_MOD_COLS} FROM jobs WHERE id = ?",
                    (job_id,),
                ).fetchone()
        finally:
            conn.close()
    return _owner(row)


def staff_update_ad(job_id: int, fields: dict) -> dict:
    with _LOCK:
        conn = _connect()
        try:
            row = _moderation_row(conn, job_id)
            if row is None:
                raise CabinetError(404, "Elan tapılmadı")
            if (row["status"] or "") == CLOSED:
                raise CabinetError(409, "Bağlanmış elan dəyişdirilə bilməz")
            form = fields["form"] if "form" in fields else parse_stored(row["apply_form"])
            scraped = not (row["owner_subject"] or "").strip()
            if scraped:
                conn.execute(
                    """
                    UPDATE jobs
                    SET title = ?, company = ?, city = ?, text = ?, cleaned_text = NULL,
                        language = ?, salary = ?, job_type = ?, remote = ?, updated_at = ?,
                        content_locked = 1
                    WHERE id = ?
                    """,
                    (
                        fields["title"],
                        fields["company"],
                        fields["city"],
                        fields["text"],
                        fields["language"],
                        fields["salary"],
                        fields["job_type"],
                        1 if fields["remote"] else 0,
                        _now(),
                        job_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE jobs
                    SET title = ?, company = ?, city = ?, text = ?, cleaned_text = NULL,
                        language = ?, salary = ?, job_type = ?, remote = ?, updated_at = ?,
                        apply_form = ?
                    WHERE id = ?
                    """,
                    (
                        fields["title"],
                        fields["company"],
                        fields["city"],
                        fields["text"],
                        fields["language"],
                        fields["salary"],
                        fields["job_type"],
                        1 if fields["remote"] else 0,
                        _now(),
                        dump_form(form),
                        job_id,
                    ),
                )
            conn.commit()
            saved = conn.execute(
                f"SELECT {_MOD_COLS} FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        finally:
            conn.close()
    return _owner(saved)


def create_sourced_ad(subject: str, fields: dict, source_url: str) -> dict:
    """Staff ad with an original URL. Published immediately. The URL is not returned."""
    now = _now()
    key = f"cabinet:{subject}:{uuid.uuid4().hex}"
    with _LOCK:
        conn = _connect()
        try:
            try:
                cur = conn.execute(
                    """
                    INSERT INTO jobs (
                        title, company, city, text, cleaned_text, status, created_at, norm_key,
                        owner_subject, language, salary, job_type, remote, updated_at, content_locked,
                        apply_form
                    ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                    """,
                    (
                        fields["title"],
                        fields["company"],
                        fields["city"],
                        fields["text"],
                        PUBLISHED,
                        now,
                        key,
                        subject,
                        fields["language"],
                        fields["salary"],
                        fields["job_type"],
                        1 if fields["remote"] else 0,
                        now,
                        dump_form(fields.get("form") or default_form()),
                    ),
                )
                job_id = int(cur.lastrowid)
                conn.execute(
                    """
                    INSERT INTO job_sources (
                        job_id, source_name, source_url, external_id, last_seen, credit_note
                    ) VALUES (?, 'manual', ?, '', ?, '')
                    """,
                    (job_id, source_url, now),
                )
                conn.commit()
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise CabinetError(409, "Bu ünvan artıq yazılıb") from exc
            row = _cabinet_row(conn, job_id)
        finally:
            conn.close()
    return _owner(row)
