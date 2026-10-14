"""Candidate job detail views — which ads a person has opened."""

from __future__ import annotations

from app.cabinet_store import CabinetError, _LOCK, _connect, _now

_NOT_FOUND = "Elan tapılmadı"


def _published_job(conn, job_id: int):
    return conn.execute(
        """
        SELECT id
        FROM jobs
        WHERE id = ?
          AND status = 'published'
          AND COALESCE(hidden, 0) = 0
          AND (merged_into IS NULL OR merged_into = 0)
        """,
        (job_id,),
    ).fetchone()


def list_viewed_ids(*, user_id: str) -> list[int]:
    who = (user_id or "").strip()
    if not who:
        return []
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT v.job_id
                FROM viewed_jobs v
                JOIN jobs j ON j.id = v.job_id
                WHERE v.user_id = ?
                  AND j.status = 'published'
                  AND COALESCE(j.hidden, 0) = 0
                  AND (j.merged_into IS NULL OR j.merged_into = 0)
                ORDER BY v.id DESC
                """,
                (who,),
            ).fetchall()
        finally:
            conn.close()
    return [int(row[0]) for row in rows]


def mark_viewed(*, user_id: str, job_id: int) -> dict:
    who = (user_id or "").strip()
    if not who:
        raise CabinetError(401, "Hesab tələb olunur")
    jid = int(job_id)
    with _LOCK:
        conn = _connect()
        try:
            if _published_job(conn, jid) is None:
                raise CabinetError(404, _NOT_FOUND)
            existing = conn.execute(
                "SELECT id, created_at FROM viewed_jobs WHERE user_id = ? AND job_id = ?",
                (who, jid),
            ).fetchone()
            if existing is not None:
                created = existing[1] or ""
                created_new = False
            else:
                created = _now()
                conn.execute(
                    """
                    INSERT INTO viewed_jobs (user_id, job_id, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (who, jid, created),
                )
                conn.commit()
                created_new = True
        finally:
            conn.close()
    return {"job_id": jid, "viewed_at": created, "created": created_new}
