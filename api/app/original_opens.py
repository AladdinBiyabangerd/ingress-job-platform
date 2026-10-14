"""Unique candidates who opened the original / external listing URL.

Count is per person (user_id), not per click — gir/çıx spam does not inflate it.
"""

from __future__ import annotations

import sqlite3

from app.cabinet_store import _LOCK, _connect, _now


def record_original_open(*, user_id: str, job_id: int) -> bool:
    """Record at most one open per user+job. Returns True when a new row was inserted."""
    who = (user_id or "").strip()
    if not who:
        return False
    jid = int(job_id)
    with _LOCK:
        conn = _connect()
        try:
            published = conn.execute(
                """
                SELECT id
                FROM jobs
                WHERE id = ?
                  AND status = 'published'
                  AND COALESCE(hidden, 0) = 0
                  AND (merged_into IS NULL OR merged_into = 0)
                """,
                (jid,),
            ).fetchone()
            if published is None:
                return False
            existing = conn.execute(
                "SELECT 1 FROM job_original_opens WHERE user_id = ? AND job_id = ?",
                (who, jid),
            ).fetchone()
            if existing is not None:
                return False
            try:
                cur = conn.execute(
                    """
                    INSERT INTO job_original_opens (user_id, job_id, created_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT (user_id, job_id) DO NOTHING
                    """,
                    (who, jid, _now()),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                return False
            return int(getattr(cur, "rowcount", 0) or 0) > 0
        finally:
            conn.close()


def original_open_counts(conn, job_ids: list[int] | None = None) -> dict[int, int]:
    """job id -> unique openers count."""
    try:
        if job_ids is not None:
            if not job_ids:
                return {}
            placeholders = ",".join("?" * len(job_ids))
            rows = conn.execute(
                f"""
                SELECT job_id, COUNT(*) AS total
                FROM job_original_opens
                WHERE job_id IN ({placeholders})
                GROUP BY job_id
                """,
                job_ids,
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT job_id, COUNT(*) AS total
                FROM job_original_opens
                GROUP BY job_id
                """
            ).fetchall()
    except Exception:
        return {}
    out: dict[int, int] = {}
    for row in rows:
        try:
            job_id = int(row["job_id"])
            total = int(row["total"] or 0)
        except (KeyError, IndexError, TypeError, ValueError):
            job_id = int(row[0])
            total = int(row[1] or 0)
        out[job_id] = total
    return out


def original_open_count(conn, job_id: int) -> int:
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS total FROM job_original_opens WHERE job_id = ?",
            (int(job_id),),
        ).fetchone()
    except Exception:
        return 0
    return int(row["total"] or 0) if row is not None else 0
