"""Weekly digests and high-match alerts (plan §8.1 / §8.4).

AI #4 optional personal intro via digest_intro (soft-fails to static copy).
Empty digests are not sent. At most one non-transactional email per user per UTC day.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any

from app.email_prefs import (
    already_logged,
    claim_email,
    day_key,
    digest_enabled,
    ensure_email_tables,
    finish_email,
    get_prefs,
    high_match_enabled,
    list_candidate_user_ids,
    marketing_sent_today,
    period_key_for_digest,
    prune_skip_log,
    record_skip,
    unsubscribe_url,
)
logger = logging.getLogger("ingress-job.digests")

HIGH_MATCH_MIN_SCORE = float(os.environ.get("HIGH_MATCH_MIN_SCORE") or "0.75")


def _digest_match_limit() -> int:
    """Multi-job digest size (Djinni-style list). Env DIGEST_MATCH_LIMIT, 1..20."""
    try:
        return max(1, min(int(os.environ.get("DIGEST_MATCH_LIMIT") or "12"), 20))
    except ValueError:
        return 12


DIGEST_MATCH_LIMIT = _digest_match_limit()
HIGH_MATCH_LOOKBACK_HOURS = int(os.environ.get("HIGH_MATCH_LOOKBACK_HOURS") or "26")
BATCH_PAUSE_EVERY = int(os.environ.get("DIGEST_BATCH_SIZE") or "30")
ACADEMY_COURSE_BASE = (
    os.environ.get("ACADEMY_COURSE_BASE")
    or os.environ.get("NEXT_PUBLIC_ACADEMY_COURSE_BASE")
    or "https://ingress.academy/trainings/"
).rstrip("/") + "/"


def academy_course_url(course_id: str, *, utm_medium: str = "digest") -> str:
    slug = str(course_id or "").strip().strip("/")
    if not slug:
        return ""
    from urllib.parse import urlencode

    qs = urlencode(
        {
            "utm_source": "ingress_job",
            "utm_medium": utm_medium,
            "utm_campaign": "academy_cross_sell",
        }
    )
    return f"{ACADEMY_COURSE_BASE}{slug}/?{qs}"


def academy_career_path_url(path_id: str, *, utm_medium: str = "digest") -> str:
    from app.academy_paths import academy_career_path_url as _url

    return _url(path_id, utm_medium=utm_medium)

COPY = {
    "az": {
        "digest_subject": "Technology Jobs: bu həftənin uyğun elanları",
        "digest_intro": "Profilinizə uyğun yeni elanlar:",
        "digest_trends": "Bacarıq trendləri:",
        "digest_gap": "Öyrənmə tövsiyəsi:",
        "digest_empty_skip": "empty",
        "digest_cta": "Elanlara keçid üçün məktubdakı düymələrə klikləyin.",
        "high_subject": "Yüksək uyğunluq: {title}",
        "high_body": "Yeni elan «{title}» ({company}) profilinizə yaxşı uyğun gəlir (skor {score}%).\n{explanation}\n\nElanı görüntüləmək üçün məktubdakı düyməyə klikləyin.",
        "unsub": "Abunəlikdən çıxmaq üçün məktubun altındakı linkə klikləyin.",
        "footer": "Technology Jobs",
    },
    "en": {
        "digest_subject": "Technology Jobs: matches for you this period",
        "digest_intro": "New jobs that fit your profile:",
        "digest_trends": "Skill trends:",
        "digest_gap": "Learning tip:",
        "digest_empty_skip": "empty",
        "digest_cta": "Use the buttons in this email to open each job.",
        "high_subject": "Strong match: {title}",
        "high_body": "New job «{title}» ({company}) looks like a strong match (score {score}%).\n{explanation}\n\nOpen the job with the button in this email.",
        "unsub": "To unsubscribe, use the link at the bottom of this email.",
        "footer": "Technology Jobs",
    },
    "ru": {
        "digest_subject": "Technology Jobs: подходящие вакансии за период",
        "digest_intro": "Новые вакансии под ваш профиль:",
        "digest_trends": "Тренды навыков:",
        "digest_gap": "Совет по обучению:",
        "digest_empty_skip": "empty",
        "digest_cta": "Откройте вакансии кнопками в этом письме.",
        "high_subject": "Сильное совпадение: {title}",
        "high_body": "Новая вакансия «{title}» ({company}) хорошо совпадает с профилем (оценка {score}%).\n{explanation}\n\nОткройте вакансию кнопкой в этом письме.",
        "unsub": "Чтобы отписаться, используйте ссылку внизу письма.",
        "footer": "Technology Jobs",
    },
}


def _lang(value: str) -> str:
    text = (value or "").strip().lower()[:2]
    return text if text in COPY else "az"


def _since_for_frequency(frequency: str, *, when: datetime) -> datetime:
    if frequency == "daily":
        return when - timedelta(days=1)
    if frequency == "biweekly":
        return when - timedelta(days=14)
    return when - timedelta(days=7)


def _weekday_iso(when: datetime) -> int:
    return when.weekday()  # Mon=0


def _due_for_digest(prefs: dict, *, when: datetime) -> bool:
    """Is a digest due in the period that contains ``when``?

    Daily: every day. Weekly: from the chosen weekday to the end of that ISO
    week, so a Monday that was missed (deploy, SMTP error, daily cap) is caught
    up on Tuesday–Sunday. Biweekly: from the chosen weekday of the first week of
    the pair through the end of the second week. The per-period email_log row
    (status ``sent``) keeps it to one digest per period.
    """
    if not digest_enabled(prefs):
        return False
    frequency = prefs.get("frequency")
    if frequency == "daily":
        return True
    try:
        chosen = int(prefs.get("send_weekday") or 0)
    except (TypeError, ValueError):
        chosen = 0
    if frequency == "biweekly":
        iso = when.isocalendar()
        if (iso.week - 1) % 2 == 1:
            return True  # second week of the pair: the chosen day has passed
    return _weekday_iso(when) >= chosen


def _recipient(user_id: str) -> str:
    from app.profiles import contact_email_for

    return (contact_email_for(user_id) or "").strip().lower()


def _top_matches(
    conn,
    *,
    user_id: str,
    limit: int,
    lang: str,
    fresh_since: datetime | None = None,
) -> list[dict]:
    """Best current matches. Used by digests + engagement.

    With ``fresh_since`` the list is the top ``limit`` plus every other gated
    match created on/after that date (searched over the whole scored list, not
    only the top N), so a new 78% ad ranked 25th still counts as fresh.
    """
    from app.matching import matches_payload

    since_key = fresh_since.date().isoformat() if fresh_since is not None else None
    if since_key:
        payload = matches_payload(
            conn,
            user_id=user_id,
            limit=max(limit, 20),
            lang=lang,
            fresh_since=since_key,
        )
    else:
        payload = matches_payload(conn, user_id=user_id, limit=max(limit, 20), lang=lang)
    if not payload.get("matching_consent"):
        return []
    items = list(payload.get("matches") or [])[:limit]
    if since_key:
        seen = {item.get("job_id") for item in items}
        for item in payload.get("fresh_matches") or []:
            if item.get("job_id") in seen:
                continue
            seen.add(item.get("job_id"))
            items.append(item)
    return items


def _matches_since(conn, *, user_id: str, since: datetime, limit: int, lang: str) -> list[dict]:
    items = _top_matches(
        conn, user_id=user_id, limit=max(limit, 20), lang=lang, fresh_since=since
    )
    since_key = since.date().isoformat()
    fresh: list[dict] = []
    for item in items:
        created = str(item.get("created_at") or "")[:10]
        if created and created >= since_key:
            fresh.append(item)
        if len(fresh) >= limit:
            break
    return fresh


def _trend_lines(conn, *, category: str, lang: str, limit: int = 2) -> list[str]:
    from app.trends import trends_payload

    payload = trends_payload(conn, category=category or "", limit=limit, lang=lang)
    lines: list[str] = []
    for item in payload.get("items") or []:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        share = item.get("share")
        growth = item.get("growth_wow")
        bits = [name]
        if isinstance(share, (int, float)):
            bits.append(f"{round(share * 100)}%")
        if isinstance(growth, (int, float)):
            bits.append(f"{'+' if growth >= 0 else ''}{round(growth * 100)}%")
        lines.append(" · ".join(bits))
    return lines


def _gap_tip(conn, *, user_id: str, lang: str) -> str:
    from app.role_suggestions import suggest_roles_payload
    from app.skill_gap import skill_gap_payload

    roles = suggest_roles_payload(conn, user_id=user_id, limit=1, lang=lang)
    top = (roles.get("roles") or [None])[0]
    if not top:
        return ""
    role_name = str(top.get("canonical_name") or "").strip()
    if not role_name:
        return ""
    gap = skill_gap_payload(conn, user_id=user_id, role=role_name, top=3, lang=lang)
    missing = gap.get("missing") or []
    if not missing:
        return ""
    tip = missing[0]
    name = str(tip.get("name") or "").strip()
    if not name:
        return ""
    courses = tip.get("academy_courses") or []
    if courses:
        href = academy_course_url(str(courses[0]))
        if href:
            return f"{name} → {href}"
        return f"{name} → {courses[0]}"
    path_id = str(gap.get("academy_career_path") or "").strip()
    if path_id:
        href = academy_career_path_url(path_id)
        if href:
            return f"{name} → {href}"
    return name


def _build_digest_body(
    *,
    user_id: str,
    lang: str,
    matches: list[dict],
    trends: list[str],
    gap: str,
    unsub: str,
    ai_intro: str | None = None,
) -> str:
    # Plaintext must not dump tracked / unsubscribe URLs — those live in HTML
    # anchors (and List-Unsubscribe). ``unsub`` / ``user_id`` kept for call sites.
    _ = (user_id, unsub)
    pack = COPY[_lang(lang)]
    intro = (ai_intro or "").strip() or pack["digest_intro"]
    lines = [intro, ""]
    for item in matches:
        title = item.get("title") or ""
        company = item.get("company") or ""
        score = item.get("score")
        score_pct = f"{round(float(score) * 100)}%" if isinstance(score, (int, float)) else ""
        lines.append(f"- {title} ({company}) {score_pct}".rstrip())
        if item.get("explanation"):
            lines.append(f"  {item['explanation']}")
        lines.append("")
    lines.append(pack["digest_cta"])
    lines.append("")
    if trends:
        lines.append(pack["digest_trends"])
        for row in trends:
            lines.append(f"- {row}")
        lines.append("")
    if gap:
        lines.append(f"{pack['digest_gap']} {gap}")
        lines.append("")
    lines.append(pack["unsub"])
    lines.append(pack["footer"])
    return "\n".join(lines).strip() + "\n"


class SendResult:
    """Outcome of one SMTP send. Truthy only when the server accepted it."""

    __slots__ = ("ok", "reason")

    def __init__(self, ok: bool, reason: str = "") -> None:
        self.ok = bool(ok)
        self.reason = "" if ok else (reason or "send_failed")

    def __bool__(self) -> bool:
        return self.ok

    def __repr__(self) -> str:
        return f"SendResult(ok={self.ok}, reason={self.reason!r})"


_UNCONFIGURED_LOGGED_AT = 0.0


def _log_unconfigured(what: str) -> None:
    """Loud, but at most every 10 minutes (one line per run, not per user)."""
    import time

    global _UNCONFIGURED_LOGGED_AT
    now = time.monotonic()
    if now - _UNCONFIGURED_LOGGED_AT < 600:
        return
    _UNCONFIGURED_LOGGED_AT = now
    logger.error("marketing email not sent: %s is not configured", what)


def send_marketing_email(
    *,
    to: str,
    subject: str,
    body: str,
    unsubscribe_link: str,
    html_body: str | None = None,
) -> SendResult:
    """Like notifications.send_email, plus List-Unsubscribe headers.

    Plaintext ``body`` is always set; optional ``html_body`` is added as
    multipart/alternative for HTML-capable clients. Returns a SendResult —
    callers mark the email_log row ``sent`` only when it is truthy.
    """
    host = (os.environ.get("EMAIL_HOST") or "").strip()
    if not to:
        return SendResult(False, "no_recipient")
    if not host:
        _log_unconfigured("EMAIL_HOST")
        return SendResult(False, "smtp_unconfigured")
    from app.notifications import _from_address, env_bool
    import smtplib

    address = _from_address()
    if not address:
        _log_unconfigured("DEFAULT_FROM_EMAIL / EMAIL_HOST_USER")
        return SendResult(False, "no_from_address")
    try:
        port = int(os.environ.get("EMAIL_PORT") or "587")
        timeout = int(os.environ.get("EMAIL_TIMEOUT") or "20")
    except ValueError:
        logger.error("marketing email not sent: EMAIL_PORT / EMAIL_TIMEOUT invalid")
        return SendResult(False, "bad_smtp_config")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr(("Technology Jobs", address))
    message["To"] = to
    if unsubscribe_link:
        message["List-Unsubscribe"] = f"<{unsubscribe_link}>"
        message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    message.set_content(body)
    if html_body:
        message.add_alternative(html_body, subtype="html")
    user = os.environ.get("EMAIL_HOST_USER") or ""
    password = os.environ.get("EMAIL_HOST_PASSWORD") or ""
    use_ssl = env_bool("EMAIL_USE_SSL", False)
    use_tls = env_bool("EMAIL_USE_TLS", True)
    try:
        client = (
            smtplib.SMTP_SSL(host, port, timeout=timeout)
            if use_ssl
            else smtplib.SMTP(host, port, timeout=timeout)
        )
        try:
            if not use_ssl and use_tls:
                client.starttls()
            if user:
                client.login(user, password)
            client.send_message(message)
        finally:
            try:
                client.quit()
            except Exception:
                pass
    except Exception as exc:
        logger.warning("marketing email was not sent (%s)", type(exc).__name__)
        return SendResult(False, f"smtp_error:{type(exc).__name__}")
    return SendResult(True)


def deliver_logged_email(
    conn,
    *,
    user_id: str,
    kind: str,
    period_key: str,
    to: str,
    meta: str,
    subject: str,
    body: str,
    html_body: str | None,
    unsubscribe_link: str,
) -> str:
    """Claim the email_log row, send, then mark it sent/failed.

    Returns ``"sent"`` or a skip/failure reason. A failed send leaves a
    ``failed`` row that the next hourly run retries (EMAIL_SEND_MAX_ATTEMPTS).
    """
    if not claim_email(
        conn,
        user_id=user_id,
        kind=kind,
        period_key=period_key,
        to_email=to,
        meta=meta,
    ):
        return "already_sent"
    try:
        outcome = send_marketing_email(
            to=to,
            subject=subject,
            body=body,
            html_body=html_body,
            unsubscribe_link=unsubscribe_link,
        )
    except Exception as exc:  # never leave a row stuck in 'sending'
        logger.exception("marketing email crashed")
        outcome = SendResult(False, f"error:{type(exc).__name__}")
    ok = bool(outcome)
    reason = "" if ok else str(getattr(outcome, "reason", "") or "send_failed")
    finish_email(conn, user_id=user_id, kind=kind, period_key=period_key, ok=ok, reason=reason)
    return "sent" if ok else f"send_failed:{reason}"


def send_digest_for_user(conn, *, user_id: str, when: datetime | None = None) -> dict[str, Any]:
    ensure_email_tables(conn)
    moment = when or datetime.now(timezone.utc)
    prefs = get_prefs(conn, user_id)
    result: dict[str, Any] = {"user_id": user_id, "kind": "digest", "status": "skipped"}
    if not _due_for_digest(prefs, when=moment):
        result["reason"] = "not_due"
        return result
    frequency = prefs["frequency"]
    period = period_key_for_digest(when=moment, frequency=frequency)
    if already_logged(conn, user_id=user_id, kind="digest", period_key=period):
        result["reason"] = "already_sent"
        return result
    if marketing_sent_today(conn, user_id=user_id, day=day_key(when=moment)):
        result["reason"] = "daily_limit"
        return result
    to = _recipient(user_id)
    if not to:
        result["reason"] = "no_email"
        return result
    lang = prefs["language"]
    since = _since_for_frequency(frequency, when=moment)
    limit = _digest_match_limit()
    matches = _matches_since(conn, user_id=user_id, since=since, limit=limit, lang=lang)
    # Prefer period-fresh ads; backfill from current top matches so the mail
    # is a multi-job list (not a single card) when the window is thin.
    if len(matches) < limit:
        seen: set[int] = set()
        for item in matches:
            try:
                seen.add(int(item["job_id"]))
            except (KeyError, TypeError, ValueError):
                continue
        for item in _top_matches(conn, user_id=user_id, limit=limit * 2, lang=lang):
            try:
                jid = int(item["job_id"])
            except (KeyError, TypeError, ValueError):
                continue
            if jid in seen:
                continue
            matches.append(item)
            seen.add(jid)
            if len(matches) >= limit:
                break
    if not matches:
        result["reason"] = "empty"
        return result
    category = ""
    try:
        from app.role_suggestions import suggest_roles_payload

        roles = suggest_roles_payload(conn, user_id=user_id, limit=1, lang=lang)
        top = (roles.get("roles") or [None])[0]
        if top:
            category = str(top.get("category") or "")
    except Exception:
        category = ""
    trends = _trend_lines(conn, category=category, lang=lang)
    gap = _gap_tip(conn, user_id=user_id, lang=lang)
    unsub = unsubscribe_url(user_id, lang=lang)
    if not unsub:
        result["reason"] = "no_app_url"
        return result
    pack = COPY[_lang(lang)]
    from app.digest_intro import maybe_digest_intro

    ai_intro, ai_status = maybe_digest_intro(
        conn,
        user_id=user_id,
        lang=lang,
        matches=matches,
        trends=trends,
        gap=gap,
    )
    body = _build_digest_body(
        user_id=user_id,
        lang=lang,
        matches=matches,
        trends=trends,
        gap=gap,
        unsub=unsub,
        ai_intro=ai_intro,
    )
    from app.email_clicks import tracked_job_url
    from app.email_templates import render_digest_html

    job_urls: dict[int, str] = {}
    for item in matches:
        try:
            jid = int(item["job_id"])
        except (KeyError, TypeError, ValueError):
            continue
        href = tracked_job_url(user_id, job_id=jid, kind="digest", lang=lang)
        if href:
            job_urls[jid] = href
    if not job_urls:
        result["reason"] = "no_app_url"
        return result
    html_body = render_digest_html(
        lang=lang,
        matches=matches,
        job_urls=job_urls,
        trends=trends,
        gap=gap,
        unsubscribe_url=unsub,
        intro=ai_intro or "",
    )
    outcome = deliver_logged_email(
        conn,
        user_id=user_id,
        kind="digest",
        period_key=period,
        to=to,
        meta=json.dumps(
            {"match_count": len(matches), "ai_intro": ai_status},
            ensure_ascii=False,
        ),
        subject=pack["digest_subject"],
        body=body,
        html_body=html_body,
        unsubscribe_link=unsub,
    )
    if outcome != "sent":
        result["reason"] = outcome
        return result
    result["status"] = "sent"
    result["period_key"] = period
    result["match_count"] = len(matches)
    result["ai_intro"] = ai_status
    return result


def send_high_match_for_user(conn, *, user_id: str, when: datetime | None = None) -> dict[str, Any]:
    ensure_email_tables(conn)
    moment = when or datetime.now(timezone.utc)
    prefs = get_prefs(conn, user_id)
    result: dict[str, Any] = {"user_id": user_id, "kind": "high_match", "status": "skipped"}
    if not high_match_enabled(prefs):
        result["reason"] = "disabled"
        return result
    if marketing_sent_today(conn, user_id=user_id, day=day_key(when=moment)):
        result["reason"] = "daily_limit"
        return result
    to = _recipient(user_id)
    if not to:
        result["reason"] = "no_email"
        return result
    lang = prefs["language"]
    since = moment - timedelta(hours=HIGH_MATCH_LOOKBACK_HOURS)
    matches = _matches_since(conn, user_id=user_id, since=since, limit=10, lang=lang)
    best = None
    for item in matches:
        score = item.get("score")
        if not isinstance(score, (int, float)):
            continue
        if float(score) < HIGH_MATCH_MIN_SCORE:
            continue
        best = item
        break
    if best is None:
        result["reason"] = "none"
        return result
    job_id = int(best["job_id"])
    period = f"{day_key(when=moment)}:{job_id}"
    if already_logged(conn, user_id=user_id, kind="high_match", period_key=period):
        result["reason"] = "already_sent"
        return result
    # One high-match alert per UTC day.
    day = day_key(when=moment)
    row = conn.execute(
        """
        SELECT 1 FROM email_log
        WHERE user_id = ? AND kind = 'high_match' AND status = 'sent'
          AND period_key LIKE ?
        LIMIT 1
        """,
        (user_id, f"{day}:%"),
    ).fetchone()
    if row is not None:
        result["reason"] = "daily_alert_limit"
        return result
    from app.email_clicks import tracked_job_url

    pack = COPY[_lang(lang)]
    unsub = unsubscribe_url(user_id, lang=lang)
    score_pct = round(float(best["score"]) * 100)
    url = tracked_job_url(user_id, job_id=job_id, kind="high_match", lang=lang)
    if not url or not unsub:
        result["reason"] = "no_app_url"
        return result
    subject = pack["high_subject"].format(title=best.get("title") or "")
    body = pack["high_body"].format(
        title=best.get("title") or "",
        company=best.get("company") or "",
        score=score_pct,
        explanation=best.get("explanation") or "",
    )
    body = body + "\n\n" + pack["unsub"] + "\n" + pack["footer"] + "\n"
    from app.email_templates import render_match_job_html

    html_body = render_match_job_html(
        kind="high_match",
        lang=lang,
        match=best,
        job_url=url,
        unsubscribe_url=unsub,
        tip=str(best.get("explanation") or ""),
    )
    outcome = deliver_logged_email(
        conn,
        user_id=user_id,
        kind="high_match",
        period_key=period,
        to=to,
        meta=json.dumps({"job_id": job_id, "score": best.get("score")}, ensure_ascii=False),
        subject=subject,
        body=body,
        html_body=html_body,
        unsubscribe_link=unsub,
    )
    if outcome != "sent":
        result["reason"] = outcome
        return result
    result["status"] = "sent"
    result["job_id"] = job_id
    result["period_key"] = period
    return result


def run_email_jobs(*, dry_run: bool = False) -> dict[str, Any]:
    """Process digests for all eligible users.

    High-match alerts are owned by ``run_engagement_jobs`` (match_new fanout)
    so the same event is not emailed twice.
    """
    from app.cabinet_store import _LOCK, _connect, ensure_schema

    ensure_schema(create=True)
    when = datetime.now(timezone.utc)
    stats = {
        "digest_sent": 0,
        "digest_skipped": 0,
        "digest_failed": 0,
        "high_match_sent": 0,
        "high_match_skipped": 0,
        "users": 0,
        "dry_run": dry_run,
    }
    with _LOCK:
        conn = _connect()
        try:
            ensure_email_tables(conn)
            if not dry_run:
                prune_skip_log(conn)
            users = list_candidate_user_ids(conn)
            stats["users"] = len(users)
            for index, user_id in enumerate(users):
                if dry_run:
                    prefs = get_prefs(conn, user_id)
                    if _due_for_digest(prefs, when=when):
                        stats["digest_skipped"] += 1
                    continue
                try:
                    digest_result = send_digest_for_user(conn, user_id=user_id, when=when)
                except Exception:
                    # One broken profile must not stop everyone else's digest.
                    logger.exception("digest failed for one user")
                    digest_result = {"status": "skipped", "reason": "error"}
                if digest_result.get("status") == "sent":
                    stats["digest_sent"] += 1
                else:
                    stats["digest_skipped"] += 1
                    reason = str(digest_result.get("reason") or "")
                    if reason.startswith("send_failed"):
                        stats["digest_failed"] = int(stats.get("digest_failed") or 0) + 1
                    record_skip(conn, user_id=user_id, kind="digest", reason=reason, when=when)
                if BATCH_PAUSE_EVERY > 0 and (index + 1) % BATCH_PAUSE_EVERY == 0:
                    conn.commit()
            conn.commit()
        finally:
            conn.close()
    return stats
