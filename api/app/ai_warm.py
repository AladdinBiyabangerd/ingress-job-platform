"""Background warm for request-path AI (role coach, match LLM/why).

HTTP handlers use complete_json(allow_provider=False) so they only serve
cache hits. Cache misses return ai_pending and schedule a daemon thread that
re-runs the same payload with providers enabled, filling ai_cache for the
next poll / request.

After the current-language role coach is ready, sibling locales (az/en/ru)
are warmed in the background so a language switch hits cache instead of
waiting for a new generation.

After a warm attempt fails, a short cooldown surfaces the real error so the
UI stops polling instead of looping forever while providers are down.
"""

from __future__ import annotations

import logging
import threading
import time

log = logging.getLogger("ingress-job.api.ai_warm")

_FAIL_COOLDOWN_SEC = 90.0
# Avoid re-scheduling sibling-lang warms on every recommendations poll.
_SIBLING_COOLDOWN_SEC = 3600.0
_COACH_LANGS = ("az", "en", "ru")

_lock = threading.Lock()
_inflight: set[str] = set()
# key → (monotonic_ts, error_code) after an unsuccessful warm
_last_fail: dict[str, tuple[float, str]] = {}
# siblings:{user}:{role}:{top} → monotonic_ts when sibling warm was scheduled
_sibling_scheduled: dict[str, float] = {}


def _gap_key(*, user_id: str, role: str, lang: str, top: int | None) -> str:
    return f"gap:{user_id}:{role}:{lang}:{top}"


def _siblings_key(*, user_id: str, role: str, top: int | None) -> str:
    return f"siblings:{user_id}:{role}:{top}"


def _matches_key(*, user_id: str, role: str, lang: str, limit: int | None) -> str:
    return f"matches:{user_id}:{role}:{lang}:{limit}"


def _analyze_key(*, user_id: str, job_id: int, lang: str) -> str:
    return f"analyze:{user_id}:{int(job_id)}:{lang}"


def _apply_draft_key(*, user_id: str, job_id: int, lang: str) -> str:
    return f"apply-draft:{user_id}:{int(job_id)}:{lang}"


def _pick_locale(lang: str) -> str:
    text = (lang or "").strip().lower()[:2]
    return text if text in _COACH_LANGS else "az"


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


def job_analyze_warm_fail_code(
    *,
    user_id: str,
    job_id: int,
    lang: str,
) -> str | None:
    subject = (user_id or "").strip()
    if not subject or int(job_id or 0) <= 0:
        return None
    locale = _pick_locale(lang)
    return recent_fail_code(_analyze_key(user_id=subject, job_id=int(job_id), lang=locale))


def schedule_skill_gap_sibling_langs(
    *,
    user_id: str,
    role: str,
    lang: str,
    top: int | None = None,
) -> bool:
    """Warm other coach locales once the current language is ready.

    Returns True if at least one sibling warm was scheduled.
    """
    subject = (user_id or "").strip()
    role_name = (role or "").strip()
    if not subject or not role_name:
        return False
    locale = _pick_locale(lang)
    sk = _siblings_key(user_id=subject, role=role_name, top=top)
    now = time.monotonic()
    with _lock:
        prev = _sibling_scheduled.get(sk)
        if prev is not None and now - prev < _SIBLING_COOLDOWN_SEC:
            return False
        _sibling_scheduled[sk] = now

    started = False
    for other in _COACH_LANGS:
        if other == locale:
            continue
        if schedule_skill_gap_ai_warm(
            user_id=subject,
            role=role_name,
            lang=other,
            top=top,
            warm_siblings=False,
        ):
            started = True
    if started:
        log.info(
            "skill_gap sibling warm scheduled user=%s role=%s from=%s",
            subject,
            role_name,
            locale,
        )
    return started


