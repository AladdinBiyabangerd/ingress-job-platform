"""parse_cv_queue + candidate_profile stub (Phase 1.2).

Enqueue on CV upload; worker drains with rules + OCR cv_parse. No AI #1.
candidate_profile lives in the shared jobs DB (plan §12). It is separate from
accounts.sqlite candidate_profiles (display name / phone / email only).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from worker.cv_files import read_cv
from worker.cv_parse import parse_bytes

MAX_ATTEMPTS = 5
PER_RUN = 20
ENQUEUE_EXISTING_STEP = "enqueue-existing-application-cvs-v1"

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

_MAINTENANCE = """
CREATE TABLE IF NOT EXISTS maintenance_steps (
    name TEXT PRIMARY KEY,
    done_at TEXT NOT NULL
)
"""


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def ensure_cv_queue_tables(conn) -> None:
    conn.executescript(SCHEMA)
    for sql in INDEXES:
        conn.execute(sql)


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


def _has_applications(conn) -> bool:
    try:
        conn.execute("SELECT 1 FROM applications LIMIT 1")
        return True
    except Exception:
        return False


def enqueue_existing_application_cvs(conn) -> int:
    """One-time: queue every application CV that is not already pending/processing."""
    ensure_cv_queue_tables(conn)
    conn.execute(_MAINTENANCE)
    done = conn.execute(
        "SELECT 1 FROM maintenance_steps WHERE name = ?",
        (ENQUEUE_EXISTING_STEP,),
    ).fetchone()
    if done:
        return 0
    if not _has_applications(conn):
        # Worker-only fresh DB may not have applications yet; try again later.
        return 0
    rows = conn.execute(
        """
        SELECT id, candidate_subject, cv_stored, cv_name
        FROM applications
        WHERE COALESCE(cv_stored, '') != ''
        ORDER BY id
        """
    ).fetchall()
    queued = 0
    for row in rows:
        job_id = enqueue_parse(
            conn,
            user_id=row["candidate_subject"],
            cv_file_key=row["cv_stored"],
            cv_name=row["cv_name"] or "",
            application_id=int(row["id"]),
        )
        if job_id is not None:
            queued += 1
    conn.execute(
        "INSERT INTO maintenance_steps (name, done_at) VALUES (?, ?) ON CONFLICT (name) DO NOTHING",
        (ENQUEUE_EXISTING_STEP, _now()),
    )
    return queued


def upsert_candidate_profile(conn, *, user_id: str, cv_file_key: str, profile: dict) -> int:
    """Store rules-parse output as a draft candidate_profile (plan §12 stub)."""
    ensure_cv_queue_tables(conn)
    meta = profile.get("parse_meta") if isinstance(profile.get("parse_meta"), dict) else {}
    prefs = profile.get("preferences") if isinstance(profile.get("preferences"), dict) else {}
    data = json.dumps(profile, ensure_ascii=False, separators=(",", ":"))
    headline = str(profile.get("headline") or "")[:200]
    seniority = str(profile.get("seniority") or "")[:40]
    total_years = profile.get("total_years")
    if total_years is not None:
        try:
            total_years = float(total_years)
        except (TypeError, ValueError):
            total_years = None
    parse_method = str(meta.get("method") or "rules")[:40]
    confidence = meta.get("confidence")
    if confidence is not None:
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = None
    # Preferences columns are not all materialised yet; keep them inside data.
    _ = prefs
    now = _now()
    existing = conn.execute(
        "SELECT id, status FROM candidate_profile WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if existing is not None:
        # Never overwrite a confirmed profile from an automatic parse.
        status = existing["status"] if "status" in existing.keys() else existing[1]
        if status == "confirmed":
            return int(existing["id"] if "id" in existing.keys() else existing[0])
        conn.execute(
            """
            UPDATE candidate_profile
            SET cv_file_key = ?, data = ?, headline = ?, seniority = ?,
                total_years = ?, status = 'draft', parse_method = ?,
                confidence = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (
                cv_file_key,
                data,
                headline,
                seniority,
                total_years,
                parse_method,
                confidence,
                now,
                user_id,
            ),
        )
        return int(existing["id"] if "id" in existing.keys() else existing[0])
    cur = conn.execute(
        """
        INSERT INTO candidate_profile (
            user_id, cv_file_key, data, headline, seniority, total_years,
            status, parse_method, confidence, visibility, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, ?, 'hidden', ?)
        """,
        (
            user_id,
            cv_file_key,
            data,
            headline,
            seniority,
            total_years,
            parse_method,
            confidence,
            now,
        ),
    )
    return int(cur.lastrowid)


