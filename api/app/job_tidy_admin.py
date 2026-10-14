"""Staff list of published ads that still need AI job_tidy."""

from __future__ import annotations

from app.cabinet_store import _connect


def _public(row) -> dict:
    body = row["text"] or ""
    return {
        "id": int(row["id"]),
        "title": row["title"] or "",
        "company": row["company"] or "",
        "city": row["city"] or "",
        "remote": bool(int(row["remote"] or 0)),
        "language": row["language"] or "",
        "created_at": row["created_at"] or "",
        "source_name": row["source_name"] or "",
        "text_chars": len(body.strip()),
    }


def list_untidy_jobs(*, limit: int = 500) -> list[dict]:
    """Published ads with empty cleaned_text that look messy (same gate as worker)."""
    from worker.tidy import messy

    cap = max(1, min(2000, int(limit or 500)))
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT
                j.id,
                j.title,
                j.company,
                j.city,
                j.remote,
                j.language,
                j.created_at,
                j.text,
                COALESCE((
                    SELECT js.source_name
                    FROM job_sources js
                    WHERE js.job_id = j.id
                    ORDER BY js.id
                    LIMIT 1
                ), '') AS source_name
            FROM jobs j
            WHERE j.status = 'published'
              AND COALESCE(j.merged_into, 0) = 0
              AND COALESCE(j.hidden, 0) = 0
              AND (j.cleaned_text IS NULL OR TRIM(j.cleaned_text) = '')
            ORDER BY j.id DESC
            LIMIT ?
            """,
            (cap * 3,),
        ).fetchall()
    finally:
        conn.close()

    out: list[dict] = []
    for row in rows:
        if not messy(row["text"] or ""):
            continue
        out.append(_public(row))
        if len(out) >= cap:
            break
    return out