def schedule_skill_gap_ai_warm(
    *,
    user_id: str,
    role: str,
    lang: str,
    top: int | None = None,
    warm_siblings: bool = True,
) -> bool:
    """Start background warm. Returns False if skipped (in-flight or cooldown)."""
    subject = (user_id or "").strip()
    role_name = (role or "").strip()
    if not subject or not role_name:
        return False
    locale = _pick_locale(lang)
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
                if warm_siblings:
                    schedule_skill_gap_sibling_langs(
                        user_id=subject,
                        role=role_name,
                        lang=locale,
                        top=top,
                    )
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


def schedule_job_analyze_ai_warm(
    *,
    user_id: str,
    job_id: int,
    lang: str,
    refresh: bool = False,
) -> bool:
    """Start background warm for job-detail analyze AI report."""
    subject = (user_id or "").strip()
    jid = int(job_id or 0)
    if not subject or jid <= 0:
        return False
    locale = _pick_locale(lang)
    key = _analyze_key(user_id=subject, job_id=jid, lang=locale)
    if not refresh and recent_fail_code(key):
        return False
    if not _track(key):
        return False

    def run() -> None:
        try:
            from app.cabinet_store import _LOCK, _connect
            from app.job_analyze import analyze_payload

            with _LOCK:
                conn = _connect()
                try:
                    payload = analyze_payload(
                        conn,
                        user_id=subject,
                        job_id=jid,
                        lang=locale,
                        refresh=refresh,
                        allow_ai_provider=True,
                    )
                    conn.commit()
                finally:
                    conn.close()
            if payload.get("ai_report"):
                _clear_fail(key)
            else:
                err = str(payload.get("ai_error") or "ai_failed").strip() or "ai_failed"
                if err in {"ai_pending", "job_analyze_disabled"}:
                    err = "ai_failed" if err == "ai_pending" else err
                if err == "job_analyze_disabled":
                    _clear_fail(key)
                else:
                    _mark_fail(key, err)
        except Exception as exc:
            log.warning(
                "job_analyze AI warm failed user=%s job=%s: %s", subject, jid, exc
            )
            _mark_fail(key, "ai_failed")
        finally:
            _done(key)

    threading.Thread(target=run, daemon=True, name="ai-warm-analyze").start()
    return True


def job_apply_draft_warm_fail_code(
    *,
    user_id: str,
    job_id: int,
    lang: str,
) -> str | None:
    subject = (user_id or "").strip()
    locale = _pick_locale(lang)
    return recent_fail_code(
        _apply_draft_key(user_id=subject, job_id=int(job_id), lang=locale)
    )


def schedule_job_apply_draft_ai_warm(
    *,
    user_id: str,
    job_id: int,
    lang: str,
    refresh: bool = False,
) -> bool:
    """Start background warm for job-detail apply-message draft."""
    subject = (user_id or "").strip()
    jid = int(job_id or 0)
    if not subject or jid <= 0:
        return False
    locale = _pick_locale(lang)
    key = _apply_draft_key(user_id=subject, job_id=jid, lang=locale)
    if not refresh and recent_fail_code(key):
        return False
    if not _track(key):
        return False

    def run() -> None:
        try:
            from app.cabinet_store import _LOCK, _connect
            from app.job_apply_draft import apply_draft_payload

            with _LOCK:
                conn = _connect()
                try:
                    payload = apply_draft_payload(
                        conn,
                        user_id=subject,
                        job_id=jid,
                        lang=locale,
                        refresh=refresh,
                        allow_ai_provider=True,
                    )
                    conn.commit()
                finally:
                    conn.close()
            if str(payload.get("message") or "").strip():
                _clear_fail(key)
            else:
                err = str(payload.get("ai_error") or "ai_failed").strip() or "ai_failed"
                if err in {"ai_pending", "job_apply_draft_disabled"}:
                    err = "ai_failed" if err == "ai_pending" else err
                if err == "job_apply_draft_disabled":
                    _clear_fail(key)
                else:
                    _mark_fail(key, err)
        except Exception as exc:
            log.warning(
                "job_apply_draft AI warm failed user=%s job=%s: %s", subject, jid, exc
            )
            _mark_fail(key, "ai_failed")
        finally:
            _done(key)

    threading.Thread(target=run, daemon=True, name="ai-warm-apply-draft").start()
    return True
