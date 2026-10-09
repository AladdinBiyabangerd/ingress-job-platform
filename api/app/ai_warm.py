"""Background warm for request-path AI (role coach, match LLM/why).

HTTP handlers use complete_json(allow_provider=False) so they only serve
cache hits. Cache misses return ai_pending and schedule a daemon thread that
re-runs the same payload with providers enabled, filling ai_cache for the
next poll / request.

After a warm attempt fails, a short cooldown surfaces the real error so the
UI stops polling instead of looping forever while providers are down.
"""

from __future__ import annotations

import logging
import threading
import time

log = logging.getLogger("ingress-job.api.ai_warm")

_FAIL_COOLDOWN_SEC = 90.0

_lock = threading.Lock()
_inflight: set[str] = set()
# key → (monotonic_ts, error_code) after an unsuccessful warm
_last_fail: dict[str, tuple[float, str]] = {}


def _gap_key(*, user_id: str, role: str, lang: str, top: int | None) -> str:
    return f"gap:{user_id}:{role}:{lang}:{top}"


def _matches_key(*, user_id: str, role: str, lang: str, limit: int | None) -> str:
    return f"matches:{user_id}:{role}:{lang}:{limit}"


def _track(key: str) -> bool:
    """Return True if this key should start a new warm job."""
    with _lock:
        if key in _inflight:
            return False
        _inflight.add(key)
        return True


def _done(key: str) -> None:
    with _lock:
        _inflight.discard(key)


def _mark_fail(key: str, code: str) -> None:
    err = (code or "ai_failed").strip()[:80] or "ai_failed"
    with _lock:
        _last_fail[key] = (time.monotonic(), err)


def _clear_fail(key: str) -> None:
    with _lock:
        _last_fail.pop(key, None)


def recent_fail_code(key: str) -> str | None:
    """Return sticky error during cooldown, else None."""
    with _lock:
        row = _last_fail.get(key)
    if not row:
        return None
    ts, code = row
    if time.monotonic() - ts > _FAIL_COOLDOWN_SEC:
        with _lock:
            _last_fail.pop(key, None)
        return None
    return code


def skill_gap_warm_fail_code(
    *,
    user_id: str,
    role: str,
    lang: str,
    top: int | None = None,
) -> str | None:
    subject = (user_id or "").strip()
    role_name = (role or "").strip()
    if not subject or not role_name:
        return None
    locale = (lang or "az").strip().lower()[:2] or "az"
    return recent_fail_code(_gap_key(user_id=subject, role=role_name, lang=locale, top=top))


def matches_warm_fail_code(
    *,
    user_id: str,
    lang: str,
    role: str | None = None,
    limit: int | None = None,
) -> str | None:
    subject = (user_id or "").strip()
    if not subject:
        return None
    locale = (lang or "az").strip().lower()[:2] or "az"
    role_name = (role or "").strip()
    return recent_fail_code(
        _matches_key(user_id=subject, role=role_name, lang=locale, limit=limit)
    )


def schedule_skill_gap_ai_warm(
    *,
    user_id: str,
    role: str,
    lang: str,
    top: int | None = None,
) -> bool:
    """Start background warm. Returns False if skipped (in-flight or cooldown)."""
    subject = (user_id or "").strip()
    role_name = (role or "").strip()
    if not subject or not role_name:
        return False
    locale = (lang or "az").strip().lower()[:2] or "az"
    key = _gap_key(user_id=subject, role=role_name, lang=locale, top=top)
    if recent_fail_code(key):
        return False
    if not _track(key):
        return False

    def run() -> None:
        try:
            from app.cabinet_store import _LOCK, _connect
            from app.skill_gap import skill_gap_payload

            with _LOCK:
                conn = _connect()
                try:
                    payload = skill_gap_payload(
                        conn,
                        user_id=subject,
                        role=role_name,
                        top=top,
                        lang=locale,
                        allow_ai_provider=True,
                    )
                    conn.commit()
                finally:
                    conn.close()
            if payload.get("ai_coach"):
                _clear_fail(key)
            else:
                err = str(payload.get("coach_error") or "ai_failed").strip() or "ai_failed"
                if err == "ai_pending":
                    err = "ai_failed"
                _mark_fail(key, err)
        except Exception as exc:
            log.warning("skill_gap AI warm failed user=%s role=%s: %s", subject, role_name, exc)
            _mark_fail(key, "ai_failed")
        finally:
            _done(key)

    threading.Thread(target=run, daemon=True, name="ai-warm-gap").start()
    return True


def schedule_matches_ai_warm(
    *,
    user_id: str,
    lang: str,
    role: str | None = None,
    limit: int | None = None,
) -> bool:
    """Start background warm. Returns False if skipped (in-flight or cooldown)."""
    subject = (user_id or "").strip()
    if not subject:
        return False
    locale = (lang or "az").strip().lower()[:2] or "az"
    role_name = (role or "").strip()
    key = _matches_key(user_id=subject, role=role_name, lang=locale, limit=limit)
    if recent_fail_code(key):
        return False
    if not _track(key):
        return False

    def run() -> None:
        try:
            from app.cabinet_store import _LOCK, _connect
            from app.matching import matches_payload

            with _LOCK:
                conn = _connect()
                try:
                    payload = matches_payload(
                        conn,
                        user_id=subject,
                        limit=limit,
                        lang=locale,
                        role=role_name or None,
                        allow_ai_provider=True,
                    )
                    conn.commit()
                finally:
                    conn.close()
            from app.match_llm_rerank import llm_rerank_enabled
            from app.match_why import why_enabled

            # Re-open briefly for flag reads if needed — flags also check env.
            wanted = llm_rerank_enabled(None) or why_enabled(None)
            got = bool(payload.get("ai_llm_rerank")) or any(
                isinstance(m, dict) and m.get("ai_why")
                for m in (payload.get("matches") or [])
            )
            if not wanted or got:
                _clear_fail(key)
            else:
                _mark_fail(key, "ai_failed")
        except Exception as exc:
            log.warning("matches AI warm failed user=%s: %s", subject, exc)
            _mark_fail(key, "ai_failed")
        finally:
            _done(key)

    threading.Thread(target=run, daemon=True, name="ai-warm-matches").start()
    return True
