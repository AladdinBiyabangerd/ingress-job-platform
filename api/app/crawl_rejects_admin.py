"""Staff tools for crawl_rejects (URL skip list + optional linked job)."""

from __future__ import annotations

import sqlite3

from app.cabinet_store import (
    PUBLISHED,
    CabinetError,
    _LOCK,
    _connect,
    _now,
    _score_or_none,
)


def _ensure_table(conn: sqlite3.Connection) -> None:
    from worker.market_fit import ensure_rejects_table

    ensure_rejects_table(conn)


def _public(row: sqlite3.Row) -> dict:
    keys = set(row.keys())
    job_id = None
    if "job_id" in keys and row["job_id"] is not None:
        try:
            job_id = int(row["job_id"])
        except (TypeError, ValueError):
            job_id = None
    return {
        "source_url": row["source_url"] or "",
        "reason": row["reason"] or "",
        "decided_at": row["decided_at"] or "",
        "via_ai": bool(int(row["via_ai"] or 0)),
        "job_id": job_id,
        "title": (row["title"] or "") if "title" in keys else "",
        "company": (row["company"] or "") if "company" in keys else "",
        "status": (row["status"] or "") if "status" in keys else "",
        "hidden": bool(int(row["hidden"] or 0)) if "hidden" in keys else False,
        "rule_confidence": _score_or_none(row, "rule_confidence") if "rule_confidence" in keys else None,
        "ai_confidence": _score_or_none(row, "ai_confidence") if "ai_confidence" in keys else None,
        "market_fit_reason": (row["market_fit_reason"] or "") if "market_fit_reason" in keys else "",
        "source_name": (row["source_name"] or "") if "source_name" in keys else "",
    }


def list_crawl_rejects() -> list[dict]:
    """URL skips newest first; join first matching unmerged job when present."""
    conn = _connect()
    try:
        _ensure_table(conn)
        rows = conn.execute(
            """
            SELECT
                cr.source_url,
                cr.reason,
                cr.decided_at,
                cr.via_ai,
                j.id AS job_id,
                COALESCE(j.title, '') AS title,
                COALESCE(j.company, '') AS company,
                COALESCE(j.status, '') AS status,
                COALESCE(j.hidden, 0) AS hidden,
                j.rule_confidence,
                j.ai_confidence,
                COALESCE(j.market_fit_reason, '') AS market_fit_reason,
                COALESCE(js.source_name, '') AS source_name
            FROM crawl_rejects cr
            LEFT JOIN (
                SELECT source_url, MIN(job_id) AS job_id, MIN(id) AS src_id
                FROM job_sources
                WHERE TRIM(COALESCE(source_url, '')) != ''
                GROUP BY source_url
            ) link ON link.source_url = cr.source_url
            LEFT JOIN jobs j
                ON j.id = link.job_id
               AND COALESCE(j.merged_into, 0) = 0
            LEFT JOIN job_sources js ON js.id = link.src_id
            ORDER BY cr.decided_at DESC, cr.source_url
            """
        ).fetchall()
    finally:
        conn.close()
    return [_public(row) for row in rows]


def _score_column(score: str) -> str:
    if score == "ai":
        return "ai_confidence"
    if score == "rule":
        return "rule_confidence"
    raise CabinetError(422, "Skor ai və ya rule olmalıdır")


def _threshold_ok(value: int | None, op: str, threshold: int) -> bool:
    if value is None:
        return False
    if op == "gte":
        return value >= threshold
    if op == "lte":
        return value <= threshold
    raise CabinetError(422, "Operator gte və ya lte olmalıdır")


def _publish_linked(conn: sqlite3.Connection, job_id: int) -> None:
    conn.execute(
        """
        UPDATE jobs
        SET status = ?, hidden = 0, reject_reason = '', updated_at = ?
        WHERE id = ?
          AND COALESCE(owner_subject, '') = ''
          AND COALESCE(merged_into, 0) = 0
        """,
        (PUBLISHED, _now(), job_id),
    )
    urls = conn.execute(
        """
        SELECT source_url FROM job_sources
        WHERE job_id = ? AND TRIM(COALESCE(source_url, '')) != ''
        """,
        (job_id,),
    ).fetchall()
    for row in urls:
        url = (row["source_url"] if hasattr(row, "keys") else row[0]) or ""
        url = str(url).strip()
        if url:
            conn.execute("DELETE FROM crawl_rejects WHERE source_url = ?", (url,))


def publish_crawl_rejects_by_threshold(
    *,
    score: str,
    op: str,
    threshold: int,
) -> dict:
    """Publish linked jobs whose rule/AI % matches; clear their URLs from crawl_rejects."""
    col = _score_column(score)
    if op not in ("gte", "lte"):
        raise CabinetError(422, "Operator gte və ya lte olmalıdır")
    if threshold < 0 or threshold > 100:
        raise CabinetError(422, "Faiz 0–100 arasında olmalıdır")

    published = 0
    with _LOCK:
        conn = _connect()
        try:
            _ensure_table(conn)
            rows = conn.execute(
                f"""
                SELECT DISTINCT j.id AS job_id, j.{col} AS score
                FROM crawl_rejects cr
                JOIN job_sources js ON js.source_url = cr.source_url
                JOIN jobs j ON j.id = js.job_id
                WHERE COALESCE(j.owner_subject, '') = ''
                  AND COALESCE(j.merged_into, 0) = 0
                  AND j.{col} IS NOT NULL
                ORDER BY j.id
                """
            ).fetchall()
            seen: set[int] = set()
            for row in rows:
                job_id = int(row["job_id"])
                if job_id in seen:
                    continue
                raw = row["score"]
                try:
                    value = int(raw)
                except (TypeError, ValueError):
                    continue
                if not _threshold_ok(value, op, threshold):
                    continue
                seen.add(job_id)
                _publish_linked(conn, job_id)
                published += 1
            conn.commit()
        finally:
            conn.close()
    return {"published": published}


def clear_crawl_rejects(urls: list[str]) -> dict:
    """Remove URLs from the skip list so the next crawl may fetch them again."""
    ordered: list[str] = []
    seen: set[str] = set()
    for raw in urls:
        url = str(raw or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        ordered.append(url)
    if not ordered:
        raise CabinetError(422, "URL seçilməyib")
    if len(ordered) > 500:
        raise CabinetError(422, "Birdən çox 500 URL seçilə bilər")

    cleared = 0
    with _LOCK:
        conn = _connect()
        try:
            _ensure_table(conn)
            for url in ordered:
                cur = conn.execute(
                    "DELETE FROM crawl_rejects WHERE source_url = ?",
                    (url,),
                )
                cleared += int(cur.rowcount or 0)
            conn.commit()
        finally:
            conn.close()
    return {"cleared": cleared}