def _claim(conn, limit: int) -> list[sqlite3.Row]:
    rows = list(
        conn.execute(
            """
            SELECT id, user_id, cv_file_key, cv_name, application_id, attempts
            FROM parse_cv_queue
            WHERE status = 'pending' AND attempts < ?
            ORDER BY id
            LIMIT ?
            """,
            (MAX_ATTEMPTS, limit),
        )
    )
    claimed: list[sqlite3.Row] = []
    now = _now()
    for row in rows:
        cur = conn.execute(
            """
            UPDATE parse_cv_queue
            SET status = 'processing', started_at = ?, attempts = attempts + 1
            WHERE id = ? AND status = 'pending'
            """,
            (now, int(row["id"])),
        )
        if cur.rowcount:
            claimed.append(row)
    return claimed


def _finish(conn, queue_id: int, *, status: str, error: str = "") -> None:
    finished = _now() if status in {"done", "failed"} else ""
    conn.execute(
        """
        UPDATE parse_cv_queue
        SET status = ?, error = ?, finished_at = ?
        WHERE id = ?
        """,
        (status, (error or "")[:1000], finished, queue_id),
    )


def _process_one(conn, row: sqlite3.Row, *, root: Path | None) -> str:
    stored = row["cv_file_key"] or ""
    data = read_cv(stored, root=root)
    if data is None:
        _finish(conn, int(row["id"]), status="failed", error="cv_missing")
        return "failed"
    profile = parse_bytes(data, filename=row["cv_name"] or stored)
    upsert_candidate_profile(
        conn,
        user_id=row["user_id"],
        cv_file_key=stored,
        profile=profile,
    )
    meta = profile.get("parse_meta") if isinstance(profile.get("parse_meta"), dict) else {}
    err = str(meta.get("error") or "")
    if err and not (profile.get("skills") or profile.get("work_history")):
        _finish(conn, int(row["id"]), status="failed", error=err[:1000])
        return "failed"
    _finish(conn, int(row["id"]), status="done", error=err[:1000] if err else "")
    return "done"


def drain_parse_cv_queue(
    conn,
    *,
    limit: int = PER_RUN,
    cv_root: Path | None = None,
) -> dict[str, int]:
    """Claim pending jobs and run rules-only parse. Returns status counts."""
    ensure_cv_queue_tables(conn)
    stats = {"claimed": 0, "done": 0, "failed": 0}
    claimed = _claim(conn, limit)
    stats["claimed"] = len(claimed)
    for row in claimed:
        try:
            result = _process_one(conn, row, root=cv_root)
            stats[result] = stats.get(result, 0) + 1
        except Exception as exc:
            attempts = int(row["attempts"]) + 1
            status = "failed" if attempts >= MAX_ATTEMPTS else "pending"
            _finish(
                conn,
                int(row["id"]),
                status=status,
                error=f"{type(exc).__name__}: {exc}"[:1000],
            )
            stats["failed"] = stats.get("failed", 0) + 1
    return stats


def ensure_cv_queue(conn) -> int:
    """Create tables and enqueue existing application CVs once. Returns queued count."""
    ensure_cv_queue_tables(conn)
    return enqueue_existing_application_cvs(conn)
