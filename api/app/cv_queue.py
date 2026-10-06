"""Enqueue CV parse jobs (Phase 1.2).

Schema matches worker/worker/cv_queue.py. The API inserts pending rows on CV
upload and drains them in-process via app.cv_parse_jobs (async background).
The hourly crawl worker may still drain stranded rows as a backup.
"""

from __future__ import annotations

from datetime import datetime
from threading import Lock

SCHEMA = """
CREATE TABLE IF NOT EXISTS parse_cv_queue (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    cv_file_key TEXT NOT NULL,
    cv_name TEXT NOT NULL DEFAULT '',
    application_id INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT '',
    finished_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS candidate_profile (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,
    cv_file_key TEXT NOT NULL DEFAULT '',
    data TEXT NOT NULL DEFAULT '{}',
    headline TEXT NOT NULL DEFAULT '',
    seniority TEXT NOT NULL DEFAULT '',
    total_years REAL,
    status TEXT NOT NULL DEFAULT 'draft',
    parse_method TEXT NOT NULL DEFAULT '',
    confidence REAL,
    visibility TEXT NOT NULL DEFAULT 'hidden',
    updated_at TEXT NOT NULL
);
"""

INDEXES = (
    "CREATE INDEX IF NOT EXISTS parse_cv_queue_status ON parse_cv_queue(status, id)",
    "CREATE INDEX IF NOT EXISTS parse_cv_queue_user ON parse_cv_queue(user_id)",
    "CREATE INDEX IF NOT EXISTS candidate_profile_status ON candidate_profile(status)",
)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


_QUEUE_ENSURED: set[str] = set()
_QUEUE_LOCK = Lock()


def ensure_cv_queue_tables(conn) -> None:
    from app.jobs_db import schema_cache_key

    key = schema_cache_key()
    if key in _QUEUE_ENSURED:
        return
    with _QUEUE_LOCK:
        if key in _QUEUE_ENSURED:
            return
        conn.executescript(SCHEMA)
        for sql in INDEXES:
            conn.execute(sql)
        _QUEUE_ENSURED.add(key)


def enqueue_parse(
    conn,
    *,
    user_id: str,
    cv_file_key: str,
    cv_name: str = "",
    application_id: int | None = None,
) -> int | None:
    """Insert a pending parse job. Skips when the same CV is already queued or in flight."""
    ensure_cv_queue_tables(conn)
    subject = (user_id or "").strip()
    key = (cv_file_key or "").strip()
    if not subject or not key:
        return None
    open_row = conn.execute(
        """
        SELECT id FROM parse_cv_queue
        WHERE user_id = ? AND cv_file_key = ? AND status IN ('pending', 'processing')
        LIMIT 1
        """,
        (subject, key),
    ).fetchone()
    if open_row is not None:
        return int(open_row[0])
    cur = conn.execute(
        """
        INSERT INTO parse_cv_queue (
            user_id, cv_file_key, cv_name, application_id, status, attempts,
            error, created_at, started_at, finished_at
        ) VALUES (?, ?, ?, ?, 'pending', 0, '', ?, '', '')
        """,
        (
            subject,
            key,
            (cv_name or "").strip()[:200],
            application_id,
            _now(),
        ),
    )
    return int(cur.lastrowid)
