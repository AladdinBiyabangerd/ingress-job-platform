"""Staff tools for crawled rows. Does not fetch any site."""

from __future__ import annotations

import sqlite3

from app.cabinet_store import CabinetError, _LOCK, _connect, _now

# List responses keep a short body; edit loads the full row via get_crawled.
_TEXT_PREVIEW = 400

_SOURCE_JOIN = """
LEFT JOIN (
    SELECT job_id, source_name
    FROM job_sources
    WHERE id IN (SELECT MIN(id) FROM job_sources GROUP BY job_id)
) js ON js.job_id = j.id
"""

_LIST = f"""
SELECT
    j.id,
    j.title,
    j.company,
    j.city,
    COALESCE(j.remote, 0) AS remote,
    j.text,
    COALESCE(j.language, '') AS language,
    COALESCE(j.salary, '') AS salary,
    COALESCE(j.job_type, '') AS job_type,
    j.status,
    j.created_at,
    COALESCE(j.updated_at, '') AS updated_at,
    COALESCE(j.hidden, 0) AS hidden,
    j.merged_into,
    COALESCE(js.source_name, '') AS source_name
FROM jobs j
{_SOURCE_JOIN}
WHERE COALESCE(j.owner_subject, '') = ''
"""

_LIST_PREVIEW = f"""
SELECT
    j.id,
    j.title,
    j.company,
    j.city,
    COALESCE(j.remote, 0) AS remote,
    substr(j.text, 1, {_TEXT_PREVIEW}) AS text,
    COALESCE(j.language, '') AS language,
    COALESCE(j.salary, '') AS salary,
    COALESCE(j.job_type, '') AS job_type,
    j.status,
    j.created_at,
    COALESCE(j.updated_at, '') AS updated_at,
    COALESCE(j.hidden, 0) AS hidden,
    j.merged_into,
    COALESCE(js.source_name, '') AS source_name
FROM jobs j
{_SOURCE_JOIN}
WHERE COALESCE(j.owner_subject, '') = ''
"""


def _public(row: sqlite3.Row) -> dict:
    merged = row["merged_into"]
    return {
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
        "hidden": bool(int(row["hidden"] or 0)),
        "merged_into": int(merged) if merged else None,
        "source_name": row["source_name"] or "",
        "created_at": row["created_at"] or "",
        "updated_at": row["updated_at"] or "",
    }


def _one(conn: sqlite3.Connection, job_id: int) -> sqlite3.Row | None:
    return conn.execute(f"{_LIST} AND j.id = ?", (job_id,)).fetchone()


def list_crawled() -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            f"{_LIST_PREVIEW} ORDER BY COALESCE(j.hidden, 0), j.id DESC"
        ).fetchall()
    finally:
        conn.close()
    return [_public(row) for row in rows]


def get_crawled(job_id: int) -> dict:
    conn = _connect()
    try:
        row = _one(conn, job_id)
    finally:
        conn.close()
    if row is None:
        raise CabinetError(404, "Elan tapılmadı")
    return _public(row)


def update_crawled(job_id: int, fields: dict) -> dict:
    with _LOCK:
        conn = _connect()
        try:
            row = _one(conn, job_id)
            if row is None:
                raise CabinetError(404, "Elan tapılmadı")
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
            conn.commit()
            saved = _one(conn, job_id)
        finally:
            conn.close()
    return _public(saved)


def set_crawled_hidden(job_id: int, hidden: bool) -> dict:
    with _LOCK:
        conn = _connect()
        try:
            row = _one(conn, job_id)
            if row is None:
                raise CabinetError(404, "Elan tapılmadı")
            if row["merged_into"] and not hidden:
                raise CabinetError(409, "Birləşdirilmiş dublikat açıla bilməz")
            conn.execute(
                "UPDATE jobs SET hidden = ?, updated_at = ? WHERE id = ?",
                (1 if hidden else 0, _now(), job_id),
            )
            conn.commit()
            saved = _one(conn, job_id)
        finally:
            conn.close()
    return _public(saved)


def merge_crawled(keep_id: int, hide_id: int) -> dict:
    if keep_id == hide_id:
        raise CabinetError(409, "Elan özü ilə birləşdirilə bilməz")
    with _LOCK:
        conn = _connect()
        try:
            keep = _one(conn, keep_id)
            duplicate = _one(conn, hide_id)
            if keep is None or duplicate is None:
                raise CabinetError(404, "Elan tapılmadı")
            if int(keep["hidden"] or 0):
                raise CabinetError(409, "Saxlanılan elan gizlidir")
            if duplicate["merged_into"]:
                raise CabinetError(409, "Bu elan artıq birləşdirilib")
            now = _now()
            conn.execute(
                """
                UPDATE jobs
                SET hidden = 1, merged_into = ?, updated_at = ?
                WHERE id = ?
                """,
                (keep_id, now, hide_id),
            )
            conn.execute(
                """
                INSERT INTO job_merges (kept_id, hidden_id, created_at)
                VALUES (?, ?, ?)
                """,
                (keep_id, hide_id, now),
            )
            conn.commit()
            keep = _one(conn, keep_id)
            duplicate = _one(conn, hide_id)
        finally:
            conn.close()
    return {"kept": _public(keep), "hidden": _public(duplicate)}
