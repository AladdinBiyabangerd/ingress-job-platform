"""Async market-fit recheck jobs for staff (start + poll).

POST starts a daemon thread that rechecks one ad at a time. Progress lives in
the shared jobs DB so any API replica can answer GET polls.

``fresh`` runs (queue «AI ilə yenidən yoxla») bypass the AI answer cache so the
model is really asked again; only one can be active per scope. The gateway's
daily budget still applies: a fresh run stops early (status ``budget_stopped``)
when the AI says it is over budget / switched off, instead of failing every
remaining ad. Targets are explicit ids (capped at ``FRESH_MAX_IDS`` when
fresh), the staff list filter + limit, or — for the queue threshold panel —
every pending ad matching AI/rule op+percent, with no cap. The thread checks
one ad at a time, so the HTTP start call returns at once and the UI polls.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime
from typing import Any

from app.cabinet_store import (
    CabinetError,
    _LOCK,
    _connect,
    _now,
    pending_ids_by_list_filter,
    pending_ids_by_threshold,
    recheck_one,
)

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
# AI call timeout is 45s; no progress past this means the worker thread died
# (API restart / replica) and the UI would stick on «Dayandırılır…».
_STALE_SECONDS = 90
# Fresh (cache-bypassing) reruns cost one provider call per ad.
FRESH_MAX_IDS = 200
# AI miss reasons that will fail every remaining ad too → stop the run early.
_HARD_STOP_ERRORS = frozenset({"ai_budget_exceeded", "ai_disabled", "market_fit_off"})


def _ensure(conn) -> None:
    conn.execute(_SCHEMA)


def _parse_ts(raw: str | None) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


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


def _finalize_stale_row(conn, row) -> Any:
    """If an active job has no progress for too long, close it so polls end."""
    status = row["status"] or ""
    if status not in ("queued", "running", "cancelling"):
        return row
    updated = _parse_ts(row["updated_at"] if "updated_at" in row.keys() else "")
    if updated is None:
        return row
    age = (datetime.now().astimezone() - updated).total_seconds()
    if age < _STALE_SECONDS:
        return row
    final = "cancelled" if status == "cancelling" else "failed"
    err = (row["error"] or "").strip() if "error" in row.keys() else ""
    if not err:
        err = "stale_worker"
    now = _now()
    conn.execute(
        """
        UPDATE market_fit_recheck_jobs
        SET status = ?, error = ?, updated_at = ?
        WHERE id = ? AND status IN ('queued', 'running', 'cancelling')
        """,
        (final, err[:300], now, row["id"]),
    )
    conn.commit()
    log.warning(
        "market_fit recheck stale job=%s was=%s age=%.0fs → %s",
        str(row["id"])[:8],
        status,
        age,
        final,
    )
    refreshed = conn.execute(
        "SELECT * FROM market_fit_recheck_jobs WHERE id = ?",
        (row["id"],),
    ).fetchone()
    with _inflight_lock:
        _inflight.discard(row["id"])
    return refreshed or row


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


def _parse_payload(raw: str | None) -> tuple[list, bool]:
    """job_ids column: legacy JSON list, or {"ids": [...], "fresh": true}."""
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return [], False
    if isinstance(data, dict):
        ids = data.get("ids")
        return (ids if isinstance(ids, list) else []), bool(data.get("fresh"))
    if isinstance(data, list):
        return data, False
    return [], False


def _active_fresh_job(conn, scope: str) -> str:
    rows = conn.execute(
        """
        SELECT * FROM market_fit_recheck_jobs
        WHERE scope = ? AND status IN ('queued', 'running', 'cancelling')
        """,
        (scope,),
    ).fetchall()
    for row in rows:
        _, fresh = _parse_payload(row["job_ids"])
        if not fresh:
            continue
        row = _finalize_stale_row(conn, row)
        if (row["status"] or "") in ("queued", "running", "cancelling"):
            return str(row["id"])
    return ""


def start_recheck_job(
    job_ids: list[int],
    *,
    scope: str = "queue",
    created_by: str = "",
    fresh: bool = False,
    list_filter: dict[str, Any] | None = None,
    limit: int | None = None,
    threshold: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Start a background recheck.

    ``job_ids`` wins when given (checkbox selection). With no ids and a
    ``list_filter`` (queue only), pending ads matching the filter are taken in
    table order. ``limit`` trims either list; fresh runs are also capped at
    ``FRESH_MAX_IDS``. With no ids and a ``threshold`` ({score, op,
    threshold}; queue only) every matching pending ad is taken — no limit and
    no fresh cap. Response adds ``requested`` (before trimming) and ``capped``.
    """
    if scope not in ("queue", "crawled", "crawl_rejects"):
        raise CabinetError(422, "scope queue, crawled və ya crawl_rejects olmalıdır")
    if limit is not None and (limit < 1 or limit > FRESH_MAX_IDS):
        raise CabinetError(422, f"Limit 1–{FRESH_MAX_IDS} arasında olmalıdır")
    ordered = _normalize_ids(job_ids)
    by_threshold = False
    if not ordered and threshold is not None:
        if scope != "queue":
            raise CabinetError(422, "Faizlə yoxlama yalnız növbə üçündür")
        ordered = pending_ids_by_threshold(
            score=str(threshold.get("score") or ""),
            op=str(threshold.get("op") or ""),
            threshold=int(threshold.get("threshold") or 0),
        )
        if not ordered:
            raise CabinetError(422, "Bu faizə uyğun gözləyən elan yoxdur")
        by_threshold = True
        limit = None
    elif not ordered and list_filter is not None:
        if scope != "queue":
            raise CabinetError(422, "Filtrlə yoxlama yalnız növbə üçündür")
        ordered = pending_ids_by_list_filter(**list_filter)
        if not ordered:
            raise CabinetError(422, "Filtrə uyğun gözləyən elan yoxdur")
    if not ordered:
        raise CabinetError(422, "Elan seçilməyib")
    if len(ordered) > _MAX_IDS and not by_threshold:
        raise CabinetError(422, f"Birdən çox {_MAX_IDS} elan seçilə bilər")
    requested = len(ordered)
    cut = limit
    if fresh and not by_threshold:
        cut = min(cut or FRESH_MAX_IDS, FRESH_MAX_IDS)
    if cut is not None:
        ordered = ordered[:cut]
    payload = json.dumps({"ids": ordered, "fresh": True}) if fresh else json.dumps(ordered)

    job_id = uuid.uuid4().hex
    now = _now()
    with _LOCK:
        conn = _connect()
        try:
            _ensure(conn)
            if fresh:
                busy = _active_fresh_job(conn, scope)
                if busy:
                    raise CabinetError(409, "AI yenidən yoxlama artıq gedir; bitməsini gözləyin və ya dayandırın")
            conn.execute(
                """
                INSERT INTO market_fit_recheck_jobs (
                    id, scope, status, total, done, checked, rejected, hidden,
                    failed, skipped, error, job_ids, created_by, created_at, updated_at
                ) VALUES (?, ?, 'queued', ?, 0, 0, 0, 0, 0, 0, '', ?, ?, ?, ?)
                """,
                (job_id, scope, len(ordered), payload, created_by or "", now, now),
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
    out = get_recheck_job(job_id)
    out["requested"] = requested
    out["capped"] = requested > len(ordered)
    out["fresh"] = bool(fresh)
    return out


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
            if row is not None:
                row = _finalize_stale_row(conn, row)
        finally:
            conn.close()
    if row is None:
        raise CabinetError(404, "Job tapılmadı")
    return _row_public(row)


def cancel_recheck_job(job_id: str) -> dict[str, Any]:
    """Request stop of remaining work; already-checked ads stay (no undo).

    Sets status to ``cancelling`` so polls keep reading until the worker
    finishes the in-flight ad and writes final ``cancelled`` counts.
    """
    key = (job_id or "").strip()
    if not key:
        raise CabinetError(404, "Job tapılmadı")
    with _LOCK:
        conn = _connect()
        try:
            _ensure(conn)
            row = conn.execute(
                "SELECT status FROM market_fit_recheck_jobs WHERE id = ?",
                (key,),
            ).fetchone()
            if row is None:
                raise CabinetError(404, "Job tapılmadı")
            status = row["status"] or ""
            if status in ("queued", "running"):
                conn.execute(
                    """
                    UPDATE market_fit_recheck_jobs
                    SET status = 'cancelling', updated_at = ?
                    WHERE id = ?
                    """,
                    (_now(), key),
                )
                conn.commit()
        finally:
            conn.close()
    return get_recheck_job(key)


def _should_stop(job_id: str) -> bool:
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT status FROM market_fit_recheck_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        finally:
            conn.close()
    return bool(row) and (row["status"] or "") in ("cancelling", "cancelled")


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


def _hard_stop_reason() -> str:
    """AI miss reason that makes the rest of a fresh run pointless, else ''."""
    try:
        from worker.market_fit import last_miss_error
    except Exception:
        return ""
    reason = (last_miss_error or "").strip()
    return reason if reason in _HARD_STOP_ERRORS else ""


def _run_job(job_id: str) -> None:
    try:
        with _LOCK:
            conn = _connect()
            try:
                row = conn.execute(
                    "SELECT scope, job_ids, status FROM market_fit_recheck_jobs WHERE id = ?",
                    (job_id,),
                ).fetchone()
                if row is None:
                    return
                status = row["status"] or ""
                # Cancel may land while still queued — do not wipe «cancelling».
                if status in ("cancelling", "cancelled"):
                    conn.execute(
                        """
                        UPDATE market_fit_recheck_jobs
                        SET status = 'cancelled', updated_at = ?
                        WHERE id = ?
                        """,
                        (_now(), job_id),
                    )
                    conn.commit()
                    with _inflight_lock:
                        _inflight.discard(job_id)
                    return
                if status != "queued":
                    with _inflight_lock:
                        _inflight.discard(job_id)
                    return
                conn.execute(
                    """
                    UPDATE market_fit_recheck_jobs
                    SET status = 'running', updated_at = ?
                    WHERE id = ? AND status = 'queued'
                    """,
                    (_now(), job_id),
                )
                conn.commit()
                scope = row["scope"] or "queue"
                ids, fresh = _parse_payload(row["job_ids"])
            finally:
                conn.close()

        if not isinstance(ids, list):
            ids = []
        first_fail = ""
        for raw in ids:
            if _should_stop(job_id):
                _finish(job_id, status="cancelled", error=first_fail)
                return
            try:
                ad_id = int(raw)
            except (TypeError, ValueError):
                _bump(job_id, fields=["skipped"])
                continue
            stop_reason = ""
            if fresh:
                outcome = recheck_one(ad_id, scope=scope, fresh=True)
            else:
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
                if fresh:
                    stop_reason = _hard_stop_reason()
            else:
                _bump(job_id, fields=["skipped"])
            if stop_reason:
                log.warning(
                    "market_fit recheck job=%s stopped early: %s", job_id[:8], stop_reason
                )
                _finish(job_id, status="budget_stopped", error=stop_reason)
                return

        if _should_stop(job_id):
            _finish(job_id, status="cancelled", error=first_fail)
        else:
            _finish(job_id, status="done", error=first_fail)
    except Exception as exc:
        log.exception("market_fit recheck job %s failed", job_id)
        _finish(job_id, status="failed", error=str(exc)[:300])
