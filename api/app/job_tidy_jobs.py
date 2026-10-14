"""Async job_tidy runs for staff (start + poll + cancel).

POST starts a daemon thread that tidies one ad at a time. Progress lives in
the shared jobs DB so any API replica can answer GET polls.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from typing import Any

from app.cabinet_store import CabinetError, _LOCK, _connect, _now

log = logging.getLogger("ingress-job.api.job_tidy")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS job_tidy_jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    total INTEGER NOT NULL DEFAULT 0,
    done INTEGER NOT NULL DEFAULT 0,
    saved INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    job_ids TEXT NOT NULL DEFAULT '[]',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

_inflight = set()
_inflight_lock = threading.Lock()
_MAX_IDS = 2000


def _ensure(conn) -> None:
    conn.execute(_SCHEMA)


def _row_public(row) -> dict[str, Any]:
    total = int(row["total"] or 0)
    done = int(row["done"] or 0)
    return {
        "job_id": row["id"],
        "status": row["status"] or "",
        "total": total,
        "done": done,
        "remaining": max(0, total - done),
        "saved": int(row["saved"] or 0),
        "failed": int(row["failed"] or 0),
        "skipped": int(row["skipped"] or 0),
        "error": row["error"] or "",
    }


def _normalize_ids(job_ids: list[int]) -> list[int]:
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
    return ordered


def start_tidy_job(job_ids: list[int], *, created_by: str = "") -> dict[str, Any]:
    ordered = _normalize_ids(job_ids)
    if not ordered:
        raise CabinetError(422, "Elan seçilməyib")
    if len(ordered) > _MAX_IDS:
        raise CabinetError(422, f"Birdən çox {_MAX_IDS} elan seçilə bilər")

    job_id = uuid.uuid4().hex
    now = _now()
    with _LOCK:
        conn = _connect()
        try:
            _ensure(conn)
            conn.execute(
                """
                INSERT INTO job_tidy_jobs (
                    id, status, total, done, saved, failed, skipped,
                    error, job_ids, created_by, created_at, updated_at
                ) VALUES (?, 'queued', ?, 0, 0, 0, 0, '', ?, ?, ?, ?)
                """,
                (job_id, len(ordered), json.dumps(ordered), created_by or "", now, now),
            )
            conn.commit()
        finally:
            conn.close()

    with _inflight_lock:
        if job_id in _inflight:
            raise CabinetError(409, "Job artıq işləyir")
        _inflight.add(job_id)

    threading.Thread(
        target=_run_job,
        args=(job_id,),
        daemon=True,
        name=f"job-tidy-{job_id[:8]}",
    ).start()
    return get_tidy_job(job_id)


def get_tidy_job(job_id: str) -> dict[str, Any]:
    key = (job_id or "").strip()
    if not key:
        raise CabinetError(404, "Job tapılmadı")
    with _LOCK:
        conn = _connect()
        try:
            _ensure(conn)
            row = conn.execute(
                "SELECT * FROM job_tidy_jobs WHERE id = ?",
                (key,),
            ).fetchone()
        finally:
            conn.close()
    if row is None:
        raise CabinetError(404, "Job tapılmadı")
    return _row_public(row)


def cancel_tidy_job(job_id: str) -> dict[str, Any]:
    """Stop remaining work; already-saved cleaned_text stays."""
    key = (job_id or "").strip()
    if not key:
        raise CabinetError(404, "Job tapılmadı")
    with _LOCK:
        conn = _connect()
        try:
            _ensure(conn)
            row = conn.execute(
                "SELECT status FROM job_tidy_jobs WHERE id = ?",
                (key,),
            ).fetchone()
            if row is None:
                raise CabinetError(404, "Job tapılmadı")
            status = row["status"] or ""
            if status in ("queued", "running"):
                conn.execute(
                    """
                    UPDATE job_tidy_jobs
                    SET status = 'cancelled', updated_at = ?
                    WHERE id = ?
                    """,
                    (_now(), key),
                )
                conn.commit()
        finally:
            conn.close()
    return get_tidy_job(key)


def _is_cancelled(job_id: str) -> bool:
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT status FROM job_tidy_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        finally:
            conn.close()
    return bool(row) and (row["status"] or "") == "cancelled"


def _bump(job_id: str, *, fields: list[str] | None = None, done_inc: int = 1) -> None:
    allowed = {"saved", "failed", "skipped"}
    sets = ["updated_at = ?", "done = done + ?"]
    args: list[Any] = [_now(), done_inc]
    for field in fields or []:
        if field not in allowed:
            continue
        sets.append(f"{field} = {field} + 1")
    args.append(job_id)
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                f"UPDATE job_tidy_jobs SET {', '.join(sets)} WHERE id = ?",
                args,
            )
            conn.commit()
        finally:
            conn.close()


def _finish(job_id: str, *, status: str, error: str = "") -> None:
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                UPDATE job_tidy_jobs
                SET status = ?, error = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, (error or "")[:300], _now(), job_id),
            )
            conn.commit()
        finally:
            conn.close()
    with _inflight_lock:
        _inflight.discard(job_id)


def _run_job(job_id: str) -> None:
    try:
        with _LOCK:
            conn = _connect()
            try:
                row = conn.execute(
                    "SELECT job_ids FROM job_tidy_jobs WHERE id = ?",
                    (job_id,),
                ).fetchone()
                if row is None:
                    return
                conn.execute(
                    """
                    UPDATE job_tidy_jobs
                    SET status = 'running', updated_at = ?
                    WHERE id = ?
                    """,
                    (_now(), job_id),
                )
                conn.commit()
                try:
                    ids = json.loads(row["job_ids"] or "[]")
                except json.JSONDecodeError:
                    ids = []
            finally:
                conn.close()

        if not isinstance(ids, list):
            ids = []

        from worker.tidy import tidy_one

        first_fail = ""
        for raw in ids:
            if _is_cancelled(job_id):
                _finish(job_id, status="cancelled", error=first_fail)
                return
            try:
                ad_id = int(raw)
            except (TypeError, ValueError):
                _bump(job_id, fields=["skipped"])
                continue

            # Do not hold cabinet _LOCK across the LLM call.
            conn = _connect()
            try:
                outcome = tidy_one(conn, ad_id)
            finally:
                conn.close()

            if outcome == "saved":
                _bump(job_id, fields=["saved"])
            elif outcome == "failed":
                _bump(job_id, fields=["failed"])
                if not first_fail:
                    first_fail = "failed"
                    log.warning("job_tidy first fail job=%s ad=%s", job_id[:8], ad_id)
            elif outcome == "disabled":
                _bump(job_id, fields=["failed"])
                if not first_fail:
                    first_fail = "ai_disabled"
                _finish(job_id, status="failed", error=first_fail)
                return
            else:
                _bump(job_id, fields=["skipped"])

        if _is_cancelled(job_id):
            _finish(job_id, status="cancelled", error=first_fail)
        else:
            _finish(job_id, status="done", error=first_fail)
    except Exception as exc:
        log.exception("job_tidy job %s failed", job_id)
        _finish(job_id, status="failed", error=str(exc)[:300])
