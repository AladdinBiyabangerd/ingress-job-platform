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

Scraped rows keep an empty owner_subject. Cabinet moderation does not return
them. hidden=1 or merged_into takes a scraped row off the public list without
deleting it. Ordinary cabinet creates do not write a source URL.
"""

from __future__ import annotations

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
}

_APP_COLUMNS = {
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


def _apply_schema(conn) -> None:
    conn.execute(_JOBS)
    conn.execute(_SOURCES)
    conn.execute(_CRAWL_SOURCES)
    conn.execute(_MERGES)
    conn.execute(_APPLICATIONS)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
    for name, decl in _COLUMNS.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {decl}")
    app_cols = {row[1] for row in conn.execute("PRAGMA table_info(applications)")}
    for name, decl in _APP_COLUMNS.items():
        if name not in app_cols:
            conn.execute(f"ALTER TABLE applications ADD COLUMN {name} {decl}")
    conn.execute("CREATE INDEX IF NOT EXISTS jobs_owner ON jobs(owner_subject)")
    conn.execute("CREATE INDEX IF NOT EXISTS applications_job ON applications(job_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS applications_candidate ON applications(candidate_subject)"
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
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS notifications_recipient ON notifications(recipient_subject, id)"
    )
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
    return payload


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


def _cabinet_row(conn: sqlite3.Connection, job_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, title, company, city, remote, text, language, salary,
               job_type, status, created_at, updated_at, reject_reason, apply_form, owner_subject
        FROM jobs
        WHERE id = ? AND owner_subject != ''
        """,
        (job_id,),
    ).fetchone()


def list_moderation() -> list[dict]:
    """Pending company ads first, then published, closed, and rejected."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT id, title, company, city, remote, text, language, salary,
                   job_type, status, created_at, updated_at, reject_reason, apply_form, owner_subject
            FROM jobs
            WHERE owner_subject != ''
            ORDER BY
                CASE status
                    WHEN 'pending' THEN 0
                    WHEN 'published' THEN 1
                    WHEN 'closed' THEN 2
                    WHEN 'rejected' THEN 3
                    ELSE 4
                END,
                id DESC
            """
        ).fetchall()
    finally:
        conn.close()
    return [_owner(row) for row in rows]


def approve_ad(job_id: int) -> dict:
    note = None
    with _LOCK:
        conn = _connect()
        try:
            row = _cabinet_row(conn, job_id)
            if row is None:
                raise CabinetError(404, "Elan tapılmadı")
            if (row["status"] or "") != PENDING:
                raise CabinetError(409, "Yalnız gözləyən elan təsdiqlənə bilər")
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, reject_reason = '', updated_at = ?
                WHERE id = ?
                """,
                (PUBLISHED, _now(), job_id),
            )
            row = _cabinet_row(conn, job_id)
            from app.notifications import insert_notification

            note = insert_notification(
                conn,
                recipient=row["owner_subject"] or "",
                kind="ad_approved",
                job_id=job_id,
                job_title=row["title"] or "",
                application_id=None,
                status=PUBLISHED,
                reason="",
                language=row["language"] or "",
            )
            conn.commit()
        finally:
            conn.close()
    if note:
        from app.notifications import deliver_email

        deliver_email(note)
    return _owner(row)


def reject_ad(job_id: int, reason: str) -> dict:
    cleaned = " ".join((reason or "").split())
    note = None
    with _LOCK:
        conn = _connect()
        try:
            row = _cabinet_row(conn, job_id)
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
            row = _cabinet_row(conn, job_id)
            from app.notifications import insert_notification

            note = insert_notification(
                conn,
                recipient=row["owner_subject"] or "",
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
            row = _cabinet_row(conn, job_id)
            if row is None:
                raise CabinetError(404, "Elan tapılmadı")
            if (row["status"] or "") != CLOSED:
                conn.execute(
                    "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
                    (CLOSED, _now(), job_id),
                )
                conn.commit()
                row = _cabinet_row(conn, job_id)
        finally:
            conn.close()
    return _owner(row)


def staff_update_ad(job_id: int, fields: dict) -> dict:
    with _LOCK:
        conn = _connect()
        try:
            row = _cabinet_row(conn, job_id)
            if row is None:
                raise CabinetError(404, "Elan tapılmadı")
            if (row["status"] or "") == CLOSED:
                raise CabinetError(409, "Bağlanmış elan dəyişdirilə bilməz")
            form = fields["form"] if "form" in fields else parse_stored(row["apply_form"])
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
            saved = _cabinet_row(conn, job_id)
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
