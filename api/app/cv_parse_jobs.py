"""Drain parse_cv_queue in-process after CV upload (API async path)."""

from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path

log = logging.getLogger("ingress-job.api.cv_parse")

_state_lock = threading.Lock()
_draining = False
_drain_again = False


def _ensure_worker_importable() -> bool:
    try:
        import worker.cv_queue  # noqa: F401

        return True
    except ImportError:
        pass
    repo_worker = Path(__file__).resolve().parents[2] / "worker"
    if not repo_worker.is_dir():
        return False
    path = str(repo_worker)
    if path not in sys.path:
        sys.path.insert(0, path)
    try:
        import worker.cv_queue  # noqa: F401

        return True
    except ImportError:
        return False


def _drain_fn():
    """Return worker.cv_queue.drain_parse_cv_queue, or None when unavailable."""
    if not _ensure_worker_importable():
        return None
    from worker.cv_queue import drain_parse_cv_queue

    return drain_parse_cv_queue


def drain_parse_cv_queue_now() -> dict[str, int]:
    """Claim and parse pending CVs on the jobs DB. Empty dict when unavailable."""
    drain = _drain_fn()
    if drain is None:
        log.warning("cv parse drain skipped: worker package unavailable")
        return {}
    from app.applications import CV_ROOT
    from app.cabinet_store import _connect

    conn = _connect()
    try:
        stats = drain(conn, cv_root=CV_ROOT)
        conn.commit()
        return stats
    finally:
        conn.close()


def schedule_parse_cv_drain() -> None:
    """Best-effort background drain after enqueue. Serializes overlapping kicks."""

    def run() -> None:
        global _draining, _drain_again
        with _state_lock:
            if _draining:
                _drain_again = True
                return
            _draining = True
            _drain_again = False
        try:
            while True:
                try:
                    stats = drain_parse_cv_queue_now()
                    if stats.get("claimed"):
                        log.info(
                            "cv parse drain: claimed=%s done=%s failed=%s",
                            stats.get("claimed", 0),
                            stats.get("done", 0),
                            stats.get("failed", 0),
                        )
                except Exception:
                    log.exception("cv parse drain failed")
                with _state_lock:
                    if not _drain_again:
                        _draining = False
                        return
                    _drain_again = False
        except Exception:
            with _state_lock:
                _draining = False
            raise

    threading.Thread(target=run, daemon=True, name="cv-parse-drain").start()
