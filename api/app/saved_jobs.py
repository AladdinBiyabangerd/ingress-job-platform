"""Candidate saved / favorited jobs."""

from __future__ import annotations

from app.cabinet_store import CabinetError, _LOCK, _connect, _now

_NOT_FOUND = "Elan tapılmadı"
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 60


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


def list_saved_ids(*, user_id: str) -> list[int]:
    who = (user_id or "").strip()
    if not who:
        return []
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT s.job_id
                FROM saved_jobs s
                JOIN jobs j ON j.id = s.job_id
                WHERE s.user_id = ?
                  AND j.status = 'published'
                  AND COALESCE(j.hidden, 0) = 0
                  AND (j.merged_into IS NULL OR j.merged_into = 0)
                ORDER BY s.id DESC
                """,
                (who,),
            ).fetchall()
        finally:
            conn.close()
    return [int(row[0]) for row in rows]


def list_saved(
    *,
    user_id: str,
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
) -> dict:
    from app.sqlite_jobs import _public_jobs_for_ids

    who = (user_id or "").strip()
    current = max(1, int(page or 1))
    size = min(MAX_PER_PAGE, max(1, int(per_page or DEFAULT_PER_PAGE)))
    if not who:
        return {"items": [], "total": 0, "page": current, "per_page": size, "pages": 0}

    with _LOCK:
        conn = _connect()
        try:
            total = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM saved_jobs s
                    JOIN jobs j ON j.id = s.job_id
                    WHERE s.user_id = ?
                      AND j.status = 'published'
                      AND COALESCE(j.hidden, 0) = 0
                      AND (j.merged_into IS NULL OR j.merged_into = 0)
                    """,
                    (who,),
                ).fetchone()[0]
            )
            pages = (total + size - 1) // size if total else 0
            if pages and current > pages:
                current = pages
            offset = (current - 1) * size
            rows = conn.execute(
                """
                SELECT s.job_id, s.created_at
                FROM saved_jobs s
                JOIN jobs j ON j.id = s.job_id
                WHERE s.user_id = ?
                  AND j.status = 'published'
                  AND COALESCE(j.hidden, 0) = 0
                  AND (j.merged_into IS NULL OR j.merged_into = 0)
                ORDER BY s.id DESC
                LIMIT ? OFFSET ?
                """,
                (who, size, offset),
            ).fetchall()
            ids = [int(row[0]) for row in rows]
            saved_at = {int(row[0]): row[1] or "" for row in rows}
            jobs = _public_jobs_for_ids(conn, ids)
        finally:
            conn.close()

    by_id = {int(job["id"]): job for job in jobs}
    items = []
    for job_id in ids:
        job = by_id.get(job_id)
        if not job:
            continue
        item = dict(job)
        item["saved_at"] = saved_at.get(job_id, "")
        items.append(item)
    return {
        "items": items,
        "total": total,
        "page": current,
        "per_page": size,
        "pages": pages,
    }


def save_job(*, user_id: str, job_id: int) -> dict:
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
                "SELECT id, created_at FROM saved_jobs WHERE user_id = ? AND job_id = ?",
                (who, jid),
            ).fetchone()
            if existing is not None:
                created = existing[1] or ""
                created_new = False
            else:
                created = _now()
                conn.execute(
                    """
                    INSERT INTO saved_jobs (user_id, job_id, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (who, jid, created),
                )
                conn.commit()
                created_new = True
        finally:
            conn.close()
    return {"job_id": jid, "saved_at": created, "created": created_new}


def unsave_job(*, user_id: str, job_id: int) -> None:
    who = (user_id or "").strip()
    if not who:
        raise CabinetError(401, "Hesab tələb olunur")
    jid = int(job_id)
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                "DELETE FROM saved_jobs WHERE user_id = ? AND job_id = ?",
                (who, jid),
            )
            conn.commit()
            if cur.rowcount == 0:
                # Idempotent when already gone; still 404 if job never published?
                # Treat missing save as success (idempotent unsave).
                pass
        finally:
            conn.close()
