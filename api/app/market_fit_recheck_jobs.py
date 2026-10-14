"""Async market-fit recheck jobs for staff (start + poll).

POST starts a daemon thread that rechecks one ad at a time. Progress lives in
the shared jobs DB so any API replica can answer GET polls.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from typing import Any

from app.cabinet_store import CabinetError, _LOCK, _connect, _now, recheck_one

log = logging.getLogger("ingress-job.api.market_fit_recheck")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS market_fit_recheck_jobs (
    id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    status TEXT NOT NULL,
    total INTEGER NOT NULL DEFAULT 0,
    done INTEGER NOT NULL DEFAULT 0,
    checked INTEGER NOT NULL DEFAULT 0,
    rejected INTEGER NOT NULL DEFAULT 0,
    hidden INTEGER NOT NULL DEFAULT 0,
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
        "scope": row["scope"] or "queue",
        "status": row["status"] or "",
        "total": total,
        "done": done,
        "remaining": max(0, total - done),
        "checked": int(row["checked"] or 0),
        "rejected": int(row["rejected"] or 0),
        "hidden": int(row["hidden"] or 0),
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


def start_recheck_job(
    job_ids: list[int],
    *,
    scope: str = "queue",
    created_by: str = "",
) -> dict[str, Any]:
    if scope not in ("queue", "crawled"):
        raise CabinetError(422, "scope queue və ya crawled olmalıdır")
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
                INSERT INTO market_fit_recheck_jobs (
                    id, scope, status, total, done, checked, rejected, hidden,
                    failed, skipped, error, job_ids, created_by, created_at, updated_at
                ) VALUES (?, ?, 'queued', ?, 0, 0, 0, 0, 0, 0, '', ?, ?, ?, ?)
                """,
                (job_id, scope, len(ordered), json.dumps(ordered), created_by or "", now, now),
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
        name=f"market-fit-recheck-{job_id[:8]}",
    ).start()
    return get_recheck_job(job_id)


def get_recheck_job(job_id: str) -> dict[str, Any]:
    key = (job_id or "").strip()
    if not key:
        raise CabinetError(404, "Job tapılmadı")
    with _LOCK:
        conn = _connect()
        try:
            _ensure(conn)
            row = conn.execute(
                "SELECT * FROM market_fit_recheck_jobs WHERE id = ?",
                (key,),
            ).fetchone()
        finally:
            conn.close()
    if row is None:
        raise CabinetError(404, "Job tapılmadı")
    return _row_public(row)


def _bump(job_id: str, *, fields: list[str] | None = None, done_inc: int = 1) -> None:
    allowed = {"checked", "rejected", "hidden", "failed", "skipped"}
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
                f"UPDATE market_fit_recheck_jobs SET {', '.join(sets)} WHERE id = ?",
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
                UPDATE market_fit_recheck_jobs
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
                    "SELECT scope, job_ids FROM market_fit_recheck_jobs WHERE id = ?",
                    (job_id,),
                ).fetchone()
                if row is None:
                    return
                conn.execute(
                    """
                    UPDATE market_fit_recheck_jobs
                    SET status = 'running', updated_at = ?
                    WHERE id = ?
                    """,
                    (_now(), job_id),
                )
                conn.commit()
                scope = row["scope"] or "queue"
                try:
                    ids = json.loads(row["job_ids"] or "[]")
                except json.JSONDecodeError:
                    ids = []
            finally:
                conn.close()

        if not isinstance(ids, list):
            ids = []
        first_fail = ""
        for raw in ids:
            try:
                ad_id = int(raw)
            except (TypeError, ValueError):
                _bump(job_id, fields=["skipped"])
                continue
            outcome = recheck_one(ad_id, scope=scope)
            if outcome == "checked":
                _bump(job_id, fields=["checked"])
            elif outcome == "rejected":
                _bump(job_id, fields=["checked", "rejected"])
            elif outcome == "hidden":
                _bump(job_id, fields=["checked", "hidden"])
            elif outcome == "failed":
                _bump(job_id, fields=["failed"])
                if not first_fail:
                    try:
                        from worker.market_fit import last_miss_error

                        first_fail = (last_miss_error or "failed")[:180]
                    except Exception:
                        first_fail = "failed"
                    log.warning(
                        "market_fit recheck first fail job=%s ad=%s reason=%s",
                        job_id[:8],
                        ad_id,
                        first_fail,
                    )
            else:
                _bump(job_id, fields=["skipped"])

        _finish(job_id, status="done", error=first_fail)
    except Exception as exc:
        log.exception("market_fit recheck job %s failed", job_id)
        _finish(job_id, status="failed", error=str(exc)[:300])
